#!/usr/bin/env python3
"""M15 r2 drift oracle (Grok self-validation, written by Grok, black box).
The drift fix under test came from Grok's own M15 patch (plus the builder's homogeneity test); this oracle was
written after reading only the r2 doc text, not the r2 code. Expected outcomes are derived here from the doc rule:
weeks are 7-day blocks from cohort.start; weeks with at least 20 units are tested; a week's chi-square against the
planned split below 0.001 / weeks tested, or an arm x week chi-square (weeks - 1 df) below 0.001, is
invalid_experiment. Chi-square tails use closed forms (even and odd df), independent of the tool's gamma code.
Usage: PY m15r2_drift.py REPO [--tool TOOL] OUT.json. Core rows (D*) score; OBS rows record only."""
import csv, io, json, math, random, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from statistics import NormalDist
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/data/data-scientist/experiment_readout.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
TOP = Path(tempfile.mkdtemp(prefix="m15r2top-", dir="/tmp")).resolve(); rows = []
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
CS = datetime(2026, 3, 4, 6, tzinfo=timezone.utc)  # a Wednesday, 06:00, so blocks are not calendar weeks
H = 7
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
def sf(x, k):
    """chi-square upper tail, closed forms."""
    if x <= 0: return 1.0
    if k % 2 == 0:
        s, t = 0.0, 1.0
        for i in range(k // 2):
            if i: t *= (x / 2) / i
            s += t
        return min(1.0, math.exp(-x / 2) * s)
    q = math.erfc(math.sqrt(x / 2)); t = math.sqrt(2 * x / math.pi) * math.exp(-x / 2); s = 0.0; term = 1.0
    for i in range(1, (k - 1) // 2 + 1):
        term = (1.0 if i == 1 else term * x / (2 * i - 1)); s += term
    return min(1.0, q + t * s)
def expected(units, split, days):
    """units: list of (arm, assigned_at, converted). Returns doc-rule outcome and the drift numbers."""
    n = {"base": 0, "variant": 0}; x = {"base": 0, "variant": 0}; wk = {}
    for arm, t, cv in units:
        n[arm] += 1; x[arm] += cv; k = int((t - CS).total_seconds() // (7 * 86400)); wk.setdefault(k, {"base": 0, "variant": 0})[arm] += 1
    tot = n["base"] + n["variant"]; e0, e1 = tot * split[0], tot * split[1]; srm_p = sf((n["base"] - e0) ** 2 / e0 + (n["variant"] - e1) ** 2 / e1, 1)
    tested = [(k, w) for k, w in sorted(wk.items()) if w["base"] + w["variant"] >= 20]
    pw = []
    for k, w in tested:
        m = w["base"] + w["variant"]; pw.append(sf((w["base"] - m * split[0]) ** 2 / (m * split[0]) + (w["variant"] - m * split[1]) ** 2 / (m * split[1]), 1))
    worst = min(pw) if pw else None; hom = None
    if len(tested) > 1:
        mt = sum(w["base"] + w["variant"] for _, w in tested); s = sum(w["variant"] for _, w in tested) / mt; h = 0.0
        if 0 < s < 1:
            for _, w in tested:
                m = w["base"] + w["variant"]; h += (w["base"] - m * (1 - s)) ** 2 / (m * (1 - s)) + (w["variant"] - m * s) ** 2 / (m * s)
        hom = sf(h, len(tested) - 1)
    drift = (worst is not None and worst < 0.001 / len(tested)) or (hom is not None and hom < 0.001)
    pb, pv = x["base"] / n["base"], x["variant"] / n["variant"]; d = pv - pb; se = math.sqrt(pb * (1 - pb) / n["base"] + pv * (1 - pv) / n["variant"]); z = NormalDist().inv_cdf(0.975)
    if min(n.values()) < 100: out = "insufficient_information"
    elif srm_p < 0.001 or drift: out = "invalid_experiment"
    elif d - z * se <= 0 <= d + z * se: out = "no_detectable_difference"
    else: out = "difference_detected"
    return {"outcome": out, "weeks_tested": len(tested), "worst_p": worst, "hom_p": hom, "srm_p": srm_p, "diff": d}
def build(name, units, split=(0.5, 0.5), days=28):
    d = TOP / name; d.mkdir(parents=True); A = io.StringIO(); E = io.StringIO(); wa = csv.writer(A, lineterminator="\n"); we = csv.writer(E, lineterminator="\n")
    wa.writerow(["unit_id", "arm", "assigned_at"]); we.writerow(["unit_id", "event", "occurred_at", "session_id"])
    for i, (arm, t, cv) in enumerate(units):
        u = "u%06d" % i; wa.writerow([u, arm, iso(t)])
        if cv: we.writerow([u, "signup", iso(t + timedelta(hours=5)), "s1"])
    (d / "a.csv").write_text(A.getvalue()); (d / "e.csv").write_text(E.getvalue())
    end = CS + timedelta(days=days)
    p = {"schema": "solaris.experiment/1", "experiment": name, "unit": "unit_id", "assignment": "randomized", "arms": ["base", "variant"], "planned_split": list(split),
         "timezone": "UTC", "cohort": {"start": iso(CS), "end": iso(end)}, "as_of": iso(end + timedelta(days=H + 1)), "outcome": {"event": "signup", "horizon_days": H},
         "min_sample_per_arm": 100, "alpha": 0.05, "assignments": {"file": "a.csv"}, "events": {"file": "e.csv"}}
    (d / "p.json").write_text(json.dumps(p))
    cp = subprocess.run([PY, str(TOOL), "analyse", str(d / "p.json"), "--json"], cwd=d, env=ENV, capture_output=True, text=True, timeout=300); shutil.rmtree(d)
    try: return cp.returncode, json.loads(cp.stdout)
    except Exception: return cp.returncode, {}
def gen(r, days, share_fn, rate_fn, per_day, eff=0.0):
    """share_fn(day) = variant share; rate_fn(day) = base conversion; eff = true variant lift."""
    us = []
    for dd in range(days):
        for _ in range(per_day(dd) if callable(per_day) else per_day):
            t = CS + timedelta(days=dd, minutes=r.randint(0, 1439)); arm = "variant" if r.random() < share_fn(dd) else "base"
            p = rate_fn(dd) + (eff if arm == "variant" else 0); us.append((arm, t, 1 if r.random() < p else 0))
    return us
def check(name, units, split=(0.5, 0.5), days=28):
    rc, rep = build(name, units, split, days); e = expected(units, split, days); ab = rep.get("allocation_by_week") or {}
    pmatch = True
    for mine, theirs in ((e["worst_p"], ab.get("p_value")), (e["hom_p"], ab.get("homogeneity_p_value"))):
        if mine is None: pmatch &= theirs is None; continue
        pmatch &= theirs is not None and abs(float(theirs) - round(mine, 6)) <= 1.5e-6
    ok = rc == 0 and rep.get("outcome") == e["outcome"] and (ab.get("weeks_tested") == e["weeks_tested"] if ab else e["weeks_tested"] == 0) and pmatch
    claims = rep.get("claims_allowed")
    return ok, {"rc": rc, "tool": rep.get("outcome"), "doc_rule": e["outcome"], "weeks": (ab.get("weeks_tested"), e["weeks_tested"]), "tool_p": (ab.get("p_value"), ab.get("homogeneity_p_value")),
                "my_p": (None if e["worst_p"] is None else round(e["worst_p"], 6), None if e["hom_p"] is None else round(e["hom_p"], 6)), "srm_p": round(e["srm_p"], 6), "diff": round(e["diff"], 4), "claims": claims}
def d01():  # my M15 ramps, regression: invalid
    res = {}
    for nm, s1, s2 in (("x13", 0.8, 0.2), ("x13b", 0.2, 0.8)):
        r = random.Random(1); us = gen(r, 28, lambda d: s1 if d < 7 else s2, lambda d: 0.5 if d < 7 else 0.1, lambda d: 72 if d < 7 else 26, eff=0.05)
        ok, det = check("d01" + nm, us); res[nm] = (ok, det)
    row("D01_m15_ramps_still_invalid", all(o and d["tool"] == "invalid_experiment" for o, d in res.values()), {k: d for k, (o, d) in res.items()})
def d02():  # gradual ramps of several strengths over 8 blocks: tool equals the doc rule and its p-values equal mine
    res = {}; ok_all = True
    for k, (lo, hi) in enumerate(((0.5, 0.5), (0.47, 0.53), (0.44, 0.56), (0.40, 0.60), (0.30, 0.70))):
        r = random.Random(10 + k); us = gen(r, 56, lambda d: lo + (hi - lo) * d / 55, lambda d: 0.30 - 0.2 * d / 55, 40, eff=0.0)
        ok, det = check("d02-%d" % k, us, days=56); res["%.2f->%.2f" % (lo, hi)] = det; ok_all &= ok
    row("D02_gradual_ramps_follow_doc_rule", ok_all, res)
def d03():  # single bad day: one day sends every unit to variant on a high-converting day; doc rule vs tool
    res = {}; ok_all = True
    for k, vol in enumerate((60, 120, 300)):
        r = random.Random(20 + k); us = gen(r, 28, lambda d: 1.0 if d == 9 else 0.5, lambda d: 0.9 if d == 9 else 0.1, lambda d: vol if d == 9 else 60)
        ok, det = check("d03-%d" % vol, us); res["bad_day_%d_units" % vol] = det; ok_all &= ok
    row("D03_single_bad_day_follows_doc_rule", ok_all, res)
def d04():  # many short weeks: 20 blocks of low traffic, some below 20 units (untested), plus a ramp in one block
    res = {}; ok_all = True
    for k, per in enumerate((2, 3, 6)):
        r = random.Random(30 + k); us = gen(r, 140, lambda d: 0.9 if 70 <= d < 77 else 0.5, lambda d: 0.2, per)
        ok, det = check("d04-%d" % per, us, days=140); res["%d_per_day" % per] = det; ok_all &= ok
    row("D04_many_short_weeks_follow_doc_rule", ok_all, res)
def d05():  # 30/70 plan with a drift toward 50/50 halfway; block boundaries from a Wednesday 06:00 start
    r = random.Random(40); us = gen(r, 28, lambda d: 0.7 if d < 14 else 0.5, lambda d: 0.2, 50)
    ok, det = check("d05", us, split=(0.3, 0.7)); row("D05_unequal_plan_drift", ok, det)
def d06():  # random shapes property test: 30 experiments, random step, oscillation, spike or none; tool equals doc rule on every one
    r = random.Random(50); bad = []; n = 0
    for k in range(30):
        shape = r.choice(["none", "step", "osc", "spike", "gradual"]); days = r.choice([21, 28, 35, 49]); per = r.choice([8, 15, 30])
        a0 = r.choice([0.5, 0.45]); amp = r.choice([0.03, 0.08, 0.15]); sd = r.randint(0, days - 1)
        fn = {"none": lambda d: 0.5, "step": lambda d: a0 if d < sd else 1 - a0, "osc": lambda d: 0.5 + amp * (1 if (d // 7) % 2 else -1),
              "spike": lambda d: 0.95 if d == sd else 0.5, "gradual": lambda d: 0.5 - amp + 2 * amp * d / days}[shape]
        us = gen(random.Random(500 + k), days, fn, lambda d: 0.25, per); ok, det = check("d06-%d" % k, us, days=days); n += 1
        if not ok: bad.append(dict(det, shape=shape, days=days, per=per))
    row("D06_random_shapes_property", not bad, {"run": n, "mismatches": bad[:5]})
def o07():  # OBS: false invalidation of healthy experiments (power loss from the extra tests), 200 A/B with a true +0.04 lift
    r = random.Random(60); inv = det = 0; inv_srm = 0; n = 200
    for k in range(n):
        us = gen(random.Random(600 + k), 28, lambda d: 0.5, lambda d: 0.2, 30, eff=0.04); rc, rep = build("o07-%d" % k, us)
        inv += rep.get("outcome") == "invalid_experiment"; det += rep.get("outcome") == "difference_detected"; inv_srm += bool((rep.get("srm") or {}).get("mismatch"))
    row("O07_healthy_invalidation_rate", True, {"experiments": n, "invalidated": inv, "of_which_pooled_srm": inv_srm, "difference_detected": det}, obs=True)
def o08():  # OBS: bias and claim on the single bad day; what the readout lets a PM repeat
    out = {}
    for vol in (40, 60, 90):
        us = gen(random.Random(70 + vol), 28, lambda d: 1.0 if d == 9 else 0.5, lambda d: 0.9 if d == 9 else 0.1, lambda d: vol if d == 9 else 60); rc, rep = build("o08-%d" % vol, us)
        out[vol] = {"outcome": rep.get("outcome"), "claims": rep.get("claims_allowed"), "effect": rep.get("effect"), "drift": rep.get("allocation_by_week"), "true_effect": 0.0}
    row("O08_bad_day_claim", True, out, obs=True)
def o09():  # OBS: detection power of a ramp vs the number of tested weeks (Bonferroni gets stricter with more weeks)
    out = {}
    for days in (28, 91, 182):
        hits = 0
        for k in range(20):
            us = gen(random.Random(900 + k + days), days, lambda d, D=days: 0.65 if D // 2 <= d < D // 2 + 7 else 0.5, lambda d: 0.2, 20); rc, rep = build("o09", us, days=days)
            hits += rep.get("outcome") == "invalid_experiment"
        out["%d_days_one_block_at_0.65" % days] = "%d/20 invalidated" % hits
    row("O09_ramp_detection_vs_weeks", True, out, obs=True)
import os
ALL = (("D01", d01), ("D02", d02), ("D03", d03), ("D04", d04), ("D05", d05), ("D06", d06), ("O07", o07), ("O08", o08), ("O09", o09))
if os.environ.get("M15R2_FAST"): ALL = tuple(x for x in ALL if x[0] not in ("O07", "O09"))  # teeth runs skip the two slow statistical OBS rows
for rid, fn in ALL:
    try: fn()
    except Exception as e: row(rid + "_crash", False, "harness or tool crash: %r" % (e,))
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:1500])
print("M15R2 DRIFT %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
