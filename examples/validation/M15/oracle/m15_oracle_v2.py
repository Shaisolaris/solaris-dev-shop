#!/usr/bin/env python3
"""M15 oracle (Grok self-validation, written by Grok, black box). Expectations come from experiment-readout.md and
the G15 README, never from the tool's output. Units and events are generated here; counts, Wald interval, pooled z
test and SRM chi-square are computed here (statistics.NormalDist, math.erfc).
Usage: PY m15_oracle.py REPO [--tool TOOL.py] OUT.json. Core rows (X*) score; OBS rows record only.
v2 (disclosed): X04 no longer assumes an event exactly at assignment + horizon counts (the doc does not say whether the
horizon end is inclusive); that boundary is recorded in X04b. X13b adds a ramp that reverses the pooled sign."""
import csv, io, json, math, random, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from statistics import NormalDist
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/data/data-scientist/experiment_readout.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
TOP = Path(tempfile.mkdtemp(prefix="m15top-", dir="/tmp")).resolve(); rows = []
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
CS = datetime(2026, 5, 4, tzinfo=timezone.utc); CE = datetime(2026, 6, 1, tzinfo=timezone.utc); ASOF = datetime(2026, 6, 20, tzinfo=timezone.utc); H = 10
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
def write(name, asg, ev, **pk):
    d = TOP / name; d.mkdir(parents=True)
    for fn, h, rs in (("a.csv", ["unit_id", "arm", "assigned_at"], asg), ("e.csv", ["unit_id", "event", "occurred_at", "session_id"], ev)):
        b = io.StringIO(); w = csv.writer(b, lineterminator="\n"); w.writerow(h); [w.writerow(r) for r in rs]; (d / fn).write_text(b.getvalue())
    p = {"schema": "solaris.experiment/1", "experiment": "checkout-copy-" + name, "unit": "unit_id", "assignment": "randomized", "arms": ["base", "variant"],
         "planned_split": [0.5, 0.5], "timezone": "UTC", "cohort": {"start": iso(CS), "end": iso(CE)}, "as_of": iso(ASOF), "outcome": {"event": "purchase", "horizon_days": H},
         "min_sample_per_arm": 150, "alpha": 0.05, "assignments": {"file": "a.csv"}, "events": {"file": "e.csv"}}
    p.update(pk); (d / "pkg.json").write_text(json.dumps(p)); return d / "pkg.json"
def run(p, *extra):
    cp = subprocess.run([PY, str(TOOL), "analyse", str(p), "--json"] + list(extra), cwd=p.parent, env=ENV, capture_output=True, text=True, timeout=300)
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    return cp.returncode, rep or {}, cp
def gen(nb, nv, rb, rv, seed, sessions=1, start=CS, span_days=26, conv_exact=True):
    """nb, nv units; rb, rv conversion share (converted = round(share * n), chosen at random); returns rows and truth."""
    r = random.Random(seed); asg, ev = [], []; truth = {}
    for arm, n, rate, pre in (("base", nb, rb, "b"), ("variant", nv, rv, "v")):
        conv = set(r.sample(range(n), int(round(rate * n)))); truth[arm] = (n, len(conv))
        for i in range(n):
            u = "%s%05d_%d" % (pre, i, seed); t = start + timedelta(minutes=r.randint(0, span_days * 1440)); asg.append([u, arm, iso(t)])
            if i in conv:
                for s in range(sessions): ev.append([u, "purchase", iso(t + timedelta(hours=r.randint(1, H * 24 - 1))), "s%d" % s])
            else:
                if r.random() < 0.3: ev.append([u, "view", iso(t + timedelta(hours=2)), "s0"])
    r.shuffle(asg); r.shuffle(ev); return asg, ev, truth
def stats(nb, xb, nv, xv, alpha=0.05):
    pb, pv = xb / nb, xv / nv; d = pv - pb; se = math.sqrt(pb * (1 - pb) / nb + pv * (1 - pv) / nv); z = NormalDist().inv_cdf(1 - alpha / 2)
    p = (xb + xv) / (nb + nv); se0 = math.sqrt(p * (1 - p) * (1 / nb + 1 / nv)); zz = d / se0 if se0 else 0.0
    return {"difference": d, "ci_low": d - z * se, "ci_high": d + z * se, "p_value": math.erfc(abs(zz) / math.sqrt(2))}
def close(rep, exp, tol=1.5e-6):
    e = rep.get("effect") or {}; bad = {k: (e.get(k), round(v, 6)) for k, v in exp.items() if e.get(k) is None or abs(float(e[k]) - v) > tol}; return bad
def counts(rep): return {k: ((rep.get("arms") or {}).get(k) or {}).get("units") for k in ("base", "variant")}, {k: ((rep.get("arms") or {}).get(k) or {}).get("converted") for k in ("base", "variant")}
def x01():  # A/A: identical deterministic conversion, no difference, no claim
    asg, ev, t = gen(300, 300, 0.3, 0.3, 1); rc, rep, _ = run(write("x01", asg, ev)); n, c = counts(rep)
    ok = rc == 0 and n == {"base": 300, "variant": 300} and c == {"base": 90, "variant": 90} and rep.get("outcome") == "no_detectable_difference" and rep.get("claims_allowed") == {"causal": False, "significance": False}
    row("X01_aa_no_claim", ok, {"rc": rc, "units": n, "converted": c, "outcome": rep.get("outcome"), "claims": rep.get("claims_allowed")})
def x02():  # real lift with exact counts and independently computed interval and p value
    asg, ev, t = gen(400, 400, 0.15, 0.24, 2); rc, rep, _ = run(write("x02", asg, ev)); n, c = counts(rep); bad = close(rep, stats(400, 60, 400, 96))
    ok = rc == 0 and c == {"base": 60, "variant": 96} and not bad and rep.get("outcome") == "difference_detected" and rep.get("claims_allowed") == {"causal": True, "significance": True}
    row("X02_lift_exact_interval", ok, {"rc": rc, "converted": c, "effect_mismatch": bad, "effect": rep.get("effect"), "outcome": rep.get("outcome")})
def x03():  # repeated users: 9 sessions per converting unit and repeat assignment rows in the same arm count once
    asg, ev, t = gen(250, 250, 0.2, 0.2, 3, sessions=9); asg2 = asg + [[u, arm, iso(datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) + timedelta(hours=5))] for u, arm, ts in asg[:40]]
    rc, rep, _ = run(write("x03", asg2, ev)); n, c = counts(rep)
    row("X03_repeated_users_once", rc == 0 and n == {"base": 250, "variant": 250} and c == {"base": 50, "variant": 50}, {"rc": rc, "units": n, "converted": c, "exclusions": rep.get("exclusions")})
def x04():  # leakage: pre-assignment and post-horizon events do not count; at assignment and exactly at the horizon count; unassigned ignored
    asg, ev, t = gen(200, 200, 0.0, 0.0, 4); r = random.Random(4); A = {u: datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) for u, arm, ts in asg}
    base_units = sorted(u for u, arm, ts in asg if arm == "base"); var_units = sorted(u for u, arm, ts in asg if arm == "variant")
    for u in base_units[:30]: ev.append([u, "purchase", iso(A[u] - timedelta(seconds=1)), "pre"])          # leakage before assignment: not counted
    for u in base_units[30:40]: ev.append([u, "purchase", iso(A[u] + timedelta(days=H, seconds=1)), "late"])  # after the horizon: not counted
    for u in var_units[:12]: ev.append([u, "purchase", iso(A[u]), "at"])                                   # at assignment: counted
    for u in var_units[12:20]: ev.append([u, "purchase", iso(A[u] + timedelta(days=H)), "edge"])          # exactly at the horizon: counted
    for k in range(7): ev.append(["ghost%d" % k, "purchase", iso(CS + timedelta(days=3)), "g"])
    rc, rep, _ = run(write("x04", asg, ev)); n, c = counts(rep); ex = rep.get("exclusions") or {}
    ok = rc == 0 and c["base"] == 0 and c["variant"] in (12, 20) and ex.get("events_unassigned_units") == 7 and ex.get("events_before_assignment", 0) >= 30
    row("X04_leakage_windows", ok, {"rc": rc, "converted": c, "exclusions": ex})
    row("X04b_horizon_end_boundary", True, {"event_exactly_at_assignment_plus_horizon_counted": c["variant"] == 20}, obs=True)
def x05():  # units in both arms excluded and named; 5% exactly is not invalid, above 5% is
    res = {}
    for name, k in (("at5", 20), ("over5", 21)):
        asg, ev, t = gen(200, 200, 0.2, 0.2, 5); bu = [u for u, arm, ts in asg if arm == "base"][:k]
        asg2 = asg + [[u, "variant", iso(CS + timedelta(days=27))] for u in bu]
        rc, rep, _ = run(write("x05" + name, asg2, ev)); n, c = counts(rep)
        res[name] = {"rc": rc, "outcome": rep.get("outcome"), "named": len((rep.get("exclusions") or {}).get("multiple_arms") or []), "units": n, "claims": rep.get("claims_allowed")}
    ok = res["at5"]["named"] == 20 and res["at5"]["outcome"] != "invalid_experiment" and res["at5"]["units"]["base"] == 180 and res["over5"]["outcome"] == "invalid_experiment" and res["over5"]["claims"] == {"causal": False, "significance": False}
    row("X05_contamination_threshold", ok, res)
def x06():  # underpowered: below min sample in one arm is insufficient_information even with a big gap; exactly at min is read
    asg, ev, t = gen(149, 400, 0.05, 0.5, 6); rc, rep, _ = run(write("x06a", asg, ev)); o1 = (rep.get("outcome"), rep.get("claims_allowed"))
    asg, ev, t = gen(150, 150, 0.05, 0.5, 7); rc2, rep2, _ = run(write("x06b", asg, ev, planned_split=[0.5, 0.5])); o2 = rep2.get("outcome")
    row("X06_underpowered", o1 == ("insufficient_information", {"causal": False, "significance": False}) and o2 == "difference_detected", {"below_min": o1, "at_min": o2})
def x07():  # SRM against the planned split, chi-square p < 0.001 invalid; a mild imbalance is not; a 30/70 plan with 30/70 data is fine
    def chi(nb, nv, s):
        n = nb + nv; eb, evv = n * s[0], n * s[1]; x = (nb - eb) ** 2 / eb + (nv - evv) ** 2 / evv; return x, math.erfc(math.sqrt(x / 2))
    res = {}
    for name, nb, nv, split in (("srm", 330, 450, [0.5, 0.5]), ("mild", 380, 420, [0.5, 0.5]), ("planned_30_70", 240, 560, [0.3, 0.7])):
        asg, ev, t = gen(nb, nv, 0.2, 0.2, 8); rc, rep, _ = run(write("x07" + name, asg, ev, planned_split=split)); x, p = chi(nb, nv, split)
        s = rep.get("srm") or {}; res[name] = {"rc": rc, "outcome": rep.get("outcome"), "chi_ok": s.get("chi_square") is not None and abs(float(s["chi_square"]) - x) < 1.5e-6, "p": p, "tool_p": s.get("p_value")}
    ok = res["srm"]["outcome"] == "invalid_experiment" and res["mild"]["outcome"] != "invalid_experiment" and res["planned_30_70"]["outcome"] != "invalid_experiment" and all(v["chi_ok"] for v in res.values())
    row("X07_srm", ok, res)
def x08():  # observational: association only, never causal
    asg, ev, t = gen(400, 400, 0.15, 0.3, 9); rc, rep, _ = run(write("x08", asg, ev, assignment="observational"))
    row("X08_observational_association_only", rc == 0 and rep.get("outcome") == "association_only" and rep.get("claims_allowed") == {"causal": False, "significance": True}, {"outcome": rep.get("outcome"), "claims": rep.get("claims_allowed")})
def x09():  # cohort: first assignment fixes the cohort; outside-cohort units excluded; immature units excluded and counted, not failures
    asg, ev, t = gen(200, 200, 0.25, 0.25, 10)
    extra = [["out%d" % k, "base", iso(CS - timedelta(hours=k + 1))] for k in range(9)] + [["late%d" % k, "variant", iso(CE + timedelta(hours=k))] for k in range(4)]
    imm = [["imm%d" % k, "variant", iso(ASOF - timedelta(days=2, hours=k))] for k in range(5)]
    rc, rep, _ = run(write("x09", asg + extra, ev)); n, c = counts(rep); ex = rep.get("exclusions") or {}
    p2 = write("x09b", asg + imm, ev, cohort={"start": iso(CS), "end": iso(ASOF)}); rc2, rep2, _ = run(p2); n2, c2 = counts(rep2); ex2 = rep2.get("exclusions") or {}
    ok = rc == 0 and n == {"base": 200, "variant": 200} and ex.get("outside_cohort") == 13 and rc2 == 0 and ex2.get("immature", 0) >= 5 and n2["variant"] == 200 + 5 - ex2.get("immature") + 0 and c2 == c
    row("X09_cohort_and_immature", ok, {"units": n, "outside": ex.get("outside_cohort"), "immature_run": {"units": n2, "immature": ex2.get("immature"), "converted": c2}})
def x10():  # invalid packages exit 2 and keep the previous --out; then recovery
    asg, ev, t = gen(160, 160, 0.2, 0.2, 11); p = write("x10", asg, ev); d = p.parent; o = d / "r.json"
    rc0 = subprocess.run([PY, str(TOOL), "analyse", str(p), "--json", "--out", str(o)], cwd=d, env=ENV, capture_output=True).returncode; keep = o.read_bytes() if o.exists() else None
    res = {}
    for name, f in (("split_not_one", lambda k: k.update(planned_split=[0.5, 0.6])), ("three_arms", lambda k: k.update(arms=["a", "b", "c"])), ("unit_not_unit_id", lambda k: k.update(unit="session_id")),
                    ("alpha_one", lambda k: k.update(alpha=1)), ("unknown_field", lambda k: k.update(segment="mobile")), ("missing_file", lambda k: k["events"].update(file="none.csv")),
                    ("cohort_reversed", lambda k: k.update(cohort={"start": iso(CE), "end": iso(CS)})), ("bad_assignment_kind", lambda k: k.update(assignment="quasi"))):
        pk = json.loads(p.read_text()); f(pk); q = d / ("bad-%s.json" % name); q.write_text(json.dumps(pk))
        res[name] = subprocess.run([PY, str(TOOL), "analyse", str(q), "--json", "--out", str(o)], cwd=d, env=ENV, capture_output=True).returncode
    kept = o.exists() and o.read_bytes() == keep; rc9, _, _ = run(p)
    row("X10_invalid_refused_out_kept", rc0 == 0 and all(v == 2 for v in res.values()) and kept and rc9 == 0, dict(res, first=rc0, kept=kept, recover=rc9))
def x11():  # order and repeat stability
    asg, ev, t = gen(220, 220, 0.2, 0.3, 12); rc, rep, cp = run(write("x11a", asg, ev)); r = random.Random(3); a2, e2 = asg[:], ev[:]; r.shuffle(a2); r.shuffle(e2)
    rc2, rep2, cp2 = run(write("x11b", a2, e2)); _, _, cp3 = run(write("x11c", asg, ev))
    strip = lambda x: {k: v for k, v in x.items() if k not in ("inputs", "package_sha256", "experiment")}
    row("X11_order_stable", rc == rc2 == 0 and strip(rep) == strip(rep2) and strip(json.loads(cp3.stdout)) == strip(rep), {"equal": strip(rep) == strip(rep2)})
def x12():  # reads only, no bytecode left (G13 import), run without PYTHONDONTWRITEBYTECODE
    asg, ev, t = gen(160, 160, 0.2, 0.2, 13); p = write("x12", asg, ev); d = p.parent; before = {x.name: x.read_bytes() for x in d.iterdir()}
    env = dict(ENV); env.pop("PYTHONDONTWRITEBYTECODE"); pc0 = sorted(str(x) for x in REPO.rglob("__pycache__"))
    rc = subprocess.run([PY, str(TOOL), "analyse", str(p)], cwd=d, env=env, capture_output=True).returncode
    row("X12_reads_only_no_bytecode", rc == 0 and before == {x.name: x.read_bytes() for x in d.iterdir()} and pc0 == sorted(str(x) for x in REPO.rglob("__pycache__")), {"rc": rc})
def x13():  # Simpson by ramp: allocation 20/80 in week 1 (high base rate) then 80/20 later (low base rate); pooled split 50/50.
    # Within each period the variant is better by 5 points; pooled, the variant looks worse. Doc has no segment or ramp rule: recorded.
    r = random.Random(14); asg, ev = [], []; k = 0
    def add(arm, n, rate, t0, days):
        nonlocal k
        conv = set(r.sample(range(n), int(round(rate * n))))
        for i in range(n):
            u = "s%05d" % k; k += 1; t = t0 + timedelta(minutes=r.randint(0, days * 1440)); asg.append([u, arm, iso(t)])
            if i in conv: ev.append([u, "purchase", iso(t + timedelta(hours=3)), "s"])
    add("base", 100, 0.50, CS, 6); add("variant", 400, 0.55, CS, 6); add("base", 400, 0.10, CS + timedelta(days=7), 19); add("variant", 100, 0.15, CS + timedelta(days=7), 19)
    rc, rep, _ = run(write("x13", asg, ev)); n, c = counts(rep)
    asg2, ev2 = asg, ev; asg, ev = [], []
    add("base", 400, 0.50, CS, 6); add("variant", 100, 0.55, CS, 6); add("base", 100, 0.10, CS + timedelta(days=7), 19); add("variant", 400, 0.15, CS + timedelta(days=7), 19)
    rcb, repb, _ = run(write("x13b", asg, ev)); nb_, cb_ = counts(repb)
    row("X13b_simpson_ramp_reversal", True, {"rc": rcb, "units": nb_, "converted": cb_, "outcome": repb.get("outcome"), "effect": repb.get("effect"), "claims": repb.get("claims_allowed"), "truth": "variant +0.05 in each period; pooled sign reversed"}, obs=True)
    row("X13_simpson_ramp", True, {"rc": rc, "units": n, "converted": c, "outcome": rep.get("outcome"), "effect": rep.get("effect"), "claims": rep.get("claims_allowed"),
        "truth": "variant +0.05 in each period (0.50 vs 0.55, then 0.10 vs 0.15)", "srm": rep.get("srm")}, obs=True)
def x14():  # small-sample and edge rates (Wald near 0): 0/150 vs 6/150; recorded
    asg, ev, t = gen(150, 150, 0.0, 0.04, 15); rc, rep, _ = run(write("x14", asg, ev)); exp = stats(150, 0, 150, 6)
    row("X14_wald_near_zero", True, {"rc": rc, "outcome": rep.get("outcome"), "effect": rep.get("effect"), "my_wald": {k: round(v, 6) for k, v in exp.items()}}, obs=True)
for rid, fn in (("X01", x01), ("X02", x02), ("X03", x03), ("X04", x04), ("X05", x05), ("X06", x06), ("X07", x07), ("X08", x08), ("X09", x09), ("X10", x10), ("X11", x11), ("X12", x12), ("X13", x13), ("X14", x14)):
    try: fn()
    except Exception as e: row(rid + "_crash", False, "harness or tool crash: %r" % (e,))
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:900])
print("M15 ORACLE %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
