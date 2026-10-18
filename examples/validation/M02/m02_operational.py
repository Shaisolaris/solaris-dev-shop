#!/usr/bin/env python3
"""M02 operational depth for the G02 activation CLI: external SIGKILL at random times, documented
recovery, concurrency at scale, and a large owner tree. Synthetic temp dirs only.

Usage: python m02_operational.py [--iterations N] -- <candidate command prefix...>
"""
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DOCS = ("STATUS.md", "Scope/ROUND-PLAN.md", "Delivery/CREDENTIALS.md")
LOCK = ".solaris-activation.lock"
CMD = []


def env():
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def run(*a):
    p = subprocess.run(CMD + [str(x) for x in a] + ["--json"], capture_output=True, text=True, env=env(), timeout=120)
    try:
        return p.returncode, json.loads(p.stdout)
    except ValueError:
        return p.returncode, {"status": None, "raw": p.stdout + p.stderr}


def names_in(root):
    out = {}
    for d in DOCS:
        t = (root / d).read_text() if (root / d).exists() else ""
        out[d] = [n for n in ("Alpha", "Beta") if f": {n}" in t]
    return out


def tree_hash(root):
    h = hashlib.sha256()
    for dp, dn, fn in sorted(os.walk(root)):
        dn.sort()
        for f in sorted(fn):
            p = Path(dp) / f
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def sigkill_loop(tmp, iterations):
    rng = random.Random(20261018)
    stats = {"killed": 0, "finished_before_kill": 0, "recovered": 0, "stale_lock_deleted": 0, "temp_leftovers": 0,
             "mixed_after_kill": 0, "bad": []}
    for i in range(iterations):
        base = Path(tempfile.mkdtemp(prefix=f"op-kill-{i}-", dir=tmp))
        root = base / "proj"
        (base / "outside.txt").write_text("KEEP\n")
        rc, r = run("activate", root, "--name", "Alpha", "--type", "web app", "--deploy-model", "staging-a")
        assert rc == 0, r
        (root / "Development" / "owner.py").write_text("print('owner')\n")
        delay = rng.uniform(0.02, 0.07)
        p = subprocess.Popen(CMD + ["activate", str(root), "--name", "Beta", "--deploy-model", "prod-b"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env())
        time.sleep(delay)
        try:
            os.kill(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        rc = p.wait()
        if rc == -9:
            stats["killed"] += 1
        else:
            stats["finished_before_kill"] += 1
        n = names_in(root)
        if any(v == ["Beta"] for v in n.values()) and any(v == ["Alpha"] for v in n.values()):
            stats["mixed_after_kill"] += 1
        lock_bytes = (root / LOCK).read_bytes() if (root / LOCK).exists() else None
        # documented recovery
        rc, r = run("resume", root)
        if rc != 0 and (root / LOCK).exists() and "stale" in json.dumps(r).lower():
            os.unlink(root / LOCK)
            stats["stale_lock_deleted"] += 1
            rc, r = run("resume", root)
        n = names_in(root)
        # a kill before Beta's intent reached the journal legitimately resumes Alpha; after it, Beta.
        conv = n["STATUS.md"][0] if len(n["STATUS.md"]) == 1 else None
        stats.setdefault("converged_on", {}).setdefault(str(conv), 0)
        stats["converged_on"][str(conv)] += 1
        dep = {"Alpha": "DEPLOY-MODEL: staging-a", "Beta": "DEPLOY-MODEL: prod-b"}.get(conv, "?")
        ok = (rc == 0 and r.get("status") == "complete" and conv and all(v == [conv] for v in n.values())
              and dep in (root / "STATUS.md").read_text() and dep.split(": ")[1] in (root / DOCS[1]).read_text()
              and (root / "Development" / "owner.py").read_text() == "print('owner')\n"
              and (base / "outside.txt").read_text() == "KEEP\n" and not (root / LOCK).exists())
        if ok:
            h = tree_hash(root)
            rc2, r2 = run("resume", root)
            ok = rc2 == 0 and tree_hash(root) == h
        if ok:
            stats["recovered"] += 1
        else:
            stats["bad"].append({"i": i, "delay_ms": round(delay * 1000), "rc": rc, "status": r.get("status"), "names": n,
                                 "lock_bytes_after_kill": None if lock_bytes is None else lock_bytes.decode(errors="replace"),
                                 "errors": r.get("errors")})
        if any(f.endswith(".activation-tmp") for _, _, fs in os.walk(root) for f in fs):
            stats["temp_leftovers"] += 1
        shutil.rmtree(base)
    return stats


def concurrency_scale(tmp):
    base = Path(tempfile.mkdtemp(prefix="op-conc-", dir=tmp))
    # 24 different projects at once plus 12 racers on one shared project, plus resume racing activate
    procs = []
    t_spawn = time.time()
    for i in range(24):
        procs.append(("own", i, subprocess.Popen(CMD + ["activate", str(base / f"p{i}"), "--name", f"Solo{i}", "--deploy-model", f"d{i}"],
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env())))
    shared = base / "shared"
    for i in range(12):
        procs.append(("shared", i, subprocess.Popen(CMD + ["activate", str(shared), "--name", f"Racer{i}", "--deploy-model", f"r{i}"],
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env())))
    codes = [(k, i, p.wait(timeout=180)) for k, i, p in procs]
    elapsed = time.time() - t_spawn
    own_ok = all(c == 0 for k, i, c in codes if k == "own") and all(
        f"Solo{i}" in (base / f"p{i}" / d).read_text() for i in range(24) for d in DOCS)
    st = (shared / "STATUS.md").read_text()
    winner = [f"Racer{i}" for i in range(12) if f"# Project status: Racer{i}\n" in st]
    agree = len(winner) == 1 and all(f": {winner[0]}\n" in (shared / d).read_text() for d in DOCS)
    shared_ok_count = sum(1 for k, i, c in codes if k == "shared" and c == 0)
    # resume racing an activation with changed intake on the same project
    rr = base / "rr"
    run("activate", rr, "--name", "Alpha", "--deploy-model", "a")
    race = []
    for _ in range(10):
        pa = subprocess.Popen(CMD + ["activate", str(rr), "--name", "Beta", "--deploy-model", "b"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env=env())
        pr = subprocess.Popen(CMD + ["resume", str(rr)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env())
        race.append((pa.wait(), pr.wait()))
        n = names_in(rr)
        race[-1] += (all(v == n["STATUS.md"] and len(v) == 1 for v in n.values()),)
        run("activate", rr, "--name", "Alpha", "--deploy-model", "a")
    lock_left = any((base / x / LOCK).exists() for x in [f"p{i}" for i in range(24)] + ["shared", "rr"])
    return {"independent_projects_ok": own_ok, "elapsed_s": round(elapsed, 2), "shared_success_runs": shared_ok_count,
            "shared_winner": winner, "shared_docs_agree": agree, "activate_vs_resume": race, "lock_left": lock_left}


def big_owner_tree(tmp):
    base = Path(tempfile.mkdtemp(prefix="op-big-", dir=tmp))
    root = base / "proj"
    for i in range(5000):
        p = root / "Development" / f"pkg{i % 50}" / f"m{i}.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# owner module {i}\n")
    before = tree_hash(root / "Development")
    t0 = time.time()
    rc, r = run("activate", root, "--name", "Big", "--deploy-model", "none")
    t1 = time.time() - t0
    t0 = time.time()
    rc2, r2 = run("activate", root, "--name", "Big", "--deploy-model", "none")
    t2 = time.time() - t0
    return {"rc": rc, "status": r.get("status"), "owner_tree_identical": tree_hash(root / "Development") == before,
            "first_s": round(t1, 2), "rerun_s": round(t2, 2), "rerun_status": r2.get("status")}


def main(argv):
    global CMD
    i = argv.index("--")
    opts, CMD = argv[:i], argv[i + 1:]
    iters = int(opts[opts.index("--iterations") + 1]) if "--iterations" in opts else 60
    tmp = Path(tempfile.mkdtemp(prefix="m02-op-")).resolve()
    try:
        s = sigkill_loop(tmp, iters)
        print("SIGKILL_LOOP", json.dumps(s))
        c = concurrency_scale(tmp)
        print("CONCURRENCY", json.dumps(c))
        b = big_owner_tree(tmp)
        print("BIG_OWNER_TREE", json.dumps(b))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = (not s["bad"] and s["killed"] > 0 and c["independent_projects_ok"] and c["shared_docs_agree"]
          and not c["lock_left"] and all(x[2] for x in c["activate_vs_resume"]) and b["owner_tree_identical"])
    print("SUMMARY", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
