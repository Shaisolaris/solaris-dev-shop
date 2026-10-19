"""M02 r2 operational depth (Grok self-validation): external SIGKILL at random times during a changed intake,
documented recovery, then checks; plus activate-vs-resume races and a copied-template stress.
Usage: python m02r2_operational.py ITER -- <python> <activate.py>"""
import json, os, random, shutil, signal, subprocess, sys, tempfile, threading, time
from pathlib import Path
ITER = int(sys.argv[1]); CMD = sys.argv[3:]
J, LOCK = ".solaris-activation.json", ".solaris-activation.lock"
FILES = ("STATUS.md", "Scope/ROUND-PLAN.md", "Delivery/CREDENTIALS.md")
random.seed(20261019)
def run(*a):
    p = subprocess.run(CMD + [str(x) for x in a] + ["--json"], capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    try: return p.returncode, json.loads(p.stdout), p.stderr
    except ValueError: return p.returncode, None, p.stderr
def names(r):
    s = set()
    for f in FILES:
        t = (r / f).read_text() if (r / f).is_file() else ""
        s |= {n for n in ("Alpha Corp", "Beta LLC") if n in t}
    return s
T = Path(tempfile.mkdtemp(prefix="m02r2-op-")).resolve()
stats = dict(iters=0, killed_mid=0, finished_before_kill=0, stale_lock_deleted=0, mixed_after_kill=0, temps_after_kill=0,
             conv_beta=0, conv_alpha=0, bad=0, tracebacks=0)
bad = []
for i in range(ITER):
    r = T / f"it{i}"
    rc, js, _ = run("activate", r, "--name", "Alpha Corp", "--type", "web app", "--deploy-model", "alpha: main=live")
    assert js and js["status"] == "complete", js
    (r / "Assets").mkdir(exist_ok=True); (r / "Assets/owner.png").write_bytes(b"owner")
    p = subprocess.Popen(CMD + ["activate", str(r), "--name", "Beta LLC", "--type", "website", "--deploy-model", "beta: tags", "--json"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    time.sleep(random.uniform(0.015, 0.06))
    if p.poll() is None:
        p.send_signal(signal.SIGKILL); stats["killed_mid"] += 1
    else:
        stats["finished_before_kill"] += 1
    p.communicate()
    if len(names(r)) > 1: stats["mixed_after_kill"] += 1
    if list(r.rglob("*.activation-tmp")): stats["temps_after_kill"] += 1
    if os.path.lexists(r / LOCK):
        rc, js, err = run("resume", r)
        if not (js and js["status"] == "blocked" and "stale" in json.dumps(js.get("errors"))):
            bad.append(f"it{i}: lock left but not reported stale: {js and js.get('errors')}")
        os.unlink(r / LOCK); stats["stale_lock_deleted"] += 1
    rc, js, err = run("resume", r)
    if "Traceback" in err: stats["tracebacks"] += 1
    nm = names(r)
    ok = js and js["status"] == "complete" and len(nm) == 1 and not list(r.rglob("*.activation-tmp")) \
        and not os.path.lexists(r / LOCK) and (r / "Assets/owner.png").read_bytes() == b"owner"
    if ok:
        before = {f: (r / f).read_bytes() for f in FILES}
        rc2, js2, _ = run("resume", r)
        ok = js2 and js2["status"] == "complete" and all((r / f).read_bytes() == v for f, v in before.items())
    if not ok:
        stats["bad"] += 1; bad.append(f"it{i}: status={js and js['status']} names={nm} temps={list(r.rglob('*.activation-tmp'))}")
    else:
        stats["conv_beta" if "Beta LLC" in nm else "conv_alpha"] += 1
    stats["iters"] += 1
    shutil.rmtree(r)
# activate vs resume races
race_bad = 0
for k in range(12):
    r = T / f"race{k}"
    run("activate", r, "--name", "Alpha Corp", "--type", "web app", "--deploy-model", "x")
    out = []
    th = [threading.Thread(target=lambda: out.append(run("activate", r, "--name", "Beta LLC", "--deploy-model", "y"))),
          threading.Thread(target=lambda: out.append(run("resume", r)))]
    [t.start() for t in th]; [t.join() for t in th]
    if len(names(r)) != 1 or os.path.lexists(r / LOCK) or list(r.rglob("*.activation-tmp")) or any("Traceback" in o[2] for o in out):
        race_bad += 1
# template stress: one live project copied to 30 new clients in parallel, none inherits live deploy
src = T / "template"; run("activate", src, "--name", "Alpha Corp", "--type", "web app", "--deploy-model", "production: main=live")
copies = [T / f"client{i:02d}" for i in range(30)]
for c in copies: shutil.copytree(src, c, symlinks=True)
res = [None] * 30
def go(i): res[i] = run("activate", copies[i], "--name", f"Client {i:02d}", "--type", "website")
th = [threading.Thread(target=go, args=(i,)) for i in range(30)]; [t.start() for t in th]; [t.join() for t in th]
leak = sum(1 for i, c in enumerate(copies) if "main=live" in (c / "STATUS.md").read_text() or (res[i][1] or {}).get("status") == "complete")
shutil.rmtree(T, ignore_errors=True)
print(json.dumps(stats))
print(f"activate_vs_resume_races 12 bad {race_bad}")
print(f"template_copies 30 parallel: live deploy leaked or complete in {leak}")
for b in bad[:20]: print("BAD", b)
ok = stats["bad"] == 0 and stats["tracebacks"] == 0 and not bad and race_bad == 0 and leak == 0
print("OPERATIONAL", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
