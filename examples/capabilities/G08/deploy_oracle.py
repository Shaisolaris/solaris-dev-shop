#!/usr/bin/env python3
"""G08 oracle: local deployment preflight and safe rollback, run against a deploy tool by CLI.

Each scenario builds a fresh world with make_world.py. Expectations come from the G08 contract: a valid
approved deploy succeeds and a later rollback restores the previous release and its data; a missing approval,
wrong environment, changed artifact, unhealthy live release or unavailable rollback is refused before any
change (the whole environment tree is byte-identical afterwards); a deploy that fails its health check, or
was interrupted, ends on the previous release with the previous data. Exit 0 done, 1 rolled back, 2 refused,
75 crash drill. Data is read with sqlite3 directly, never from the tool's output.
"""
import argparse
import fcntl
import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOL = ROOT / "employees/engineering/devops-engineer/local_deploy.py"
sys.path.insert(0, str(HERE))
import make_world  # noqa: E402

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


class World:
    def __init__(self, tool):
        self.tool = str(tool)
        self.tmp = Path(tempfile.mkdtemp(prefix="g08-oracle-"))
        self.w = make_world.build(self.tmp / "w")
        self.env = self.w / "env"

    def run(self, cmd, name, approval=None, *extra):
        args = [sys.executable, self.tool, cmd, str(self.w / ("plan-%s.json" % name))]
        if approval:
            args += ["--approval", str(self.w / approval)]
        return subprocess.run(args + list(extra), capture_output=True, text=True, env=ENV, cwd=str(self.w),
                              timeout=300).returncode

    def deploy(self, name, *extra):
        return self.run("deploy", name, "approval-%s.json" % name, *extra)

    def live(self):
        c = self.env / "current"
        return Path(os.readlink(str(c))).name if os.path.islink(str(c)) else None

    def data(self):
        con = sqlite3.connect("file:%s?mode=ro" % (self.env / "data" / "app.db"), uri=True)
        try:
            rows = con.execute("SELECT * FROM orders ORDER BY id").fetchall()
            return con.execute("PRAGMA user_version").fetchone()[0], rows
        finally:
            con.close()

    def tree(self):
        out = {}
        for dp, dns, fns in os.walk(str(self.env)):
            for n in dns + fns:
                p = Path(dp) / n
                rel = str(p.relative_to(self.env))
                out[rel] = ("link", os.readlink(str(p))) if p.is_symlink() else \
                    ("file", hashlib.sha256(p.read_bytes()).hexdigest()) if p.is_file() else ("dir",)
        return out

    def close(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


def check(fn, tool):
    w = World(tool)
    try:
        return bool(fn(w))
    except Exception as e:  # a crash in a scenario is a failed check
        sys.stderr.write("%s: %s: %s\n" % (fn.__name__, e.__class__.__name__, e))
        return False
    finally:
        w.close()


def at_r2(w):
    return w.deploy("r1") == 0 and w.deploy("r2") == 0 and w.live() == "r2"


def unchanged(w, fn):
    before = w.tree()
    rc = fn()
    return rc == 2 and w.tree() == before


def o1(w):  # clean control: first deploy, upgrade with a migration
    seed = w.data()
    ok = w.deploy("r1") == 0 and w.live() == "r1" and w.data() == (1, seed[1])
    ok = ok and w.deploy("r2") == 0 and w.live() == "r2"
    v, rows = w.data()
    return ok and v == 2 and [r[3] for r in rows] == ["migrated r2"] * 3 and \
        (w.env / "releases/r2/index.html").read_text().startswith("<h1>Harbor Kiosk r2")


def o2(w):  # missing authority refuses before any change (first deploy and upgrade)
    if not unchanged(w, lambda: w.run("deploy", "r1")):
        return False
    return w.deploy("r1") == 0 and unchanged(w, lambda: w.run("deploy", "r2")) and w.live() == "r1"


def o3(w):  # an approval that does not cover this deploy
    if w.deploy("r1") != 0:
        return False
    a = json.loads((w.w / "approval-r2.json").read_text())
    variants = [dict(a, revision="r9"), dict(a, environment="production"), dict(a, artifact_sha256="0" * 64),
                dict(a, action="rollback"), dict(a, approved_by="  "), {k: v for k, v in a.items() if k != "schema"}]
    for i, v in enumerate(variants):
        (w.w / ("bad-%d.json" % i)).write_text(json.dumps(v))
        if not unchanged(w, lambda: w.run("deploy", "r2", "bad-%d.json" % i)):
            return False
    return w.live() == "r1"


def o4(w):  # wrong or non-local environment
    if w.deploy("r1") != 0:
        return False
    p = w.env / "ENVIRONMENT.json"
    e = json.loads(p.read_text())
    for v in (dict(e, name="production"), dict(e, kind="cloud"), "not json"):
        p.write_text(v if isinstance(v, str) else json.dumps(v))
        if not unchanged(w, lambda: w.deploy("r2")):
            return False
    return w.live() == "r1"


def repin(w, name, a):
    sha = make_world.digest(a)
    for f, k in (("plan-%s.json" % name, "artifact"), ("approval-%s.json" % name, None)):
        d = json.loads((w.w / f).read_text())
        if k:
            d[k]["sha256"] = sha
        else:
            d["artifact_sha256"] = sha
        (w.w / f).write_text(json.dumps(d))


def o5(w):  # the artifact is not what was planned and approved
    if w.deploy("r1") != 0:
        return False
    a = w.w / "artifact-r2"
    orig = (a / "index.html").read_text()
    (a / "index.html").write_text(orig + "<script>changed</script>\n")
    t1 = unchanged(w, lambda: w.deploy("r2"))
    (a / "index.html").write_text(orig)
    (a / "REVISION").write_text("r2b\n")
    t2 = unchanged(w, lambda: w.deploy("r2"))
    repin(w, "r2", a)  # digest pinned to the relabelled artifact: the revision itself must still match
    t2b = unchanged(w, lambda: w.deploy("r2"))
    (a / "REVISION").write_text("r2\n")
    (a / ".env").write_text("API_TOKEN=synthetic-not-a-secret\n")
    repin(w, "r2", a)
    t3 = unchanged(w, lambda: w.deploy("r2"))
    return t1 and t2 and t2b and t3 and w.live() == "r1"


def o6(w):  # health precondition: never deploy over a live release that is already broken
    if not at_r2(w):
        return False
    db = w.env / "data" / "app.db"
    good = db.read_bytes()
    con = sqlite3.connect(str(db))  # data at the wrong schema version, release files untouched
    con.execute("PRAGMA user_version = 9")
    con.close()
    t1 = unchanged(w, lambda: w.run("preflight", "r3-broken", "approval-r3-broken.json")) and \
        unchanged(w, lambda: w.deploy("r3-broken"))
    db.unlink()  # a database with no tables at the right version: only the G03 health check sees it
    con = sqlite3.connect(str(db))
    con.execute("PRAGMA user_version = 2")
    con.close()
    t2 = unchanged(w, lambda: w.deploy("r3-broken"))
    db.write_bytes(good)
    (w.env / "releases/r2/index.html").write_text("")
    t3 = unchanged(w, lambda: w.deploy("r3-broken"))
    return t1 and t2 and t3


def o7(w):  # rollback unavailable: live release changed since deploy; an unfinished deploy pending
    if not at_r2(w):
        return False
    (w.env / "releases/r2/extra.txt").write_text("hand edit\n")
    t1 = unchanged(w, lambda: w.deploy("r3-broken"))
    os.unlink(str(w.env / "releases/r2/extra.txt"))
    (w.env / ".deploy/journal.json").write_text(json.dumps({"deploy_id": "x", "revision": "r3", "phase": "staged"}))
    t2 = unchanged(w, lambda: w.deploy("r3-broken"))
    return t1 and t2


def o8(w):  # migration fails mid-way: transaction undone, health fails, back on r2 with r2's data
    if not at_r2(w):
        return False
    before = w.data()
    rc = w.deploy("r3-badmigration")
    return rc == 1 and w.live() == "r2" and w.data() == before and not (w.env / "releases/r3").exists()


def o9(w):  # release fails health after a successful migration: data restored from the snapshot
    if not at_r2(w):
        return False
    before = w.data()
    rc = w.deploy("r3-broken")
    return rc == 1 and w.live() == "r2" and w.data() == before and not (w.env / "releases/r3").exists() and \
        w.run("preflight", "r2", "approval-r2.json") == 2  # r2 is live: re-deploying it is not a fresh release


def o10(w):  # interrupted deploys: refused until recovered; recovery restores release and data
    if not at_r2(w):
        return False
    before = w.data()
    for point in ("staged", "migrated", "switched"):
        if w.deploy("r3-broken", "--fail-at", point) != 75:
            return False
        if not unchanged(w, lambda: w.deploy("r2")):
            return False
        if w.run("recover", "r2") != 1 or w.live() != "r2" or w.data() != before:
            return False
    return w.run("recover", "r2") == 0 and w.run("preflight", "r3-broken", "approval-r3-broken.json") == 0


def o11(w):  # explicit rollback: needs its own approval naming the revision returned to
    if not at_r2(w):
        return False
    t1 = unchanged(w, lambda: w.run("rollback", "r2"))
    t2 = unchanged(w, lambda: w.run("rollback", "r2", "approval-rollback-to-r2.json"))
    t3 = unchanged(w, lambda: w.run("rollback", "r2", "approval-r1.json"))
    rc = w.run("rollback", "r2", "approval-rollback-to-r1.json")
    v, rows = w.data()
    return t1 and t2 and t3 and rc == 0 and w.live() == "r1" and v == 1 and all(len(r) == 3 for r in rows)


def o12(w):  # redeploy after rollback; a repeated deploy changes nothing
    if not at_r2(w) or w.run("rollback", "r2", "approval-rollback-to-r1.json") != 0:
        return False
    ok = w.deploy("r2") == 0 and w.live() == "r2" and w.data()[0] == 2
    before = w.tree()
    return ok and w.deploy("r2") == 0 and w.tree() == before


def o13(w):  # preflight writes nothing, passing or failing
    t = w.tree()
    a = w.run("preflight", "r1", "approval-r1.json")
    b = w.run("preflight", "r1")
    return a == 0 and b == 2 and w.tree() == t


def o14(w):  # operational variant: 12 cycles of deploy, failure, crash and recovery with seeded randomness
    rnd = random.Random(7)
    if w.deploy("r1") != 0:
        return False
    want = {"r1": 1, "r2": 2}
    for _ in range(12):
        live = w.live()
        step = rnd.choice(["up", "bad", "broken", "crash", "back"])
        if step == "up" and live == "r1":
            if w.deploy("r2") != 0:
                return False
        elif step in ("bad", "broken"):
            before = w.data()
            if w.deploy("r3-badmigration" if step == "bad" else "r3-broken") != 1 or w.data() != before:
                return False
        elif step == "crash":
            before = w.data()
            if w.deploy("r3-broken", "--fail-at", rnd.choice(["staged", "migrated", "switched"])) != 75 or \
                    w.run("recover", "r2") != 1 or w.data() != before:
                return False
        elif step == "back" and live == "r2":
            if w.run("rollback", "r2", "approval-rollback-to-r1.json") != 0:
                return False
        if w.live() not in want or w.data()[0] != want[w.live()]:
            return False
    return True


def o15(w):  # invalid plans create nothing
    p = json.loads((w.w / "plan-r1.json").read_text())
    shutil.copytree(str(w.env), str(w.tmp / "outside"))  # a valid environment, but outside the plan's folder
    outside = {k: v for k, v in World.tree(type("X", (), {"env": w.tmp / "outside"})()).items()}
    bad = [dict(p, target="../outside"), dict(p, artifact=dict(p["artifact"], revision="r 1")),
           dict(p, health={"required_files": [], "databases": ["app.db"]}), dict(p, schema="x"),
           dict(p, environment="Prod!"), dict(p, health={"required_files": ["../x"], "databases": []})]
    t = w.tree()
    for i, b in enumerate(bad):
        (w.w / ("plan-bad%d.json" % i)).write_text(json.dumps(b))
        if w.run("deploy", "bad%d" % i, "approval-r1.json") != 2:
            return False
    still = World.tree(type("X", (), {"env": w.tmp / "outside"})()) == outside
    return w.tree() == t and still and w.deploy("r1") == 0  # positive control


LAUNCH = "import os,sys,time\nt=float(sys.argv[1])\nwhile time.time()<t: pass\nos.execv(sys.argv[2], sys.argv[2:])\n"
OFFSETS_MS = (0, 2, 4, 5, 6, 8, 10, 12, 15)


def race(w, name, offset_ms):
    """Two deploys of one plan on one target, released offset_ms apart from a common start time (a spin-wait
    launcher takes interpreter start-up out of the timing); returns both exit codes, sorted."""
    t0 = time.time() + 0.4
    args = [w.tool, "deploy", str(w.w / ("plan-%s.json" % name)), "--approval", str(w.w / ("approval-%s.json" % name))]
    ps = [subprocess.Popen([sys.executable, "-c", LAUNCH, "%.4f" % (t0 + d / 1000.0), sys.executable] + args,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ENV, cwd=str(w.w))
          for d in (0, offset_ms)]
    return sorted(p.wait(timeout=300) for p in ps)


def deployed(w, rev):
    h = w.env / ".deploy" / "history.jsonl"
    rows = [json.loads(x) for x in h.read_text().splitlines() if x.strip()] if h.exists() else []
    return sum(1 for r in rows if r.get("event") == "deployed" and r.get("revision") == rev)


def o16(w):  # concurrency: a held target lock refuses; overlapping deploys never corrupt or double-report
    if not at_r2(w):
        return False
    fd = os.open(str(w.env), os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held = unchanged(w, lambda: w.deploy("r3-broken")) and \
            unchanged(w, lambda: w.run("rollback", "r2", "approval-rollback-to-r1.json")) and \
            unchanged(w, lambda: w.run("recover", "r2"))
    finally:
        os.close(fd)
    if not held:
        return False
    before = w.data()
    for i in range(18):  # two broken deploys at once: both end on r2 with r2's data, nothing pending
        rcs = race(w, "r3-broken", OFFSETS_MS[i % len(OFFSETS_MS)])
        if not set(rcs) <= {1, 2} or w.live() != "r2" or w.data() != before or (w.env / ".deploy/journal.json").exists():
            return False
    for i in range(9):  # two deploys of r2 at once from r1: exactly one deploy happens
        if w.run("rollback", "r2", "approval-rollback-to-r1.json") != 0:
            return False
        n = deployed(w, "r2")
        rcs = race(w, "r2", OFFSETS_MS[i])
        if rcs not in ([0, 0], [0, 2]) or deployed(w, "r2") != n + 1 or w.live() != "r2" or w.data()[0] != 2:
            return False
    return True


def o17(w):  # a repeat deploy of the live release still needs approval and a healthy live release
    if not at_r2(w):
        return False
    t1 = unchanged(w, lambda: w.run("deploy", "r2"))  # no approval
    t2 = unchanged(w, lambda: w.run("deploy", "r2", "approval-r1.json"))  # approval for another revision
    before = w.tree()
    t3 = w.deploy("r2") == 0 and w.tree() == before  # approved and healthy: success, nothing changed
    con = sqlite3.connect(str(w.env / "data" / "app.db"))
    try:
        con.execute("PRAGMA user_version = 3")  # an outside writer breaks the live release's precondition
        con.commit()
    finally:
        con.close()
    t4 = unchanged(w, lambda: w.deploy("r2"))
    return t1 and t2 and t3 and t4


def s1(w):  # static: no network, cloud SDK or process launch
    src = Path(w.tool).read_text()
    return not any(x in src for x in ("import subprocess", "import socket", "urllib", "http.client", "boto",
                                      "requests", "os.system"))


CHECKS = [o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16, o17, s1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(TOOL))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tool = os.path.abspath(a.tool)
    res = [{"id": f.__name__, "ok": check(f, tool)} for f in CHECKS]
    n = sum(r["ok"] for r in res)
    if a.json:
        print(json.dumps({"tool": a.tool, "passed": n, "total": len(res), "checks": res}))
    else:
        for r in res:
            print("%-4s %s" % (r["id"], "ok" if r["ok"] else "FAIL"))
        print("%d/%d" % (n, len(res)))
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
