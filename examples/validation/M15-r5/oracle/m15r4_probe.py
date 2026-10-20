#!/usr/bin/env python3
"""M15 r4 probe (Grok self-validation, not independent review). Generates its own experiment packages (31 days,
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
    rnd = random.Random(seed); d = Path(tempfile.mkdtemp(prefix="m15r4-")); A = []; E = []
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
    j = json.loads(p.stdout); return {"rc": 0, "outcome": j["outcome"], "causal": j["claims_allowed"]["causal"], "check": j.get("assignment_check")}
def many(**kw): return [analyse(gen(1000 + s, **kw)) for s in range(SEEDS)]
def tally(rs):
    t = {}
    for r in rs: k = r.get("outcome", "rc%s" % r.get("rc")); t[k] = t.get(k, 0) + 1
    return t
def row(rid, desc, ok, detail, scored=True):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "scored": scored, "detail": detail})
    print("%s %s %s %s" % (rid, ("PASS" if ok else "FAIL") if scored else "OBS", desc, json.dumps(detail, default=str)[:300]))
rs = many(burst=(40, 12, 0.9)); row("B1", "root: 40-unit all-treatment burst (90%% converting) interleaved into one day, with contract: no causal claim in %d seeds (invalid_experiment)" % SEEDS,
    sum(r.get("causal") is True for r in rs) == 0 and all(r.get("outcome") == "invalid_experiment" for r in rs), tally(rs))
rs = many(burst=(40, 12, 0.9), contract=False); row("B2", "same burst without a contract: never a causal claim", sum(r.get("causal") is True for r in rs) == 0, tally(rs))
rs = many(burst=(50, 20, 0.9), contract=False); assoc = sum(r.get("outcome") == "association_only" for r in rs)
row("B2b", "50-unit burst without contract: outcomes recorded (association_only shows the guards missed it)", True, {"tally": tally(rs), "association_only": assoc}, scored=False)
rs = many(burst=(6, 12, 0.9)); row("B3", "6-unit burst with contract (expected escape rate 1/64): outcomes recorded", True, tally(rs), scored=False)
rs = many(); fp = sum(r.get("causal") is True for r in rs); ver = sum(bool((r.get("check") or {}).get("verified")) for r in rs)
row("B4", "A/A with contract: assignment verified in every seed and causal false positives at most 3 of %d" % SEEDS, ver == SEEDS and fp <= 3, {"tally": tally(rs), "verified": ver, "causal": fp})
rs = many(pt=0.30); hit = sum(r.get("outcome") == "difference_detected" and r.get("causal") is True for r in rs)
row("B5", "true effect 20%% -> 30%% with contract: difference_detected and causal in at least %d of %d" % (SEEDS - 2, SEEDS), hit >= SEEDS - 2, {"tally": tally(rs)})
rs = many(pt=0.30, split=(0.3, 0.7)); hit = sum(r.get("outcome") == "difference_detected" for r in rs)
row("B6", "30/70 split, true effect, contract: verified and difference_detected", hit >= SEEDS - 2 and all((r.get("check") or {}).get("verified") for r in rs), {"tally": tally(rs)})
r7 = [analyse(gen(2000 + s, pt=0.30, pkg_salt="another-salt")) for s in range(3)]
row("B7", "package declares a salt that did not assign the arms: invalid_experiment, never causal", all(r.get("outcome") == "invalid_experiment" and not r.get("causal") for r in r7),
    {"outcomes": [r.get("outcome") for r in r7], "mismatched": [(r.get("check") or {}).get("mismatched") for r in r7]})
bad = {"observational": dict(assignment="observational"),
       "method md5": dict(randomization={"method": "md5_bucket", "salt": "x"}), "blank salt": dict(randomization={"method": "sha256_bucket", "salt": "  "}),
       "extra key": dict(randomization={"method": "sha256_bucket", "salt": "x", "share": 0.5}), "salt not string": dict(randomization={"method": "sha256_bucket", "salt": 7})}
r8 = {k: analyse(gen(3000, **v)) for k, v in bad.items()}
row("B8", "malformed contract or a contract on an observational package: refused, exit 2", all(r.get("rc") == 2 for r in r8.values()), {k: v.get("rc") for k, v in r8.items()})
r9 = [analyse(gen(4000 + s, ids="\u00fcnit-\u00e9-%d-%d-%d")) for s in range(3)]
row("B9", "non-ASCII unit ids: the documented UTF-8 rule verifies them", all((r.get("check") or {}).get("verified") for r in r9), {"checks": [r.get("check") for r in r9]})
rs = many(drop=0.25); row("B10", "OBS: with no true effect, 25%% of converting control units missing from the assignment log, contract present: outcomes (the contract checks arms of present units, not missing ones)",
    True, {"tally": tally(rs), "causal": sum(r.get("causal") is True for r in rs), "verified": sum(bool((r.get("check") or {}).get("verified")) for r in rs)}, scored=False)
sc = [r for r in ROWS if r["scored"]]
json.dump({"python": sys.version.split()[0], "seeds": SEEDS, "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M15R4 PROBE %d/%d" % (sum(r["pass"] for r in sc), len(sc)))
