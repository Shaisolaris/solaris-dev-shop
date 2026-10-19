"""M08 concurrency follow-up (Grok self-validation). Usage: PY m08_race_followup.py REPO OUT.json.
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
for off in (0, 2, 4, 5, 6, 8, 10, 12, 15):
    for k in range(3):
        w = TOP / ("A-%d-%d" % (off, k)); subprocess.run([PY, str(MW), str(w)], env=ENV, capture_output=True, check=True)
        T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); d2 = data(w)
        rcs = race(w, "r3-broken", off); st = {"live": live(w), "pending": (w / "env/.deploy/journal.json").exists(), "data_is_r2": data(w) == d2, "uv": data(w)[0]}
        rec = T(w, "recover", "plan-r2.json") if st["pending"] else None
        fin = {"live": live(w), "data_is_r2": data(w) == d2, "uv": data(w)[0], "totals": [r[2] for r in data(w)[1]], "pending": (w / "env/.deploy/journal.json").exists()}
        nxt = T(w, "preflight", "plan-r3-badmigration.json", "--approval", "approval-r3-badmigration.json")
        res.append({"case": "A", "offset_ms": off, "trial": k, "rcs": rcs, "after_race": st, "recover_rc": rec, "final": fin, "next_preflight_rc": nxt,
                    "bad": not (fin["live"] == "r2" and fin["data_is_r2"] and not fin["pending"])})
        shutil.rmtree(w, ignore_errors=True)
for off in (0, 10, 20, 30, 40, 50, 60):
    for k in range(2):
        w = TOP / ("B-%d-%d" % (off, k)); subprocess.run([PY, str(MW), str(w)], env=ENV, capture_output=True, check=True)
        T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); d1 = data(w)
        rcs = race(w, "r2", off); h = [json.loads(x) for x in (w / "env/.deploy/history.jsonl").read_text().splitlines()]
        rb = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json")
        fin = {"live": live(w), "data_is_r1": data(w) == d1, "uv": data(w)[0]}
        res.append({"case": "B", "offset_ms": off, "trial": k, "rcs": rcs, "deployed_r2_events": sum(1 for e in h if e.get("event") == "deployed" and e.get("revision") == "r2"),
                    "rollback_rc": rb, "final": fin, "bad": rb == 0 and not (fin["live"] == "r1" and fin["data_is_r1"])})
        shutil.rmtree(w, ignore_errors=True)
shutil.rmtree(TOP, ignore_errors=True); json.dump(res, open(OUT, "w"), indent=1)
for c in "AB":
    rs = [r for r in res if r["case"] == c]; print("CASE %s trials %d inconsistent after documented recovery %d" % (c, len(rs), sum(r["bad"] for r in rs)))
    for r in [r for r in rs if r["bad"]][:6]: print("  " + json.dumps(r)[:420])
