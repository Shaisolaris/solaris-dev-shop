#!/usr/bin/env python3
"""M03 operational depth: documented crash drill at every N, random external SIGKILL during restore
and during recover, and scale. Usage: python m03_operational.py [--rounds N] -- <candidate prefix...>"""
import os
import random
import signal
import sqlite3
import subprocess
import sys
import tempfile
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m03_oracle as M  # noqa: E402


def classify(ds, v_live, v_snap):
    cur = M.vals(ds)
    return "live" if cur == v_live else "snap" if cur == v_snap else "MIXED"


def debris(ds, before):
    return sorted(n for n in set(os.listdir(ds)) - before if ".pre-restore-" not in n and not n.endswith(("-shm", "-wal")))


def setup(tmp, label):
    base, ds = M.fixture(tmp, label)
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    M.mutate(ds, "1")
    return base, ds, snap, sid, M.vals(ds), {k: M.values(snap / k) for k in ("app.db", "audit.db")}, set(os.listdir(ds))


def drill(tmp):
    out, problems = [], []
    for n in range(1, 30):
        base, ds, snap, sid, v_live, v_snap, before = setup(tmp, f"drill{n}")
        rc, o, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--simulate-crash-after", str(n))
        if rc != 137:
            out.append(f"N={n}: rc={rc} (no rename left to interrupt)")
            break
        h1, _, _ = M.run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        r, ro, _ = M.run("recover", ds)
        st = classify(ds, v_live, v_snap)
        h2, _, _ = M.run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        kept = v_live["app.db"] in list(M.all_value_sets(ds).values())
        d = debris(ds, before)
        out.append(f"N={n}: health-before={h1} recover={r} -> {st}, health-after={h2}, live kept={kept}, debris={d}")
        if h1 == 0 or h2 != 0 or st == "MIXED" or not kept or d:
            problems.append(out[-1])
    return out, problems


def random_kill(tmp, rounds, target):
    """Kill -9 the restore (target=restore) or the recover that follows a killed restore (target=recover)."""
    out, problems, hist = [], [], {}
    rnd = random.Random(20261018 if target == "restore" else 4242)
    for i in range(rounds):
        base, ds, snap, sid, v_live, v_snap, before = setup(tmp, f"rk-{target}-{i}")
        delay = rnd.uniform(0.005, 0.04)  # window measured: restore wall time ~0.034 s
        cmd = M.CMD + ["restore", str(ds), "--snapshot", str(snap), "--confirm", sid]
        if target == "recover":
            M.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--simulate-crash-after", str(rnd.randint(1, 4)))
            cmd = M.CMD + ["recover", str(ds)]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=M.env())
        time.sleep(delay)
        killed = p.poll() is None
        if killed:
            p.send_signal(signal.SIGKILL)
        p.wait()
        r, ro, _ = M.run("recover", ds)
        r2, _, _ = M.run("recover", ds)
        st = classify(ds, v_live, v_snap)
        h, _, _ = M.run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        kept = st != "snap" or v_live["app.db"] in list(M.all_value_sets(ds).values())
        d = debris(ds, before)
        key = f"{'killed' if killed else 'finished'}->{st}"
        hist[key] = hist.get(key, 0) + 1
        if st == "MIXED" or h != 0 or not kept or d or r not in (0,) or r2 != 0:
            problems.append(f"round {i} delay {delay:.3f}s killed={killed}: recover={r}/{r2} state={st} health={h} kept={kept} debris={d}: {ro[-160:]}")
    out.append(f"{rounds} rounds, outcomes {hist}")
    return out, problems


def scale(tmp):
    base = Path(tempfile.mkdtemp(prefix="scale-", dir=tmp))
    ds = base / "data"
    ds.mkdir()
    for k in range(8):
        c = sqlite3.connect(ds / f"db{k}.db")
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, a TEXT, b REAL, c BLOB)")
        c.executemany("INSERT INTO t(a,b,c) VALUES (?,?,?)", ((f"row{i}-{k}", i * 0.5, os.urandom(16)) for i in range(50000)))
        c.commit()
        c.close()
    t0 = time.time()
    sid = M.snap_id(ds, base / "snap")
    t_snap = time.time() - t0
    want = {n: M.values(ds / n) for n in os.listdir(ds) if n.endswith(".db")}
    for k in range(8):
        M.sql(ds / f"db{k}.db", "UPDATE t SET a='changed' WHERE id % 1000 = 0; DELETE FROM t WHERE id > 49990;")
    t0 = time.time()
    rc_v, _, t_ver = M.run("verify", base / "snap")
    rc, out, t_res = M.run("restore", ds, "--snapshot", base / "snap", "--confirm", sid, timeout=600)
    ok = rc == 0 and all(M.values(ds / n) == v for n, v in want.items())
    return [f"8 DBs x 50000 rows: snapshot {t_snap:.1f}s, verify rc={rc_v} {t_ver:.1f}s, restore rc={rc} {t_res:.1f}s, values exact={ok}"], ([] if ok else ["scale restore not exact"])


def main(argv):
    i = argv.index("--")
    M.CMD = argv[i + 1:]
    rounds = int(argv[argv.index("--rounds") + 1]) if "--rounds" in argv[:i] else 40
    tmp = Path(tempfile.mkdtemp(prefix="m03-op-")).resolve()
    total = []
    try:
        for name, fn in (("drill", lambda: drill(tmp)), ("kill-restore", lambda: random_kill(tmp, rounds, "restore")),
                         ("kill-recover", lambda: random_kill(tmp, rounds, "recover")), ("scale", lambda: scale(tmp))):
            t0 = time.time()
            lines, probs = fn()
            print(f"== {name} ({time.time() - t0:.1f}s): {'OK' if not probs else 'PROBLEMS ' + str(len(probs))}")
            for l in lines:
                print("   " + l)
            for p in probs:
                print("   PROBLEM " + p)
            total += probs
            sys.stdout.flush()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"SUMMARY operational problems={len(total)}")


if __name__ == "__main__":
    main(sys.argv[1:])
