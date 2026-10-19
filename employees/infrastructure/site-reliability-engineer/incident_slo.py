#!/usr/bin/env python3
"""Incident timeline, SLO / error budget and rollback decision from synthetic records (Solaris SRE).

Reads one incident bundle (schema "solaris.incident-bundle/1": service, service window, SLO,
per-minute request telemetry, incident events, the change under suspicion and optional G10
network traces) and writes one report: the merged timeline, exact SLO and error-budget values
for the named window, the telemetry it does not have, and a rollback decision whose trace
names the service, the window and the revision.

Records arrive late, twice and out of order. A telemetry minute delivered twice with the same
counts is counted once; a minute with two different counts is "conflicting" and, like a minute
with no record, is labelled and left out of the measured values instead of being guessed. An
event id delivered twice with the same content is kept once; with different content the bundle
is refused. The same bundle always gives the same bytes (no wall clock, sorted JSON), and
re-importing the same records (duplicated, reordered) gives the same SLO, timeline and decision.

Sources it reuses, both read-only:
  * G10 network-engineer/netdiag.py analyses each supplied trace; a fault it places at the
    dns, route or tls layer during the impact is a reason not to roll back the code.
  * G03 database-administrator/sqlite_recovery.py verifies the data snapshot a rollback needs
    when the change migrated data. Without a verified snapshot the rollback is blocked.

It never opens a socket, deploys, rolls back or changes any file other than --out.

Usage:
  incident_slo.py report BUNDLE.json [--json] [--out REPORT]
Exit codes: 0 analysed, 2 invalid input (nothing written).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BUNDLE_SCHEMA = "solaris.incident-bundle/1"
REPORT_SCHEMA = "solaris.incident-report/1"
EVENT_KINDS = ("detected", "declared", "mitigated", "resolved", "deploy", "rollback", "status", "note")
NON_APP_LAYERS = ("dns", "route", "tls")
LATE_AFTER_S = 300
MAX_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 500000
MAX_WINDOW_MIN = 31 * 24 * 60
DEFAULT_BURN = Fraction(10)
DEFAULT_COVERAGE = Fraction(9, 10)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MINUTE = dt.timedelta(minutes=1)
HERE = Path(__file__).resolve().parent
NETDIAG = HERE.parent / "network-engineer" / "netdiag.py"
RECOVERY = HERE.parent / "database-administrator" / "sqlite_recovery.py"


class Invalid(Exception):
    """The bundle cannot be analysed; nothing is written."""


def _load_module(name: str, path: Path) -> Any:
    """Import a sibling role's tool without leaving __pycache__ in its folder."""
    if name in sys.modules:
        return sys.modules[name]
    if not path.is_file():
        raise Invalid(f"required tool {path.parent.name}/{path.name} is not present")
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        sys.dont_write_bytecode = old
    return mod


# -- input validation -----------------------------------------------------------------

def _no_dupes(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise Invalid(f"duplicate key {k!r}; ambiguous evidence")
        out[k] = v
    return out


def _reject_const(name: str) -> Any:
    raise Invalid(f"non-finite number {name} is not valid evidence")


def _obj(v: Any, where: str) -> Dict[str, Any]:
    if not isinstance(v, dict):
        raise Invalid(f"{where}: expected an object")
    return v


def _str(v: Any, where: str, limit: int = 300) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > limit or any(ord(c) < 32 for c in v):
        raise Invalid(f"{where}: expected a non-empty single-line string of at most {limit} characters")
    return v


def _name(v: Any, where: str) -> str:
    if not isinstance(v, str) or not NAME_RE.match(v):
        raise Invalid(f"{where}: expected a name of letters, digits, '.', '_' or '-'")
    return v


def _time(v: Any, where: str) -> dt.datetime:
    if not isinstance(v, str) or len(v) > 40:
        raise Invalid(f"{where}: expected an ISO 8601 timestamp with a zone")
    s = v[:-1] + "+00:00" if v.endswith(("Z", "z")) else v
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        raise Invalid(f"{where}: {v[:40]!r} is not an ISO 8601 timestamp") from None
    if t.tzinfo is None:
        raise Invalid(f"{where}: {v[:40]!r} has no zone; times must be absolute")
    return t.astimezone(dt.timezone.utc)


def _minute(v: Any, where: str) -> dt.datetime:
    t = _time(v, where)
    if t.second or t.microsecond:
        raise Invalid(f"{where}: telemetry buckets and window bounds must start on a whole minute")
    return t


def _count(v: Any, where: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 10 ** 12:
        raise Invalid(f"{where}: expected a whole number of requests")
    return v


def _ratio(v: Any, where: str, lo: Fraction, hi: Fraction, open_hi: bool = True) -> Fraction:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Invalid(f"{where}: expected a number")
    f = Fraction(str(v))
    if not (lo < f and (f < hi if open_hi else f <= hi)):
        raise Invalid(f"{where}: {v} is outside the allowed range")
    return f


def _inside(base: Path, rel: Any, where: str) -> Path:
    if not isinstance(rel, str) or not rel or os.path.isabs(rel):
        raise Invalid(f"{where}: expected a path relative to the bundle")
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise Invalid(f"{where}: {rel!r} leaves the bundle folder")
    return p


def iso(t: Optional[dt.datetime]) -> Optional[str]:
    return None if t is None else t.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_bundle(path: Path) -> Tuple[Dict[str, Any], str]:
    try:
        st = path.stat()
        if not path.is_file():
            raise Invalid(f"{path.name}: not a regular file")
        if st.st_size > MAX_BYTES:
            raise Invalid(f"{path.name}: larger than {MAX_BYTES} bytes")
        raw = path.read_bytes()
    except OSError as exc:
        raise Invalid(f"cannot read bundle: {exc.strerror}") from None
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_reject_const)
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, Invalid):
            raise
        raise Invalid(f"{path.name}: not valid UTF-8 JSON") from None
    return normalise(doc, path.resolve().parent), hashlib.sha256(raw).hexdigest()


def normalise(doc: Any, base: Path) -> Dict[str, Any]:
    d = _obj(doc, "bundle")
    if d.get("schema") != BUNDLE_SCHEMA:
        raise Invalid(f"schema must be {BUNDLE_SCHEMA!r}")
    known = {"schema", "service", "window", "slo", "telemetry", "events", "change", "diagnoses"}
    extra = sorted(set(d) - known)
    if extra:
        raise Invalid(f"unknown field(s) {extra}; refusing to ignore evidence")
    service = _name(d.get("service"), "service")
    w = _obj(d.get("window"), "window")
    start, end = _minute(w.get("start"), "window.start"), _minute(w.get("end"), "window.end")
    if end <= start:
        raise Invalid("window.end must be after window.start")
    if (end - start) // MINUTE > MAX_WINDOW_MIN:
        raise Invalid(f"window longer than {MAX_WINDOW_MIN} minutes")
    s = _obj(d.get("slo"), "slo")
    objective = _ratio(s.get("objective"), "slo.objective", Fraction(0), Fraction(1))
    burn = DEFAULT_BURN if s.get("rollback_burn_rate") is None else \
        _ratio(s.get("rollback_burn_rate"), "slo.rollback_burn_rate", Fraction(0), Fraction(10 ** 6))
    cov = DEFAULT_COVERAGE if s.get("min_coverage") is None else \
        _ratio(s.get("min_coverage"), "slo.min_coverage", Fraction(0), Fraction(1), open_hi=False)

    tel = d.get("telemetry")
    if not isinstance(tel, list):
        raise Invalid("telemetry: expected a list")
    evs = d.get("events", [])
    if not isinstance(evs, list):
        raise Invalid("events: expected a list")
    if len(tel) + len(evs) > MAX_RECORDS:
        raise Invalid(f"more than {MAX_RECORDS} records")
    buckets: Dict[dt.datetime, List[Tuple[int, int]]] = {}
    stats = {"telemetry_records": len(tel), "telemetry_duplicates": 0, "telemetry_late": 0,
             "telemetry_outside_window": 0, "event_records": len(evs), "event_duplicates": 0, "events_late": 0}
    for i, r in enumerate(tel):
        r = _obj(r, f"telemetry[{i}]")
        m = _minute(r.get("minute"), f"telemetry[{i}].minute")
        good, total = _count(r.get("good"), f"telemetry[{i}].good"), _count(r.get("total"), f"telemetry[{i}].total")
        if good > total:
            raise Invalid(f"telemetry[{i}]: good {good} exceeds total {total}")
        if r.get("source") is not None:
            _str(r.get("source"), f"telemetry[{i}].source", 100)
        if r.get("received_at") is not None:
            if (_time(r["received_at"], f"telemetry[{i}].received_at") - (m + MINUTE)).total_seconds() > LATE_AFTER_S:
                stats["telemetry_late"] += 1
        if not (start <= m < end):
            stats["telemetry_outside_window"] += 1
            continue
        vals = buckets.setdefault(m, [])
        if (good, total) in vals:
            stats["telemetry_duplicates"] += 1
        else:
            vals.append((good, total))

    events: Dict[str, Dict[str, Any]] = {}
    for i, e in enumerate(evs):
        e = _obj(e, f"events[{i}]")
        bad_keys = sorted(set(e) - {"id", "at", "kind", "actor", "detail", "received_at"})
        if bad_keys:
            raise Invalid(f"events[{i}]: unknown field(s) {bad_keys}")
        eid = _str(e.get("id"), f"events[{i}].id", 100)
        at = _time(e.get("at"), f"events[{i}].at")
        kind = e.get("kind")
        if kind not in EVENT_KINDS:
            raise Invalid(f"events[{i}].kind must be one of {', '.join(EVENT_KINDS)}")
        rec = {"id": eid, "at": at, "kind": kind,
               "actor": None if e.get("actor") is None else _str(e["actor"], f"events[{i}].actor", 100),
               "detail": None if e.get("detail") is None else _str(e["detail"], f"events[{i}].detail")}
        recv = None if e.get("received_at") is None else _time(e["received_at"], f"events[{i}].received_at")
        if eid in events:
            prev = events[eid]
            if {k: prev[k] for k in rec} != rec:
                raise Invalid(f"event id {eid!r} was delivered twice with different content; ambiguous evidence")
            stats["event_duplicates"] += 1
            if recv is not None and (prev["received_at"] is None or recv < prev["received_at"]):
                prev["received_at"] = recv
            continue
        rec["received_at"] = recv
        events[eid] = rec
    for rec in events.values():
        rec["late"] = rec["received_at"] is not None and (rec["received_at"] - rec["at"]).total_seconds() > LATE_AFTER_S
        stats["events_late"] += int(rec["late"])

    change = None
    if d.get("change") is not None:
        c = _obj(d["change"], "change")
        bad_keys = sorted(set(c) - {"revision", "previous", "deployed_at", "migrates_data", "data"})
        if bad_keys:
            raise Invalid(f"change: unknown field(s) {bad_keys}")
        mig = c.get("migrates_data", False)
        if not isinstance(mig, bool):
            raise Invalid("change.migrates_data must be true or false")
        change = {"revision": _name(c.get("revision"), "change.revision"),
                  "previous": _name(c.get("previous"), "change.previous"),
                  "deployed_at": _time(c.get("deployed_at"), "change.deployed_at"), "migrates_data": mig, "data": None}
        if c.get("data") is not None:
            dd = _obj(c["data"], "change.data")
            dbs = dd.get("databases")
            if not isinstance(dbs, list) or not dbs or not all(isinstance(x, str) and NAME_RE.match(x) for x in dbs):
                raise Invalid("change.data.databases: expected a list of database file names")
            change["data"] = {"snapshot": _inside(base, dd.get("snapshot"), "change.data.snapshot"),
                              "snapshot_rel": dd.get("snapshot"), "databases": sorted(set(dbs))}
    diags = d.get("diagnoses", [])
    if not isinstance(diags, list) or len(diags) > 100:
        raise Invalid("diagnoses: expected a list of at most 100 trace paths")
    diag_paths = sorted({(str(x), _inside(base, x, f"diagnoses[{i}]")) for i, x in enumerate(diags)})
    return {"service": service, "start": start, "end": end, "objective": objective, "burn": burn,
            "min_coverage": cov, "buckets": buckets, "events": events, "change": change,
            "diagnoses": diag_paths, "stats": stats}


# -- analysis -------------------------------------------------------------------------

def dec(f: Optional[Fraction], places: int = 6) -> Optional[str]:
    """Exact decimal rendering (round half to even) of a rational value."""
    if f is None:
        return None
    q = round(f * 10 ** places)
    sign = "-" if q < 0 else ""
    q = abs(q)
    return f"{sign}{q // 10 ** places}.{q % 10 ** places:0{places}d}"


def _ranges(minutes: List[dt.datetime]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in minutes:
        if out and out[-1]["_end"] == m:
            out[-1]["_end"] = m + MINUTE
            out[-1]["minutes"] += 1
        else:
            out.append({"_start": m, "_end": m + MINUTE, "minutes": 1})
    return [{"start": iso(r["_start"]), "end": iso(r["_end"]), "minutes": r["minutes"]} for r in out]


def _sums(b: Dict[str, Any], minutes: List[dt.datetime]) -> Tuple[int, int, int]:
    good = total = n = 0
    for m in minutes:
        v = b["buckets"].get(m)
        if v and len(v) == 1:
            good += v[0][0]
            total += v[0][1]
            n += 1
    return good, total, n


def _slo(b: Dict[str, Any], good: int, total: int, measured: int, n: int) -> Dict[str, Any]:
    o = b["objective"]
    bad = total - good
    allowed = (1 - o) * total
    cov = Fraction(measured, n) if n else Fraction(0)
    avail = Fraction(good, total) if total else None
    burn = Fraction(bad, total) / (1 - o) if total else None
    if not total or cov < b["min_coverage"]:
        status = "insufficient_telemetry"
    else:
        status = "met" if avail >= o else "breached"
    return {"good": good, "total": total, "bad": bad, "minutes": n, "measured_minutes": measured,
            "coverage": dec(cov), "availability": dec(avail), "error_budget_requests": dec(allowed),
            "budget_consumed": dec(Fraction(bad) / allowed) if allowed else None,
            "budget_remaining": dec(1 - Fraction(bad) / allowed) if allowed else None,
            "burn_rate": dec(burn), "status": status, "_burn": burn, "_cov": cov}


def _diagnose(b: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    if not b["diagnoses"]:
        return out
    nd = _load_module("solaris_g11_netdiag", NETDIAG)
    for rel, path in b["diagnoses"]:
        try:
            trace, sha = nd.load_trace(path)
            rep = nd.analyse(trace, sha)
        except nd.Invalid as exc:
            out.append({"trace": rel, "status": "invalid", "error": str(exc)[:200], "at": None})
            continue
        at = _time(trace["captured_at"], "captured_at") if trace.get("captured_at") else None
        out.append({"trace": rel, "status": "ok", "input_sha256": rep["input_sha256"], "at": at,
                    "target": rep["target"], "verdict": rep["verdict"], "layer": rep["layer"],
                    "confidence": rep["confidence"], "candidates": list(rep["candidates"])})
    return out


def _decide(b: Dict[str, Any], minutes: List[dt.datetime], impact: Dict[str, Any],
            diags: List[Dict[str, Any]], gaps: Any) -> Optional[Dict[str, Any]]:
    c = b["change"]
    if c is None:
        return None
    svc, w = b["service"], f"{iso(b['start'])}/{iso(b['end'])}"
    head = {"service": svc, "window": w, "revision": c["revision"], "previous": c["previous"],
            "deployed_at": iso(c["deployed_at"])}
    trace: List[Dict[str, str]] = []

    def done(decision: str, reason: str) -> Dict[str, Any]:
        return dict(head, decision=decision, reason=f"{svc} {w}: {reason}", trace=trace)

    dep = c["deployed_at"]
    if not (b["start"] <= dep < b["end"]):
        trace.append({"check": "change inside window", "observed": iso(dep), "result": "no"})
        return done("not_applicable", f"change {c['revision']} was deployed at {iso(dep)}, outside the window")
    trace.append({"check": "change inside window", "observed": iso(dep), "result": "yes"})
    dep_min = dep.replace(second=0, microsecond=0)
    post = [m for m in minutes if m >= dep_min]
    good, total, measured = _sums(b, post)
    p = _slo(b, good, total, measured, len(post))
    trace.append({"check": "telemetry after the change", "observed": f"{measured}/{len(post)} minutes measured (coverage {p['coverage']}, minimum {dec(b['min_coverage'])})",
                  "result": "enough" if p["_cov"] >= b["min_coverage"] and total else "not enough"})
    if p["_cov"] < b["min_coverage"] or not total:
        return done("insufficient_evidence", f"only {measured} of {len(post)} minutes after {c['revision']} have telemetry; no rollback decision without it")
    start = impact["_start"]
    if start is None:
        trace.append({"check": "budget-burning impact", "observed": "no minute burned faster than the budget", "result": "none"})
        return done("do_not_rollback", f"no minute burned error budget faster than allowed after {c['revision']}")
    if start < dep_min:
        trace.append({"check": "impact began after the change", "observed": f"impact from {iso(start)}", "result": "no"})
        return done("do_not_rollback", f"impact began at {iso(start)}, before {c['revision']} was deployed at {iso(dep)}; rolling back cannot be the fix")
    if impact["start_bound"] != "exact":
        gap_start = start
        while gap_start - MINUTE in gaps:
            gap_start -= MINUTE
        if gap_start <= dep_min:
            trace.append({"check": "impact began after the change", "observed": f"no telemetry from {iso(gap_start)} to {iso(start)}", "result": "unknown"})
            return done("insufficient_evidence", f"telemetry is missing from {iso(gap_start)} to {iso(start)}, so the impact may have begun before {c['revision']}")
    trace.append({"check": "impact began after the change", "observed": f"impact from {iso(start)}", "result": "yes"})
    end = impact["_end"]
    span = [m for m in post if m < end]
    sg, stot, smeas = _sums(b, span)
    p = _slo(b, sg, stot, smeas, len(span))
    trace.append({"check": "burn rate from the change to the end of the impact",
                  "observed": f"{p['burn_rate']} over {iso(dep_min)}/{iso(end)} (rollback threshold {dec(b['burn'])})",
                  "result": "above" if p["_burn"] >= b["burn"] else "below"})
    if p["_burn"] < b["burn"]:
        return done("do_not_rollback", f"burn rate from {c['revision']} to the end of the impact is {p['burn_rate']}, below the rollback threshold {dec(b['burn'])}")
    for dg in diags:
        if dg["status"] != "ok" or dg["at"] is None or not (start <= dg["at"] <= end):
            continue
        if dg["verdict"] in ("localized", "probable") and dg["layer"] in NON_APP_LAYERS and "application" not in dg["candidates"]:
            trace.append({"check": "G10 network diagnosis during the impact", "observed": f"{dg['trace']}: {dg['verdict']} at {dg['layer']} ({dg['confidence']}) at {iso(dg['at'])}", "result": "fault outside the application"})
            return done("do_not_rollback", f"G10 places the fault at the {dg['layer']} layer ({dg['verdict']}, {dg['confidence']}) at {iso(dg['at'])}; rolling back {c['revision']} does not change that layer")
        trace.append({"check": "G10 network diagnosis during the impact", "observed": f"{dg['trace']}: {dg['verdict']}" + (f" at {dg['layer']}" if dg["layer"] else ""), "result": "does not exclude the application"})
    if not c["migrates_data"]:
        trace.append({"check": "data restore needed", "observed": "change does not migrate data", "result": "code-only rollback"})
        return done("rollback", f"roll back {c['revision']} to {c['previous']} (code only): impact began after the change and burns {p['burn_rate']}x the budget")
    if c["data"] is None:
        trace.append({"check": "G03 data snapshot", "observed": "the change migrated data and no snapshot is named", "result": "missing"})
        return done("rollback_blocked", f"{c['revision']} migrated data and no verified snapshot is named; a code-only rollback would leave migrated data under {c['previous']}")
    rec = _load_module("solaris_g11_sqlite_recovery", RECOVERY)
    res = rec.verify(str(c["data"]["snapshot"]), c["data"]["databases"])
    if res.get("status") != "ok":
        msg = "; ".join(res.get("messages", []))[:200]
        trace.append({"check": "G03 data snapshot", "observed": f"{c['data']['snapshot_rel']}: {msg}", "result": "not verified"})
        return done("rollback_blocked", f"{c['revision']} migrated data and snapshot {c['data']['snapshot_rel']} does not verify (G03); a code-only rollback would leave migrated data under {c['previous']}")
    trace.append({"check": "G03 data snapshot", "observed": f"{c['data']['snapshot_rel']}: snapshot {res['snapshot_id']} verified", "result": "verified"})
    return done("rollback", f"roll back {c['revision']} to {c['previous']} and restore data from G03 snapshot {res['snapshot_id']}: impact began after the change and burns {p['burn_rate']}x the budget")


def analyse(b: Dict[str, Any], sha: str) -> Dict[str, Any]:
    n = (b["end"] - b["start"]) // MINUTE
    minutes = [b["start"] + i * MINUTE for i in range(n)]
    missing = [m for m in minutes if m not in b["buckets"]]
    conflicting = [m for m in minutes if len(b["buckets"].get(m, ())) > 1]
    gaps = set(missing) | set(conflicting)
    good, total, measured = _sums(b, minutes)
    slo = _slo(b, good, total, measured, n)
    allowed_ratio = 1 - b["objective"]
    burning = [m for m in minutes if m not in gaps and b["buckets"][m][0][1] and
               Fraction(b["buckets"][m][0][1] - b["buckets"][m][0][0], b["buckets"][m][0][1]) > allowed_ratio]
    impact = {"_start": burning[0] if burning else None, "_end": burning[-1] + MINUTE if burning else None,
              "start_bound": "exact", "end_bound": "exact"}
    if burning:
        if burning[0] - MINUTE in gaps or burning[0] == b["start"]:
            impact["start_bound"] = "at_or_before"
        if burning[-1] + MINUTE in gaps or impact["_end"] == b["end"]:
            impact["end_bound"] = "at_or_after"
    diags = _diagnose(b)
    decision = _decide(b, minutes, impact, diags, gaps)

    tl: List[Dict[str, Any]] = []
    for e in b["events"].values():
        tl.append({"at": iso(e["at"]), "kind": e["kind"], "source": "event", "id": e["id"], "actor": e["actor"],
                   "detail": e["detail"], "late": e["late"], "outside_window": not (b["start"] <= e["at"] < b["end"])})
    c = b["change"]
    if c is not None:
        tl.append({"at": iso(c["deployed_at"]), "kind": "change", "source": "change", "id": c["revision"],
                   "detail": f"{c['previous']} -> {c['revision']}" + (" (migrates data)" if c["migrates_data"] else "")})
    if burning:
        tl.append({"at": iso(impact["_start"]), "kind": "impact_start", "source": "telemetry", "id": "impact",
                   "detail": f"first minute burning budget faster than allowed ({impact['start_bound']})"})
        tl.append({"at": iso(impact["_end"]), "kind": "impact_end", "source": "telemetry", "id": "impact",
                   "detail": f"end of the last minute burning budget faster than allowed ({impact['end_bound']})"})
    for r in _ranges(missing):
        tl.append({"at": r["start"], "kind": "telemetry_missing", "source": "telemetry", "id": "gap",
                   "detail": f"no telemetry for {r['minutes']} minute(s) until {r['end']}"})
    for r in _ranges(conflicting):
        tl.append({"at": r["start"], "kind": "telemetry_conflicting", "source": "telemetry", "id": "conflict",
                   "detail": f"two different counts for {r['minutes']} minute(s) until {r['end']}; left out"})
    for dg in diags:
        det = f"G10 {dg['verdict']}" + (f" at {dg['layer']}" if dg.get("layer") else "") + \
            (f" ({dg['confidence']})" if dg.get("confidence") else "") if dg["status"] == "ok" else f"unreadable trace: {dg['error']}"
        tl.append({"at": iso(dg["at"]), "kind": "diagnosis", "source": "g10", "id": dg["trace"], "detail": det})
    order = {k: i for i, k in enumerate(("telemetry_missing", "telemetry_conflicting", "change", "deploy", "impact_start",
                                          "diagnosis", "detected", "declared", "status", "note", "mitigated",
                                          "rollback", "impact_end", "resolved"))}
    tl.sort(key=lambda x: (x["at"] is None, x["at"] or "", order.get(x["kind"], 99), x["id"]))

    first = {}
    for k in ("detected", "declared", "mitigated", "resolved"):
        ts = sorted(e["at"] for e in b["events"].values() if e["kind"] == k)
        first[k] = ts[0] if ts else None
    det = min([t for t in (first["detected"], first["declared"]) if t is not None], default=None)
    response: Dict[str, Any] = {}
    labels = []
    for key, t in (("time_to_detect_s", det), ("time_to_mitigate_s", first["mitigated"]), ("time_to_resolve_s", first["resolved"])):
        if impact["_start"] is None or t is None:
            response[key] = None
        else:
            response[key] = int((t - impact["_start"]).total_seconds())
    if impact["_start"] is not None:
        for k, t in (("detected or declared", det), ("mitigated", first["mitigated"]), ("resolved", first["resolved"])):
            if t is None:
                labels.append(f"no {k} event")
    if missing:
        labels.append(f"telemetry missing for {len(missing)} minute(s); left out of the SLO, not counted as good or bad")
    if conflicting:
        labels.append(f"conflicting telemetry for {len(conflicting)} minute(s); left out of the SLO")
    if impact["start_bound"] != "exact" and impact["_start"] is not None:
        labels.append("impact start is bounded by missing telemetry or the window start; response times are lower bounds")

    for k in ("_burn", "_cov"):
        slo.pop(k)
    slo.update({"service": b["service"], "window": {"start": iso(b["start"]), "end": iso(b["end"])},
                "objective": dec(b["objective"])})
    return {
        "schema": REPORT_SCHEMA, "input_sha256": sha, "service": b["service"],
        "window": {"start": iso(b["start"]), "end": iso(b["end"]), "minutes": n},
        "slo": slo,
        "missing_telemetry": {"minutes": len(missing), "ranges": _ranges(missing),
                              "conflicting_minutes": len(conflicting), "conflicting_ranges": _ranges(conflicting)},
        "impact": {"start": iso(impact["_start"]), "end": iso(impact["_end"]), "start_bound": impact["start_bound"],
                   "end_bound": impact["end_bound"], "minutes": len(burning)},
        "response": response, "labels": labels, "timeline": tl,
        "diagnoses": [dict(dg, at=iso(dg["at"])) for dg in diags],
        "decision": decision, "import": b["stats"],
        "read_only": "offline analysis of the supplied records; nothing was deployed, rolled back or sent",
    }


def render(r: Dict[str, Any]) -> str:
    s = r["slo"]
    lines = [f"service {r['service']} window {r['window']['start']} to {r['window']['end']}",
             f"  SLO {s['objective']}: availability {s['availability']} ({s['good']}/{s['total']}), status {s['status']}, "
             f"budget remaining {s['budget_remaining']}, burn {s['burn_rate']}, coverage {s['coverage']}"]
    mt = r["missing_telemetry"]
    if mt["minutes"] or mt["conflicting_minutes"]:
        lines.append(f"  missing telemetry: {mt['minutes']} minute(s), conflicting: {mt['conflicting_minutes']} minute(s)")
    for t in r["timeline"]:
        lines.append(f"  {t['at'] or 'time unknown'} {t['kind']}: {t.get('detail') or t['id']}" + (" [late]" if t.get("late") else ""))
    if r["decision"]:
        lines.append(f"decision: {r['decision']['decision']} - {r['decision']['reason']}")
    lines += [f"  label: {x}" for x in r["labels"]]
    return "\n".join(lines) + "\n"


def _write_atomic(out: Path, data: bytes) -> None:
    out = out.resolve()
    fd, tmp = tempfile.mkstemp(prefix=".incident-", dir=str(out.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def report_file(path: str) -> Dict[str, Any]:
    b, sha = load_bundle(Path(path))
    return analyse(b, sha)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="incident_slo.py", description="Incident timeline, SLO and rollback decision.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report", help="analyse one incident bundle")
    r.add_argument("bundle")
    r.add_argument("--json", action="store_true", help="print the JSON report")
    r.add_argument("--out", help="also write the JSON report here, atomically")
    a = ap.parse_args(argv)
    try:
        rep = report_file(a.bundle)
    except Invalid as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    data = (json.dumps(rep, sort_keys=True, indent=1) + "\n").encode()
    if a.out:
        _write_atomic(Path(a.out), data)
    sys.stdout.write(data.decode() if a.json else render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
