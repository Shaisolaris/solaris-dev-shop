#!/usr/bin/env python3
"""M15 r3 scan oracle (Grok self-validation, written by Grok, black box). Written from the r3 doc text (rule 5) and
the M15 r2 residuals; the r3 fix is builder code. Expected outcomes come from my own implementation of the doc rule:
pooled SRM p < 0.001; 7-day blocks from cohort.start with >= 20 units, worst block p < 0.001 / blocks tested;
arm x block homogeneity p < 0.001; plus the sliding-window scan: units sorted by (assigned_at, unit_id), window
sizes 20, 40, 80, ... up to half the cohort, starts every max(1, size // 8) units plus one window ending at the
last unit, exact two-sided binomial p (sum of outcomes no more likely than the observed one) against the planned
split, chi-square 1 df above 1,280 units; invalid when min p < 0.002 / windows tested.
Usage: PY m15r3_scan.py REPO [--tool TOOL] OUT.json. Core rows (S*) score; OBS rows record only.
Authoring fix before scoring (disclosed): S05 first tested the claims dict for emptiness instead of claims.causal.
Set M15R3_FAST=1 to skip the slow null-simulation rows (teeth runs)."""
import csv, io, json, math, os, random, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from statistics import NormalDist
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/data/data-scientist/experiment_readout.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; TOP = Path(tempfile.mkdtemp(prefix="m15r3top-", dir="/tmp")).resolve(); rows = []
ENV = {"PATH": "/usr/bin:/bin", "HOME": str(TOP), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
def row(rid, ok, detail, obs=False): rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
CS = datetime(2026, 3, 4, 6, tzinfo=timezone.utc); H = 7
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
def sf(x, k):
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
_PV = {}
def binom_p(n, k, p):
    """exact two-sided binomial p (minlike), cached per (n, p)."""
    key = (n, p)
    if key not in _PV:
        lp = [math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1) + j * math.log(p) + (n - j) * math.log(1 - p) for j in range(n + 1)]
        pm = [math.exp(v) for v in lp]; order = sorted(range(n + 1), key=lambda j: pm[j]); pv = [0.0] * (n + 1); acc = 0.0; i = 0
        while i <= n:
            j = i; grp = 0.0
            while j <= n and pm[order[j]] <= pm[order[i]] * (1 + 1e-7): grp += pm[order[j]]; j += 1
            acc += grp
            for t in range(i, j): pv[order[t]] = min(1.0, acc)
            i = j
        _PV[key] = pv
    return _PV[key][k]
def scan(units, split):
    """units: list of (uid, arm, t). Returns windows tested, min p, worst window size, mismatch."""
    order = sorted(units, key=lambda u: (u[2], u[0])); n = len(order); pre = [0]
    for _, arm, _ in order: pre.append(pre[-1] + (arm == "variant"))
    sizes = []; w = 20
    while w <= n // 2: sizes.append(w); w *= 2
    K = 0; best = (2.0, None)
    for w in sizes:
        st = list(range(0, n - w + 1, max(1, w // 8)))
        if st[-1] != n - w: st.append(n - w)
        for s in st:
            k = pre[s + w] - pre[s]; K += 1
            if w > 1280: e1 = w * split[1]; e0 = w - e1; pv = sf((w - k - e0) ** 2 / e0 + (k - e1) ** 2 / e1, 1)
            else: pv = binom_p(w, k, split[1])
            if pv < best[0]: best = (pv, w)
    if not K: return {"K": 0, "min_p": None, "w": None, "mismatch": False}
    return {"K": K, "min_p": best[0], "w": best[1], "mismatch": best[0] < 0.002 / K}
def expected(units, split, start):
    n = {"base": 0, "variant": 0}; x = {"base": 0, "variant": 0}; wk = {}
    for uid, arm, t, cv in units:
        n[arm] += 1; x[arm] += cv; k = int((t - start).total_seconds() // (7 * 86400)); wk.setdefault(k, {"base": 0, "variant": 0})[arm] += 1
    tot = n["base"] + n["variant"]; e0, e1 = tot * split[0], tot * split[1]; srm_p = sf((n["base"] - e0) ** 2 / e0 + (n["variant"] - e1) ** 2 / e1, 1)
    tested = [w for _, w in sorted(wk.items()) if w["base"] + w["variant"] >= 20]; pw = []
    for w in tested:
        m = w["base"] + w["variant"]; pw.append(sf((w["base"] - m * split[0]) ** 2 / (m * split[0]) + (w["variant"] - m * split[1]) ** 2 / (m * split[1]), 1))
    hom = None
    if len(tested) > 1:
        mt = sum(w["base"] + w["variant"] for w in tested); s = sum(w["variant"] for w in tested) / mt; h = 0.0
        if 0 < s < 1:
            for w in tested: m = w["base"] + w["variant"]; h += (w["base"] - m * (1 - s)) ** 2 / (m * (1 - s)) + (w["variant"] - m * s) ** 2 / (m * s)
        hom = sf(h, len(tested) - 1)
    block = (bool(pw) and min(pw) < 0.001 / len(tested)) or (hom is not None and hom < 0.001)
    sc = scan([(u, a_, t) for u, a_, t, _ in units], split)
    pb, pv = x["base"] / n["base"], x["variant"] / n["variant"]; d = pv - pb; se = math.sqrt(pb * (1 - pb) / n["base"] + pv * (1 - pv) / n["variant"]); z = NormalDist().inv_cdf(0.975)
    if min(n.values()) < 100: out = "insufficient_information"
    elif srm_p < 0.001 or block or sc["mismatch"]: out = "invalid_experiment"
    elif d - z * se <= 0 <= d + z * se: out = "no_detectable_difference"
    else: out = "difference_detected"
    return {"outcome": out, "srm_p": srm_p, "block": block, "scan": sc, "diff": d}
def build(name, units, split=(0.5, 0.5), days=28, start=CS):
    d = TOP / name; d.mkdir(parents=True); A = io.StringIO(); E = io.StringIO(); wa = csv.writer(A, lineterminator="\n"); we = csv.writer(E, lineterminator="\n")
    wa.writerow(["unit_id", "arm", "assigned_at"]); we.writerow(["unit_id", "event", "occurred_at", "session_id"])
    for uid, arm, t, cv in units:
        wa.writerow([uid, arm, iso(t)])
        if cv: we.writerow([uid, "signup", iso(t + timedelta(hours=5)), "s1"])
    (d / "a.csv").write_text(A.getvalue()); (d / "e.csv").write_text(E.getvalue()); end = CS + timedelta(days=days)
    p = {"schema": "solaris.experiment/1", "experiment": name, "unit": "unit_id", "assignment": "randomized", "arms": ["base", "variant"], "planned_split": list(split),
         "timezone": "UTC", "cohort": {"start": iso(start), "end": iso(end)}, "as_of": iso(end + timedelta(days=H + 1)), "outcome": {"event": "signup", "horizon_days": H},
         "min_sample_per_arm": 100, "alpha": 0.05, "assignments": {"file": "a.csv"}, "events": {"file": "e.csv"}}
    (d / "p.json").write_text(json.dumps(p))
    cp = subprocess.run([PY, str(TOOL), "analyse", str(d / "p.json"), "--json"], cwd=d, env=ENV, capture_output=True, text=True, timeout=300); shutil.rmtree(d)
    try: return cp.returncode, json.loads(cp.stdout)
    except Exception: return cp.returncode, {}
def gen(r, days, share_fn, rate_fn, per_day, eff=0.0, burst=None):
    """burst = (day, size, replace, minute0, span_minutes): size all-variant units at high conversion."""
    us = []; i = 0
    for dd in range(days):
        cnt = per_day(dd) if callable(per_day) else per_day
        if burst and burst[2] and dd == burst[0]: cnt = max(0, cnt - burst[1])
        for _ in range(cnt):
            t = CS + timedelta(days=dd, minutes=r.randint(0, 1439)); arm = "variant" if r.random() < share_fn(dd) else "base"
            p = rate_fn(dd) + (eff if arm == "variant" else 0); us.append(["u%06d" % i, arm, t, 1 if r.random() < p else 0]); i += 1
    if burst:
        day, size, _, m0, span = burst
        for j in range(size):
            t = CS + timedelta(days=day, minutes=m0 + (span * j) // max(1, size)); us.append(["u%06d" % i, "variant", t, 1 if r.random() < 0.9 else 0]); i += 1
    return [tuple(u) for u in us]
def check(name, units, split=(0.5, 0.5), days=28, start=CS):
    rc, rep = build(name, units, split, days, start); e = expected(units, split, start); s = rep.get("allocation_scan") or {}
    w = s.get("worst") or {}; tp = w.get("p_value")
    pmatch = s.get("windows_tested") == e["scan"]["K"] and tp is not None and e["scan"]["min_p"] is not None and abs(float(tp) - e["scan"]["min_p"]) <= max(1e-12, 2e-3 * e["scan"]["min_p"])
    ok = rc == 0 and rep.get("outcome") == e["outcome"] and s.get("mismatch") == e["scan"]["mismatch"] and pmatch
    return ok, {"rc": rc, "tool": rep.get("outcome"), "doc_rule": e["outcome"], "tool_scan": {"K": s.get("windows_tested"), "p": tp, "units": w.get("units"), "mismatch": s.get("mismatch"), "threshold": s.get("threshold")},
                "my_scan": {"K": e["scan"]["K"], "p": "%.3e" % e["scan"]["min_p"] if e["scan"]["min_p"] is not None else None, "units": e["scan"]["w"], "mismatch": e["scan"]["mismatch"]},
                "block": e["block"], "srm_p": round(e["srm_p"], 6), "diff": round(e["diff"], 4), "claims": rep.get("claims_allowed")}
def s01():  # bursts around the documented 30-unit limit: one day, all variant, high conversion, replacing the day's traffic
    res = {}; ok_all = True; caught = {}
    for size in (10, 20, 25, 30, 35, 40, 60):
        r = random.Random(100 + size); us = gen(r, 28, lambda d: 0.5, lambda d: 0.1, 60, burst=(9, size, True, 600, 60))
        ok, det = check("s01-%d" % size, us); res["burst_%d_replace" % size] = det; ok_all &= ok; caught[size] = det["tool"] == "invalid_experiment"
    row("S01_bursts_replacing_traffic_follow_doc_rule", ok_all, res)
    row("S01b_bursts_of_40_and_more_caught", all(caught[s] for s in (40, 60)), caught)
def s02():  # the same bursts interleaved with normal traffic and straddling midnight
    res = {}; ok_all = True
    for size in (20, 30, 40, 60):
        for nm, b in (("interleaved", (9, size, False, 0, 1439)), ("midnight", (9, size, False, 1380, 120))):
            r = random.Random(200 + size); us = gen(r, 28, lambda d: 0.5, lambda d: 0.1, 60, burst=b)
            ok, det = check("s02-%s-%d" % (nm, size), us); res["%s_%d" % (nm, size)] = det; ok_all &= ok
    row("S02_interleaved_and_midnight_bursts_follow_doc_rule", ok_all, res)
def s03():  # alignment: the same units with cohort.start moved by 0..6 days and 13 h: scan result identical, outcome by doc rule
    r = random.Random(300); us = gen(r, 28, lambda d: 0.5, lambda d: 0.1, 60, burst=(10, 60, True, 1380, 100)); res = {}; ok_all = True; scans = set()
    for sh in (0, 1, 3, 6):
        st = CS - timedelta(days=sh, hours=13 if sh else 0); ok, det = check("s03-%d" % sh, us, start=st, days=28); res["start_minus_%dd" % sh] = det; ok_all &= ok; scans.add(json.dumps(det["tool_scan"], sort_keys=True))
    row("S03_scan_independent_of_cohort_start", ok_all and len(scans) == 1, {"distinct_scans": len(scans), "runs": res})
def s04():  # 30/70 plan with a short reverse burst; and clean controls 50/50 and 30/70: tool equals doc rule
    res = {}; ok_all = True
    for nm, split, share, b in (("clean_50", (0.5, 0.5), 0.5, None), ("clean_30_70", (0.3, 0.7), 0.7, None), ("burst_30_70", (0.3, 0.7), 0.7, (12, 50, True, 300, 30))):
        r = random.Random(400 + len(nm)); us = gen(r, 28, lambda d, s=share: s, lambda d: 0.2, 60, eff=0.0, burst=b)
        ok, det = check("s04-" + nm, us, split=split); res[nm] = det; ok_all &= ok
    row("S04_unequal_plan_and_clean_controls", ok_all and res["clean_50"]["tool"] != "invalid_experiment" and res["clean_30_70"]["tool"] != "invalid_experiment", res)
def s05():  # r2 residual P3-1 shape: one-day all-variant burst of 120 inside healthy weeks must not give a causal claim
    r = random.Random(500); us = gen(r, 28, lambda d: 0.5, lambda d: 0.1, 60, burst=(9, 120, True, 0, 1439)); ok, det = check("s05", us)
    row("S05_r2_residual_burst_no_causal_claim", ok and det["tool"] == "invalid_experiment" and not (det["claims"] or {}).get("causal"), det)
def s06():  # ties: equal assigned_at, order by unit_id (doc); a block of 40 variant units sharing one timestamp
    r = random.Random(600); us = gen(r, 28, lambda d: 0.5, lambda d: 0.1, 60)
    t0 = CS + timedelta(days=11, hours=4); us += [("z%04d" % j, "variant", t0, 1) for j in range(40)]; ok, det = check("s06", us)
    row("S06_tied_timestamps_follow_doc_rule", ok, det)
def s07():  # property: 40 random shapes (none, step, spike, short burst) and sizes; tool equals doc rule on each
    r = random.Random(700); bad = []
    for k in range(40):
        days = r.choice([14, 21, 28]); per = r.choice([20, 40, 80]); shape = r.choice(["none", "none", "burst", "step"]); sd = r.randint(1, days - 2)
        b = (sd, r.choice([20, 30, 45, 80]), r.random() < 0.5, r.randint(0, 1300), r.choice([10, 120, 1439])) if shape == "burst" else None
        fn = (lambda d, sd=sd: 0.5 if d < sd else 0.62) if shape == "step" else (lambda d: 0.5)
        us = gen(random.Random(7000 + k), days, fn, lambda d: 0.2, per, burst=b); ok, det = check("s07-%d" % k, us, days=days)
        if not ok: bad.append(dict(det, shape=shape, days=days, per=per, burst=b))
    row("S07_random_shapes_property", not bad, {"run": 40, "mismatches": bad[:4]})
def o08():  # false invalidation on null runs: 50/50 and 30/70, 60/day for 28 days, true effect 0.03
    out = {}
    for nm, split, n in (("50_50", (0.5, 0.5), 150), ("30_70", (0.3, 0.7), 150)):
        inv = scan_inv = 0
        for k in range(n):
            us = gen(random.Random(80000 + k + int(split[0] * 1000)), 28, lambda d, s=split[1]: s, lambda d: 0.2, 60, eff=0.03); rc, rep = build("o08", us, split=split)
            inv += rep.get("outcome") == "invalid_experiment"; scan_inv += bool((rep.get("allocation_scan") or {}).get("mismatch"))
        out[nm] = {"runs": n, "invalidated": inv, "by_scan": scan_inv, "rate": round(inv / n, 4)}
    tot = sum(v["invalidated"] for v in out.values()); runs = sum(v["runs"] for v in out.values())
    out["binomial_upper_95_at_0.5pct"] = "P(X >= %d | n=%d, p=0.005) = %.3g" % (tot, runs, sum(math.comb(runs, j) * 0.005 ** j * 0.995 ** (runs - j) for j in range(tot, runs + 1)))
    row("O08_false_invalidation_null_runs", True, out, obs=True)
    row("S08_false_invalidation_within_doc_bound", sum(math.comb(runs, j) * 0.005 ** j * 0.995 ** (runs - j) for j in range(tot, runs + 1)) > 0.01, {"invalidated": tot, "runs": runs})
def o09():  # power curve: share of 20 runs invalidated per burst size, replace vs interleave
    out = {}
    for size in (20, 30, 40, 60):
        for nm, rep_ in (("replace", True), ("interleave", False)):
            hits = 0; outs = {}
            for k in range(20):
                us = gen(random.Random(9000 + size * 31 + k), 28, lambda d: 0.5, lambda d: 0.1, 60, burst=(9, size, rep_, 600 if rep_ else 0, 60 if rep_ else 1439)); rc, rep = build("o09", us)
                hits += rep.get("outcome") == "invalid_experiment"; o = rep.get("outcome"); outs[o] = outs.get(o, 0) + 1
                if (rep.get("claims_allowed") or {}).get("causal"): outs["causal_claim"] = outs.get("causal_claim", 0) + 1
            out["%s_%d" % (nm, size)] = {"invalidated": "%d/20" % hits, "outcomes": outs}
    row("O09_burst_power_curve", True, out, obs=True)
ALL = [("S01", s01), ("S02", s02), ("S03", s03), ("S04", s04), ("S05", s05), ("S06", s06), ("S07", s07), ("O08", o08), ("O09", o09)]
if os.environ.get("M15R3_FAST"): ALL = [x for x in ALL if x[0] not in ("O08", "O09")]
for rid, fn in ALL:
    try: fn()
    except Exception as e: row(rid + "_crash", False, "harness or tool crash: %r" % (e,))
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:900])
print("M15R3 SCAN %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
