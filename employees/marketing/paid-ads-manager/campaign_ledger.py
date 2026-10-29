#!/usr/bin/env python3
"""campaign_ledger.py: synthetic campaign accounting without live spend (G35).

Reconciles a local campaign package: the platform spend export and the order book (both deduplicated by
the data engineer's csv_reconcile.py, G13), click/view touches and pixel/server conversion events, against
campaign budgets, flights and attribution windows. It can tie order value to the CFO's recognized revenue
(cash_revenue_reconcile.py, G14) and reviews draft creatives so every number in the copy matches a computed
figure. Local files only: no ad account, no network, nothing published, scheduled or spent.

Exit 0 reconciled, 1 reconciled_with_findings (each finding named), 2 invalid (nothing written).
Reference: campaign-accounting.md next to this file.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

SCHEMA = "solaris.campaign-ledger/1"
REPORT_SCHEMA = "solaris.campaign-ledger-report/1"
HERE = Path(__file__).resolve().parent
G13 = HERE.parent.parent / "data" / "data-engineer" / "csv_reconcile.py"
G14 = HERE.parent.parent / "leadership" / "cfo" / "cash_revenue_reconcile.py"
CENT = Decimal("0.01")
RATIO = Decimal("0.0001")
MONEY_RE = re.compile(r"^\d{1,12}(\.\d{1,2})?$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
CUR_RE = re.compile(r"^[A-Z]{3}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})$")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
PKG_KEYS = {"schema", "as_of", "window", "spend", "orders", "finance", "campaigns", "touches", "conversions", "creatives"}
CAMPAIGN_KEYS = {"id", "name", "currency", "flight_start", "flight_end", "budget_total", "budget_daily",
                 "click_window_days", "view_window_days"}
TOUCH_FIELDS = ("touch_id", "campaign_id", "user", "kind", "at", "loaded_at")
CONV_FIELDS = ("event_id", "order_id", "user", "at", "loaded_at", "source")
CREATIVE_KEYS = {"id", "campaign_id", "channel", "headline", "body", "claims", "material_connection", "disclosure", "status"}
PUBLISH_KEYS = ("publish_at", "scheduled_at", "schedule", "post_id", "ad_id", "live_url", "boost", "go_live")
FIGURES = ("spend", "conversions", "attributed_revenue", "cpa", "roas", "budget_total")
PROHIBITED = ("guaranteed", "guarantee", "risk-free", "risk free", "#1", "number one", "best ever", "no risk")
CONNECTIONS = ("none", "paid", "gifted", "employee", "affiliate", "unknown")
DISCLOSURE_TOKENS = ("#ad", "#sponsored", "sponsored", "paid partnership", "#employee", "employee", "gifted", "affiliate")
MAX_BYTES = 256 * 1024 * 1024
MAX_EVENTS = 2_000_000
CAVEATS = [
    "Attribution: last click inside the campaign's click window, else last view inside its view window, matched on "
    "the synthetic user key only; no cross-device, modelled or platform-reported conversions are counted.",
    "Revenue is order value from the reconciled order book (G13), never the value a pixel or platform reported; "
    "refunds and credit notes after the order only show through the finance tie-out (G14).",
    "Spend is the deduplicated platform export (latest restatement per campaign and day); it is not an invoice "
    "or a payment, and nothing here moves money.",
    "Currencies are never combined and no FX conversion is made.",
    "Local files only: no ad account, network, publish, schedule or spend was used.",
]


class Invalid(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Invalid(msg)


def _no_float(s):
    raise Invalid("floats are refused; write money as a two-decimal string")


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Invalid("duplicate JSON key %r" % k)
        out[k] = v
    return out


def _json(text, where):
    try:
        return json.loads(text, object_pairs_hook=_no_dupes, parse_float=_no_float,
                          parse_constant=lambda c: _no_float(c))
    except json.JSONDecodeError as exc:
        raise Invalid("%s: not JSON (%s)" % (where, exc.msg)) from None
    except RecursionError:
        raise Invalid("%s: JSON nested too deeply" % where) from None


def ts(s, where):
    need(isinstance(s, str) and TS_RE.match(s), "%s: timestamp with Z or an offset, got %r" % (where, s))
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def _ts_or_none(s):
    try:
        return ts(s, "")
    except Invalid:
        return None


def day(s, where):
    need(isinstance(s, str) and DATE_RE.match(s), "%s: YYYY-MM-DD, got %r" % (where, s))
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise Invalid("%s: not a calendar date %r" % (where, s)) from None


def money(s, where):
    need(isinstance(s, str) and MONEY_RE.match(s), "%s: non-negative money string with at most 2 decimals, got %r" % (where, s))
    return Decimal(s).quantize(CENT)


def m2(d):
    return str(d.quantize(CENT, rounding=ROUND_HALF_EVEN))


def inside(base, rel, where):
    need(isinstance(rel, str) and rel and not os.path.isabs(rel), "%s: a relative path inside the package folder" % where)
    p = Path(os.path.realpath(base / rel))
    need(p == base or base in p.parents, "%s: %r leaves the package folder" % (where, rel))
    need(p.is_file(), "%s: %r is not a file" % (where, rel))
    need(p.stat().st_size <= MAX_BYTES, "%s: file larger than 256 MiB" % where)
    return p


def load_package(path):
    p = Path(path)
    need(p.is_file(), "%s: no such package" % p.name)
    need(p.stat().st_size < 1024 * 1024, "%s: package must be under 1 MiB" % p.name)
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Invalid("%s: not UTF-8" % p.name) from None
    c = _json(text, p.name)
    need(isinstance(c, dict) and c.get("schema") == SCHEMA, "package: schema must be %r" % SCHEMA)
    extra = sorted(set(c) - PKG_KEYS)
    need(not extra, "package: unknown keys %s (schema drift)" % extra)
    base = Path(os.path.realpath(p.parent))
    P = {"base": base, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    P["as_of"] = ts(c.get("as_of"), "as_of")
    w = c.get("window")
    need(isinstance(w, dict) and set(w) == {"start", "end"}, "window: {start, end}")
    P["window"] = (ts(w["start"], "window.start"), ts(w["end"], "window.end"))
    need(P["window"][0] < P["window"][1], "window: start must be before end")
    for k in ("spend", "orders"):
        need(isinstance(c.get(k), dict) and set(c[k]) == {"contract"}, "%s: {contract}" % k)
        P[k] = inside(base, c[k]["contract"], k + ".contract")
    fin = c.get("finance")
    P["finance"] = None
    if fin is not None:
        need(isinstance(fin, dict) and set(fin) == {"g14_package"}, "finance: {g14_package}")
        P["finance"] = inside(base, fin["g14_package"], "finance.g14_package")
    cs = c.get("campaigns")
    need(isinstance(cs, list) and cs, "campaigns: a non-empty list")
    P["campaigns"] = {}
    for i, k in enumerate(cs):
        where = "campaigns[%d]" % i
        need(isinstance(k, dict), where + ": an object")
        extra = sorted(set(k) - CAMPAIGN_KEYS)
        need(not extra, "%s: unknown keys %s" % (where, extra))
        need(isinstance(k.get("id"), str) and ID_RE.match(k["id"]), where + ".id: a plain id")
        need(k["id"] not in P["campaigns"], "%s.id: %r appears twice" % (where, k["id"]))
        need(isinstance(k.get("currency"), str) and CUR_RE.match(k["currency"]), where + ".currency: three capital letters")
        cw, vw = k.get("click_window_days"), k.get("view_window_days")
        need(type(cw) is int and 1 <= cw <= 90, where + ".click_window_days: integer 1..90")
        need(type(vw) is int and 0 <= vw <= 30, where + ".view_window_days: integer 0..30 (0 = no view-through)")
        fs, fe = day(k.get("flight_start"), where + ".flight_start"), day(k.get("flight_end"), where + ".flight_end")
        need(fs <= fe, where + ": flight_start after flight_end")
        bt, bd = money(k.get("budget_total"), where + ".budget_total"), money(k.get("budget_daily"), where + ".budget_daily")
        need(bd <= bt, where + ": budget_daily above budget_total")
        P["campaigns"][k["id"]] = {"id": k["id"], "name": k.get("name", k["id"]), "currency": k["currency"],
                                   "flight": (fs, fe), "budget_total": bt, "budget_daily": bd,
                                   "click": dt.timedelta(days=cw), "view": dt.timedelta(days=vw),
                                   "click_window_days": cw, "view_window_days": vw}
    P["touches"] = inside(base, c.get("touches"), "touches")
    P["conversions"] = inside(base, c.get("conversions"), "conversions")
    P["creatives"] = inside(base, c["creatives"], "creatives") if c.get("creatives") is not None else None
    return P


def run_tool(tool, arg, what):
    need(tool.is_file(), "%s tool missing at %s" % (what, tool.name))
    env = dict({name: os.environ[name] for name in (
                   'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                   'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                   'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                   'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                   'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                   'GITHUB_ACTIONS',
               ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, str(tool), "reconcile", str(arg), "--json"], capture_output=True, text=True, env=env)
    if r.returncode not in (0, 1):
        last = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-1]
        raise Invalid("%s refused %s: %s" % (what, Path(arg).name, last[:300]))
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise Invalid("%s printed no JSON report for %s" % (what, Path(arg).name)) from None


def metric(rep, name, by, where):
    m = rep.get("metrics", {}).get(name)
    need(m is not None and m.get("agg") == "sum" and set(m.get("by", [])) == set(by),
         "%s: the G13 contract needs a sum metric %r by %s" % (where, name, sorted(by)))
    return m["groups"]


def read_events(path, fields, idkey, P, kind):
    """JSON lines -> (kept rows by id, report counts, findings). Every line is accounted for."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Invalid("%s: not UTF-8" % path.name) from None
    lines = text.splitlines()
    need(len(lines) <= MAX_EVENTS, "%s: more than %d lines" % (path.name, MAX_EVENTS))
    seen, bad, late, copies, conflicts = {}, [], [], 0, {}
    blank = 0
    for n, line in enumerate(lines, 1):
        if not line.strip():
            blank += 1
            continue
        try:
            o = json.loads(line, parse_float=_no_float, object_pairs_hook=_no_dupes)
        except (json.JSONDecodeError, Invalid, RecursionError):
            bad.append({"line": n, "reason": "not_json_object"})
            continue
        if not isinstance(o, dict):
            bad.append({"line": n, "reason": "not_json_object"})
            continue
        miss = [f for f in fields if not isinstance(o.get(f), str) or not o[f].strip()]
        if miss:
            bad.append({"line": n, "reason": "missing_" + miss[0]})
            continue
        at, ld = _ts_or_none(o["at"]), _ts_or_none(o["loaded_at"])
        if at is None or ld is None:
            bad.append({"line": n, "reason": "bad_timestamp"})
            continue
        if kind == "touch" and o["kind"] not in ("click", "view"):
            bad.append({"line": n, "reason": "bad_kind"})
            continue
        if kind == "conversion":
            v, cur = o.get("value"), o.get("currency")
            if v is not None and not (isinstance(v, str) and MONEY_RE.match(v)) or (cur is not None and not (isinstance(cur, str) and CUR_RE.match(cur))):
                bad.append({"line": n, "reason": "bad_reported_value"})
                continue
        if ld > P["as_of"]:
            late.append({"line": n, "id": o[idkey]})
            continue
        body = {f: o[f] for f in fields if f != "loaded_at"}
        body["at"] = at
        if kind == "conversion":
            body["value"], body["currency"] = o.get("value"), o.get("currency")
        k = o[idkey]
        if k in conflicts:
            conflicts[k] += 1
        elif k in seen:
            if seen[k] == body:
                copies += 1
            else:
                conflicts[k] = 2
                del seen[k]
        else:
            seen[k] = body
    counts = {"lines": len(lines), "blank": blank, "rejected": len(bad), "late": len(late), "exact_copies": copies,
              "conflicting_ids": len(conflicts), "kept": len(seen)}
    F = []
    if bad:
        F.append({"code": "rejected_%s_rows" % kind, "count": len(bad), "examples": bad[:20]})
    if late:
        F.append({"code": "late_%s_rows" % kind, "count": len(late), "examples": late[:20]})
    if conflicts:
        F.append({"code": "conflicting_%s_ids" % kind, "count": len(conflicts), "examples": sorted(conflicts)[:20]})
    return seen, counts, F


def fmt_ratio(num, den, q):
    if den == 0:
        return None
    return str((Decimal(num) / Decimal(den)).quantize(q, rounding=ROUND_HALF_EVEN))


def build(P):
    F, notes = [], []
    camps = P["campaigns"]
    win0, win1 = P["window"]
    # spend export via G13
    srep = run_tool(G13, P["spend"], "csv_reconcile.py (spend export)")
    _same_basis(srep, "spend", P)
    sgroups = metric(srep, "spend", ["campaign_id", "day", "currency"], "spend")
    if srep.get("status") != "reconciled":
        F.append({"code": "spend_export_gaps", "gaps": srep.get("gaps", [])})
    spend_total, cs = {}, {k: {"spend": Decimal(0), "days": {}} for k in camps}
    unassigned = {}
    for g in sgroups:
        grp, v = g["group"], Decimal(g["value"])
        cid, cur = grp.get("campaign_id"), grp.get("currency")
        d = dt.datetime.fromisoformat(grp["day"]).astimezone(dt.timezone.utc).date() if grp.get("day") else None
        spend_total[cur] = spend_total.get(cur, Decimal(0)) + v
        if cid not in camps:
            unassigned.setdefault(cur, []).append({"campaign_id": cid, "day": str(d), "spend": m2(v)})
            continue
        if cur != camps[cid]["currency"]:
            unassigned.setdefault(cur, []).append({"campaign_id": cid, "day": str(d), "spend": m2(v), "reason": "currency"})
            F.append({"code": "spend_currency_mismatch", "campaign": cid, "day": str(d), "currency": cur, "spend": m2(v)})
            continue
        cs[cid]["spend"] += v
        cs[cid]["days"][d] = cs[cid]["days"].get(d, Decimal(0)) + v
    if any(u for cur, us in unassigned.items() for u in us if "reason" not in u):
        F.append({"code": "spend_for_unknown_campaign", "rows": [u for us in unassigned.values() for u in us if "reason" not in u][:20]})
    # order book via G13
    orep = run_tool(G13, P["orders"], "csv_reconcile.py (order book)")
    ogroups = metric(orep, "revenue", ["order_id", "currency"], "orders")
    _same_basis(orep, "orders", P)
    if orep.get("status") != "reconciled":
        F.append({"code": "order_book_gaps", "gaps": orep.get("gaps", [])})
    book = {}
    for g in ogroups:
        oid = g["group"].get("order_id")
        if oid is None:
            continue
        book[oid] = (g["group"]["currency"], Decimal(g["value"]))
    book_total = {}
    for cur, v in book.values():
        book_total[cur] = book_total.get(cur, Decimal(0)) + v
    keyless = [g for g in ogroups if g["group"].get("order_id") is None]
    for g in keyless:
        book_total[g["group"]["currency"]] = book_total.get(g["group"]["currency"], Decimal(0)) + Decimal(g["value"])
    # events
    touches, tcounts, tf = read_events(P["touches"], TOUCH_FIELDS, "touch_id", P, "touch")
    convs, ccounts, cf = read_events(P["conversions"], CONV_FIELDS, "event_id", P, "conversion")
    F += tf + cf
    by_user, unknown_touch, off_flight = {}, 0, 0
    for tid, t in touches.items():
        c = camps.get(t["campaign_id"])
        if c is None:
            unknown_touch += 1
            continue
        if not (c["flight"][0] <= t["at"].date() <= c["flight"][1]):
            off_flight += 1
            continue
        by_user.setdefault(t["user"], []).append((t["at"], t["kind"], t["campaign_id"], tid))
    if unknown_touch:
        F.append({"code": "touches_for_unknown_campaign", "count": unknown_touch})
    tcounts.update(unknown_campaign=unknown_touch, outside_flight=off_flight)
    orders, outside = {}, 0
    for eid, e in convs.items():
        if not (win0 <= e["at"] < win1):
            outside += 1
            continue
        orders.setdefault(e["order_id"], []).append((eid, e))
    ccounts.update(outside_window=outside, orders_with_events=len(orders))
    attributed = {k: {"orders": [], "revenue": Decimal(0), "click": 0, "view": 0} for k in camps}
    unattr, reported_diff, no_order = {}, [], []

    def drop(reason, oid):
        cur, v = book[oid]
        u = unattr.setdefault(reason, {})
        u.setdefault(cur, {"orders": 0, "value": Decimal(0)})
        u[cur]["orders"] += 1
        u[cur]["value"] += v

    for oid in sorted(orders):
        evs = orders[oid]
        if oid not in book:
            no_order.append({"order_id": oid, "events": sorted(e for e, _ in evs)})
            continue
        cur, val = book[oid]
        for eid, e in evs:
            if e["value"] is not None and (Decimal(e["value"]) != val or (e["currency"] or cur) != cur):
                reported_diff.append({"order_id": oid, "event_id": eid, "reported": e["value"], "book": m2(val)})
        users = {e["user"] for _, e in evs}
        if len(users) > 1:
            F.append({"code": "order_user_conflict", "order_id": oid, "users": len(users)})
            drop("user_conflict", oid)
            continue
        user = users.pop()
        at = min(e["at"] for _, e in evs)
        pick = None
        for kind in ("click", "view"):
            cand = [(t_at, cid) for (t_at, k, cid, _) in by_user.get(user, ())
                    if k == kind and t_at <= at and at - t_at <= camps[cid][kind]]
            if cand:
                last = max(a for a, _ in cand)
                cids = sorted({cid for a, cid in cand if a == last})
                pick = (kind, cids)
                break
        if pick is None:
            drop("no_eligible_touch", oid)
            continue
        kind, cids = pick
        if len(cids) > 1:
            drop("ambiguous_touch", oid)
            notes.append({"code": "ambiguous_touch", "order_id": oid, "campaigns": cids})
            continue
        cid = cids[0]
        if camps[cid]["currency"] != cur:
            F.append({"code": "conversion_currency_mismatch", "order_id": oid, "campaign": cid, "order_currency": cur})
            drop("currency_mismatch", oid)
            continue
        a = attributed[cid]
        a["orders"].append(oid)
        a["revenue"] += val
        a[kind] += 1
    for oid in book:
        if oid not in orders:
            drop("no_conversion_event", oid)
    for g in keyless:
        u = unattr.setdefault("order_without_id", {})
        cur = g["group"]["currency"]
        u.setdefault(cur, {"orders": 0, "value": Decimal(0)})
        u[cur]["orders"] += g.get("rows", 0)
        u[cur]["value"] += Decimal(g["value"])
    if no_order:
        F.append({"code": "conversion_without_order", "count": len(no_order), "examples": no_order[:20]})
    # campaigns
    out_c, totals = [], {}
    for cid in sorted(camps):
        c, s, a = camps[cid], cs[cid], attributed[cid]
        over_daily = [{"day": str(d), "spend": m2(v), "cap": m2(c["budget_daily"])}
                      for d, v in sorted(s["days"].items()) if v > c["budget_daily"]]
        off = [str(d) for d in sorted(s["days"]) if not (c["flight"][0] <= d <= c["flight"][1])]
        if over_daily:
            F.append({"code": "over_daily_budget", "campaign": cid, "days": over_daily})
        if s["spend"] > c["budget_total"]:
            F.append({"code": "over_total_budget", "campaign": cid, "spend": m2(s["spend"]), "budget_total": m2(c["budget_total"])})
        if off:
            F.append({"code": "spend_outside_flight", "campaign": cid, "days": off})
        n = len(a["orders"])
        out_c.append({"id": cid, "name": c["name"], "currency": c["currency"],
                      "flight": [str(c["flight"][0]), str(c["flight"][1])],
                      "click_window_days": c["click_window_days"], "view_window_days": c["view_window_days"],
                      "budget_total": m2(c["budget_total"]), "budget_daily": m2(c["budget_daily"]),
                      "spend": m2(s["spend"]), "budget_remaining": m2(c["budget_total"] - s["spend"]),
                      "conversions": n, "click_conversions": a["click"], "view_conversions": a["view"],
                      "attributed_revenue": m2(a["revenue"]),
                      "cpa": None if n == 0 or s["spend"] == 0 else m2(s["spend"] / n),
                      "roas": fmt_ratio(a["revenue"], s["spend"], RATIO),
                      "orders": sorted(a["orders"])})
        t = totals.setdefault(c["currency"], {"spend": Decimal(0), "attributed": Decimal(0)})
        t["spend"] += s["spend"]
        t["attributed"] += a["revenue"]
    # identities
    checks = {}
    for cur in sorted(set(book_total) | set(spend_total) | set(totals)):
        att = totals.get(cur, {}).get("attributed", Decimal(0))
        un = sum((u[cur]["value"] for u in unattr.values() if cur in u), Decimal(0))
        sp = totals.get(cur, {}).get("spend", Decimal(0))
        ua = sum((Decimal(u["spend"]) for u in unassigned.get(cur, [])), Decimal(0))
        checks[cur] = {"order_value_total": m2(book_total.get(cur, Decimal(0))), "attributed": m2(att), "unattributed": m2(un),
                       "revenue_identity_ok": att + un == book_total.get(cur, Decimal(0)),
                       "spend_export_total": m2(spend_total.get(cur, Decimal(0))), "campaign_spend": m2(sp), "unassigned_spend": m2(ua),
                       "spend_identity_ok": sp + ua == spend_total.get(cur, Decimal(0))}
        if not (checks[cur]["revenue_identity_ok"] and checks[cur]["spend_identity_ok"]):
            F.append({"code": "identity_broken", "currency": cur})
    # finance tie-out
    fin = None
    if P["finance"] is not None:
        frep = run_tool(G14, P["finance"], "cash_revenue_reconcile.py (finance)")
        fin = {"result": frep.get("result"), "currencies": {}}
        for cur in sorted(set(book_total) | set(frep.get("currencies", {}))):
            rec = Decimal(frep.get("currencies", {}).get(cur, {}).get("recognized_revenue", "0"))
            diff = book_total.get(cur, Decimal(0)) - rec
            fin["currencies"][cur] = {"order_value": m2(book_total.get(cur, Decimal(0))), "recognized_revenue": m2(rec),
                                      "difference": m2(diff)}
            if diff != 0:
                F.append({"code": "order_value_differs_from_recognized_revenue", "currency": cur,
                          "order_value": m2(book_total.get(cur, Decimal(0))), "recognized_revenue": m2(rec), "difference": m2(diff)})
        if frep.get("result") != "reconciled":
            names = sorted(k for k, v in frep.get("exceptions", {}).items() if v)
            F.append({"code": "finance_exceptions", "g14_result": frep.get("result"), "exceptions": names})
    rep = {"schema": REPORT_SCHEMA, "package_sha256": P["sha256"], "as_of": P["as_of"].isoformat(),
           "window": [win0.isoformat(), win1.isoformat()], "campaigns": out_c,
           "unattributed": {r: {cur: {"orders": v["orders"], "value": m2(v["value"])} for cur, v in sorted(u.items())}
                            for r, u in sorted(unattr.items())},
           "unassigned_spend": {cur: us for cur, us in sorted(unassigned.items())},
           "checks": checks, "finance_tie_out": fin,
           "inputs": {"spend_export": {"g13_status": srep.get("status"), "coverage": srep.get("coverage")},
                      "order_book": {"g13_status": orep.get("status"), "orders": len(book)},
                      "touches": tcounts, "conversions": ccounts},
           "reported_value_differs": {"count": len(reported_diff), "examples": reported_diff[:20]},
           "notes": notes[:50], "caveats": CAVEATS,
           "read_only": "local files only; nothing was published, scheduled, bought or sent"}
    rep["creatives"] = review_creatives(P, rep, F) if P["creatives"] is not None else []
    blocked = [c["id"] for c in rep["creatives"] if c["status"] == "blocked"]
    if blocked:
        F.append({"code": "creatives_blocked", "creatives": blocked})
    rep["findings"] = F
    rep["status"] = "reconciled" if not F else "reconciled_with_findings"
    return rep


def _same_basis(rep, label, P):
    """One window and one as_of per package (r2, from M35 P2-1): each G13 report must carry exactly the
    package window and as_of, or spend, revenue, CPA and ROAS would mix periods or cutoffs."""
    w = rep.get("window") or {}
    need(_iso_eq(w.get("start"), P["window"][0]) and _iso_eq(w.get("end"), P["window"][1]),
         "%s contract window must equal the package window (no mixed windows in CPA or ROAS)" % label)
    need(_iso_eq(rep.get("as_of"), P["as_of"]), "%s contract as_of must equal the package as_of" % label)


_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d\u00ad"), "-")


def _fold(text):
    """Case-fold and NFKC-normalize copy, map every dash variant to '-' and collapse whitespace, so a
    prohibited phrase cannot hide behind a non-breaking hyphen, an en dash or a wide character (r2, M35 P4-1)."""
    t = unicodedata.normalize("NFKC", text).translate(_DASHES).casefold()
    return " ".join(t.split())


def _iso_eq(s, t):
    try:
        return isinstance(s, str) and dt.datetime.fromisoformat(s) == t
    except ValueError:
        return False


def _figure(rep, ref):
    parts = ref.split(":") if isinstance(ref, str) else []
    if len(parts) != 3 or parts[0] != "campaign" or parts[2] not in FIGURES:
        return False, None
    c = next((c for c in rep["campaigns"] if c["id"] == parts[1]), None)
    if c is None:
        return False, None
    return True, c[parts[2]]


def _matches(text, value):
    """True when some number written in text equals value rounded to that number's decimals."""
    if value is None:
        return False
    v = Decimal(str(value))
    for tok in NUM_RE.findall(text):
        t = tok.replace(",", "")
        try:
            d = Decimal(t)
        except Exception:
            continue
        places = -d.as_tuple().exponent if d.as_tuple().exponent < 0 else 0
        if v.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN) == d:
            return True
    return False


def review_creatives(P, rep, F):
    try:
        doc = _json(P["creatives"].read_text(encoding="utf-8"), P["creatives"].name)
    except UnicodeDecodeError:
        raise Invalid("creatives: not UTF-8") from None
    need(isinstance(doc, dict) and isinstance(doc.get("creatives"), list), "creatives: {\"creatives\": [...]}")
    out, ids = [], set()
    for i, c in enumerate(doc["creatives"]):
        need(isinstance(c, dict) and isinstance(c.get("id"), str) and ID_RE.match(c["id"]), "creatives[%d].id: a plain id" % i)
        need(c["id"] not in ids, "creatives[%d].id: %r appears twice" % (i, c["id"]))
        ids.add(c["id"])
        reasons, held = [], []
        pub = [k for k in PUBLISH_KEYS if k in c]
        if pub or c.get("status", "draft") != "draft":
            reasons.append({"code": "publish_request_refused", "detail": pub or ["status=%s" % c.get("status")]})
        unknown = sorted(set(c) - CREATIVE_KEYS - set(PUBLISH_KEYS))
        if unknown:
            reasons.append({"code": "unknown_fields", "detail": unknown})
        if c.get("campaign_id") not in P["campaigns"]:
            reasons.append({"code": "unknown_campaign", "detail": c.get("campaign_id")})
        head, body = c.get("headline", ""), c.get("body", "")
        if not isinstance(head, str) or not isinstance(body, str):
            reasons.append({"code": "copy_not_text"})
            head, body = "", ""
        copy = head + "\n" + body
        low = _fold(copy)
        bad = [w for w in PROHIBITED if w in low]
        if bad:
            reasons.append({"code": "prohibited_claim", "detail": bad})
        claims = c.get("claims", [])
        if not isinstance(claims, list):
            claims = []
            reasons.append({"code": "claims_not_list"})
        spans, checked = [], []
        for j, cl in enumerate(claims):
            if not isinstance(cl, dict) or not isinstance(cl.get("text"), str) or not cl["text"].strip():
                reasons.append({"code": "claim_without_text", "detail": j})
                continue
            pos = copy.find(cl["text"])
            if pos < 0:
                reasons.append({"code": "claim_not_in_copy", "detail": cl["text"]})
                continue
            spans.append((pos, pos + len(cl["text"])))
            ok, val = _figure(rep, cl.get("figure"))
            if not ok:
                reasons.append({"code": "unknown_figure", "detail": cl.get("figure")})
            elif not _matches(cl["text"], val):
                reasons.append({"code": "claim_mismatch", "detail": {"text": cl["text"], "figure": cl.get("figure"), "computed": val}})
            else:
                checked.append({"text": cl["text"], "figure": cl["figure"], "computed": val})
        for m in NUM_RE.finditer(copy):
            if not any(a <= m.start() and m.end() <= b for a, b in spans):
                reasons.append({"code": "unsupported_number", "detail": m.group(0)})
        conn = c.get("material_connection")
        if c.get("channel") == "social" and conn is None:
            conn = "unknown"
        if conn is not None:
            if conn not in CONNECTIONS or conn == "unknown":
                reasons.append({"code": "material_connection_unknown", "detail": conn})
            elif conn != "none":
                disc = c.get("disclosure") or ""
                if not disc or disc not in copy or not any(t in disc.lower() for t in DISCLOSURE_TOKENS):
                    reasons.append({"code": "undisclosed_material_connection", "detail": conn})
        if not reasons and checked and rep_has_findings(F):
            held.append("figures come from a report with open findings; recheck after they are cleared")
        status = "blocked" if reasons else ("held_unverified" if held else "ready_for_human_review")
        out.append({"id": c["id"], "campaign_id": c.get("campaign_id"), "channel": c.get("channel"), "status": status,
                    "reasons": reasons, "held": held, "verified_claims": checked})
    return out


def rep_has_findings(F):
    return bool(F)


def brief(rep):
    L = ["# Campaign ledger (INTERNAL DRAFT)", "",
         "Nothing was published, scheduled, bought or sent. Any publish, budget change or spend is a human action "
         "in the ad platform after review.", "",
         "Status: **%s**. Window %s to %s, as of %s." % (rep["status"], rep["window"][0], rep["window"][1], rep["as_of"]), "",
         "| Campaign | Cur | Spend | Budget | Conv | Revenue | CPA | ROAS |", "|---|---|---|---|---|---|---|---|"]
    for c in rep["campaigns"]:
        L.append("| %s | %s | %s | %s | %d | %s | %s | %s |" % (c["id"], c["currency"], c["spend"], c["budget_total"],
                 c["conversions"], c["attributed_revenue"], c["cpa"] or "n/a", c["roas"] or "n/a"))
    L += ["", "## Unattributed order value"]
    for r, u in rep["unattributed"].items():
        L.append("- %s: %s" % (r, ", ".join("%s %s (%d)" % (cur, v["value"], v["orders"]) for cur, v in u.items())))
    L += ["", "## Findings"] + (["- %s: %s" % (f["code"], json.dumps({k: v for k, v in f.items() if k != "code"}, sort_keys=True)[:300])
                                  for f in rep["findings"]] or ["- none"])
    L += ["", "## Creatives"] + (["- %s (%s): %s%s" % (c["id"], c["campaign_id"], c["status"],
                                   "; " + ", ".join(r["code"] for r in c["reasons"]) if c["reasons"] else "")
                                  for c in rep["creatives"]] or ["- none supplied"])
    L += ["", "## Caveats"] + ["- " + c for c in rep["caveats"]]
    return "\n".join(L) + "\n"


def write_out(out, rep, P):
    o = Path(os.path.realpath(out))
    need(not (o == P["base"] or P["base"] in o.parents), "--out must be outside the package folder")
    try:
        o.mkdir(parents=True, exist_ok=True)
        tmps = []
        for name, text in (("report.json", json.dumps(rep, indent=1, sort_keys=True) + "\n"), ("campaign-brief.md", brief(rep))):
            fd, tmp = tempfile.mkstemp(dir=str(o), prefix="." + name + ".")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            tmps.append((tmp, o / name))
        for tmp, dst in tmps:
            os.replace(tmp, str(dst))
    except OSError as exc:
        for tmp, _ in locals().get("tmps", []):
            if os.path.exists(tmp):
                os.unlink(tmp)
        raise Invalid("--out cannot be written (%s)" % exc.__class__.__name__) from None


def summary(rep):
    L = ["campaign-ledger: %s  (as of %s)" % (rep["status"], rep["as_of"])]
    for c in rep["campaigns"]:
        L.append("  %s %s spend %s / budget %s, conversions %d, revenue %s, CPA %s, ROAS %s" % (
            c["id"], c["currency"], c["spend"], c["budget_total"], c["conversions"], c["attributed_revenue"],
            c["cpa"] or "n/a", c["roas"] or "n/a"))
    for cur, ck in rep["checks"].items():
        L.append("  %s order value %s = attributed %s + unattributed %s (%s); spend export %s = campaigns %s + unassigned %s (%s)" % (
            cur, ck["order_value_total"], ck["attributed"], ck["unattributed"], "ok" if ck["revenue_identity_ok"] else "BROKEN",
            ck["spend_export_total"], ck["campaign_spend"], ck["unassigned_spend"], "ok" if ck["spend_identity_ok"] else "BROKEN"))
    for f in rep["findings"]:
        L.append("  finding %s" % f["code"])
    for c in rep["creatives"]:
        L.append("  creative %s: %s" % (c["id"], c["status"]))
    L.append("  " + rep["read_only"])
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Campaign accounting from local synthetic files; never spends or publishes.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reconcile")
    r.add_argument("package")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", help="folder for report.json and campaign-brief.md (written atomically)")
    a = ap.parse_args(argv)
    try:
        P = load_package(a.package)
        rep = build(P)
        if a.out:
            write_out(a.out, rep, P)
    except Invalid as exc:
        print("invalid: %s (nothing written)" % exc, file=sys.stderr)
        return 2
    print(json.dumps(rep, indent=1, sort_keys=True) if a.json else summary(rep))
    return 0 if rep["status"] == "reconciled" else 1


if __name__ == "__main__":
    sys.exit(main())
