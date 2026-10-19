"""M08 concurrency follow-up 2 (Grok self-validation): when two overlapping r3-broken deploys leave r2 live on damaged data with no journal, is the approved rollback to r1 still available and correct? Stops at the first damaged case (up to 40 trials). Derived from m08_race_followup.py. Earlier header: M08 concurrency follow-up (Grok self-validation). Usage: PY m08_race_followup.py REPO OUT.json.
After two overlapping deploys (harness as m08_race_sweep.py), does the documented recovery path give a consistent target?
A) r3-broken twice from r2 at 0-15 ms offsets: if a journal is pending, run `recover`; then check live release and data vs r2.
B) r2 twice from r1 at 0-60 ms offsets: when both report deployed, run the approved rollback to r1; check live release and data vs r1."""
import json, os, sqlite3, subprocess, sys, tempfile, time, shutil
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]; PY = sys.executable
TOOL = REPO / "employees/engineering/devops-engineer/local_deploy.py"; MW = REPO / "examples/capabilities/G08/make_world.py"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}; TOP = Path(tempfile.mkdtemp(prefix="m08racef-", dir="/tmp"))
LAUNCH = "import os,sys,time\nt=float(sys.argv[1])\nwhile time.time()<t: pass\nos.execv(sys.argv[2], sys.argv[2:])\n"
def T(w, *a): return subprocess.run([PY, str(TOOL)] + list(a), cwd=w, env=ENV, capture_output=True, text=True).returncode
def data(w):
    c = sqlite3.connect("file:%s?mode=ro" % (w / "env/data/app.db"), uri=True)
    try: return [c.execute("PRAGMA user_version").fetchone()[0], [list(r) for r in c.execute("SELECT * FROM orders ORDER BY id")]]
    finally: c.close()
def live(w): c = w / "env/current"; return os.readlink(str(c)).split("/")[-1] if c.is_symlink() else None
def race(w, plan, off):
    t0 = time.time() + 0.5
    ps = [subprocess.Popen([PY, "-c", LAUNCH, "%.4f" % (t0 + d / 1000.0), PY, str(TOOL), "deploy", "plan-%s.json" % plan, "--approval", "approval-%s.json" % plan], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for d in (0, off)]
    return [p.wait(120) for p in ps]
res = []
for i in range(40):
    off = (4, 6, 8, 10, 12)[i % 5]; w = TOP / ("C-%d" % i); subprocess.run([PY, str(MW), str(w)], env=ENV, capture_output=True, check=True)
    T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); d1 = data(w); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); d2 = data(w)
    rcs = race(w, "r3-broken", off); pend = (w / "env/.deploy/journal.json").exists()
    if live(w) == "r2" and not pend and data(w) != d2:
        st = {"trial": i, "offset_ms": off, "rcs": rcs, "uv": data(w)[0], "totals": [r[2] for r in data(w)[1]], "recover_rc": T(w, "recover", "plan-r2.json")}
        st["rollback_rc"] = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"); st["after_rollback"] = {"live": live(w), "data_is_r1": data(w) == d1, "uv": data(w)[0]}
        st["redeploy_r2_rc"] = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); st["after_redeploy"] = {"live": live(w), "data_is_r2": data(w) == d2}
        res.append(st); break
    shutil.rmtree(w, ignore_errors=True)
shutil.rmtree(TOP, ignore_errors=True); json.dump(res, open(OUT, "w"), indent=1); print("damaged case found:", bool(res)); [print(json.dumps(r)) for r in res]
