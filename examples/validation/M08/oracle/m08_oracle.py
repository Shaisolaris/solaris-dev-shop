#!/usr/bin/env python3
"""M08 oracle (Grok self-validation, written by Grok, black box; expectations from local-deploy-preflight.md and
G08/README.md, never from the tool's output). Worlds come from the builder's make_world.py (fixture builder only).
Usage: PY m08_oracle.py REPO [--tool LOCAL_DEPLOY.py] OUT.json. Core rows (D*) score; OBS rows record only."""
import json, os, random, shutil, signal, sqlite3, subprocess, sys, tempfile, time, hashlib
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/engineering/devops-engineer/local_deploy.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; MW = REPO / "examples/capabilities/G08/make_world.py"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
TOP = Path(tempfile.mkdtemp(prefix="m08top-", dir="/tmp")).resolve(); rows = []
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
def guard(rid, f):
    try: f()
    except Exception as e: row(rid, False, "harness or tool crash: %r" % (e,))
def T(w, *x, timeout=120):
    p = subprocess.run([PY, str(TOOL)] + [str(y) for y in x], cwd=w, env=ENV, capture_output=True, text=True, timeout=timeout); return p.returncode
def world():
    d = Path(tempfile.mkdtemp(prefix="w-", dir=str(TOP))) / "w"; subprocess.run([PY, str(MW), str(d)], env=ENV, capture_output=True, check=True); return d
def tree(d):  # files (bytes), dirs and symlinks: a refusal must leave all three identical
    d = Path(d); out = {}
    for p in sorted(d.rglob("*")):
        k = str(p.relative_to(d))
        if p.is_symlink(): out[k] = "L:" + os.readlink(str(p))
        elif p.is_dir(): out[k] = "D"
        else: out[k] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out
def data(w):
    c = sqlite3.connect("file:%s?mode=ro" % (w / "env/data/app.db"), uri=True)
    try: return {"uv": c.execute("PRAGMA user_version").fetchone()[0], "rows": [list(r) for r in c.execute("SELECT * FROM orders ORDER BY id")]}
    finally: c.close()
def live(w):
    c = w / "env/current"; return os.readlink(str(c)).split("/")[-1] if c.is_symlink() else None
def leftovers(w):
    r = w / "env/releases"; return sorted(p.name for p in r.iterdir() if p.name.startswith(".staging")) if r.is_dir() else []
def pending(w): return (w / "env/.deploy/journal.json").exists()
def up_to(w, n):
    rc = [T(w, "deploy", "plan-r1.json", "--approval", "approval-r1.json")]
    if n >= 2: rc.append(T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"))
    return rc
def jw(p, o): Path(p).write_text(json.dumps(o, indent=2) + "\n")
def jr(p): return json.loads(Path(p).read_text())

def d01():
    w = world(); rc = up_to(w, 1); d1 = data(w); rc += [T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")]; d2 = data(w); l2 = live(w)
    rb = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"); d3 = data(w)
    ok = rc == [0, 0] and l2 == "r2" and d2["uv"] == 2 and rb == 0 and live(w) == "r1" and d3 == d1 and not pending(w)
    row("D01_clean_deploy_upgrade_rollback", ok, {"rcs": rc, "live_after_r2": l2, "uv_r2": d2["uv"], "rollback": rb, "live_after_rb": live(w), "data_back_to_r1": d3 == d1})
def d02():  # refusals leave the whole tree (files, dirs, links) identical
    res = {}
    def case(name, prep, cmd):
        w = world(); up_to(w, 1); prep(w); b = tree(w / "env"); rc = T(w, *cmd); res[name] = (rc, tree(w / "env") == b)
    def nop(w): pass
    case("no_approval", nop, ["deploy", "plan-r2.json"])
    case("approval_wrong_revision", lambda w: jw(w / "x.json", dict(jr(w / "approval-r2.json"), revision="r9")), ["deploy", "plan-r2.json", "--approval", "x.json"])
    case("approval_wrong_digest", lambda w: jw(w / "x.json", dict(jr(w / "approval-r2.json"), artifact_sha256="0" * 64)), ["deploy", "plan-r2.json", "--approval", "x.json"])
    case("approval_other_env", lambda w: jw(w / "x.json", dict(jr(w / "approval-r2.json"), environment="prod")), ["deploy", "plan-r2.json", "--approval", "x.json"])
    case("approval_blank_approver", lambda w: jw(w / "x.json", dict(jr(w / "approval-r2.json"), approved_by="  ")), ["deploy", "plan-r2.json", "--approval", "x.json"])
    case("rollback_approval_for_deploy", nop, ["deploy", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"])
    case("env_kind_production", lambda w: jw(w / "env/ENVIRONMENT.json", dict(jr(w / "env/ENVIRONMENT.json"), kind="production")), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("env_name_mismatch", lambda w: jw(w / "env/ENVIRONMENT.json", dict(jr(w / "env/ENVIRONMENT.json"), name="prod")), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("artifact_changed_after_pin", lambda w: (w / "artifact-r2/index.html").write_text("<h1>tampered</h1>\n"), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("secret_file_in_artifact", lambda w: (w / "artifact-r2/.env").write_text("X=1\n"), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("live_release_edited", lambda w: (w / "env/releases/r1/index.html").write_text("<h1>hotfix</h1>\n"), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("live_data_missing", lambda w: (w / "env/data/app.db").rename(w / "app.db.away"), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    # v2: v1 used target "../w/env", which resolves back inside the plan folder (my harness input error, disclosed)
    def outside(w):
        shutil.copytree(str(w / "env"), str(w.parent / "outside-env"), symlinks=True); jw(w / "plan-r2.json", dict(jr(w / "plan-r2.json"), target="../outside-env"))
    case("target_outside_plan_folder", outside, ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("artifact_symlink_out", lambda w: os.symlink("/etc/hosts", str(w / "artifact-r2/hosts")), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    case("data_symlink", lambda w: ((w / "env/data/app.db").rename(w / "real.db"), os.symlink(str(w / "real.db"), str(w / "env/data/app.db"))), ["deploy", "plan-r2.json", "--approval", "approval-r2.json"])
    ok = all(v == (2, True) for v in res.values())
    row("D02_refusals_exit2_tree_identical", ok, res)
def d03():
    w = world(); up_to(w, 2); b = tree(w)
    r = [T(w, "preflight", p, "--approval", ap) for p, ap in (("plan-r3-broken.json", "approval-r3-broken.json"), ("plan-r2.json", "approval-r2.json"), ("plan-r2.json", "nope.json"))]
    row("D03_preflight_writes_nothing", tree(w) == b, {"rcs": r})
def d04():  # crash drills at each phase; refused until recover; recover restores release and data; redeploy works
    res = {}
    for ph in ("staged", "migrated", "switched"):
        w = world(); up_to(w, 1); d1 = data(w)
        c = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json", "--fail-at", ph)
        b = tree(w / "env"); blocked = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); same = tree(w / "env") == b
        blocked_rb = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json")
        rec = T(w, "recover", "plan-r2.json"); after = (live(w), data(w) == d1, pending(w), leftovers(w))
        rec2 = T(w, "recover", "plan-r2.json"); again = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
        res[ph] = {"drill": c, "blocked": blocked, "blocked_unchanged": same, "rollback_while_pending": blocked_rb, "recover": rec, "after": after, "recover_again": rec2, "redeploy": again, "live": live(w), "uv": data(w)["uv"]}
    ok = all(v["drill"] == 75 and v["blocked"] == 2 and v["blocked_unchanged"] and v["rollback_while_pending"] == 2 and v["recover"] == 1 and v["after"] == ("r1", True, False, []) and v["recover_again"] == 0 and v["redeploy"] == 0 and v["live"] == "r2" and v["uv"] == 2 for v in res.values())
    row("D04_crash_drills_recover_then_redeploy", ok, res)
def deploy_seconds():
    w = world(); up_to(w, 1); t0 = time.time(); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json"); return time.time() - t0
DUR = None
def d05():  # real SIGKILL at random points during an r1 -> r2 deploy, 16 trials
    global DUR; DUR = DUR or deploy_seconds(); random.seed(11); bad = []; outcomes = []  # v2: kill times spread over the measured deploy time
    for i in range(16):
        w = world(); up_to(w, 1); d1 = data(w)
        p = subprocess.Popen([PY, str(TOOL), "deploy", "plan-r2.json", "--approval", "approval-r2.json"], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        jp = w / "env/.deploy/journal.json"; t_end = time.time() + 5  # v3: wait for the journal to appear (deploy under way), then kill 0-25 ms later
        while not jp.exists() and p.poll() is None and time.time() < t_end: pass
        time.sleep(random.uniform(0.0, 0.025)); p.send_signal(signal.SIGKILL); p.wait()
        st = (live(w), pending(w))
        if pending(w): T(w, "recover", "plan-r2.json")
        L, D = live(w), data(w)
        consistent = (L == "r1" and D == d1) or (L == "r2" and D["uv"] == 2)
        nxt = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
        outcomes.append((st, L, nxt))
        if not consistent or nxt != 0 or live(w) != "r2" or data(w)["uv"] != 2: bad.append((i, st, L, D["uv"], nxt, leftovers(w)))
    row("D05_sigkill_during_deploy_16x", not bad, {"bad": bad, "outcomes": outcomes})
def d06():  # SIGKILL during an explicit rollback (no journal is documented for rollback), 10 trials
    global DUR; DUR = DUR or deploy_seconds(); random.seed(5); res = []
    for i in range(10):
        w = world(); up_to(w, 1); d1 = data(w); T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
        p = subprocess.Popen([PY, str(TOOL), "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(random.uniform(0.0, DUR)); p.send_signal(signal.SIGKILL); p.wait()
        L, D = live(w), data(w); mixed = not ((L == "r1" and D == d1) or (L == "r2" and D["uv"] == 2))
        pre = T(w, "preflight", "plan-r2.json", "--approval", "approval-r2.json")
        again = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json") if L == "r2" else None
        res.append({"live": L, "uv": D["uv"], "mixed": mixed, "preflight_rc": pre, "rollback_again": again, "final": (live(w), data(w) == d1)})
    row("D06_sigkill_during_rollback_10x", True, res, obs=True)
def d07():  # rollback approval
    res = {}
    def case(name, appr_mut, want):
        w = world(); up_to(w, 2); b = tree(w / "env")
        if appr_mut is None: ap = "missing.json"
        else: jw(w / "x.json", appr_mut(jr(w / "approval-rollback-to-r1.json"), w)); ap = "x.json"
        rc = T(w, "rollback", "plan-r2.json", "--approval", ap); res[name] = (rc, tree(w / "env") == b)
    case("missing", None, 2)
    case("wrong_revision_r2", lambda a, w: dict(a, revision="r2"), 2)
    case("action_deploy", lambda a, w: dict(a, action="deploy"), 2)
    case("other_env", lambda a, w: dict(a, environment="prod"), 2)
    case("blank_approver", lambda a, w: dict(a, approved_by=""), 2)
    case("wrong_schema", lambda a, w: dict(a, schema="x/1"), 2)
    case("deploy_approval_r1", lambda a, w: jr(w / "approval-r1.json"), 2)
    w = world(); up_to(w, 1); b = tree(w / "env"); first = T(w, "rollback", "plan-r1.json", "--approval", "approval-rollback-to-r1.json"); res["first_release_nothing_to_return_to"] = (first, tree(w / "env") == b)
    ok = all(v == (2, True) for v in res.values())
    row("D07_rollback_needs_matching_approval", ok, res)
    w = world(); up_to(w, 2); r1 = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json"); d = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    r2 = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json")
    row("D07b_rollback_approval_reusable", True, {"first_rollback": r1, "redeploy": d, "second_rollback_same_approval": r2}, obs=True)
def d08():  # failure handling: bad migration and broken release restore data
    w = world(); up_to(w, 2); d2 = data(w)
    a = T(w, "deploy", "plan-r3-badmigration.json", "--approval", "approval-r3-badmigration.json"); da = data(w); la = live(w)
    b = T(w, "deploy", "plan-r3-broken.json", "--approval", "approval-r3-broken.json"); db = data(w); lb = live(w)
    ok = a == 1 and da == d2 and la == "r2" and b == 1 and db == d2 and lb == "r2" and not pending(w) and leftovers(w) == []
    row("D08_failed_deploys_restore_release_and_data", ok, {"badmig": (a, la, da == d2), "broken": (b, lb, db == d2)})
def d09():  # repeat deploy of live release changes nothing
    w = world(); up_to(w, 2); b = tree(w); r = T(w, "deploy", "plan-r2.json", "--approval", "approval-r2.json")
    row("D09_repeat_live_deploy_noop", r == 0 and tree(w) == b, {"rc": r})
LAUNCH = "import os,sys,time\nt=float(sys.argv[1])\nwhile time.time()<t: pass\nos.execv(sys.argv[2], sys.argv[2:])\n"
def conc(w, specs):  # v2: a start barrier (busy-wait to a shared time, then exec the unchanged tool) so the deploys overlap
    t0 = "%.3f" % (time.time() + 0.6)
    ps = [subprocess.Popen([PY, "-c", LAUNCH, t0, PY, str(TOOL), "deploy", p, "--approval", ap], cwd=w, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True) for p, ap in specs]
    out = [(p.wait(180), p.stderr.read()[-200:]) for p in ps]; return [o[0] for o in out], [o[1] for o in out if o[0] not in (0, 1, 2)]
def d10():  # concurrent deploys to one target (doc: one deployer at a time, no lock): recorded, used for severity
    res = []
    for i in range(4):
        w = world(); up_to(w, 2); d2 = data(w)
        rcs, errs = conc(w, [("plan-r3-broken.json", "approval-r3-broken.json")] * 2)
        res.append({"case": "2x r3-broken from r2", "rcs": rcs, "errs": errs, "live": live(w), "pending": pending(w), "data_equals_r2": data(w) == d2,
                    "totals": [r[2] for r in data(w)["rows"]], "next_preflight_r2_repeat": T(w, "preflight", "plan-r2.json", "--approval", "approval-r2.json")})
    for i in range(4):
        w = world(); up_to(w, 1); d1 = data(w)
        rcs, errs = conc(w, [("plan-r2.json", "approval-r2.json")] * 6)  # v3: 6 racers
        h = [json.loads(x) for x in (w / "env/.deploy/history.jsonl").read_text().splitlines()] if (w / "env/.deploy/history.jsonl").exists() else []
        rb = T(w, "rollback", "plan-r2.json", "--approval", "approval-rollback-to-r1.json")
        res.append({"case": "6x r2 from r1", "data_uv_before_rollback": None, "rcs": rcs, "errs": errs, "live": live(w), "pending": pending(w), "deployed_events_r2": sum(1 for e in h if e.get("event") == "deployed" and e.get("revision") == "r2"),
                    "rollback_rc": rb, "after_rollback_data_equals_r1": data(w) == d1, "after_rollback_live": live(w)})
    row("D10_concurrent_deploys_same_target", True, res, obs=True)
    row("D10_timing", True, {"deploy_seconds": DUR}, obs=True)
def s1():
    src = TOOL.read_text(); bad = [m for m in ("import socket", "urllib", "http.client", "boto", "subprocess") if m in src]
    row("D11_static_no_network_cloud_process", not bad, {"found": bad})
def d12():  # v4 (added after the v3 teeth run showed these gaps, disclosed): re-pinned artifacts and live-health cases
    res = {}
    def repin(w, name):
        a = w / ("artifact-%s" % name); out = subprocess.run([PY, str(TOOL), "digest", str(a)], cwd=w, env=ENV, capture_output=True, text=True).stdout.strip().split()
        if out: dg = out[-1]
        else:  # v4b: the tool's digest refuses symlinks, so re-pin with the fixture builder's digest rule (make_world.digest, which reads through links)
            import importlib.util; sp = importlib.util.spec_from_file_location("mw", str(MW)); mw = importlib.util.module_from_spec(sp); sys.dont_write_bytecode = True; sp.loader.exec_module(mw); dg = mw.digest(a)
        for f in ("plan-%s.json" % name, "approval-%s.json" % name):
            o = jr(w / f)
            if "artifact" in o: o["artifact"]["sha256"] = dg
            else: o["artifact_sha256"] = dg
            jw(w / f, o)
        return dg
    def case(name, prep, cmd, base=1):
        w = world(); up_to(w, base); prep(w); b = tree(w / "env"); rc = T(w, *cmd); res[name] = (rc, tree(w / "env") == b)
    D2 = ["deploy", "plan-r2.json", "--approval", "approval-r2.json"]
    case("revision_relabel_repinned", lambda w: ((w / "artifact-r2/REVISION").write_text("r9\n"), repin(w, "r2")), D2)
    case("secret_file_repinned", lambda w: ((w / "artifact-r2/id_rsa").write_text("x\n"), repin(w, "r2")), D2)
    case("symlink_repinned", lambda w: (os.symlink("index.html", str(w / "artifact-r2/link.html")), repin(w, "r2")), D2)
    case("approval_action_changed_only", lambda w: jw(w / "approval-r2.json", dict(jr(w / "approval-r2.json"), action="rollback")), D2)
    case("live_schema_version_wrong", lambda w: (lambda c: (c.execute("PRAGMA user_version=5"), c.commit(), c.close()))(sqlite3.connect(str(w / "env/data/app.db"))), D2)
    case("live_required_file_empty", lambda w: (w / "env/releases/r1/index.html").write_text(""), D2)
    case("release_folder_exists_other_content", lambda w: ((w / "env/releases/r2").mkdir(), (w / "env/releases/r2/x").write_text("other\n")), D2)
    row("D12_repinned_and_live_health_refusals", all(v == (2, True) for v in res.values()), res)
for rid, fn in (("D01", d01), ("D02", d02), ("D03", d03), ("D04", d04), ("D05", d05), ("D06", d06), ("D07", d07), ("D08", d08), ("D09", d09), ("D10", d10), ("D11", s1), ("D12", d12)):
    guard(rid, fn)
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:600])
print("M08 ORACLE %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
