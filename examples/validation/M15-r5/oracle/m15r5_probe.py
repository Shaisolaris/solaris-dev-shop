#!/usr/bin/env python3
"""M15 r5 probe (rows C1 to C6 for G15 r5 expected_units; helpers from the M15 r4 probe)
M15 r4 probe (Grok self-validation, not independent review). Generates its own experiment packages (31 days,
60 units a day, arms from my own implementation of the documented sha256_bucket rule) and runs the G15 CLI.
Written from the root finding (interleaved bursts escape the allocation guards and permit causal claims) and
experiment-readout.md rule 7. Usage: PY m15r4_probe.py REPO OUT.json [--seeds N]"""
import csv, datetime as dt, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
SEEDS = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 20
TOOL = REPO / "employees/data/data-scientist/experiment_readout.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
START = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
def rule(salt, uid, share):
    return "control" if int(hashlib.sha256((salt + ":" + uid).encode("utf-8")).hexdigest()[:15], 16) / 16 ** 15 < share else "treatment"
def gen(seed, *, pc=0.2, pt=0.2, salt="m15r4-salt", pkg_salt=None, split=(0.5, 0.5), contract=True, burst=None, drop=0.0,
        assignment="randomized", ids=None, per_day=60, randomization=None):
    rnd = random.Random(seed); d = Path(tempfile.mkdtemp(prefix="m15r5-")); A = []; E = []
    def add(uid, arm, t, p):
        A.append((uid, arm, iso(t)))
        if rnd.random() < p: E.append((uid, "retained", iso(t + dt.timedelta(hours=rnd.uniform(1, 160))), "s"))
    for day in range(31):
        for i in range(per_day):
            uid = (ids or "u%d-%d-%d") % (seed, day, i) if ids is None or "%" in ids else ids
            t = START + dt.timedelta(days=day, seconds=rnd.randrange(86400))
            arm = rule(salt, uid, split[0]); add(uid, arm, t, pc if arm == "control" else pt)
        if burst and day == burst[1]:
            for j in range(burst[0]):  # forced into treatment regardless of the rule, high converting, interleaved
                add("b%d-%d" % (seed, j), "treatment", START + dt.timedelta(days=day, seconds=rnd.randrange(86400)), burst[2])
    if drop:
        conv = {e[0] for e in E}
        A = [a for a in A if not (a[1] == "control" and a[0] in conv and rnd.random() < drop)]
    rnd.shuffle(A)
    with open(d / "assignments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["unit_id", "arm", "assigned_at"]); w.writerows(A)
    with open(d / "events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["unit_id", "event", "occurred_at", "session_id"]); w.writerows(E)
    pkg = {"schema": "solaris.experiment/1", "experiment": "m15r4", "unit": "unit_id", "assignment": assignment,
           "arms": ["control", "treatment"], "planned_split": list(split), "timezone": "UTC",
           "cohort": {"start": "2026-08-01T00:00:00Z", "end": "2026-09-01T00:00:00Z"}, "as_of": "2026-09-20T00:00:00Z",
           "outcome": {"event": "retained", "horizon_days": 7}, "min_sample_per_arm": 200, "alpha": 0.05,
           "assignments": {"file": "assignments.csv"}, "events": {"file": "events.csv"}}
    if randomization is not None: pkg["randomization"] = randomization
    elif contract: pkg["randomization"] = {"method": "sha256_bucket", "salt": pkg_salt or salt}
    (d / "package.json").write_text(json.dumps(pkg)); return d
def analyse(d):
    p = subprocess.run([sys.executable, str(TOOL), "analyse", str(d / "package.json"), "--json"], capture_output=True, text=True, env=ENV, timeout=300)
    shutil.rmtree(d, ignore_errors=True)
    if p.returncode != 0: return {"rc": p.returncode, "err": p.stderr.strip()[-160:]}
    j = json.loads(p.stdout); return {"rc": 0, "outcome": j["outcome"], "causal": j["claims_allowed"]["causal"], "check": j.get("assignment_check"), "trace": " ".join(j["trace"])}
def many(**kw): return [analyse(gen(1000 + s, **kw)) for s in range(SEEDS)]
def tally(rs):
    t = {}
    for r in rs: k = r.get("outcome", "rc%s" % r.get("rc")); t[k] = t.get(k, 0) + 1
    return t
def row(rid, desc, ok, detail, scored=True):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "scored": scored, "detail": detail})
    print("%s %s %s %s" % (rid, ("PASS" if ok else "FAIL") if scored else "OBS", desc, json.dumps(detail, default=str)[:300]))
TRUE_N = 31 * 60
def contract(n): return {"method": "sha256_bucket", "salt": "m15r4-salt", "expected_units": n}
rs = many(drop=0.25, randomization=contract(TRUE_N))
row("C1", "M15 r4 B10 with expected_units = the true count: 25%% of converting control units missing, no true effect: invalid_experiment and no causal claim in every seed",
    all(r.get("outcome") == "invalid_experiment" and not r.get("causal") for r in rs) and all("missing from the log" in r.get("trace", "") for r in rs),
    {"tally": tally(rs), "units_in_log": sorted({(r.get("check") or {}).get("units_in_log") for r in rs})[:5]})
rs = many(drop=0.25)
row("C2", "same data without expected_units: every difference_detected trace states that missing units were not checked",
    all("cannot be detected without randomization.expected_units" in r["trace"] for r in rs if r.get("outcome") == "difference_detected")
    and all((r.get("check") or {}).get("missing_units_checked") is False for r in rs), {"tally": tally(rs), "causal": sum(r.get("causal") is True for r in rs)})
rs = many(randomization=contract(TRUE_N)); fp = sum(r.get("causal") is True for r in rs)
row("C3", "A/A with expected_units: verified and missing_units_checked in every seed, causal false positives at most 3",
    all((r.get("check") or {}).get("verified") and (r.get("check") or {}).get("missing_units_checked") for r in rs) and fp <= 3, {"tally": tally(rs), "causal": fp})
rs = many(pt=0.30, randomization=contract(TRUE_N)); hit = [r for r in rs if r.get("outcome") == "difference_detected"]
row("C4", "true effect 20%% -> 30%% with expected_units: difference_detected in at least %d of %d and the trace says the log holds all %d" % (SEEDS - 2, SEEDS, TRUE_N),
    len(hit) >= SEEDS - 2 and all("the log holds all %d" % TRUE_N in r["trace"] for r in hit), {"tally": tally(rs)})
rs = [analyse(gen(5000 + s, pt=0.30, randomization=contract(n))) for s, n in enumerate((TRUE_N + 1, TRUE_N - 1, 1))]
row("C5", "expected_units off by one either way, or far off: invalid_experiment, never causal",
    all(r.get("outcome") == "invalid_experiment" and not r.get("causal") for r in rs), {"outcomes": [r.get("outcome") for r in rs]})
bad = {"zero": 0, "negative": -5, "bool": True, "string": "1860", "float": 1860.0, "null": None}
r6_ = {k: analyse(gen(6000, randomization=contract(v))) for k, v in bad.items()}
row("C6", "malformed expected_units refused with exit 2", all(r.get("rc") == 2 for r in r6_.values()), {k: v.get("rc") for k, v in r6_.items()})
rs = many(burst=(40, 12, 0.9), randomization=contract(TRUE_N + 40))
row("C7", "r4 B1 burst with expected_units counting the burst: still invalid (arms off the rule), never causal",
    all(r.get("outcome") == "invalid_experiment" and not r.get("causal") for r in rs), tally(rs))
sc = [r for r in ROWS if r["scored"]]
json.dump({"python": sys.version.split()[0], "seeds": SEEDS, "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M15R5 PROBE %d/%d" % (sum(r["pass"] for r in sc), len(sc)))
