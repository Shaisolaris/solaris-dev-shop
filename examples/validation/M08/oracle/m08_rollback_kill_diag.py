"""M08 diagnosis (Grok self-validation): SIGKILL an approved rollback r2->r1 at a random point (journal-free, as documented),
stop at the first case where a second rollback is refused, and print why (rollback and deploy preflight checks), plus the data
folder listing. Usage: PY m08_rollback_kill_diag.py REPO"""
import json, os, random, signal, sqlite3, subprocess, sys, tempfile, time, shutil
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); PY = sys.executable; TOOL = REPO / "employees/engineering/devops-engineer/local_deploy.py"; MW = REPO / "examples/capabilities/G08/make_world.py"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}; TOP = Path(tempfile.mkdtemp(prefix="m08rkd-", dir="/tmp"))
def T(w, *a): p = subprocess.run([PY, str(TOOL)] + list(a), cwd=w, env=ENV, capture_output=True, text=True); return p.returncode, p.stdout
random.seed(3)
for i in range(150):
    w = TOP / ("k%d" % i); subprocess.run([PY, str(MW), str(w)], env=ENV, capture_output=True, check=True)
    T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    p = subprocess.Popen([PY, str(TOOL), "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(random.uniform(0.0, 0.11)); p.send_signal(signal.SIGKILL); p.wait()
    still_r2 = os.readlink(str(w / "env/current")).endswith("r2")  # v2: v1 stopped on a completed rollback (expected refusal); look only at kills that left r2 live
    rc, out = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json", "--json")
    if rc == 2 and still_r2:
        c = sqlite3.connect("file:%s?mode=ro" % (w / "env/data/app.db"), uri=True); uv = c.execute("PRAGMA user_version").fetchone()[0]; c.close()
        print("trial", i, "live", os.readlink(str(w / "env/current")), "uv", uv)
        print("rollback refused:", [(x["check"], x["detail"][:140]) for x in json.loads(out)["checks"] if not x["ok"]])
        rc2, out2 = T(w, "preflight", "plan-r2.json", "--approval", "approval-r2.json", "--json")
        try: print("preflight r2:", rc2, [(x["check"], x["detail"][:140]) for x in json.loads(out2)["checks"] if not x["ok"]])
        except Exception: print("preflight r2:", rc2, out2[:300])
        print("data dir:", sorted(x.name for x in (w / "env/data").iterdir())); print("recover:", T(w, "recover", "plan-r2.json")[0])
        hist = [json.loads(x) for x in (w / "env/.deploy/history.jsonl").read_text().splitlines()]; print("history events:", [(h["event"], h.get("revision")) for h in hist])
        break
else: print("no stuck case in 150 trials")  # v2 note: the v2 run printed the stale v1 text "60 trials"; it ran 150
shutil.rmtree(TOP, ignore_errors=True)
