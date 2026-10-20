"""M11 h1 probe (Grok self-validation): supplied G10 traces that cannot be used, against one tree.

python m11h1_probe.py ROOT  -> one line per case, JSON summary last; exit 0 when every expectation holds.
Bundles are copies of the G11 fixtures with G10 fixture traces; everything is written to a temp folder.
"""
import json, os, shutil, subprocess, sys, tempfile
ROOT = sys.argv[1]
IS = os.path.join(ROOT, "employees/infrastructure/site-reliability-engineer/incident_slo.py")
G10 = os.path.join(ROOT, "examples/capabilities/G10/fixtures")
G11 = os.path.join(ROOT, "examples/capabilities/G11/fixtures")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def g10(name, **kw):
    t = json.load(open(os.path.join(G10, name)))
    t.update(kw)
    return t


def run(fixture, traces, text=False):
    tmp = tempfile.mkdtemp(prefix="m11h1-")
    try:
        os.makedirs(tmp + "/traces")
        names = []
        for i, t in enumerate(traces):
            n = "traces/t%d.json" % i
            with open(os.path.join(tmp, n), "w") as fh:
                fh.write(t if isinstance(t, str) else json.dumps(t))
            names.append(n)
        b = json.load(open(os.path.join(G11, fixture)))
        if fixture == "06-migration-without-snapshot.json":
            pass
        b["diagnoses"] = names
        with open(tmp + "/b.json", "w") as fh:
            json.dump(b, fh)
        argv = [sys.executable, IS, "report", tmp + "/b.json"] + ([] if text else ["--json"])
        r = subprocess.run(argv, capture_output=True, text=True, env=ENV, timeout=300)
    finally:
        shutil.rmtree(tmp)
    if text:
        return r.returncode, r.stdout, r.stderr
    try:
        return r.returncode, json.loads(r.stdout), r.stderr
    except ValueError:
        return r.returncode, None, r.stderr


def rows(rep):
    return [t for t in rep["decision"]["trace"] if t["check"].startswith("G10")]


REG = "02-deploy-regression.json"
cases = []


def case(name, fixture, traces, want, need_rows=None, reason_has=()):
    rc, rep, err = run(fixture, traces)
    if rep is None:
        got = "refused rc=%s" % rc
        ok = want == "refused"
        cases.append({"case": name, "ok": ok, "got": got, "stderr": err.strip()[-200:]})
        return
    d = rep["decision"]
    rs = [r["result"] for r in rows(rep)]
    ok = rc == 0 and d["decision"] == want and (need_rows is None or rs == need_rows) and all(s in d["reason"] for s in reason_has)
    cases.append({"case": name, "ok": ok, "got": d["decision"], "want": want, "rows": rs, "reason": d["reason"][-220:]})


U = "unusable"
case("p0 regression without evidence still rolls back", REG, [], "rollback", [])
case("p1 untimed route trace", REG, [g10("04-route-blackhole.json", captured_at=None)], "insufficient_evidence", [U], ("route layer", "r42"))
case("p2 untimed tls trace", REG, [g10("06-tls-expired.json", captured_at=None)], "insufficient_evidence", [U], ("tls layer",))
case("p3 untimed probable tls, dns+tls candidates", REG, [g10("07-tls-name-mismatch-unverified-dns.json", captured_at=None)], "insufficient_evidence", [U])
case("p4 untimed probable tls, dns+route+tls candidates", REG, [g10("12-tls-fail-no-dns-evidence.json", captured_at=None)], "insufficient_evidence", [U])
case("p5 untimed undetermined (application is a candidate)", REG, [g10("10-incomplete-dns-only.json", captured_at=None)], "rollback", ["does not exclude the application"])
case("p6 untimed healthy trace", REG, [g10("01-clean-control.json", captured_at=None)], "rollback", ["does not exclude the application"])
case("p7 two refused traces, both named", REG, [g10("02-dns-nxdomain.json", captured_at="yesterday"), g10("06-tls-expired.json", captured_at="2026-13-40T99:00:00Z")],
     "insufficient_evidence", [U, U], ("traces/t0.json", "traces/t1.json"))
case("p8 trace file that is not JSON", REG, ["{not json"], "insufficient_evidence", [U])
case("p9 trace captured the next day", REG, [g10("02-dns-nxdomain.json", captured_at="2026-10-19T09:30:00Z")], "rollback", ["outside the impact, not used"])
case("p10 timed app trace in impact plus untimed dns", REG, [g10("09-app-upstream-503.json", captured_at="2026-10-18T09:30:00Z"), g10("02-dns-nxdomain.json", captured_at=None)],
     "insufficient_evidence", None)
case("p11 refused trace, no budget-burning impact (clean control)", "01-clean-control.json", [g10("02-dns-nxdomain.json", captured_at="yesterday")], "do_not_rollback", None)
case("p12 refused trace, migration without snapshot", "06-migration-without-snapshot.json", [g10("02-dns-nxdomain.json", captured_at="yesterday")], "insufficient_evidence", [U])
case("p13 G11 fixture 03 (timed dns in impact) unchanged", "03-dns-fault-during-impact.json", [g10("02-dns-nxdomain.json", captured_at="2026-10-18T09:30:00Z")], "do_not_rollback", ["fault outside the application"])
rc, out, err = run(REG, [g10("02-dns-nxdomain.json", captured_at=None)], text=True)
cases.append({"case": "p14 text report states the reason", "ok": rc == 0 and "insufficient_evidence" in out and "no capture time" in out, "got": "rc=%s" % rc})
for c in cases:
    print(("PASS " if c["ok"] else "FAIL ") + json.dumps(c))
bad = [c["case"] for c in cases if not c["ok"]]
print(json.dumps({"python": sys.version.split()[0], "cases": len(cases), "failed": bad}))
sys.exit(1 if bad else 0)
