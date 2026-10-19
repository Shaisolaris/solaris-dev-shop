"""M08 concurrency sweep (Grok self-validation, recorded evidence for the documented 'no lock between two deploys' limit).
Usage: PY m08_race_sweep.py REPO OUT.json. Two deploys of one target: A starts, B starts OFFSET ms later (0-150 ms in 5 ms
steps, 2 trials each). Cases: r2 twice from r1 (migration adds a column), and r3-broken twice from r2 (migration multiplies
totals by 100, then health fails and the data is restored). Records exit codes, live release, schema version, totals,
pending journal, and whether a later rollback/preflight is still consistent."""
import json, os, sqlite3, subprocess, sys, tempfile, time, shutil
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]; PY = sys.executable
TOOL = REPO / "employees/engineering/devops-engineer/local_deploy.py"; MW = REPO / "examples/capabilities/G08/make_world.py"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}; TOP = Path(tempfile.mkdtemp(prefix="m08race-", dir="/tmp"))
LAUNCH = "import os,sys,time\nt=float(sys.argv[1])\nwhile time.time()<t: pass\nos.execv(sys.argv[2], sys.argv[2:])\n"
def T(w, *a): return subprocess.run([PY, str(TOOL)] + list(a), cwd=w, env=ENV, capture_output=True, text=True).returncode
def data(w):
    c = sqlite3.connect("file:%s?mode=ro" % (w / "env/data/app.db"), uri=True)
    try: return c.execute("PRAGMA user_version").fetchone()[0], [r[2] for r in c.execute("SELECT * FROM orders ORDER BY id")], [d[1] for d in c.execute("PRAGMA table_info(orders)")]
    finally: c.close()
def live(w): c = w / "env/current"; return os.readlink(str(c)).split("/")[-1] if c.is_symlink() else None
res = []
for case, base, plan in (("r2x2_from_r1", 1, "r2"), ("r3brokenx2_from_r2", 2, "r3-broken")):
    for off in range(0, 151, 5):
        for k in range(2):
            w = TOP / ("%s-%d-%d" % (case, off, k)); subprocess.run([PY, str(MW), str(w)], env=ENV, capture_output=True, check=True)
            T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json")
            if base == 2: T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
            before = data(w); t0 = time.time() + 0.5
            ps = [subprocess.Popen([PY, "-c", LAUNCH, "%.4f" % (t0 + d / 1000.0), PY, str(TOOL), "deploy", "plan-%s.json" % plan, "--approval", "approval-%s.json" % plan], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True) for d in (0, off)]
            out = [(p.wait(120), p.stderr.read()[-200:]) for p in ps]
            after = data(w); pend = (w / "env/.deploy/journal.json").exists()
            r = {"case": case, "offset_ms": off, "trial": k, "rcs": [o[0] for o in out], "tracebacks": [o[1] for o in out if o[0] not in (0, 1, 2)], "live": live(w), "pending": pend,
                 "uv": after[0], "totals": after[1], "columns": after[2], "data_changed_vs_before": after != before}
            if case == "r3brokenx2_from_r2": r["bad"] = after != before or live(w) != "r2" or pend
            else: r["bad"] = sorted(r["rcs"]) not in ([0, 2], [0, 0]) or pend or live(w) != "r2" or after[0] != 2 or after[2].count("note") != 1
            res.append(r); shutil.rmtree(w, ignore_errors=True)
shutil.rmtree(TOP, ignore_errors=True); json.dump(res, open(OUT, "w"), indent=1)
bad = [r for r in res if r["bad"]]; print("SWEEP trials %d, inconsistent %d" % (len(res), len(bad)))
for r in bad[:12]: print(json.dumps(r)[:400])
from collections import Counter; print("rcs by case:", {c: Counter(tuple(sorted(r["rcs"])) for r in res if r["case"] == c).most_common() for c in ("r2x2_from_r1", "r3brokenx2_from_r2")})
