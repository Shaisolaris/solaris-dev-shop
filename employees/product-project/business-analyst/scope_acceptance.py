#!/usr/bin/env python3
"""Customer scope, estimate and delivery acceptance check (G31).

Reads one scope package (JSON, schema solaris.scope-package/1): customer inputs, assumptions, requirements
with dependencies, estimates and acceptance criteria, demonstrated capabilities, escalated ambiguities and a
proposal with commitments. `check` refuses to call the proposal ready unless every commitment maps to a
stated input, assumption or in-scope requirement; the estimate reconciles exactly with the requirement
estimates and the rate; every ambiguity is escalated and resolved; every in-scope requirement rests on a
capability with recorded demo evidence; a fixed estimate is supported; and any delivery date is backed by a
G17 resource decision that reruns identically. `accept` checks delivery evidence against every acceptance
criterion. Nothing is invented: missing support is reported as a finding, never filled in.

Usage:
  scope_acceptance.py check PACKAGE [--json] [--out FILE]
  scope_acceptance.py accept PACKAGE DELIVERY [--json] [--out FILE]
  scope_acceptance.py verify RESULT PACKAGE [DELIVERY]
Exit codes: 0 ready / accepted / identical; 1 blocked / not accepted / different (findings listed);
2 invalid input, nothing written. Python 3.9+, standard library only. Local files only; nothing is sent.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

SCHEMA = "solaris.scope-package/1"
DELIVERY = "solaris.scope-delivery/1"
REPORT = "solaris.scope-report/1"
CENT = Decimal("0.01")
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
# vague wording that cannot be accepted or estimated without a stated measure (documented list)
VAGUE = ["fast", "quick", "quickly", "user-friendly", "intuitive", "seamless", "seamlessly", "scalable",
         "robust", "real-time", "realtime", "as needed", "etc", "tbd", "and/or", "flexible", "modern", "easy",
         "simple", "best", "optimal", "asap", "as soon as possible", "appropriate", "various", "approximately",
         "high quality", "world-class", "secure enough", "minimal"]
VAGUE_RX = re.compile(r"(?<![A-Za-z0-9-])(" + "|".join(re.escape(v) for v in sorted(VAGUE, key=len, reverse=True))
                      + r")(?![A-Za-z0-9-])", re.I)
KINDS = ("scope", "estimate", "date", "feature", "sla", "other")
G17 = Path(__file__).resolve().parents[2] / "leadership" / "coo" / "resource_decision.py"


class Invalid(Exception):
    pass


def _load(path, what):
    try:
        raw = Path(path).read_bytes()
    except OSError as ex:
        raise Invalid("cannot read %s %s: %s" % (what, path, ex.strerror))
    try:
        return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
    except (UnicodeDecodeError, ValueError) as ex:
        raise Invalid("%s %s is not UTF-8 JSON: %s" % (what, path, ex))


def _date(v, w):
    if not isinstance(v, str):
        raise Invalid("%s must be a YYYY-MM-DD date" % w)
    try:
        return dt.date.fromisoformat(v)
    except ValueError:
        raise Invalid("%s must be a YYYY-MM-DD date, got %r" % (w, v))


def _dec(v, w, allow_zero=True):
    if not isinstance(v, str):
        raise Invalid("%s must be a decimal string (exact arithmetic), got %r" % (w, v))
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise Invalid("%s is not a decimal: %r" % (w, v))
    if not d.is_finite() or d < 0 or (d == 0 and not allow_zero):
        raise Invalid("%s must be a finite %s number" % (w, "non-negative" if allow_zero else "positive"))
    return d


def _str(d, k, w):
    v = d.get(k) if isinstance(d, dict) else None
    if not isinstance(v, str) or not v.strip():
        raise Invalid("%s.%s is required (non-empty text)" % (w, k))
    return v


def _ids(lst, w, seen):
    if not isinstance(lst, list):
        raise Invalid("%s must be a list" % w)
    out = {}
    for i, x in enumerate(lst):
        if not isinstance(x, dict):
            raise Invalid("%s[%d] must be an object" % (w, i))
        k = x.get("id")
        if not isinstance(k, str) or not ID.match(k):
            raise Invalid("%s[%d].id must be a short identifier" % (w, i))
        if k in seen:
            raise Invalid("duplicate id %r" % k)
        seen.add(k)
        out[k] = x
    return out


def _refs(v, w):
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(r, str) for r in v):
        raise Invalid("%s must be a list of ids" % w)
    return list(v)


def _hours(h, w):
    if not isinstance(h, dict):
        raise Invalid("%s must be {low, likely, high}" % w)
    lo, li, hi = (_dec(h.get(k), "%s.%s" % (w, k)) for k in ("low", "likely", "high"))
    if not lo <= li <= hi:
        raise Invalid("%s must satisfy low <= likely <= high" % w)
    return {"low": lo, "likely": li, "high": hi}


def _sha_file(base, rel, w):
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise Invalid("%s.path must be a relative path inside the package folder" % w)
    p = base / rel
    try:
        return p, hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return p, None


def load_package(path):
    d, digest = _load(path, "package")
    if not isinstance(d, dict) or d.get("schema") != SCHEMA:
        raise Invalid("package schema must be %r" % SCHEMA)
    base = Path(path).resolve().parent
    e = d.get("engagement")
    for k in ("id", "customer", "owner", "as_of", "currency"):
        _str(e, k, "engagement")
    as_of = _date(e["as_of"], "engagement.as_of")
    seen = set()
    P = {"engagement": e, "as_of": as_of, "base": base, "sha256": digest}
    P["inputs"] = _ids(d.get("inputs"), "inputs", seen)
    P["assumptions"] = _ids(d.get("assumptions") or [], "assumptions", seen)
    P["ambiguities"] = _ids(d.get("ambiguities") or [], "ambiguities", seen)
    P["capabilities"] = _ids(d.get("capabilities") or [], "capabilities", seen)
    P["requirements"] = _ids(d.get("requirements"), "requirements", seen)
    if not P["inputs"] or not P["requirements"]:
        raise Invalid("inputs and requirements must not be empty")
    for k, x in list(P["inputs"].items()) + list(P["assumptions"].items()):
        w = "inputs" if k in P["inputs"] else "assumptions"
        _str(x, "text", "%s.%s" % (w, k)); _str(x, "source", "%s.%s" % (w, k))
        if _date(x.get("date"), "%s.%s.date" % (w, k)) > as_of:
            raise Invalid("%s.%s is dated after engagement.as_of" % (w, k))
        if w == "assumptions" and not isinstance(x.get("confirmed"), bool):
            raise Invalid("assumptions.%s.confirmed must be true or false" % k)
    acs = {}
    for k, r in P["requirements"].items():
        w = "requirements.%s" % k
        _str(r, "text", w)
        r["_traces"] = _refs(r.get("traces"), w + ".traces")
        r["_deps"] = _refs(r.get("depends_on"), w + ".depends_on")
        for x in r["_deps"]:
            if x not in P["requirements"]:
                raise Invalid("%s depends on unknown requirement %r" % (w, x))
        r["_est"] = _hours(r.get("estimate_hours"), w + ".estimate_hours")
        if not isinstance(r.get("optional", False), bool):
            raise Invalid("%s.optional must be true or false" % w)
        cap = r.get("capability")
        if cap is not None and not isinstance(cap, str):
            raise Invalid("%s.capability must be a capability id" % w)
        crit = r.get("acceptance") or []
        if not isinstance(crit, list):
            raise Invalid("%s.acceptance must be a list" % w)
        for c in crit:
            if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not ID.match(c["id"]):
                raise Invalid("%s.acceptance entries need an id" % w)
            if c["id"] in seen or c["id"] in acs:
                raise Invalid("duplicate id %r" % c["id"])
            _str(c, "criterion", "%s.acceptance.%s" % (w, c["id"]))
            if c.get("measure") is not None and not isinstance(c.get("measure"), str):
                raise Invalid("%s.acceptance.%s.measure must be text" % (w, c["id"]))
            acs[c["id"]] = (k, c)
    P["criteria"] = acs
    # dependency cycle check (iterative)
    state = {}
    for start in P["requirements"]:
        stack = [(start, iter(P["requirements"][start]["_deps"]))]
        if state.get(start) == 2:
            continue
        state[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2; stack.pop(); continue
            if state.get(nxt) == 1:
                raise Invalid("dependency cycle through requirement %r" % nxt)
            if state.get(nxt) is None:
                state[nxt] = 1; stack.append((nxt, iter(P["requirements"][nxt]["_deps"])))
    for k, a in P["ambiguities"].items():
        w = "ambiguities.%s" % k
        a["_about"] = _refs(a.get("about"), w + ".about")
        _str(a, "question", w); _str(a, "escalated_to", w)
        if a.get("status") not in ("open", "resolved"):
            raise Invalid("%s.status must be open or resolved" % w)
        if a["status"] == "resolved":
            res = a.get("resolution")
            _str(res, "text", w + ".resolution"); _str(res, "source", w + ".resolution")
            if _date(res.get("date"), w + ".resolution.date") > as_of:
                raise Invalid("%s.resolution is dated after engagement.as_of" % w)
    for k, c in P["capabilities"].items():
        _str(c, "name", "capabilities.%s" % k)
        demo = c.get("demo")
        if demo is not None:
            if not isinstance(demo, dict):
                raise Invalid("capabilities.%s.demo must be an object" % k)
            if not isinstance(demo.get("sha256"), str) or not SHA.match(demo["sha256"]):
                raise Invalid("capabilities.%s.demo.sha256 must be a lowercase sha256" % k)
            _sha_file(base, demo.get("path"), "capabilities.%s.demo" % k)
    rate = d.get("rate")
    _str(rate, "source", "rate")
    if _date(rate.get("date"), "rate.date") > as_of:
        raise Invalid("rate is dated after engagement.as_of")
    P["rate"] = _dec(rate.get("per_hour"), "rate.per_hour", allow_zero=False)
    pr = d.get("proposal")
    if not isinstance(pr, dict):
        raise Invalid("proposal is required")
    P["scope"] = _refs(pr.get("scope"), "proposal.scope")
    if len(set(P["scope"])) != len(P["scope"]):
        raise Invalid("proposal.scope lists a requirement twice")
    for x in P["scope"]:
        if x not in P["requirements"]:
            raise Invalid("proposal.scope names unknown requirement %r" % x)
    P["exclusions"] = _refs(pr.get("exclusions"), "proposal.exclusions")
    est = pr.get("estimate")
    if not isinstance(est, dict) or est.get("type") not in ("range", "fixed"):
        raise Invalid("proposal.estimate.type must be range or fixed")
    P["est_type"] = est["type"]
    if est["type"] == "range":
        P["est_hours"] = _hours(est.get("hours"), "proposal.estimate.hours")
        pp = est.get("price")
        if not isinstance(pp, dict):
            raise Invalid("proposal.estimate.price must be {low, high}")
        P["est_price"] = {k: _dec(pp.get(k), "proposal.estimate.price.%s" % k) for k in ("low", "high")}
    else:
        P["est_hours"] = _dec(est.get("hours"), "proposal.estimate.hours")
        P["est_price"] = _dec(est.get("price"), "proposal.estimate.price")
    P["commitments"] = _ids(pr.get("commitments") or [], "proposal.commitments", seen)
    for k, c in P["commitments"].items():
        w = "proposal.commitments.%s" % k
        _str(c, "text", w)
        if c.get("kind") not in KINDS:
            raise Invalid("%s.kind must be one of %s" % (w, ", ".join(KINDS)))
        c["_refs"] = _refs(c.get("refs"), w + ".refs")
        if c["kind"] == "date":
            c["_date"] = _date(c.get("value"), w + ".value")
    cap = d.get("capacity")
    if cap is not None:
        for k in ("package", "result", "option", "milestone"):
            _str(cap, k, "capacity")
    P["capacity"] = cap
    return P


def _sorted(f):
    return sorted(f, key=lambda x: (x["code"], x.get("ref", "")))


def _capacity(P):
    """Rerun the G17 decision named by the package; return (finish_date or None, problem or None)."""
    cap = P["capacity"]
    if cap is None:
        return None, "no capacity evidence (G17 resource decision) is named"
    if not G17.is_file():
        return None, "the G17 resource decision tool is not present"
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("g17_resource_decision", str(G17))
    rd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rd)
    pkg = P["base"] / cap["package"]
    try:
        rep, _ = rd.evaluate(str(pkg))
        stored = json.loads(Path(P["base"] / cap["result"]).read_text(encoding="utf-8"))
        cal = json.loads(pkg.read_text(encoding="utf-8"))["calendar"]["start"]
    except (rd.Invalid, OSError, ValueError, KeyError, TypeError) as ex:
        return None, "G17 evidence cannot be rerun: %s" % ex
    if rd._diff(json.loads(json.dumps(rep)), stored):
        return None, "stored G17 result does not match a rerun of its package"
    if cap["option"] not in rep.get("feasible_in_downside", []):
        return None, "G17 option %r is not feasible in the downside case" % cap["option"]
    opt = [o for o in rep["options"] if o["id"] == cap["option"]][0]
    ms = [m for m in opt["cases"]["downside"]["milestones"] if m["id"] == cap["milestone"]]
    if not ms or ms[0]["finish_week"] is None:
        return None, "G17 milestone %r has no downside finish week" % cap["milestone"]
    finish = dt.date.fromisoformat(cal) + dt.timedelta(days=7 * ms[0]["finish_week"] - 1)
    return finish, None


def check(path):
    P = load_package(path)
    F, reqs, scope = [], P["requirements"], P["scope"]
    sset = set(scope)
    known_src = set(P["inputs"]) | set(P["assumptions"])
    unconfirmed = {k for k, a in P["assumptions"].items() if not a["confirmed"]}
    # requirement traceability, dependencies, capability and acceptance criteria
    trace = {}
    for k in scope:
        r = reqs[k]
        tr = [t for t in r["_traces"] if t in known_src]
        bad = [t for t in r["_traces"] if t not in known_src]
        if bad:
            F.append({"code": "untraced_requirement", "ref": k, "detail": "traces to unknown %s" % ", ".join(bad)})
        elif not tr:
            F.append({"code": "untraced_requirement", "ref": k, "detail": "no customer input or assumption"})
        trace[k] = tr
        for x in r["_deps"]:
            if x not in sset:
                F.append({"code": "missing_dependency", "ref": k, "detail": "depends on %s, which is not in scope" % x})
        cap = P["capabilities"].get(r.get("capability"))
        why = None
        if cap is None:
            why = "no capability named" if r.get("capability") is None else "unknown capability %r" % r["capability"]
        elif cap.get("demo") is None:
            why = "capability %s has no demo evidence" % cap["id"]
        else:
            why = _demo_problem(P, cap)
        if why:
            F.append({"code": "undemonstrated_capability", "ref": k, "detail": why})
        if not (r.get("acceptance") or []):
            F.append({"code": "no_acceptance_criteria", "ref": k, "detail": "nothing defines done"})
    # ambiguity: vague wording or an unmeasured criterion must be escalated, and open ones block
    amb_for = {}
    for a in P["ambiguities"].values():
        for x in a["_about"]:
            amb_for.setdefault(x, []).append(a)
    escalations = []
    for k in scope:
        r = reqs[k]
        hits = sorted({m.group(1).lower() for m in VAGUE_RX.finditer(r["text"])})
        for c in r.get("acceptance") or []:
            hits += sorted({m.group(1).lower() for m in VAGUE_RX.finditer(c["criterion"] + " " + (c.get("measure") or ""))})
            if not (c.get("measure") or "").strip():
                hits.append("criterion %s has no measure" % c["id"])
        covered = amb_for.get(k, []) + [a for c in (r.get("acceptance") or []) for a in amb_for.get(c["id"], [])]
        if hits and not covered:
            F.append({"code": "unescalated_ambiguity", "ref": k, "detail": "; ".join(sorted(set(hits)))})
        for a in covered:
            if a["status"] == "open":
                F.append({"code": "open_ambiguity", "ref": k, "detail": "%s: %s (escalated to %s)" % (a["id"], a["question"], a["escalated_to"])})
    for a in sorted(P["ambiguities"].values(), key=lambda a: a["id"]):
        if a["status"] == "open":
            escalations.append({"id": a["id"], "about": a["_about"], "question": a["question"], "escalated_to": a["escalated_to"]})
    # silent exclusion of a required (non-optional) requirement
    for k, r in sorted(reqs.items()):
        if k not in sset and not r.get("optional", False) and k not in P["exclusions"]:
            F.append({"code": "silent_exclusion", "ref": k, "detail": "required, not in scope and not listed as excluded"})
    # estimate reconciliation, exact
    tot = {b: sum((reqs[k]["_est"][b] for k in scope), Decimal(0)) for b in ("low", "likely", "high")}
    price = {b: (tot[b] * P["rate"]).quantize(CENT, ROUND_HALF_UP) for b in ("low", "high")}
    est = {"type": P["est_type"], "hours": {b: str(v) for b, v in tot.items()}, "price": {b: str(v) for b, v in price.items()},
           "rate_per_hour": str(P["rate"])}
    if P["est_type"] == "range":
        for b in ("low", "likely", "high"):
            if P["est_hours"][b] != tot[b]:
                F.append({"code": "estimate_mismatch", "ref": "hours.%s" % b, "detail": "stated %s, requirements sum to %s" % (P["est_hours"][b], tot[b])})
        for b in ("low", "high"):
            if P["est_price"][b] != price[b]:
                F.append({"code": "estimate_mismatch", "ref": "price.%s" % b, "detail": "stated %s, hours x rate is %s" % (P["est_price"][b], price[b])})
    else:
        fp = (P["est_hours"] * P["rate"]).quantize(CENT, ROUND_HALF_UP)
        if P["est_price"] != fp:
            F.append({"code": "estimate_mismatch", "ref": "price.fixed", "detail": "stated %s, fixed hours x rate is %s" % (P["est_price"], fp)})
        why = []
        if P["est_hours"] < tot["high"]:
            why.append("fixed %s h is below the high estimate %s h" % (P["est_hours"], tot["high"]))
        if any(a["status"] == "open" for k in scope for a in amb_for.get(k, [])):
            why.append("open ambiguity in scope")
        rest = sorted({t for k in scope for t in trace[k] if t in unconfirmed})
        if rest:
            why.append("rests on unconfirmed assumption %s" % ", ".join(rest))
        if why:
            F.append({"code": "unsupported_fixed_estimate", "ref": "estimate", "detail": "; ".join(why)})
        est["hours"]["fixed"] = str(P["est_hours"]); est["price"]["fixed"] = str(P["est_price"])
    # commitments map to inputs, assumptions or in-scope requirements
    matrix = []
    finish, cap_problem = None, None
    if any(c["kind"] == "date" for c in P["commitments"].values()):
        finish, cap_problem = _capacity(P)
    blocked_reqs = {f["ref"] for f in F if f["code"] in ("open_ambiguity", "unescalated_ambiguity", "undemonstrated_capability", "untraced_requirement")}
    for k, c in sorted(P["commitments"].items()):
        refs = c["_refs"]
        unknown = [x for x in refs if x not in known_src and x not in reqs]
        outside = [x for x in refs if x in reqs and x not in sset]
        if not refs or unknown:
            F.append({"code": "invented_commitment", "ref": k, "detail": "no input, assumption or requirement" if not refs else "unknown %s" % ", ".join(unknown)})
        if outside:
            F.append({"code": "out_of_scope_commitment", "ref": k, "detail": "requirement %s is not in scope" % ", ".join(outside)})
        if c["kind"] in ("scope", "feature", "sla") and not any(x in sset for x in refs):
            F.append({"code": "invented_commitment", "ref": k, "detail": "%s commitment names no in-scope requirement" % c["kind"]})
        on_blocked = sorted(x for x in refs if x in blocked_reqs)
        if on_blocked:
            F.append({"code": "commitment_on_blocked_requirement", "ref": k, "detail": ", ".join(on_blocked)})
        if c["kind"] == "estimate" and P["est_type"] == "fixed" and any(f["code"] == "unsupported_fixed_estimate" for f in F):
            F.append({"code": "unsupported_fixed_estimate", "ref": k, "detail": "commits to the unsupported fixed estimate"})
        if c["kind"] == "date":
            if cap_problem:
                F.append({"code": "unsupported_date", "ref": k, "detail": cap_problem})
            elif finish > c["_date"]:
                F.append({"code": "unsupported_date", "ref": k, "detail": "G17 downside finish %s is after the committed %s" % (finish, c["_date"])})
        roots = sorted({t for x in refs if x in reqs for t in reqs[x]["_traces"] if t in known_src} | {x for x in refs if x in known_src})
        conds = sorted(t for t in roots if t in unconfirmed)
        matrix.append({"commitment": k, "kind": c["kind"], "refs": refs, "sources": roots, "conditional_on": conds})
    F = _sorted(F)
    status = "ready" if not F else "blocked"
    rep = {"schema": REPORT, "command": "check", "status": status, "engagement": P["engagement"]["id"],
           "owner": P["engagement"]["owner"], "as_of": str(P["as_of"]), "package_sha256": P["sha256"],
           "scope": scope, "excluded": sorted(k for k in reqs if k not in sset), "estimate": est,
           "trace_matrix": matrix, "findings": F, "escalations": escalations,
           "conditions": sorted(unconfirmed & {t for k in scope for t in trace[k]}),
           "capacity_finish": str(finish) if finish else None, "read_only": True,
           "note": "draft for the owner; no commitment is made, sent or signed by this tool"}
    return rep, (0 if status == "ready" else 1)


def _demo_problem(P, cap):
    demo = cap["demo"]
    p, got = _sha_file(P["base"], demo.get("path"), "capabilities.%s.demo" % cap["id"])
    if got is None:
        return "demo evidence %s is missing" % demo.get("path")
    if got != demo["sha256"]:
        return "demo evidence %s changed since it was recorded" % demo.get("path")
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "demo evidence %s is not a JSON run record" % demo.get("path")
    if not isinstance(rec, dict) or rec.get("capability") != cap["id"]:
        return "demo evidence records a different capability"
    if rec.get("exit_code") != 0 or rec.get("result") != "pass":
        return "recorded demo run did not pass"
    try:
        ran = dt.date.fromisoformat(str(rec.get("ran_at", ""))[:10])
    except ValueError:
        return "demo run has no date"
    if ran > P["as_of"]:
        return "demo run is dated after engagement.as_of"
    return None


def accept(path, delivery):
    rep, code = check(path)
    P = load_package(path)
    d, digest = _load(delivery, "delivery")
    if not isinstance(d, dict) or d.get("schema") != DELIVERY:
        raise Invalid("delivery schema must be %r" % DELIVERY)
    as_of = _date(d.get("as_of"), "delivery.as_of")
    base = Path(delivery).resolve().parent
    res = {}
    if not isinstance(d.get("results"), list):
        raise Invalid("delivery.results must be a list")
    for i, x in enumerate(d["results"]):
        w = "delivery.results[%d]" % i
        if not isinstance(x, dict) or x.get("criterion") not in P["criteria"]:
            raise Invalid("%s names an unknown acceptance criterion" % w)
        if x["criterion"] in res:
            raise Invalid("%s repeats criterion %s" % (w, x["criterion"]))
        if x.get("outcome") not in ("pass", "fail"):
            raise Invalid("%s.outcome must be pass or fail" % w)
        if _date(x.get("date"), w + ".date") > as_of:
            raise Invalid("%s is dated after delivery.as_of" % w)
        ev = x.get("evidence")
        if not isinstance(ev, dict) or not isinstance(ev.get("sha256"), str) or not SHA.match(ev["sha256"]):
            raise Invalid("%s.evidence needs path and sha256" % w)
        res[x["criterion"]] = x
    rows, F = [], []
    for k in P["scope"]:
        crit = P["requirements"][k].get("acceptance") or []
        st = "accepted" if crit else "no_criteria"
        for c in crit:
            x = res.get(c["id"])
            if x is None:
                F.append({"code": "missing_evidence", "ref": c["id"], "detail": "requirement %s" % k}); st = "not_accepted"; continue
            _, got = _sha_file(base, x["evidence"].get("path"), "delivery evidence")
            if got != x["evidence"]["sha256"]:
                F.append({"code": "evidence_mismatch", "ref": c["id"], "detail": "missing" if got is None else "hash differs"}); st = "not_accepted"
            elif x["outcome"] != "pass":
                F.append({"code": "criterion_failed", "ref": c["id"], "detail": "requirement %s" % k}); st = "not_accepted"
        rows.append({"requirement": k, "status": st})
    if code != 0:
        F.append({"code": "scope_not_ready", "ref": "check", "detail": "%d check finding(s)" % len(rep["findings"])})
    F = _sorted(F)
    ok = not F and all(r["status"] == "accepted" for r in rows)
    out = {"schema": REPORT, "command": "accept", "status": "accepted" if ok else "not_accepted",
           "engagement": rep["engagement"], "owner": rep["owner"], "package_sha256": P["sha256"],
           "delivery_sha256": digest, "delivery_as_of": str(as_of), "requirements": rows, "findings": F,
           "read_only": True, "note": "acceptance record for the owner to sign; this tool signs nothing"}
    return out, (0 if ok else 1)


def _write_atomic(out, data, protect):
    out = Path(out)
    for p in protect:
        if p and out.resolve() == Path(p).resolve():
            raise Invalid("--out would overwrite an input file")
    fd, tmp = tempfile.mkstemp(prefix=".g31-", dir=str(out.resolve().parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def render(r):
    L = ["%s %s: %s (owner %s)" % (r["command"], r["engagement"], r["status"].upper(), r["owner"])]
    if r["command"] == "check":
        e = r["estimate"]
        L.append("estimate %s: hours %s, price %s at %s/h" % (e["type"], e["hours"], e["price"], e["rate_per_hour"]))
        for m in r["trace_matrix"]:
            L.append("  %s (%s) -> %s%s" % (m["commitment"], m["kind"], ", ".join(m["sources"]) or "nothing",
                                            " [conditional on %s]" % ", ".join(m["conditional_on"]) if m["conditional_on"] else ""))
        for x in r["escalations"]:
            L.append("  ESCALATE %s to %s: %s" % (x["id"], x["escalated_to"], x["question"]))
    else:
        for x in r["requirements"]:
            L.append("  %s: %s" % (x["requirement"], x["status"]))
    for f in r["findings"]:
        L.append("  FINDING %s %s: %s" % (f["code"], f["ref"], f["detail"]))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scope_acceptance.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check"); c.add_argument("package"); c.add_argument("--json", action="store_true"); c.add_argument("--out")
    a = sub.add_parser("accept"); a.add_argument("package"); a.add_argument("delivery"); a.add_argument("--json", action="store_true"); a.add_argument("--out")
    v = sub.add_parser("verify"); v.add_argument("result"); v.add_argument("package"); v.add_argument("delivery", nargs="?")
    a_ = ap.parse_args(argv)
    try:
        if a_.cmd in ("check", "accept"):
            rep, code = check(a_.package) if a_.cmd == "check" else accept(a_.package, a_.delivery)
            data = (json.dumps(rep, indent=1, sort_keys=True) + "\n").encode()
            if a_.out:
                _write_atomic(a_.out, data, [a_.package, getattr(a_, "delivery", None)])
            print(data.decode().rstrip() if a_.json else render(rep))
            return code
        if a_.cmd == "verify":
            stored, _ = _load(a_.result, "result")
            rep, _ = accept(a_.package, a_.delivery) if a_.delivery else check(a_.package)
            fresh = json.loads(json.dumps(rep))
            diffs = sorted(k for k in set(fresh) | set(stored if isinstance(stored, dict) else {})
                           if not isinstance(stored, dict) or fresh.get(k) != stored.get(k))
            if diffs:
                print("DIFFERENT: %s do not match a rerun" % ", ".join(diffs))
                return 1
            print("IDENTICAL: the stored result matches a rerun (package sha256 %s)" % rep["package_sha256"])
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
