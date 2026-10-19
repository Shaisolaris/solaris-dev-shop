#!/usr/bin/env python3
"""M08 r2 lock and repeat-gate probes (Grok self-validation, black box, written from the r2 doc text).
Usage: PY m08r2_lock.py REPO [--tool TOOL] OUT.json. Core rows (L*) score; OBS rows record only.
Doc expectations: deploy, rollback and recover hold an exclusive non-blocking flock on the target folder for the
whole command; a second caller is refused with exit 2 and nothing changed; the kernel drops the lock at process end
(SIGKILL included); preflight and status take no lock and write nothing; a repeat deploy of the live release is exit 0
only when approved and healthy, else exit 2, and changes nothing either way."""
import fcntl, hashlib, json, os, signal, sqlite3, subprocess, sys, tempfile, time, shutil
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/engineering/devops-engineer/local_deploy.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; MW = REPO / "examples/capabilities/G08/make_world.py"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}; TOP = Path(tempfile.mkdtemp(prefix="m08r2lk-", dir="/tmp")).resolve(); rows = []
LAUNCH = "import os,sys,time\nt=float(sys.argv[1])\nwhile time.time()<t: pass\nos.execv(sys.argv[2], sys.argv[2:])\n"
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
def T(w, *x): p = subprocess.run([PY, str(TOOL)] + list(x), cwd=w, env=ENV, capture_output=True, text=True, timeout=120); return p.returncode, p.stdout + p.stderr
def world(tag):
    d = TOP / tag / "w"; d.parent.mkdir(parents=True); subprocess.run([PY, str(MW), str(d)], env=ENV, capture_output=True, check=True); return d
def tree(d):
    out = {}
    for p in sorted(Path(d).rglob("*")):
        k = str(p.relative_to(d)); out[k] = "L:" + os.readlink(str(p)) if p.is_symlink() else ("D" if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest())
    return out
def data(w):
    c = sqlite3.connect("file:%s?mode=ro" % (w / "env/data/app.db"), uri=True)
    try: return [c.execute("PRAGMA user_version").fetchone()[0], [list(r) for r in c.execute("SELECT * FROM orders ORDER BY id")]]
    finally: c.close()
def live(w): c = w / "env/current"; return os.readlink(str(c)).split("/")[-1] if c.is_symlink() else None
def pending(w): return (w / "env/.deploy/journal.json").exists()
def hist(w):
    h = w / "env/.deploy/history.jsonl"; return [json.loads(x) for x in h.read_text().splitlines()] if h.exists() else []
def race(w, cmds, offs):
    t0 = time.time() + 0.5
    ps = [subprocess.Popen([PY, "-c", LAUNCH, "%.4f" % (t0 + o / 1000.0), PY, str(TOOL)] + c, cwd=w, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for c, o in zip(cmds, offs)]
    return [(p.wait(120), p.stdout.read()) for p in ps]
def l01():  # deploy r3-broken racing rollback to r1, from r2 live: one side refused by the lock or both serialised; never mixed
    res = []; bad = []
    for k, off in enumerate((0, 0, 1, 2, 3, 5, 8, 10, 15, 20, 30, 50)):
        w = world("l01-%d" % k); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); d1 = data(w); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); d2 = data(w)
        (dep, dout), (rb, rout) = race(w, [["deploy", "plan-r3-broken.json", "--approval", "approval-r3-broken.json"], ["rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"]], (0, off))
        lv, dd = live(w), data(w); ok = not pending(w) and ((lv == "r1" and dd == d1) or (lv == "r2" and dd == d2))
        lock_refusal = ("holds the lock" in dout and dep == 2) or ("holds the lock" in rout and rb == 2)
        r = {"off": off, "rcs": [dep, rb], "live": lv, "consistent": ok, "lock_refusal": lock_refusal}; res.append(r)
        if not ok: bad.append(r)
        shutil.rmtree(w.parent)
    row("L01_deploy_vs_rollback_race", not bad, {"trials": len(res), "lock_refusals": sum(r["lock_refusal"] for r in res), "inconsistent": bad, "rc_pairs": sorted(set(tuple(r["rcs"]) for r in res))})
def l02():  # two recovers racing on a pending journal: exactly one rolls back, the other is refused or finds nothing; final r2, r2 data
    res = []; bad = []
    for k, off in enumerate((0, 0, 1, 3, 5, 10)):
        w = world("l02-%d" % k); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); d2 = data(w)
        T(w, "deploy", "plan-r3-broken.json", "--approval", "approval-r3-broken.json", "--fail-at", "migrated")
        out = race(w, [["recover", "plan-r2.json"], ["recover", "plan-r2.json"]], (0, off)); rcs = sorted(r for r, _ in out)
        ok = live(w) == "r2" and data(w) == d2 and not pending(w) and rcs in ([0, 1], [1, 2])
        r = {"off": off, "rcs": rcs, "live": live(w), "pending": pending(w)}; res.append(r)
        if not ok: bad.append(r)
        shutil.rmtree(w.parent)
    row("L02_recover_vs_recover_race", not bad, {"trials": len(res), "rc_pairs": sorted(set(tuple(r["rcs"]) for r in res)), "bad": bad})
def l03():  # a held lock (outside holder) refuses deploy, rollback and recover fast with the tree identical; preflight and status still answer and write nothing
    w = world("l03"); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    fd = os.open(str(w / "env"), os.O_RDONLY); fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); before = tree(w); res = {}
    try:
        for name, args in (("deploy", ["deploy", "plan-r3-broken.json", "--approval", "approval-r3-broken.json"]), ("repeat", ["deploy", "plan-r2.json", "--approval", "approval-r2.json"]),
                           ("rollback", ["rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"]), ("recover", ["recover", "plan-r2.json"]),
                           ("preflight", ["preflight", "plan-r2.json", "--approval", "approval-r2.json"]), ("status", ["status", "plan-r2.json"])):
            t = time.time(); rc, out = T(w, *args); res[name] = {"rc": rc, "secs": round(time.time() - t, 2), "lock_msg": "holds the lock" in out}
        after = tree(w)
    finally: os.close(fd)
    ok = all(res[k]["rc"] == 2 and res[k]["lock_msg"] and res[k]["secs"] < 10 for k in ("deploy", "repeat", "rollback", "recover")) and res["preflight"]["rc"] == 0 and res["status"]["rc"] == 0 and before == after
    row("L03_held_lock_refuses_mutators_only", ok, dict(res, tree_identical=before == after)); shutil.rmtree(w.parent)
def l04():  # target reached through a symlink alias: the lock is on the folder, so an aliased plan must serialise with the direct one
    res = []; bad = []; refused = 0
    for k, off in enumerate((0, 0, 1, 2, 4, 8)):
        w = world("l04-%d" % k); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); os.symlink("env", str(w / "envlink"))
        p = json.loads((w / "plan-r2.json").read_text()); p["target"] = "envlink"; (w / "plan-r2-alias.json").write_text(json.dumps(p))
        out = race(w, [["deploy", "plan-r2.json", "--approval", "approval-r2.json"], ["deploy", "plan-r2-alias.json", "--approval", "approval-r2.json"]], (0, off))
        n = sum(1 for e in hist(w) if e.get("event") == "deployed" and e.get("revision") == "r2"); rcs = [r for r, _ in out]
        alias_refused_by_preflight = rcs[1] == 2 and "holds the lock" not in out[1][1]
        refused += alias_refused_by_preflight; r = {"off": off, "rcs": rcs, "r2_deployed_events": n, "alias_refused_not_by_lock": alias_refused_by_preflight}; res.append(r)
        if n != 1 or live(w) != "r2": bad.append(r)
        shutil.rmtree(w.parent)
    row("L04_symlink_alias_target_serialised", not bad, {"trials": res, "bad": bad})
def l05():  # SIGKILL mid-deploy leaves no stale lock: recover right after is not refused by the lock and restores r2
    res = []; bad = []
    for k, delay in enumerate((0.15, 0.25, 0.35, 0.5)):
        w = world("l05-%d" % k); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); d2 = data(w)
        p = subprocess.Popen([PY, str(TOOL), "deploy", "plan-r3-broken.json", "--approval", "approval-r3-broken.json"], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(delay); p.send_signal(signal.SIGKILL); p.wait()
        rc, out = T(w, "recover", "plan-r2.json"); r = {"delay": delay, "recover_rc": rc, "lock_msg": "holds the lock" in out, "live": live(w), "data_r2": data(w) == d2, "pending": pending(w)}; res.append(r)
        if r["lock_msg"] or r["pending"] or r["live"] != "r2" or not r["data_r2"]: bad.append(r)
        shutil.rmtree(w.parent)
    row("L05_no_stale_lock_after_sigkill", not bad, {"trials": res})
def l06():  # SIGSTOPped holder: a second deploy is refused at once (non-blocking), the stopped one finishes after SIGCONT
    w = world("l06"); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json")
    p = subprocess.Popen([PY, str(TOOL), "deploy", "plan-r2.json", "--approval", "approval-r2.json"], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.12); p.send_signal(signal.SIGSTOP); t = time.time(); rc, out = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); secs = round(time.time() - t, 2)
    p.send_signal(signal.SIGCONT); rc1 = p.wait(60); n = sum(1 for e in hist(w) if e.get("event") == "deployed" and e.get("revision") == "r2")
    row("L06_stopped_holder_nonblocking", rc == 2 and "holds the lock" in out and secs < 10 and rc1 == 0 and n == 1 and live(w) == "r2", {"second_rc": rc, "secs": secs, "lock_msg": "holds the lock" in out, "first_rc": rc1, "r2_events": n})
    shutil.rmtree(w.parent)
def l07():  # repeat-deploy gate on live r2: refusals and the approved healthy case all leave the tree byte-identical
    w = world("l07"); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); res = {}
    def probe(name, *args):
        b = tree(w); rc, out = T(w, *args); res[name] = {"rc": rc, "identical": tree(w) == b}
    probe("no_approval", "deploy", "plan-r2.json"); probe("approval_for_r1", "deploy", "plan-r2.json", "--approval", "approval-r1.json")
    probe("rollback_approval_as_deploy", "deploy", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"); probe("approved_healthy", "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    ap = json.loads((w / "approval-r2.json").read_text()); ap["environment"] = "prod"; (w / "approval-r2-prod.json").write_text(json.dumps(ap)); probe("approval_other_env", "deploy", "plan-r2.json", "--approval", "approval-r2-prod.json")
    os.remove(str(w / "env/current") + "/index.html") if (w / "env/current/index.html").exists() else None; probe("live_missing_required_file", "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    ok = all(v["identical"] for v in res.values()) and res["approved_healthy"]["rc"] == 0 and all(res[k]["rc"] == 2 for k in res if k != "approved_healthy")
    row("L07_repeat_gate", ok, res); shutil.rmtree(w.parent)
def l08():  # repeat after an outside writer changed live data schema (the M08 P3-2 case): exit 2, nothing changed; status still reports r2
    w = world("l08"); T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json"); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    c = sqlite3.connect(str(w / "env/data/app.db")); c.execute("PRAGMA user_version=3"); c.commit(); c.close(); b = tree(w)
    rc, out = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); rc2, _ = T(w, "deploy", "plan-r2.json")
    row("L08_repeat_unhealthy_refused", rc == 2 and rc2 == 2 and tree(w) == b, {"approved_rc": rc, "no_approval_rc": rc2, "identical": tree(w) == b}); shutil.rmtree(w.parent)
for rid, fn in (("L01", l01), ("L02", l02), ("L03", l03), ("L04", l04), ("L05", l05), ("L06", l06), ("L07", l07), ("L08", l08)):
    try: fn()
    except Exception as e: row(rid + "_crash", False, "harness or tool crash: %r" % (e,))
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:1200])
print("M08R2 LOCK %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
