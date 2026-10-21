#!/usr/bin/env python3
"""Experiment and retention readout with fixed cohorts, leakage checks and uncertainty (Solaris data-scientist).

Reads a package (JSON, schema "solaris.experiment/1") naming an assignments file (one row per unit
and arm), an events file, the unit of analysis, the fixed cohort window, the outcome (an event within
a horizon after assignment), the planned split, the minimum sample per arm, alpha, and whether
assignment was randomized. CSV parsing, typed values and row rejects come from the G13
data-engineer reader (csv_reconcile.py read_table).

What it guarantees:
  * Unit of analysis: one outcome per unit (a unit with many events or sessions counts once).
  * Fixed cohort: only units first assigned inside [cohort.start, cohort.end); units whose horizon is
    not complete by as_of are immature and excluded, never counted as non-converted.
  * Leakage: units seen in more than one arm are excluded and named; outcome events before
    assignment or at or after assignment + horizon do not count; events of unassigned units are ignored
    and counted; a sample-ratio mismatch (chi-square against the planned split, p < 0.001) invalidates
    the readout, and so does allocation drift: a per-week sample-ratio test (Bonferroni over the weeks)
    or a split that differs between weeks (arm x week chi-square, p < 0.001), or any run of assignments
    whose split departs from the plan (sliding windows of 20, 40, 80, ... units in assignment order,
    Bonferroni at 0.002 over the windows), which does not depend on where the 7-day blocks fall.
  * Uncertainty: per-arm rates, difference with a 95% (1 - alpha) Wald interval and a two-sided
    two-proportion z test. A difference is claimed only when the interval excludes 0, both arms meet
    the minimum sample and assignment was randomized; observational data gets "association only".
  * Outcomes: insufficient_information, invalid_experiment, no_detectable_difference,
    difference_detected (randomized) or association_only (observational). No other claim is made.

Usage:
  experiment_readout.py analyse PACKAGE.json [--json] [--out REPORT]
Exit codes: 0 analysed (any outcome), 2 invalid package or input (nothing written).
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PACKAGE_SCHEMA = "solaris.experiment/1"
REPORT_SCHEMA = "solaris.experiment-readout/1"
HERE = Path(__file__).resolve().parent
G13 = HERE.parent / "data-engineer" / "csv_reconcile.py"
SRM_P = 0.001
SCAN_ALPHA = 0.002  # family-wise level of the sliding-window allocation scan (Bonferroni over its windows)
SCAN_MIN = 20  # smallest window, in units
SCAN_EXACT_MAX = 1280  # windows up to this size use the exact binomial test, larger ones chi-square
ASSIGN_COLS = {"unit_id": "str", "arm": "str", "assigned_at": "timestamp"}
EVENT_COLS = {"unit_id": "str", "event": "str", "occurred_at": "timestamp", "session_id": "str"}


class Invalid(Exception):
    """The package cannot be analysed; nothing is written."""


def _load_g13() -> Any:
    name = "solaris_g15_csv_reconcile"
    if name in sys.modules:
        return sys.modules[name]
    if not G13.is_file():
        raise Invalid("required tool data-engineer/csv_reconcile.py (G13) is not present")
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # never leave __pycache__ in the data-engineer folder
    try:
        spec = importlib.util.spec_from_file_location(name, str(G13))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        sys.dont_write_bytecode = old
    return mod


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Invalid(f"duplicate key {k!r} in the package; ambiguous")
        out[k] = v
    return out


def _bad_const(name):
    raise Invalid(f"non-finite number {name} in the package")


def _num(v: Any, where: str, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo < v < hi):
        raise Invalid(f"{where}: expected a number between {lo} and {hi}")
    return float(v)


def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def z_quantile(p: float) -> float:
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def chi2_sf_df1(x: float) -> float:
    return math.erfc(math.sqrt(x / 2.0)) if x > 0 else 1.0


def chi2_sf(x: float, df: int) -> float:
    """Upper tail of the chi-square distribution: the regularized upper incomplete gamma Q(df/2, x/2)."""
    if x <= 0:
        return 1.0
    a, z = df / 2.0, x / 2.0
    lg = math.lgamma(a)
    if z < a + 1:  # series for P, then Q = 1 - P
        term = total = 1.0 / a
        ap = a
        for _ in range(1000):
            ap += 1
            term *= z / ap
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(-z + a * math.log(z) - lg))
    b, c, d = z + 1 - a, 1e300, 1 / (z + 1 - a)  # continued fraction for Q (Lentz)
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return min(1.0, math.exp(-z + a * math.log(z) - lg) * h)


def binom_two_sided(m: int, q: float) -> List[float]:
    """Exact two-sided binomial p-values for k = 0..m treatment units out of m at planned share q:
    the total probability of counts no more likely than k (the small-window chi-square overstates
    significance)."""
    lq, l1q = math.log(q), math.log(1 - q)
    lm = math.lgamma(m + 1)
    pmf = [math.exp(lm - math.lgamma(k + 1) - math.lgamma(m - k + 1) + k * lq + (m - k) * l1q) for k in range(m + 1)]
    srt = sorted(pmf)
    cum, acc = [], 0.0
    for x in srt:
        acc += x
        cum.append(acc)
    return [min(1.0, cum[bisect.bisect_right(srt, x * (1 + 1e-9)) - 1]) for x in pmf]


def allocation_scan(units: Dict[str, Dict[str, Any]], arms: List[str], split: List[float]) -> Optional[Dict[str, Any]]:
    """Sliding-window sample-ratio scan in assignment order, independent of any calendar blocks.

    Units are ordered by (assigned_at, unit_id). Windows of 20, 40, 80, ... units (up to half the cohort)
    slide by an eighth of their length, plus one window ending at the last unit for each length; each is
    tested against the planned split (exact binomial up to 1,280 units, chi-square with 1 df above) and the smallest p-value must clear
    SCAN_ALPHA / windows tested (Bonferroni, conservative for overlapping windows)."""
    c, t = arms
    order = sorted(units.items(), key=lambda kv: (kv[1]["at"], kv[0]))
    N = len(order)
    if N < 2 * SCAN_MIN:
        return None
    pre = [0]
    for _, v in order:
        pre.append(pre[-1] + (v["arm"] == t))
    q = split[1]
    worst, K, sizes, m = None, 0, [], SCAN_MIN
    while m <= N // 2:
        sizes.append(m)
        step = max(1, m // 8)
        starts = list(range(0, N - m + 1, step))
        if starts[-1] != N - m:
            starts.append(N - m)
        exact = binom_two_sided(m, q) if m <= SCAN_EXACT_MAX else None
        for i in starts:
            k = pre[i + m] - pre[i]
            pv = exact[k] if exact is not None else chi2_sf_df1((k - m * q) ** 2 / (m * q * (1 - q)))
            K += 1
            if worst is None or pv < worst[0]:
                worst = (pv, i, m, k)
        m *= 2
    pv, i, m, k = worst
    return {"windows_tested": K, "window_units": sizes, "family_alpha": SCAN_ALPHA,
            "threshold": "%.3e" % (SCAN_ALPHA / K),
            "worst": {"units": m, "first_assigned": order[i][1]["at"].isoformat(),
                      "last_assigned": order[i + m - 1][1]["at"].isoformat(),
                      "arm_counts": [m - k, k], "p_value": "%.3e" % pv},
            "mismatch": pv < SCAN_ALPHA / K}


def bucket_arm(salt: str, unit_id: str, arms: List[str], split: Tuple[float, float]) -> str:
    """The declared assignment rule: sha256 of salt:unit_id, first 15 hex digits as a fraction of 16**15;
    below the control share goes to control."""
    b = int(hashlib.sha256((salt + ":" + unit_id).encode("utf-8")).hexdigest()[:15], 16) / 16 ** 15
    return arms[0] if b < split[0] else arms[1]


def r6(x: Optional[float]) -> Optional[str]:
    return None if x is None else f"{x:.6f}"


def load(path: str) -> Dict[str, Any]:
    g = _load_g13()
    p = Path(path)
    try:
        raw = p.read_bytes()
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_bad_const)
    except OSError as exc:
        raise Invalid(f"cannot read package: {exc.strerror}") from None
    except Invalid:
        raise
    except (UnicodeDecodeError, ValueError):
        raise Invalid(f"{p.name}: not valid UTF-8 JSON") from None
    if not isinstance(doc, dict) or doc.get("schema") != PACKAGE_SCHEMA:
        raise Invalid(f"schema must be {PACKAGE_SCHEMA!r}")
    known = {"schema", "experiment", "unit", "assignment", "arms", "planned_split", "timezone", "cohort", "as_of",
             "outcome", "min_sample_per_arm", "alpha", "assignments", "events", "randomization"}
    extra = sorted(set(doc) - known)
    if extra:
        raise Invalid(f"unknown field(s) {extra}; refusing to ignore evidence")
    if doc.get("unit") != "unit_id":
        raise Invalid('unit must be "unit_id": the assignments and events files carry one unit_id per row')
    if doc.get("assignment") not in ("randomized", "observational"):
        raise Invalid('assignment must be "randomized" or "observational"')
    arms = doc.get("arms")
    if not (isinstance(arms, list) and len(arms) == 2 and all(isinstance(a, str) and a for a in arms) and arms[0] != arms[1]):
        raise Invalid("arms: exactly two distinct names, control first")
    split = doc.get("planned_split", [0.5, 0.5])
    if not (isinstance(split, list) and len(split) == 2):
        raise Invalid("planned_split: two shares")
    s0, s1 = _num(split[0], "planned_split[0]", 0, 1), _num(split[1], "planned_split[1]", 0, 1)
    if abs(s0 + s1 - 1) > 1e-9:
        raise Invalid("planned_split must add up to 1")
    tzname = doc.get("timezone", "UTC")
    try:
        tz = g.ZoneInfo(tzname) if isinstance(tzname, str) else None
    except Exception:
        tz = None
    if tz is None:
        raise Invalid(f"timezone {tzname!r} is not a known IANA zone")
    c, o = doc.get("cohort"), doc.get("outcome")
    if not isinstance(c, dict) or not isinstance(o, dict):
        raise Invalid("cohort {start, end} and outcome {event, horizon_days} are required")
    try:
        cs, ce = g._time_const(c.get("start"), "cohort.start", tz), g._time_const(c.get("end"), "cohort.end", tz)
        as_of = g._time_const(doc.get("as_of"), "as_of", tz)
    except g.Invalid as exc:
        raise Invalid(str(exc)) from None
    if ce <= cs:
        raise Invalid("cohort.end must be after cohort.start")
    hz = o.get("horizon_days")
    if isinstance(hz, bool) or not isinstance(hz, int) or not 1 <= hz <= 365 or not isinstance(o.get("event"), str):
        raise Invalid("outcome: event name and horizon_days (1-365)")
    ms = doc.get("min_sample_per_arm")
    if isinstance(ms, bool) or not isinstance(ms, int) or ms < 1:
        raise Invalid("min_sample_per_arm: a whole number of units, at least 1")
    alpha = _num(doc.get("alpha", 0.05), "alpha", 0, 0.5)
    rz = doc.get("randomization")
    if rz is not None:
        if doc["assignment"] != "randomized":
            raise Invalid("randomization: only for assignment randomized")
        if not (isinstance(rz, dict) and set(rz) - {"expected_units"} == {"method", "salt"}
                and rz.get("method") == "sha256_bucket" and isinstance(rz.get("salt"), str) and rz["salt"].strip()):
            raise Invalid('randomization: {"method": "sha256_bucket", "salt": "<non-empty salt>", "expected_units"?: N}')
        eu = rz.get("expected_units")
        if "expected_units" in rz and (isinstance(eu, bool) or not isinstance(eu, int) or eu < 1):
            raise Invalid("randomization.expected_units: the assignment system's count of units first assigned in the cohort window, a whole number of at least 1")
    base = p.resolve().parent
    tables = {}
    for kind, cols in (("assignments", ASSIGN_COLS), ("events", EVENT_COLS)):
        spec = doc.get(kind)
        if not isinstance(spec, dict) or set(spec) - {"file", "header_aliases", "delimiter"}:
            raise Invalid(f"{kind}: give file and optionally header_aliases, delimiter")
        try:
            tables[kind] = g._table(dict(spec, columns=cols), kind, base)
        except g.Invalid as exc:
            raise Invalid(str(exc)) from None
    return {"g": g, "tz": tz, "doc": doc, "arms": arms, "split": (s0, s1), "cs": cs, "ce": ce, "as_of": as_of,
            "event": o["event"], "horizon": dt.timedelta(days=hz), "hz": hz, "min": ms, "alpha": alpha,
            "randomized": doc["assignment"] == "randomized", "randomization": rz, "tables": tables, "sha": hashlib.sha256(raw).hexdigest()}


def analyse(path: str) -> Dict[str, Any]:
    P = load(path)
    g = P["g"]
    try:
        arows, arej, af = g.read_table(P["tables"]["assignments"], P["tz"])
        erows, erej, ef = g.read_table(P["tables"]["events"], P["tz"])
    except g.Invalid as exc:
        raise Invalid(str(exc)) from None
    excl = {"rejected_rows": len(arej) + len(erej), "missing_values": 0, "unknown_arm": 0, "multiple_arms": [],
            "outside_cohort": 0, "immature": 0, "events_unassigned_units": 0, "events_before_assignment": 0,
            "events_after_horizon": 0, "repeat_assignment_rows": 0}
    seen: Dict[str, Dict[str, Any]] = {}
    arms_of: Dict[str, set] = {}
    for r in arows:
        if r["unit_id"] is None or r["arm"] is None or r["assigned_at"] is None:
            excl["missing_values"] += 1
            continue
        if r["arm"] not in P["arms"]:
            excl["unknown_arm"] += 1
            continue
        arms_of.setdefault(r["unit_id"], set()).add(r["arm"])
        prev = seen.get(r["unit_id"])
        if prev is None or r["assigned_at"] < prev["assigned_at"]:
            if prev is not None:
                excl["repeat_assignment_rows"] += 1
            seen[r["unit_id"]] = r
        else:
            excl["repeat_assignment_rows"] += 1
    units: Dict[str, Dict[str, Any]] = {}
    check = None
    if P["randomization"] is not None:
        mism = []
        checked = 0
        in_window = 0
        for u, r in seen.items():
            if not (P["cs"] <= r["assigned_at"] < P["ce"]):
                continue
            in_window += 1
            if len(arms_of[u]) > 1:
                continue
            checked += 1
            if bucket_arm(P["randomization"]["salt"], u, P["arms"], P["split"]) != r["arm"]:
                mism.append(u)
        eu = P["randomization"].get("expected_units")
        check = {"contract": "sha256_bucket", "units_checked": checked, "mismatched": len(mism),
                 "examples": sorted(mism)[:5], "expected_units": eu, "units_in_log": in_window,
                 "missing_units_checked": eu is not None,
                 "verified": checked > 0 and not mism and (eu is None or eu == in_window)}
    else:
        check = {"contract": None, "units_checked": 0, "mismatched": None, "examples": [], "expected_units": None,
                 "units_in_log": None, "missing_units_checked": False, "verified": False}
    for u, r in seen.items():
        if len(arms_of[u]) > 1:
            excl["multiple_arms"].append(u)
            continue
        if not (P["cs"] <= r["assigned_at"] < P["ce"]):
            excl["outside_cohort"] += 1
            continue
        if r["assigned_at"] + P["horizon"] > P["as_of"]:
            excl["immature"] += 1
            continue
        units[u] = {"arm": r["arm"], "at": r["assigned_at"], "converted": False}
    contaminated = set(excl["multiple_arms"])
    for e in erows:
        u = e.get("unit_id")
        if u is None or e.get("occurred_at") is None or e.get("event") != P["event"]:
            continue
        if u not in seen:
            excl["events_unassigned_units"] += 1
            continue
        if u in contaminated or u not in units:
            continue
        t0 = units[u]["at"]
        if e["occurred_at"] < t0:
            excl["events_before_assignment"] += 1
        elif e["occurred_at"] >= t0 + P["horizon"]:
            excl["events_after_horizon"] += 1
        else:
            units[u]["converted"] = True
    excl["multiple_arms"] = sorted(excl["multiple_arms"])
    c, t = P["arms"]
    n = {a: sum(1 for v in units.values() if v["arm"] == a) for a in P["arms"]}
    x = {a: sum(1 for v in units.values() if v["arm"] == a and v["converted"]) for a in P["arms"]}
    total = n[c] + n[t]
    arms_out = {a: {"units": n[a], "converted": x[a], "rate": r6(x[a] / n[a]) if n[a] else None,
                    "rate_exact": f"{x[a]}/{n[a]}" if n[a] else None} for a in P["arms"]}
    srm = None
    if total:
        e0, e1 = total * P["split"][0], total * P["split"][1]
        chi = (n[c] - e0) ** 2 / e0 + (n[t] - e1) ** 2 / e1
        srm = {"chi_square": r6(chi), "p_value": r6(chi2_sf_df1(chi)), "mismatch": chi2_sf_df1(chi) < SRM_P,
               "planned_split": list(P["split"])}
    drift = None
    if total and P["randomized"]:
        weeks: Dict[int, Dict[str, int]] = {}
        for v in units.values():
            wk = int((v["at"] - P["cs"]).total_seconds() // (7 * 86400))
            weeks.setdefault(wk, {a: 0 for a in P["arms"]})[v["arm"]] += 1
        tested = [(wk, w) for wk, w in sorted(weeks.items()) if w[c] + w[t] >= 20]
        worst = None
        for wk, w in tested:
            m = w[c] + w[t]
            e0, e1 = m * P["split"][0], m * P["split"][1]
            pw = chi2_sf_df1((w[c] - e0) ** 2 / e0 + (w[t] - e1) ** 2 / e1)
            if worst is None or pw < worst[1]:
                worst = (wk, pw, w[c], w[t])
        if worst is not None:
            drift = {"weeks_tested": len(tested), "worst_week": worst[0], "worst_week_units": [worst[2], worst[3]],
                     "p_value": r6(worst[1]), "mismatch": worst[1] < SRM_P / len(tested)}
            # a split that changes between weeks, even when every week stays near the plan: arm x week
            # independence (chi-square, weeks - 1 degrees of freedom) over the same weeks
            if len(tested) > 1:
                mt = sum(w[c] + w[t] for _, w in tested)
                share = sum(w[t] for _, w in tested) / mt
                hom = 0.0
                if 0 < share < 1:
                    for _, w in tested:
                        m = w[c] + w[t]
                        hom += (w[c] - m * (1 - share)) ** 2 / (m * (1 - share)) + (w[t] - m * share) ** 2 / (m * share)
                ph = chi2_sf(hom, len(tested) - 1)
                drift["homogeneity_p_value"] = r6(ph)
                drift["mismatch"] = drift["mismatch"] or ph < SRM_P
    scan = allocation_scan(units, P["arms"], P["split"]) if total and P["randomized"] else None
    effect = None
    trace: List[str] = []
    if n[c] and n[t]:
        p1, p2 = x[c] / n[c], x[t] / n[t]
        diff = p2 - p1
        se = math.sqrt(p1 * (1 - p1) / n[c] + p2 * (1 - p2) / n[t])
        z = z_quantile(1 - P["alpha"] / 2)
        pool = (x[c] + x[t]) / total
        se0 = math.sqrt(pool * (1 - pool) * (1 / n[c] + 1 / n[t]))
        pv = 2 * (1 - phi(abs(diff) / se0)) if se0 > 0 else 1.0
        effect = {"difference": r6(diff), "ci_low": r6(diff - z * se), "ci_high": r6(diff + z * se),
                  "confidence": r6(1 - P["alpha"]), "p_value": r6(pv), "_lo": diff - z * se, "_hi": diff + z * se}
    if total == 0 or min(n.values()) < P["min"]:
        outcome = "insufficient_information"
        trace.append(f"mature cohort units per arm {n[c]}/{n[t]}, minimum {P['min']}: not enough to read")
    elif P["randomized"] and check["contract"] and check["mismatched"] == 0 and check["units_checked"] > 0 and not check["verified"]:
        outcome = "invalid_experiment"
        trace.append(f"the assignment log holds {check['units_in_log']} cohort units but the declared randomization assigned {check['expected_units']}: units are {'missing from' if check['units_in_log'] < check['expected_units'] else 'added to'} the log, so the arms cannot be compared; no effect is read")
    elif P["randomized"] and check["contract"] and not check["verified"]:
        outcome = "invalid_experiment"
        trace.append(f"assignment does not follow the declared randomization: {check['mismatched']} of {check['units_checked']} cohort units are in an arm the sha256_bucket rule does not give them (e.g. {', '.join(check['examples'])}); no effect is read")
    elif P["randomized"] and srm["mismatch"]:
        outcome = "invalid_experiment"
        trace.append(f"sample ratio mismatch: {n[c]}/{n[t]} against planned {P['split'][0]}/{P['split'][1]} (p {srm['p_value']}); assignment is broken, no effect is read")
    elif P["randomized"] and drift is not None and drift["mismatch"]:
        outcome = "invalid_experiment"
        trace.append(f"allocation drifted over the cohort: week {drift['worst_week']} has {drift['worst_week_units'][0]}/{drift['worst_week_units'][1]} against planned {P['split'][0]}/{P['split'][1]} (p {drift['p_value']}, Bonferroni over {drift['weeks_tested']} weeks; split homogeneity across weeks p {drift.get('homogeneity_p_value')}); the pooled comparison mixes periods with different base rates, no effect is read")
    elif P["randomized"] and scan is not None and scan["mismatch"]:
        outcome = "invalid_experiment"
        w = scan["worst"]
        trace.append(f"allocation changed within the cohort: the {w['units']} units assigned {w['first_assigned']} to {w['last_assigned']} split {w['arm_counts'][0]}/{w['arm_counts'][1]} against planned {P['split'][0]}/{P['split'][1]} (p {w['p_value']}, below {scan['threshold']} = {SCAN_ALPHA} over {scan['windows_tested']} sliding windows); no effect is read")
    elif P["randomized"] and len(contaminated) > 0.05 * (total + len(contaminated)):
        outcome = "invalid_experiment"
        trace.append(f"{len(contaminated)} units were exposed to both arms (over 5% of the cohort); no effect is read")
    elif effect["_lo"] <= 0 <= effect["_hi"]:
        outcome = "no_detectable_difference"
        trace.append(f"{r6(1 - P['alpha'])} interval [{effect['ci_low']}, {effect['ci_high']}] includes 0: no difference detected at this sample size; this is not evidence of no effect")
    elif P["randomized"] and not check["verified"]:
        outcome = "association_only"
        trace.append(f"interval [{effect['ci_low']}, {effect['ci_high']}] excludes 0, but assignment is declared randomized without a randomization contract the tool can verify per unit; the allocation tests are guards with limited power (an all-variant burst interleaved with a day's traffic can pass), so this is an association, not a causal effect. Add randomization {{method: sha256_bucket, salt}} to verify every unit's arm")
    elif P["randomized"]:
        outcome = "difference_detected"
        trace.append(f"randomized assignment verified for all {check['units_checked']} cohort units in the log" + (f" (the log holds all {check['expected_units']} the assignment system declared)" if check["missing_units_checked"] else " (units missing from the log cannot be detected without randomization.expected_units; differential loss is guarded only by SRM)") + f", interval [{effect['ci_low']}, {effect['ci_high']}] excludes 0: {t} differs from {c} on {P['event']} within {P['hz']} days in this experiment")
    else:
        outcome = "association_only"
        trace.append(f"interval [{effect['ci_low']}, {effect['ci_high']}] excludes 0 but assignment was observational: an association, not a causal effect")
    if effect:
        effect = {k: v for k, v in effect.items() if not k.startswith("_")}
    if outcome == "difference_detected" and not check["missing_units_checked"]:
        trace.append("Observed difference only: the complete assignment population was not checked; no causal claim is allowed without an independent randomization.expected_units count.")
    claims_allowed = {"causal": outcome == "difference_detected" and check["missing_units_checked"],
                      "significance": outcome in ("difference_detected", "association_only")}
    return {"schema": REPORT_SCHEMA, "package_sha256": P["sha"], "experiment": P["doc"].get("experiment"),
            "unit_of_analysis": "unit_id", "assignment": P["doc"]["assignment"],
            "cohort": {"start": P["cs"].isoformat(), "end": P["ce"].isoformat(), "as_of": P["as_of"].isoformat(),
                       "outcome_event": P["event"], "horizon_days": P["hz"]},
            "arms": arms_out, "srm": srm, "allocation_by_week": drift, "allocation_scan": scan, "assignment_check": check, "effect": effect, "outcome": outcome, "claims_allowed": claims_allowed,
            "trace": trace, "exclusions": excl,
            "inputs": [{"file": f["file"], "sha256": f["sha256"], "data_rows": f["data_rows"]} for f in (af, ef)],
            "read_only": "local files only; nothing was changed or sent"}


def render(r: Dict[str, Any]) -> str:
    lines = [f"experiment {r['experiment']}: {r['outcome']}"]
    for a, v in r["arms"].items():
        lines.append(f"  {a}: {v['converted']}/{v['units']} units converted (rate {v['rate']})")
    if r["effect"]:
        e = r["effect"]
        lines.append(f"  difference {e['difference']} [{e['ci_low']}, {e['ci_high']}] at {e['confidence']}, p {e['p_value']}")
    lines += [f"  {t}" for t in r["trace"]]
    ex = r["exclusions"]
    lines.append(f"  excluded: immature {ex['immature']}, outside cohort {ex['outside_cohort']}, both arms {len(ex['multiple_arms'])}, "
                 f"pre-assignment events {ex['events_before_assignment']}, post-horizon events {ex['events_after_horizon']}")
    return "\n".join(lines) + "\n"


def _write_atomic(out: Path, data: bytes) -> None:
    out = out.resolve()
    fd, tmp = tempfile.mkstemp(prefix=".readout-", dir=str(out.parent))
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="experiment_readout.py", description="Experiment readout with fixed cohorts and leakage checks.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("analyse")
    a_.add_argument("package")
    a_.add_argument("--json", action="store_true")
    a_.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        rep = analyse(a.package)
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
