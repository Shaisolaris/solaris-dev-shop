#!/usr/bin/env python3
"""G15 oracle: experiment / retention readout with fixed cohorts, leakage checks and uncertainty.

Generates its own experiments from a seed, knows by construction which units converted inside
their horizon, computes rates, the Wald interval and the pooled z test with statistics.NormalDist
(independent of the tool's own normal functions) and reads the JSON of
  CMD analyse PACKAGE --json [--out REPORT]

Usage: readout_oracle.py [--seed N] [--quick] -- CMD...
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from statistics import NormalDist

CMD, RESULTS = [], []
UTC = dt.timezone.utc
CS, CE, AS_OF = dt.datetime(2026, 8, 1, tzinfo=UTC), dt.datetime(2026, 9, 1, tzinfo=UTC), dt.datetime(2026, 9, 20, tzinfo=UTC)
H = 7


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def experiment(rng, n=(800, 800), p=(0.2, 0.2), exact=False, outside=0, contaminated=0, unassigned=0, sessions=3,
               assignment="randomized", min_sample=200, dup_rows=0, split=(0.5, 0.5)):
    """Rows plus truth. exact=True converts every fourth unit in each arm (a deterministic A/A control)."""
    arms = ("control", "treatment")
    A, E = [], []
    truth = {a: [0, 0] for a in arms}
    k = 0

    def ev(u, t, conv):
        for s in range(rng.randrange(1, sessions + 1)):
            E.append([u, "page_view", iso(t + dt.timedelta(hours=rng.randrange(0, 24 * H))), "s%d" % s])
        E.append([u, "retained", iso(t - dt.timedelta(hours=rng.randrange(1, 48))), "pre"])  # before assignment: never counts
        if conv:
            E.append([u, "retained", iso(t + dt.timedelta(hours=rng.randrange(1, 24 * H - 1))), "s0"])
            E.append([u, "retained", iso(t + dt.timedelta(hours=rng.randrange(1, 24 * H - 1))), "s1"])  # same unit again
        else:
            E.append([u, "retained", iso(t + dt.timedelta(days=H, hours=rng.randrange(1, 100))), "late"])  # after horizon
    for i, a in enumerate(arms):
        for j in range(n[i]):
            u = "u%06d" % k
            k += 1
            t = CS + dt.timedelta(minutes=rng.randrange(0, int((CE - CS).total_seconds() // 60)))
            conv = (j % 4 == 0) if exact else rng.random() < p[i]
            A.append([u, a, iso(t)])
            truth[a][0] += 1
            truth[a][1] += int(conv)
            ev(u, t, conv)
            for _ in range(dup_rows if rng.random() < 0.1 else 0):
                A.append([u, a, iso(t + dt.timedelta(hours=1))])  # re-sent later assignment row, same arm
    for _ in range(outside):
        u = "u%06d" % k; k += 1
        t = CS - dt.timedelta(days=rng.randrange(1, 20))
        A.append([u, rng.choice(arms), iso(t)])
        ev(u, t, True)
    cont = []
    for _ in range(contaminated):
        u = "u%06d" % k; k += 1
        t = CS + dt.timedelta(days=rng.randrange(0, 20))
        A.append([u, "control", iso(t)])
        A.append([u, "treatment", iso(t + dt.timedelta(hours=2))])
        ev(u, t, True)
        cont.append(u)
    for _ in range(unassigned):
        E.append(["x%05d" % rng.randrange(99999), "retained", iso(CS + dt.timedelta(days=3)), "s0"])
    rng.shuffle(A)
    rng.shuffle(E)
    pkg = {"schema": "solaris.experiment/1", "experiment": "exp-%d" % rng.randrange(1000, 9999), "unit": "unit_id", "assignment": assignment,
           "arms": list(arms), "planned_split": list(split), "timezone": "UTC", "cohort": {"start": iso(CS), "end": iso(CE)}, "as_of": iso(AS_OF),
           "outcome": {"event": "retained", "horizon_days": H}, "min_sample_per_arm": min_sample, "alpha": 0.05,
           "assignments": {"file": "assignments.csv"}, "events": {"file": "events.csv"}}
    return pkg, A, E, truth, sorted(cont)


def write(d, pkg, A, E):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "assignments.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["unit_id", "arm", "assigned_at"]); w.writerows(A)
    with open(d / "events.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["unit_id", "event", "occurred_at", "session_id"]); w.writerows(E)
    (d / "package.json").write_text(json.dumps(pkg, indent=1))
    return d / "package.json"


def expected_effect(truth, alpha=0.05):
    (n1, x1), (n2, x2) = truth["control"], truth["treatment"]
    p1, p2 = x1 / n1, x2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    z = NormalDist().inv_cdf(1 - alpha / 2)
    pool = (x1 + x2) / (n1 + n2)
    se0 = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    pv = 2 * (1 - NormalDist().cdf(abs(p2 - p1) / se0))
    return p2 - p1, p2 - p1 - z * se, p2 - p1 + z * se, pv


def run(pkg, out=None, env=None):
    p = subprocess.run(CMD + ["analyse", str(pkg), "--json"] + (["--out", str(out)] if out else []), capture_output=True, text=True, timeout=300, env=env)
    try:
        return p.returncode, (json.loads(p.stdout) if p.returncode == 0 else None), p.stdout
    except ValueError:
        return p.returncode, None, p.stdout


def counts(rep):
    return {a: [v.get("units"), v.get("converted")] for a, v in ((rep or {}).get("arms") or {}).items()}


def close(rep, truth):
    e = (rep or {}).get("effect") or {}
    d, lo, hi, pv = expected_effect(truth)
    try:
        return all(abs(float(e[k]) - v) < 2e-6 for k, v in (("difference", d), ("ci_low", lo), ("ci_high", hi), ("p_value", pv)))
    except (KeyError, TypeError, ValueError):
        return False


def check(name, fn):
    try:
        ok, msg = fn()
    except Exception as exc:
        ok, msg = False, "%s: %s" % (type(exc).__name__, str(exc)[:200])
    RESULTS.append(ok)
    print("%s %s: %s" % ("PASS" if ok else "FAIL", name, msg))


def tree(d):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(d)):
        dirs.sort()
        for f in sorted(files):
            h.update(os.path.join(root, f).encode() + open(os.path.join(root, f), "rb").read())
    return h.hexdigest()


def main():
    global CMD
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1515)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    CMD = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not CMD:
        ap.error("give the tool command after --")
    rng = random.Random(a.seed)
    tmp = Path(tempfile.mkdtemp(prefix="g15-oracle-"))
    out = {}

    def go(name, **kw):
        pkg, A, E, truth, cont = experiment(rng, **kw)
        rc, rep, raw = run(write(tmp / name, pkg, A, E))
        out[name] = (pkg, A, E, truth, cont)
        return rc, rep, truth, cont, raw

    def o1():
        rc, rep, t, _, _ = go("o1", n=(1500, 1500), exact=True)
        d, lo, hi, _ = expected_effect(t)
        want = "no_detectable_difference" if lo <= 0 <= hi else "difference_detected"
        ok = rc == 0 and counts(rep) == t and close(rep, t) and rep["outcome"] == want and want == "no_detectable_difference" and rep["claims_allowed"]["causal"] is False
        return ok, "A/A control: exact unit counts, interval and p match an independent computation, no difference claimed" if ok else "rc %s counts %s/%s outcome %s" % (rc, counts(rep), t, (rep or {}).get("outcome"))
    check("o1 clean control", o1)

    def o2():
        rc, rep, t, _, _ = go("o2", n=(2000, 2000), p=(0.20, 0.30))
        ok = rc == 0 and counts(rep) == t and close(rep, t) and rep["outcome"] == "difference_detected" and rep["claims_allowed"] == {"causal": True, "significance": True}
        return ok, "randomized lift: exact counts and interval; difference_detected with a causal claim allowed for this experiment only" if ok else "counts %s/%s outcome %s" % (counts(rep), t, (rep or {}).get("outcome"))
    check("o2 randomized difference", o2)

    def o3():
        rc, rep, t, _, _ = go("o3", n=(600, 600), p=(0.3, 0.3), sessions=12)
        ev_rows = len(out["o3"][2])
        ok = rc == 0 and counts(rep) == t and sum(v[0] for v in counts(rep).values()) == 1200 and ev_rows > 5000
        return ok, "unit of analysis: %d event rows across sessions, 1200 units counted once each" % ev_rows if ok else "counts %s/%s" % (counts(rep), t)
    check("o3 unit of analysis", o3)

    def o4():
        rc, rep, t, _, _ = go("o4", n=(700, 700), p=(0.3, 0.3), outside=90)
        pkg, A, E, _, _ = out["o4"]
        # immature: units assigned inside the cohort whose horizon ends after as_of
        pkg2 = dict(pkg, as_of="2026-09-04T00:00:00Z")
        p2 = write(tmp / "o4b", pkg2, A, E)
        rc2, rep2, _ = run(p2)
        cutoff = dt.datetime(2026, 9, 4, tzinfo=UTC) - dt.timedelta(days=H)
        mature = {"control": [0, 0], "treatment": [0, 0]}
        imm = 0
        for u, arm, at in A:
            t0 = dt.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            if CS <= t0 < CE:
                if t0 > cutoff:
                    imm += 1
                else:
                    mature[arm][0] += 1
        ok = rc == 0 and counts(rep) == t and rep["exclusions"]["outside_cohort"] == 90 and rc2 == 0 and rep2["exclusions"]["immature"] == imm \
            and [v[0] for v in counts(rep2).values()] == [mature["control"][0], mature["treatment"][0]] and imm > 100
        return ok, "fixed cohort: 90 units assigned before the window excluded; at an earlier as_of %d immature units excluded, not counted as non-retained" % imm if ok \
            else "outside %s immature %s/%s" % ((rep or {}).get("exclusions", {}).get("outside_cohort"), (rep2 or {}).get("exclusions", {}).get("immature"), imm)
    check("o4 fixed cohort and immature units", o4)

    def o5():
        rc, rep, t, cont, _ = go("o5", n=(1000, 1000), p=(0.2, 0.2), contaminated=20, unassigned=30)
        ex = (rep or {}).get("exclusions", {})
        rc2, rep2, t2, cont2, _ = go("o5b", n=(500, 500), p=(0.2, 0.4), contaminated=200)
        ok = rc == 0 and counts(rep) == t and ex.get("multiple_arms") == cont and ex.get("events_before_assignment", 0) >= 2000 \
            and ex.get("events_after_horizon", 0) > 1000 and ex.get("events_unassigned_units") == 30 and close(rep, t) \
            and rc2 == 0 and rep2["outcome"] == "invalid_experiment" and rep2["claims_allowed"]["causal"] is False
        return ok, "leakage: pre-assignment and post-horizon events never count, units in both arms excluded and named, unassigned events counted; 200 contaminated units invalidate the readout" if ok \
            else "counts %s/%s ex %s outcome2 %s" % (counts(rep), t, {k: (v if not isinstance(v, list) else len(v)) for k, v in ex.items()}, (rep2 or {}).get("outcome"))
    check("o5 leakage checks", o5)

    def o6():
        rc, rep, t, _, _ = go("o6", n=(1000, 1300), p=(0.2, 0.35))
        ok = rc == 0 and rep["outcome"] == "invalid_experiment" and rep["srm"]["mismatch"] is True and rep["claims_allowed"] == {"causal": False, "significance": False}
        rc2, rep2, t2, _, _ = go("o6b", n=(1000, 1300), p=(0.2, 0.35), split=(1000 / 2300, 1300 / 2300))
        ok = ok and rc2 == 0 and rep2["outcome"] == "difference_detected"
        return ok, "sample ratio 1000/1300 against 50/50: invalid_experiment despite a large lift; the same counts with that planned split read normally" if ok else "outcomes %s %s" % ((rep or {}).get("outcome"), (rep2 or {}).get("outcome"))
    check("o6 sample ratio mismatch", o6)

    def o7():
        rc, rep, t, _, _ = go("o7", n=(150, 150), p=(0.1, 0.6))
        ok = rc == 0 and rep["outcome"] == "insufficient_information" and counts(rep) == t and rep["claims_allowed"] == {"causal": False, "significance": False}
        return ok, "150 units per arm under a 200 minimum: insufficient_information even with a large observed gap" if ok else "outcome %s" % (rep or {}).get("outcome")
    check("o7 insufficient information", o7)

    def o8():
        rc, rep, t, _, _ = go("o8", n=(2000, 2000), p=(0.2, 0.3), assignment="observational")
        ok = rc == 0 and rep["outcome"] == "association_only" and rep["claims_allowed"] == {"causal": False, "significance": True} and close(rep, t)
        return ok, "observational assignment: association_only, no causal claim" if ok else "outcome %s" % (rep or {}).get("outcome")
    check("o8 no causal claim without randomization", o8)

    def o9():
        pkg, A, E, t, _ = out["o2"]
        A2 = A + [r[:] for r in A[:300]] + [[r[0], r[1], iso(dt.datetime.strptime(r[2], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) + dt.timedelta(hours=3))] for r in A[300:600]]
        E2 = E + E[:2000]
        random.Random(a.seed).shuffle(A2)
        random.Random(a.seed + 1).shuffle(E2)
        rc1, r1, o1_ = run(tmp / "o2" / "package.json")
        rc2, r2, _ = run(write(tmp / "o9", pkg, A2, E2))
        rc3, _, o3_ = run(tmp / "o2" / "package.json")
        keys = ("arms", "effect", "outcome", "srm")
        ok = rc1 == rc2 == rc3 == 0 and all(r1[k] == r2[k] for k in keys) and o1_ == o3_ and r2["exclusions"]["repeat_assignment_rows"] == 600
        return ok, "re-sent assignment rows (same arm, later time) and duplicated events: same readout; rerun byte-identical" if ok else "differs %s" % [k for k in keys if (r1 or {}).get(k) != (r2 or {}).get(k)]
    check("o9 repeated import stable", o9)

    def o10():
        o = tmp / "o10.json"
        o.write_text("previous\n")
        pkg = out["o2"][0]
        bads = [dict(pkg, schema="x"), dict(pkg, arms=["a"]), dict(pkg, planned_split=[0.6, 0.6]), dict(pkg, assignment="maybe"),
                dict(pkg, cohort={"start": iso(CE), "end": iso(CS)}), dict(pkg, assignments={"file": "../x.csv"}), dict(pkg, extra=1),
                dict(pkg, outcome={"event": "retained", "horizon_days": 0})]
        rcs = []
        for i, b in enumerate(bads):
            (tmp / "o2" / ("bad%d.json" % i)).write_text(json.dumps(b))
            rcs.append(run(tmp / "o2" / ("bad%d.json" % i), out=o)[0])
        kept = o.read_text() == "previous\n"
        rc, _, _ = run(tmp / "o2" / "package.json", out=o)
        rec = rc == 0 and json.loads(o.read_text())["outcome"] == "difference_detected"
        ok = rcs == [2] * 8 and kept and rec
        return ok, "eight invalid packages exit 2 and keep the previous report; the next valid run writes it" if ok else "rcs %s kept %s rec %s" % (rcs, kept, rec)
    check("o10 invalid input and recovery", o10)

    if not a.quick:
        def o11():
            t0 = time.time()
            rc, rep, t, _, _ = go("o11", n=(60000, 60000), p=(0.30, 0.31), sessions=2)
            el = time.time() - t0
            ok = rc == 0 and counts(rep) == t and close(rep, t) and el < 120
            return ok, "120 000 units, %d event rows: exact counts and interval in %.1fs (incl. generation)" % (len(out["o11"][2]), el) if ok else "rc %s %.1fs" % (rc, el)
        check("o11 operational scale", o11)

    def o12():
        g = tmp / "guard"
        g.mkdir()
        (g / "sitecustomize.py").write_text("import socket\ndef _d(*a, **k):\n    raise RuntimeError('network denied')\nsocket.socket = _d\nsocket.create_connection = _d\n")
        before = tree(tmp / "o2")
        rc, rep, _ = run(tmp / "o2" / "package.json", env=dict(os.environ, PYTHONPATH=str(g), PYTHONDONTWRITEBYTECODE="1"))
        ok = rc == 0 and tree(tmp / "o2") == before and rep["outcome"] == "difference_detected"
        return ok, "socket-denying guard; package folder byte-identical" if ok else "rc %s" % rc
    check("o12 offline and read-only", o12)

    n = sum(RESULTS)
    print("%s: %d/%d checks passed (seed %d)" % ("ACCEPTED" if n == len(RESULTS) else "REJECTED", n, len(RESULTS), a.seed))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
