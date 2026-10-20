#!/usr/bin/env python3
"""Resource and cash decision check (G17): capacity, dependencies, cash buffer, risks and reversibility.

Reads one decision package (JSON, schema solaris.resource-decision/1) and evaluates every option week by
week under a base case and a downside case built from each assumption's adverse bound. It rejects or
narrows schedules that the stated capacity, dependencies or cash cannot carry, names the binding constraint,
and never picks for the decision owner. Every quantity must come from a named, sourced and dated
assumption; the arithmetic is exact (fractions) and can be rerun with `verify`. Cash-in evidence can come
from a G14 reconciliation package, which must reconcile cleanly to be used.

Usage:
  resource_decision.py evaluate PACKAGE [--json] [--out FILE]
  resource_decision.py verify PACKAGE RESULT.json
Exit codes: 0 at least one option is feasible in the downside case; 1 no option is feasible (the request is
rejected and narrowed alternatives are listed), or required evidence is blocked; 2 invalid package or input,
nothing written. verify: 0 identical, 1 differences listed, 2 invalid.
Python 3.9+, standard library only. Local files only; nothing is sent, posted or booked.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from pathlib import Path

SCHEMA = "solaris.resource-decision/1"
REPORT = "solaris.resource-decision-report/1"
CERTAINTY = ("computed only from the stated assumptions and their ranges; not a forecast, and no outcome is "
             "certain. The decision owner decides.")
STALE_DAYS = 180
WEEKS_PER_MONTH = Fraction(52, 12)
# which bound is adverse for a field: "high" means a larger value is worse
ADVERSE = {"hours": "high", "extra_hours": "high", "people": "low", "hours_per_week": "low", "focus": "low",
           "from_week": "high", "ramp_weeks": "high", "opening": "low", "monthly_inflow": "low",
           "monthly_outflow": "high", "one_time_cost": "high", "monthly_cost": "high", "cost": "high",
           "probability": "high", "undo_weeks": "high", "undo_cost": "high", "cost_from_week": "low", "until_week": "low", "cost_until_week": "high",
           "min_buffer_months": "high"}


class Invalid(Exception):
    pass


def _load_g14():
    p = Path(__file__).resolve().parents[1] / "cfo" / "cash_revenue_reconcile.py"
    if not p.is_file():
        raise Invalid("G14 reconciler not found at leadership/cfo/cash_revenue_reconcile.py")
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("g14_cash_revenue_reconcile", str(p))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def money(x):
    x = Fraction(x)
    return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def num(x):
    """exact number for JSON: int when whole, else a 6-decimal string."""
    if isinstance(x, Fraction) and x.denominator == 1:
        return int(x)
    if isinstance(x, int):
        return x
    q = (Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    return format(q.normalize(), "f")


def _date(s, where):
    try:
        return dt.date.fromisoformat(str(s))
    except ValueError:
        raise Invalid("%s: %r is not a YYYY-MM-DD date" % (where, s))


def _frac(v, where):
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise Invalid("%s: %r is not a number" % (where, v))
    try:
        f = Fraction(str(v))
    except (ValueError, ZeroDivisionError):
        raise Invalid("%s: %r is not a number" % (where, v))
    return f


def _pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise Invalid("duplicate key %r" % k)
        d[k] = v
    return d


class Pkg(object):
    def __init__(self, path):
        self.path = Path(path)
        try:
            raw = self.path.read_bytes()
        except OSError as e:
            raise Invalid("cannot read package: %s" % e)
        try:
            self.doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=str, parse_int=int)
        except (UnicodeDecodeError, ValueError) as e:
            raise Invalid("package is not valid JSON: %s" % e)
        self.sha = hashlib.sha256(raw).hexdigest()
        d = self.doc
        if not isinstance(d, dict) or d.get("schema") != SCHEMA:
            raise Invalid("schema must be %s" % SCHEMA)
        extra = sorted(set(d) - {"schema", "decision", "assumptions", "calendar", "capacity", "work", "milestones",
                                 "cash", "options", "risks", "dissent"})
        if extra:
            raise Invalid("unknown top-level keys: %s" % ", ".join(extra))
        dec = d.get("decision") or {}
        for k in ("question", "owner", "as_of", "currency"):
            if not isinstance(dec.get(k), str) or not dec.get(k).strip():
                raise Invalid("decision.%s is required (a decision without a named owner is a memo)" % k)
        self.as_of = _date(dec["as_of"], "decision.as_of")
        self.currency = dec["currency"]
        self.warnings, self.used, self.evidence = [], set(), {}
        self._assumptions()
        cal = d.get("calendar") or {}
        self.weeks = cal.get("weeks")
        if not isinstance(self.weeks, int) or isinstance(self.weeks, bool) or not 1 <= self.weeks <= 520:
            raise Invalid("calendar.weeks must be an integer from 1 to 520")
        self._structure()

    # -- assumptions
    def _assumptions(self):
        A = self.doc.get("assumptions")
        if not isinstance(A, dict) or not A:
            raise Invalid("assumptions: a non-empty mapping of named assumptions is required")
        self.A = {}
        for name, a in A.items():
            w = "assumptions.%s" % name
            if not isinstance(a, dict):
                raise Invalid("%s must be a mapping" % w)
            src, dated = a.get("source"), a.get("dated")
            if "from_g14" in a:
                val = self._from_g14(name, a["from_g14"])
                lo = _frac(a["low"], w + ".low") if "low" in a else None
                hi = _frac(a["high"], w + ".high") if "high" in a else None
                if not isinstance(src, str) or not src.strip():
                    src = "G14 reconciliation %s" % a["from_g14"].get("package")
            else:
                if "value" not in a:
                    raise Invalid("%s.value is required" % w)
                val = _frac(a["value"], w + ".value")
                lo = _frac(a["low"], w + ".low") if "low" in a else None
                hi = _frac(a["high"], w + ".high") if "high" in a else None
            if not isinstance(src, str) or not src.strip():
                raise Invalid("%s.source is required: every number needs a stated source" % w)
            if dated is None:
                raise Invalid("%s.dated is required: an undated figure cannot support a decision" % w)
            d = _date(dated, w + ".dated")
            if d > self.as_of:
                raise Invalid("%s.dated %s is after decision.as_of %s" % (w, d, self.as_of))
            ranged = lo is not None or hi is not None
            lo = val if lo is None else lo
            hi = val if hi is None else hi
            if not lo <= val <= hi:
                raise Invalid("%s: low <= value <= high does not hold" % w)
            stale = (self.as_of - d).days > STALE_DAYS
            if stale:
                self.warnings.append({"code": "ASSUMPTION_STALE", "assumption": name,
                                      "detail": "dated %s, more than %d days before as_of" % (d, STALE_DAYS)})
            exact = a.get("exact", False)
            if not isinstance(exact, bool):
                raise Invalid("%s.exact must be true or false" % w)
            if exact and ranged:
                raise Invalid("%s: an exact figure cannot also have a range" % w)
            dside = a.get("downside")
            if dside not in (None, "low", "high"):
                raise Invalid("%s.downside must be low or high" % w)
            self.A[name] = {"value": val, "low": lo, "high": hi, "source": src, "dated": str(d), "ranged": ranged or exact,
                            "exact": exact, "downside": dside, "directions": set(),
                            "stale": stale, "unit": a.get("unit")}

    def _from_g14(self, name, spec):
        w = "assumptions.%s.from_g14" % name
        if not isinstance(spec, dict) or not isinstance(spec.get("package"), str) or spec.get("measure") not in ("monthly_net_cash", "closing_ar_owed"):
            raise Invalid("%s needs package and measure (monthly_net_cash or closing_ar_owed)" % w)
        p = Path(spec["package"])
        if not p.is_absolute():
            p = (self.path.parent / p)
        g = _load_g14()
        try:
            rep, code = g.reconcile(str(p))
        except g.Invalid as e:
            raise Invalid("%s: G14 package invalid: %s" % (w, e))
        cur = rep["currencies"].get(self.currency)
        if cur is None:
            raise Invalid("%s: G14 reconciliation has no %s figures (currencies are never converted)" % (w, self.currency))
        self.evidence[name] = {"package": spec["package"], "result": rep["result"], "exit": code,
                               "package_sha256": rep["package_sha256"], "period": rep["period"]}
        if code != 0:
            self.evidence[name]["blocked"] = True
        if spec["measure"] == "closing_ar_owed":
            return Fraction(cur["closing"]["ar_owed"])
        start, end = dt.datetime.fromisoformat(rep["period"]["start"]), dt.datetime.fromisoformat(rep["period"]["end"])
        days = Fraction(int((end - start).total_seconds()), 86400)
        if days <= 0:
            raise Invalid("%s: G14 period is empty" % w)
        return Fraction(cur["net_cash"]) * Fraction(365, 12) / days

    def ref(self, v, where, field):
        """value of an assumption reference -> {'base','downside'} Fractions."""
        if not isinstance(v, str):
            raise Invalid("%s: %r must name an assumption (literal numbers are not accepted for %s)" % (where, v, field))
        if v not in self.A:
            raise Invalid("%s: unknown assumption %r" % (where, v))
        a = self.A[v]
        self.used.add(v)
        direction = a["downside"] or ADVERSE.get(field, "high")
        a["directions"].add(ADVERSE.get(field, "high"))
        adv = a["high"] if direction == "high" else a["low"]
        return {"base": a["value"], "downside": adv}

    # -- structure
    def _structure(self):
        d = self.doc
        cap = d.get("capacity")
        if not isinstance(cap, list) or not cap:
            raise Invalid("capacity: at least one role is required")
        self.roles = {}
        for i, c in enumerate(cap):
            w = "capacity[%d]" % i
            if not isinstance(c, dict) or not isinstance(c.get("role"), str):
                raise Invalid("%s.role is required" % w)
            if c["role"] in self.roles:
                raise Invalid("%s: role %r listed twice" % (w, c["role"]))
            r = {f: self.ref(c.get(f), "%s.%s" % (w, f), f) for f in ("people", "hours_per_week", "focus")}
            for case in ("base", "downside"):
                if not 0 < r["focus"][case] <= 1:
                    raise Invalid("%s.focus must be in (0, 1]" % w)
                if r["people"][case] < 0 or r["hours_per_week"][case] < 0:
                    raise Invalid("%s: people and hours_per_week cannot be negative" % w)
            if r["focus"]["base"] > Fraction(85, 100):
                self.warnings.append({"code": "FOCUS_ABOVE_85", "role": c["role"],
                                      "detail": "focus above 0.85 leaves no slack for meetings, support and rework"})
            self.roles[c["role"]] = r
        work = d.get("work")
        if not isinstance(work, list) or not work:
            raise Invalid("work: at least one item is required")
        self.work = {}
        for i, x in enumerate(work):
            w = "work[%d]" % i
            if not isinstance(x, dict) or not isinstance(x.get("id"), str):
                raise Invalid("%s.id is required" % w)
            if x["id"] in self.work:
                raise Invalid("%s: work id %r listed twice" % (w, x["id"]))
            if x.get("role") not in self.roles:
                raise Invalid("%s.role %r is not in capacity" % (w, x.get("role")))
            pr = x.get("priority", 1)
            mp = x.get("max_people")
            if not isinstance(pr, int) or isinstance(pr, bool):
                raise Invalid("%s.priority must be an integer" % w)
            if mp is not None and (not isinstance(mp, int) or isinstance(mp, bool) or mp < 1):
                raise Invalid("%s.max_people must be a positive integer" % w)
            after = x.get("after", [])
            if not isinstance(after, list) or not all(isinstance(a, str) for a in after):
                raise Invalid("%s.after must be a list of work ids" % w)
            self.work[x["id"]] = {"id": x["id"], "role": x["role"], "hours": self.ref(x.get("hours"), w + ".hours", "hours"),
                                  "after": list(after), "priority": pr, "max_people": mp}
        for k, x in self.work.items():
            for a in x["after"]:
                if a not in self.work:
                    raise Invalid("work %s: after %r is not a work id" % (k, a))
        self.order = self._topo()
        self.milestones = []
        for i, m in enumerate(d.get("milestones") or []):
            w = "milestones[%d]" % i
            if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not isinstance(m.get("needs"), list):
                raise Invalid("%s needs id and needs" % w)
            dl = m.get("deadline_week")
            if not isinstance(dl, int) or isinstance(dl, bool) or dl < 1:
                raise Invalid("%s.deadline_week must be a positive integer" % w)
            for n in m["needs"]:
                if n not in self.work:
                    raise Invalid("%s: needs %r is not a work id" % (w, n))
            self.milestones.append({"id": m["id"], "needs": list(m["needs"]), "deadline_week": dl})
        if not self.milestones:
            raise Invalid("milestones: at least one dated milestone is required")
        c = d.get("cash")
        if not isinstance(c, dict):
            raise Invalid("cash is required")
        self.cash = {f: self.ref(c.get(f), "cash." + f, f) for f in ("opening", "monthly_inflow", "monthly_outflow")}
        mb = c.get("min_buffer_months")
        self.buffer_months = self.ref(mb, "cash.min_buffer_months", "min_buffer_months")
        opts = d.get("options")
        if not isinstance(opts, list) or not opts:
            raise Invalid("options: at least one option is required (include the as-is plan)")
        self.options = []
        seen = set()
        for i, o in enumerate(opts):
            w = "options[%d]" % i
            if not isinstance(o, dict) or not isinstance(o.get("id"), str) or o["id"] in seen:
                raise Invalid("%s.id is required and must be unique" % w)
            seen.add(o["id"])
            if not isinstance(o.get("reversible"), bool):
                raise Invalid("%s.reversible must be true or false" % w)
            undo = None
            if o["reversible"]:
                u = o.get("undo")
                if not isinstance(u, dict):
                    raise Invalid("%s: a reversible option must state undo.weeks and undo.cost" % w)
                undo = {"weeks": self.ref(u.get("weeks"), w + ".undo.weeks", "undo_weeks"),
                        "cost": self.ref(u.get("cost"), w + ".undo.cost", "undo_cost")}
            elif not isinstance(o.get("why_irreversible"), str) or not o["why_irreversible"].strip():
                raise Invalid("%s: an irreversible option must say why_irreversible" % w)
            adds = []
            for j, a in enumerate(o.get("capacity_add") or []):
                ww = "%s.capacity_add[%d]" % (w, j)
                if not isinstance(a, dict) or a.get("role") not in self.roles:
                    raise Invalid("%s.role must be a capacity role" % ww)
                adds.append({"role": a["role"], "people": self.ref(a.get("people"), ww + ".people", "people"),
                             "from_week": self.ref(a.get("from_week"), ww + ".from_week", "from_week"),
                             "ramp_weeks": self.ref(a.get("ramp_weeks"), ww + ".ramp_weeks", "ramp_weeks"),
                             "until": self.ref(a["until_week"], ww + ".until_week", "until_week") if "until_week" in a else None})
            desc = o.get("descope") or []
            for x in desc:
                if x not in self.work:
                    raise Invalid("%s.descope %r is not a work id" % (w, x))
                for y in self.work.values():
                    if x in y["after"] and y["id"] not in desc:
                        raise Invalid("%s.descope %r: %s depends on it; descope that too" % (w, x, y["id"]))
            shift = o.get("deadline_shift_weeks", 0)
            if not isinstance(shift, int) or isinstance(shift, bool) or shift < 0:
                raise Invalid("%s.deadline_shift_weeks must be a non-negative integer" % w)
            costs = {}
            for f in ("one_time_cost", "monthly_cost"):
                costs[f] = self.ref(o[f], "%s.%s" % (w, f), f) if f in o else None
            cfrom = self.ref(o["cost_from_week"], w + ".cost_from_week", "cost_from_week") if "cost_from_week" in o else None
            cuntil = self.ref(o["cost_until_week"], w + ".cost_until_week", "cost_until_week") if "cost_until_week" in o else None
            self.options.append({"id": o["id"], "label": str(o.get("label", o["id"])), "reversible": o["reversible"],
                                 "undo": undo, "why_irreversible": o.get("why_irreversible"), "adds": adds,
                                 "descope": list(desc), "shift": shift, "costs": costs, "cost_from": cfrom,
                                 "cost_until": cuntil})
        self.risks = []
        for i, r in enumerate(d.get("risks") or []):
            w = "risks[%d]" % i
            if not isinstance(r, dict) or not isinstance(r.get("id"), str):
                raise Invalid("%s.id is required" % w)
            for f in ("owner", "mitigation", "text"):
                if not isinstance(r.get(f), str) or not r[f].strip():
                    raise Invalid("%s.%s is required: a risk without an owner and mitigation is not managed" % (w, f))
            ap = r.get("applies_to", "all")
            if ap != "all" and (not isinstance(ap, list) or any(x not in seen for x in ap)):
                raise Invalid("%s.applies_to must be 'all' or a list of option ids" % w)
            item = r.get("work")
            if item is not None and item not in self.work:
                raise Invalid("%s.work %r is not a work id" % (w, item))
            self.risks.append({"id": r["id"], "text": r["text"], "owner": r["owner"], "mitigation": r["mitigation"],
                               "applies_to": ap, "work": item,
                               "probability": self.ref(r.get("probability"), w + ".probability", "probability"),
                               "extra_hours": self.ref(r["extra_hours"], w + ".extra_hours", "extra_hours") if "extra_hours" in r else None,
                               "cost": self.ref(r["cost"], w + ".cost", "cost") if "cost" in r else None})
            for c in ("base", "downside"):
                if not 0 <= self.risks[-1]["probability"][c] <= 1:
                    raise Invalid("%s.probability must be within [0, 1]" % w)
        self.dissent = d.get("dissent") or []
        if not isinstance(self.dissent, list):
            raise Invalid("dissent must be a list")
        for k, a in sorted(self.A.items()):
            if len(a["directions"]) > 1 and a["downside"] is None and a["low"] != a["high"]:
                raise Invalid("assumptions.%s is used where a high value is adverse and where a low value is adverse; "
                              "state downside: low or high so the downside case stays one consistent world" % k)
        unused = sorted(set(self.A) - self.used)
        if unused:
            self.warnings.append({"code": "ASSUMPTION_UNUSED", "detail": ", ".join(unused)})

    def _topo(self):
        state, out = {}, []

        def visit(k, path):
            if state.get(k) == 1:
                raise Invalid("work dependencies form a cycle: %s" % " -> ".join(path + [k]))
            if state.get(k) == 2:
                return
            state[k] = 1
            for a in self.work[k]["after"]:
                visit(a, path + [k])
            state[k] = 2
            out.append(k)
        for k in sorted(self.work):
            visit(k, [])
        return out


# ---------------------------------------------------------------- evaluation
def _capacity(P, opt, case, week, role):
    r = P.roles[role]
    base = r["people"][case] * r["hours_per_week"][case] * r["focus"][case]
    for a in opt["adds"]:
        if a["role"] != role:
            continue
        start = a["from_week"][case]
        if week < start or (a["until"] is not None and week > a["until"][case]):
            continue
        full = r["hours_per_week"][case] * r["focus"][case] * a["people"][case]
        base += full / 2 if week < start + a["ramp_weeks"][case] else full
    return base


def schedule(P, opt, case, extra=None):
    """weekly list scheduling by priority within each role; returns {id: finish_week or None}, shortfall."""
    items = {k: v for k, v in P.work.items() if k not in opt["descope"]}
    rem = {k: v["hours"][case] + (extra or {}).get(k, 0) for k, v in items.items()}
    finish, start = {}, {}
    for week in range(1, P.weeks + 1):
        for role in sorted(P.roles):
            cap = _capacity(P, opt, case, week, role)
            ready = [k for k, v in items.items() if v["role"] == role and k not in finish and
                     all(a in finish and finish[a] < week for a in v["after"])]
            ready.sort(key=lambda k: (items[k]["priority"], k))
            for k in ready:
                if cap <= 0:
                    break
                lim = rem[k]
                mp = items[k]["max_people"]
                if mp is not None:
                    r = P.roles[role]
                    lim = min(lim, mp * r["hours_per_week"][case] * r["focus"][case])
                take = min(cap, lim)
                if take > 0:
                    start.setdefault(k, week)
                rem[k] -= take
                cap -= take
                if rem[k] <= 0:
                    finish[k] = week
    left = {k: rem[k] for k in items if k not in finish}
    return {k: finish.get(k) for k in items}, left


def chain_minimum(P, opt, case, extra=None):
    """weeks needed by dependencies and per-item staffing caps alone, with unlimited people."""
    need = {}
    for k in P.order:
        if k in opt["descope"]:
            continue
        x = P.work[k]
        r = P.roles[x["role"]]
        per_week = None
        if x["max_people"] is not None:
            per_week = x["max_people"] * r["hours_per_week"][case] * r["focus"][case]
        hours = x["hours"][case] + (extra or {}).get(k, 0)
        own = 1 if per_week is None or per_week <= 0 else max(1, math.ceil(hours / per_week))
        need[k] = own + max([need[a] for a in x["after"]] or [0])
    return need


def cashflow(P, opt, case, risks_on):
    wk = lambda m: m / WEEKS_PER_MONTH  # monthly -> weekly
    bal = P.cash["opening"][case]
    inflow, outflow = wk(P.cash["monthly_inflow"][case]), wk(P.cash["monthly_outflow"][case])
    mc = opt["costs"]["monthly_cost"]
    ot = opt["costs"]["one_time_cost"]
    cfrom = opt["cost_from"][case] if opt["cost_from"] else Fraction(1)
    cfrom_w = max(1, math.ceil(cfrom))
    cuntil_w = math.floor(opt["cost_until"][case]) if opt["cost_until"] else P.weeks
    active = lambda week: cfrom_w <= week <= cuntil_w
    risk_cost = sum((r["cost"][case] for r in risks_on if r["cost"] is not None), Fraction(0))
    low, low_week, breach, rows = bal, 0, None, []
    monthly_total = P.cash["monthly_outflow"][case]
    for week in range(1, P.weeks + 1):
        out = outflow
        if mc is not None and active(week):
            out += wk(mc[case])
        if ot is not None and week == cfrom_w:
            out += ot[case]
        if risk_cost and week == 1:
            out += risk_cost
        bal = bal + inflow - out
        cur_monthly = P.cash["monthly_outflow"][case] + (mc[case] if mc is not None and active(week) else 0)
        buf = P.buffer_months[case] * cur_monthly
        monthly_total = cur_monthly
        if bal < low:
            low, low_week = bal, week
        if breach is None and bal < buf:
            breach = {"week": week, "balance": money(bal), "buffer": money(buf)}
        rows.append(bal)
    net = inflow - wk(monthly_total)
    runway = None if net >= 0 else (P.weeks + (bal / -net if bal > 0 else 0))
    return {"closing": money(bal), "lowest": money(low), "lowest_week": low_week, "buffer_breach": breach,
            "weekly_net_at_end": money(net), "runway_weeks": None if runway is None else num(Fraction(runway)),
            "runway_note": "not exhausted at the stated rates" if runway is None else "weeks from start until cash reaches zero at the end-of-horizon rate"}


def evaluate_option(P, opt):
    out = {"id": opt["id"], "label": opt["label"], "reversible": opt["reversible"], "descope": opt["descope"],
           "deadline_shift_weeks": opt["shift"], "cases": {}}
    if opt["reversible"]:
        out["undo"] = {"weeks": {c: num(opt["undo"]["weeks"][c]) for c in ("base", "downside")},
                       "cost": {c: money(opt["undo"]["cost"][c]) for c in ("base", "downside")}}
    else:
        out["why_irreversible"] = opt["why_irreversible"]
    risks_on = [r for r in P.risks if r["applies_to"] == "all" or opt["id"] in r["applies_to"]]
    out["risk_exposure"] = [{"id": r["id"], "owner": r["owner"], "mitigation": r["mitigation"],
                             "probability": num(r["probability"]["base"]),
                             "expected_cost": money(r["probability"]["base"] * r["cost"]["base"]) if r["cost"] else "0.00",
                             "extra_hours": num(r["extra_hours"]["base"]) if r["extra_hours"] else 0, "work": r["work"]}
                            for r in risks_on]
    for case in ("base", "downside"):
        on = risks_on if case == "downside" else []
        extra = {}
        for r in on:
            if r["extra_hours"] is not None and r["work"] and r["work"] not in opt["descope"]:
                extra[r["work"]] = extra.get(r["work"], 0) + r["extra_hours"][case]
        fin, left = schedule(P, opt, case, extra)
        chain = chain_minimum(P, opt, case, extra)
        ms, ok_all, binding = [], True, []
        for m in P.milestones:
            needs = [n for n in m["needs"] if n not in opt["descope"]]
            dl = m["deadline_week"] + opt["shift"]
            weeks = [fin[n] for n in needs]
            done = None if any(w is None for w in weeks) else max(weeks or [0])
            met = done is not None and done <= dl
            row = {"id": m["id"], "deadline_week": dl, "finish_week": done, "met": met,
                   "descoped_needs": [n for n in m["needs"] if n in opt["descope"]]}
            if not met:
                ok_all = False
                cm = max([chain[n] for n in needs] or [0])
                if cm > dl:
                    row["binding"] = "dependencies: the chain alone needs %d weeks with unlimited people" % cm
                    binding.append("dependencies")
                else:
                    late = [n for n in needs if fin[n] is None or fin[n] > dl]
                    scope = set()
                    stack = list(needs)
                    while stack:
                        n = stack.pop()
                        if n not in scope:
                            scope.add(n)
                            stack.extend(P.work[n]["after"])
                    roles = sorted({P.work[n]["role"] for n in late})
                    short = {}
                    for role in sorted({P.work[n]["role"] for n in scope}):
                        need_h = sum((P.work[n]["hours"][case] + extra.get(n, 0)) for n in scope if P.work[n]["role"] == role)
                        have = sum((_capacity(P, opt, case, w, role) for w in range(1, dl + 1)), Fraction(0))
                        if need_h > have:
                            short[role] = num(need_h - have)
                    if short:
                        row["binding"] = "capacity: %s" % ", ".join("%s short %s hours by week %d" % (r, short[r], dl) for r in sorted(short))
                        binding.append("capacity")
                    else:
                        row["binding"] = ("sequencing: enough %s hours in total by week %d, but dependencies, staffing "
                                          "caps and priority order finish it later" % ("/".join(roles), dl))
                        binding.append("sequencing")
                    row["late_work"] = late
                    row["capacity_short_hours"] = short
                row["earliest_feasible_week"] = done
            ms.append(row)
        cash = cashflow(P, opt, case, on)
        cash_ok = cash["buffer_breach"] is None
        if not cash_ok:
            binding.append("cash")
        out["cases"][case] = {"finish_weeks": {k: v for k, v in sorted(fin.items())},
                              "unfinished_hours": {k: num(v) for k, v in sorted(left.items())},
                              "milestones": ms, "cash": cash, "feasible": ok_all and cash_ok,
                              "binding_constraints": sorted(set(binding))}
    out["feasible_downside"] = out["cases"]["downside"]["feasible"]
    out["feasible_base"] = out["cases"]["base"]["feasible"]
    return out


def narrow(P, ev):
    """for an infeasible option: drop the lowest-priority work not needed by a milestone, one by one."""
    opt = [o for o in P.options if o["id"] == ev["id"]][0]
    required = set()
    for m in P.milestones:
        stack = list(m["needs"])
        while stack:
            k = stack.pop()
            if k not in required:
                required.add(k)
                stack.extend(P.work[k]["after"])
    optional = sorted([k for k in P.work if k not in required and k not in opt["descope"]],
                      key=lambda k: (-P.work[k]["priority"], k))
    dropped = []
    for k in optional:
        dependents = [y for y in P.work if k in P.work[y]["after"] and y not in opt["descope"] and y not in dropped]
        if dependents:
            continue
        dropped.append(k)
        trial = dict(opt, descope=opt["descope"] + dropped)
        e = evaluate_option(P, trial)
        if e["feasible_downside"]:
            return {"drop_optional_work": list(dropped), "feasible_downside": True,
                    "note": "narrowed by dropping work no milestone needs, lowest priority first"}
    lates = [m for m in ev["cases"]["downside"]["milestones"] if not m["met"]]
    if not lates:
        bb = ev["cases"]["downside"]["cash"]["buffer_breach"]
        return {"drop_optional_work": [], "feasible_downside": False, "cash_buffer_breach": bb,
                "note": "the schedule holds but cash falls below the buffer in week %d; it needs a lower or shorter "
                        "cost, more cash, or a buffer exception (the owner's call)" % bb["week"]}
    return {"drop_optional_work": [], "feasible_downside": False,
            "earliest_milestone_weeks": {m["id"]: m.get("earliest_feasible_week") for m in lates},
            "note": "dropping optional work does not make it feasible; the milestones need a later date, more "
                    "capacity, or less required scope (the owner's call)"}


def evaluate(path):
    P = Pkg(path)
    opts = [evaluate_option(P, o) for o in P.options]
    blocked = sorted(k for k, v in P.evidence.items() if v.get("blocked"))
    for e in opts:
        if not e["feasible_downside"]:
            e["narrowed"] = narrow(P, e)
    feas = [e for e in opts if e["feasible_downside"]]
    feas.sort(key=lambda e: (not e["reversible"], -Decimal(e["cases"]["downside"]["cash"]["lowest"]), e["id"]))
    unranged = sorted(k for k in P.used if not P.A[k]["ranged"])  # exact figures count as ranged
    if blocked:
        status = "blocked_evidence"
    elif not feas:
        status = "rejected_as_stated"
    elif all(not e["reversible"] for e in feas):
        status = "feasible_irreversible_only"
    else:
        status = "feasible_options"
    required = ["assumption %s: reconcile the G14 package cleanly before relying on it" % k for k in blocked]
    required += ["assumption %s: no low/high range and not marked exact, so the downside equals the base" % k for k in unranged]
    required += ["assumption %s: stale (older than %d days)" % (w["assumption"], STALE_DAYS) for w in P.warnings if w["code"] == "ASSUMPTION_STALE"]
    rep = {"schema": REPORT, "package_sha256": P.sha, "question": P.doc["decision"]["question"],
           "decision_owner": P.doc["decision"]["owner"], "as_of": str(P.as_of), "currency": P.currency,
           "status": status, "certainty": CERTAINTY, "weeks": P.weeks,
           "facts": {k: {"source": v["source"], "dated": v["dated"]} for k, v in sorted(P.A.items())},
           "assumptions": {k: {"value": num(v["value"]), "low": num(v["low"]), "high": num(v["high"]), "unit": v["unit"],
                               "ranged": v["ranged"], "exact": v["exact"], "stale": v["stale"],
                               "downside_bound": v["downside"]} for k, v in sorted(P.A.items())},
           "evidence": P.evidence, "options": opts,
           "feasible_in_downside": [e["id"] for e in feas],
           "ordering_rule": "options feasible in the downside case, reversible first, then by highest lowest-cash; "
                            "an ordering of what the numbers allow, not a recommendation",
           "risk": [{"id": r["id"], "text": r["text"], "owner": r["owner"], "mitigation": r["mitigation"],
                     "applies_to": r["applies_to"]} for r in P.risks],
           "dissent": P.dissent or ["none recorded"], "required_evidence": required, "warnings": P.warnings,
           "read_only": "local files only; nothing was sent, posted, hired, bought or booked"}
    code = 0 if status in ("feasible_options", "feasible_irreversible_only") else 1
    return rep, code


def render(r):
    L = ["Decision: %s" % r["question"], "Owner: %s (decides; this report does not)" % r["decision_owner"],
         "As of %s, %s. Status: %s" % (r["as_of"], r["currency"], r["status"])]
    for e in r["options"]:
        d = e["cases"]["downside"]
        b = e["cases"]["base"]
        L.append("- %s [%s]: base %s, downside %s; lowest cash downside %s (week %s)%s" % (
            e["id"], "reversible" if e["reversible"] else "irreversible",
            "feasible" if b["feasible"] else "not feasible", "feasible" if d["feasible"] else "not feasible",
            d["cash"]["lowest"], d["cash"]["lowest_week"],
            "" if not d["binding_constraints"] else "; binding: " + ", ".join(d["binding_constraints"])))
        for m in d["milestones"]:
            if not m["met"]:
                L.append("    %s due week %d, finishes %s: %s" % (m["id"], m["deadline_week"], m["finish_week"] or "after week %d" % r["weeks"], m.get("binding")))
        if d["cash"]["buffer_breach"]:
            bb = d["cash"]["buffer_breach"]
            L.append("    cash below buffer in week %d: %s < %s" % (bb["week"], bb["balance"], bb["buffer"]))
        if e.get("narrowed"):
            L.append("    narrowed: %s" % json.dumps(e["narrowed"], sort_keys=True))
    L.append("Feasible in the downside case: %s" % (", ".join(r["feasible_in_downside"]) or "none"))
    for x in r["required_evidence"]:
        L.append("Required evidence: %s" % x)
    L.append(r["certainty"])
    return "\n".join(L)


def _write_atomic(out, data, pkg):
    out = Path(out)
    if out.resolve() == Path(pkg).resolve():
        raise Invalid("--out would overwrite the package")
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), prefix=".%s." % out.name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s.%s present on one side only" % (path, k))
            else:
                out.extend(_diff(a[k], b[k], "%s.%s" % (path, k)))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return ["%s length %d != %d" % (path, len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(_diff(x, y, "%s[%d]" % (path, i)))
        return out
    return [] if a == b else ["%s: stored %r, recomputed %r" % (path, b, a)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="resource_decision.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("evaluate")
    e.add_argument("package")
    e.add_argument("--json", action="store_true")
    e.add_argument("--out")
    v = sub.add_parser("verify")
    v.add_argument("package")
    v.add_argument("result")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "evaluate":
            rep, code = evaluate(a.package)
            data = (json.dumps(rep, indent=1, sort_keys=True) + "\n").encode()
            if a.out:
                _write_atomic(a.out, data, a.package)
            print(data.decode().rstrip() if a.json else render(rep))
            return code
        if a.cmd == "verify":
            rep, _ = evaluate(a.package)
            try:
                stored = json.loads(Path(a.result).read_text())
            except (OSError, ValueError) as ex:
                raise Invalid("cannot read result: %s" % ex)
            diffs = _diff(json.loads(json.dumps(rep)), stored)
            if diffs:
                print("DIFFERENT: %d field(s) do not match a rerun of the package" % len(diffs))
                for d in diffs[:50]:
                    print("  " + d)
                return 1
            print("IDENTICAL: the stored result matches a rerun of the package (sha256 %s)" % rep["package_sha256"])
            return 0
        ap.print_help()
        return 2
    except Invalid as ex:
        print("INVALID: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    except RecursionError:
        print("INVALID: input nests too deeply. Nothing was written.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
