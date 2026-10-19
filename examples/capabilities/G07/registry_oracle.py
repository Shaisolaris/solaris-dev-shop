#!/usr/bin/env python3
"""G07 oracle: fleet registration without duplicate ownership, run against a registry tool by CLI.

Every scenario runs in a fresh temporary folder. Expectations come from the G07 contract (one registration per
machine; a repeated request applies once; only the registered machine, for its current owner at its current
owner_epoch, may claim work; a failed or interrupted ownership change keeps the prior owner; refusals change
nothing; exit 0 done, 2 refused, 75 crash drill), never from the tool's own output.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOL = ROOT / "employees/infrastructure/fleet-provisioner/registry.py"
HANDOFF = ROOT / "employees/infrastructure/fleet-dispatcher/handoff.py"
G04 = ROOT / "examples/capabilities/G04/fixtures"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
ENV.pop("SOLARIS_FLEET_ROOT", None)
ENV.pop("SOLARIS_MACHINE_IDENTITY", None)


class Box:
    def __init__(self, tool):
        self.tool = str(tool)
        self.d = Path(tempfile.mkdtemp(prefix="g07-oracle-"))
        shutil.copytree(HERE / "fixtures", self.d / "id")
        self.root = self.d / "fleet"
        self.root.mkdir()

    def ident(self, name):
        return str(self.d / "id" / ("identity-%s.json" % name))

    def make_ident(self, name, mid):
        p = self.d / "id" / ("identity-%s.json" % name)
        p.write_text(json.dumps({"machine_id": mid}))
        return str(p)

    def run(self, *args):
        p = subprocess.run([sys.executable, self.tool, args[0], "--root", str(self.root)] + list(args[1:]),
                           capture_output=True, text=True, env=ENV, timeout=120)
        return p.returncode

    def reg(self, alias, ident, owner, req, *extra):
        return self.run("register", "--alias", alias, "--identity", ident, "--owner", owner, "--request-id", req,
                        *extra)

    def transfer(self, alias, frm, epoch, to, req, *extra):
        return self.run("transfer", "--alias", alias, "--from-owner", frm, "--expect-epoch", str(epoch),
                        "--to-owner", to, "--request-id", req, *extra)

    def claim(self, alias, ident, owner, epoch):
        return self.run("claim", "--alias", alias, "--identity", ident, "--owner", owner, "--epoch", str(epoch))

    def machines(self):
        p = subprocess.run([sys.executable, self.tool, "status", "--root", str(self.root)], capture_output=True,
                           text=True, env=ENV, timeout=120)
        try:
            return json.loads(p.stdout).get("machines") or []
        except ValueError:
            return []

    def owner(self, alias):
        m = [x for x in self.machines() if x.get("alias") == alias]
        return (m[0].get("owner"), m[0].get("owner_epoch"), m[0].get("status")) if len(m) == 1 else None

    def snap(self):
        return {p.name: p.read_bytes() for p in sorted(self.root.iterdir()) if p.is_file() and not p.name.startswith(".")}

    def close(self):
        shutil.rmtree(str(self.d), ignore_errors=True)


def check(fn, tool, scale):
    b = Box(tool)
    try:
        return bool(fn(b, scale))
    except Exception as e:  # a crash in a scenario is a failed check, never a pass
        sys.stderr.write("%s: %s: %s\n" % (fn.__name__, e.__class__.__name__, e))
        return False
    finally:
        b.close()


def o1(b, n):  # clean control
    rc = [b.reg("mini1", b.ident("mini1"), "ana", "r1"), b.reg("mini2", b.ident("mini2"), "ben", "r2")]
    ms = b.machines()
    fleet = (b.root / "FLEET.md").read_text() if (b.root / "FLEET.md").exists() else ""
    return rc == [0, 0] and len(ms) == 2 and b.owner("mini1") == ("ana", 1, "active") and \
        b.claim("mini1", b.ident("mini1"), "ana", 1) == 0 and b.claim("mini2", b.ident("mini2"), "ben", 1) == 0 \
        and "mini-7f3a-0001" in fleet and "mini-7f3a-0002" in fleet


def o2(b, n):  # retried request applies once
    rc = [b.reg("mini1", b.ident("mini1"), "ana", "r1") for _ in range(3)]
    return rc == [0, 0, 0] and len(b.machines()) == 1


def o3(b, n):  # same machine and alias, new request id: still one registration
    rc = [b.reg("mini1", b.ident("mini1"), "ana", "r%d" % i) for i in range(3)]
    return rc == [0, 0, 0] and len(b.machines()) == 1 and b.owner("mini1") == ("ana", 1, "active")


def o4(b, n):  # same machine under a second alias is a duplicate registration
    pre = b.reg("mini1", b.ident("mini1"), "ana", "r1") == 0 and len(b.machines()) == 1
    s = b.snap()
    return pre and b.reg("spare", b.ident("mini1"), "ben", "r2") == 2 and b.snap() == s


def o5(b, n):  # alias held by another machine; same alias, same machine, other owner must use transfer
    pre = b.reg("mini1", b.ident("mini1"), "ana", "r1") == 0 and len(b.machines()) == 1
    s = b.snap()
    return pre and b.reg("mini1", b.ident("impostor"), "ana", "r2") == 2 and \
        b.reg("mini1", b.ident("mini1"), "ben", "r3") == 2 and b.snap() == s


def o6(b, n):  # wrong machine cannot claim, even with the right hostname, owner and epoch
    b.reg("mini1", b.ident("mini1"), "ana", "r1")
    return b.claim("mini1", b.ident("impostor"), "ana", 1) == 2 and b.claim("mini1", b.ident("mini2"), "ana", 1) == 2 \
        and b.claim("ghost", b.ident("mini1"), "ana", 1) == 2 and b.claim("mini1", b.ident("mini1"), "ana", 1) == 0


def o7(b, n):  # stale owner cannot claim or change ownership
    b.reg("mini1", b.ident("mini1"), "ana", "r1")
    ok = b.transfer("mini1", "ana", 1, "ben", "t1") == 0
    s = b.snap()
    return ok and b.claim("mini1", b.ident("mini1"), "ana", 1) == 2 and b.claim("mini1", b.ident("mini1"), "ben", 1) == 2 \
        and b.claim("mini1", b.ident("mini1"), "ana", 2) == 2 and b.transfer("mini1", "ana", 2, "cy", "t4") == 2 \
        and b.transfer("mini1", "ben", 2, "ben", "t5") == 2 \
        and b.claim("mini1", b.ident("mini1"), "ben", 2) == 0 and b.transfer("mini1", "ana", 1, "cy", "t2") == 2 \
        and b.transfer("mini1", "ben", 1, "cy", "t3") == 2 and b.snap() == s and b.owner("mini1") == ("ben", 2, "active")


def o8(b, n):  # crash before the registry is replaced: prior owner kept; the same request then applies once
    b.reg("mini1", b.ident("mini1"), "ana", "r1")
    crash = b.transfer("mini1", "ana", 1, "ben", "t1", "--fail-at", "before-replace")
    kept = b.owner("mini1") == ("ana", 1, "active") and b.claim("mini1", b.ident("mini1"), "ana", 1) == 0
    again = b.transfer("mini1", "ana", 1, "ben", "t1")
    return crash == 75 and kept and again == 0 and b.owner("mini1") == ("ben", 2, "active") and \
        b.transfer("mini1", "ana", 1, "ben", "t1") == 0 and b.owner("mini1") == ("ben", 2, "active")


def o9(b, n):  # crash after replace, before commit: change stands, a retry does not apply it twice
    b.reg("mini1", b.ident("mini1"), "ana", "r1")
    crash = b.transfer("mini1", "ana", 1, "ben", "t1", "--fail-at", "after-replace")
    after = b.owner("mini1")
    again = b.transfer("mini1", "ana", 1, "ben", "t1")
    return crash == 75 and after == ("ben", 2, "active") and again == 0 and b.owner("mini1") == ("ben", 2, "active") \
        and b.claim("mini1", b.ident("mini1"), "ana", 1) == 2


def o10(b, n):  # eight concurrent owner changes from the same view: exactly one wins
    b.reg("mini1", b.ident("mini1"), "ana", "r1")
    with ThreadPoolExecutor(8) as ex:
        rcs = list(ex.map(lambda i: b.transfer("mini1", "ana", 1, "new%d" % i, "t%d" % i), range(8)))
    o = b.owner("mini1")
    return sorted(rcs) == [0] + [2] * 7 and o is not None and o[1] == 2 and o[0] == "new%d" % rcs.index(0)


def o11(b, n):  # scale: n machines, four concurrent registrars each retrying every request, plus duplicates
    ids = [b.make_ident("m%d" % i, "synth-%04d-machine" % i) for i in range(n)]

    def registrar(k):
        bad = 0
        for i in range(n):
            bad += b.reg("m%d" % i, ids[i], "owner-%d" % (i % 7), "reg-%d" % i) != 0
            if k == 0 and b.reg("dup%d" % i, ids[i], "owner-x", "dup-%d" % i) != 2:
                bad += 1
        return bad

    with ThreadPoolExecutor(4) as ex:
        bad = sum(ex.map(registrar, range(4)))
    ms = b.machines()
    return bad == 0 and len(ms) == n and len({m["machine_id"] for m in ms}) == n and \
        all(m["owner_epoch"] == 1 for m in ms)


def o12(b, n):  # a request id reused for a different change is refused
    pre = b.reg("mini1", b.ident("mini1"), "ana", "r1") == 0 and len(b.machines()) == 1
    s = b.snap()
    return pre and b.reg("mini2", b.ident("mini2"), "ben", "r1") == 2 and b.snap() == s and \
        b.reg("mini2", b.ident("mini2"), "ben", "r2") == 0


def o13(b, n):  # registry edited outside the tool: no change or claim is built on it
    if b.reg("mini1", b.ident("mini1"), "ana", "r1") != 0:
        return False
    p = b.root / "registry.json"
    p.write_text(p.read_text().replace('"ana"', '"mallory"'))
    s = b.snap()
    return b.reg("mini2", b.ident("mini2"), "ben", "r2") == 2 and b.claim("mini1", b.ident("mini1"), "mallory", 1) == 2 \
        and b.transfer("mini1", "mallory", 1, "eve", "t1") == 2 and b.snap() == s


def o14(b, n):  # retirement: stale view refused; retired machine takes no work and is not reassigned
    b.reg("mini1", b.ident("mini1"), "ana", "r1")
    stale = b.run("retire", "--alias", "mini1", "--from-owner", "ana", "--expect-epoch", "2", "--request-id", "x1")
    ok = b.run("retire", "--alias", "mini1", "--from-owner", "ana", "--expect-epoch", "1", "--request-id", "x2")
    return stale == 2 and ok == 0 and b.claim("mini1", b.ident("mini1"), "ana", 2) == 2 and \
        b.reg("mini1", b.ident("mini1"), "ana", "r2") == 2 and \
        b.transfer("mini1", "ana", 2, "ben", "t1") == 2 and b.owner("mini1") == ("ana", 2, "retired")


def o15(b, n):  # invalid input creates nothing
    bad = b.make_ident("bad", "x")
    rcs = [b.reg("Mini 1", b.ident("mini1"), "ana", "r1"), b.reg("mini1", str(b.d / "missing.json"), "ana", "r2"),
           b.reg("mini1", bad, "ana", "r3"), b.reg("mini1", b.ident("mini1"), "a|b", "r4"),
           b.reg("mini1", b.ident("mini1"), "  ", "r5"), b.reg("mini1", b.ident("mini1"), "ana", "bad id"),
           b.transfer("mini1", "ana", 1, "ana", "t1")]
    p = subprocess.run([sys.executable, b.tool, "status", "--root", str(b.d / "nope")], capture_output=True, env=ENV)
    clean = b.machines() == [] and not (b.root / "registry.json").exists() and not (b.d / "nope").exists()
    return rcs == [2] * 7 and p.returncode == 2 and clean and b.reg("mini1", b.ident("mini1"), "ana", "r1") == 0 \
        and len(b.machines()) == 1  # positive control: the same root accepts a valid registration


def o16(b, n):  # the G04 work-order runner admits a fleet-bound order only on the right machine, owner and epoch
    w = b.d / "wo"
    shutil.copytree(str(G04), str(w))
    order = json.loads((w / "order.json").read_text())
    order["fleet"] = {"machine": "mini1", "owner_epoch": 1}  # registry from SOLARIS_FLEET_ROOT
    env = dict(ENV, SOLARIS_FLEET_ROOT=str(b.root))
    b.reg("mini1", b.ident("mini1"), order["owner"], "r1")

    def go(ident, epoch=1):
        order["fleet"]["owner_epoch"] = epoch
        (w / "order.json").write_text(json.dumps(order))
        args = [sys.executable, str(HANDOFF), "run", str(w / "order.json"), "--worker", "w"]
        return subprocess.run(args + (["--identity", ident] if ident else []), capture_output=True, env=env,
                              cwd=str(w), timeout=300).returncode

    ledger = w / "outbox" / "ledger.jsonl"
    refused = [go(b.ident("impostor")), go(None), go(b.ident("mini1"), 2)]
    nothing = not ledger.exists() and not (w / ".handoff").exists()
    ok = go(b.ident("mini1"))
    t = b.transfer("mini1", order["owner"], 1, "ben", "t1")
    stale = go(b.ident("mini1"), 1)
    lines = ledger.read_text().splitlines() if ledger.exists() else []
    order["fleet"]["registry"] = "../fleet"  # an order may not point outside its folder
    return refused == [2, 2, 2] and nothing and ok == 0 and t == 0 and stale == 2 and len(lines) == 1 \
        and go(b.ident("mini1"), 2) == 2


def s1(b, n):  # static: no process launch or network import in the tool
    src = Path(b.tool).read_text()
    return not any(x in src for x in ("import subprocess", "import socket", "urllib", "http.client", "os.system"))


CHECKS = [o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16, s1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(TOOL))
    ap.add_argument("--scale", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = [{"id": f.__name__, "ok": check(f, a.tool, a.scale)} for f in CHECKS]
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
