#!/usr/bin/env python3
"""M03 r2 regression hunt: behaviour introduced by the G03 rework (9f2fbbc). Synthetic data only.
Usage: python m03r2_regressions.py PYTHON TOOL   (PYTHON runs both the tool and the helpers)
Each case prints OK / NOTE / FINDING with observed values."""
import concurrent.futures as cf, fcntl, hashlib, json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, time
from pathlib import Path

PY, TOOL = sys.argv[1], sys.argv[2]
ROOT = Path(tempfile.mkdtemp(prefix="m03r2g-"))
JOURNAL, LOCK = ".solaris-recovery.json", ".solaris-recovery.lock"


def tool(*a, timeout=120):
    t0 = time.time()
    p = subprocess.run([PY, TOOL, *map(str, a)], capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip(), time.time() - t0


def helper(code, *a):
    return subprocess.run([PY, "-c", code, *map(str, a)], capture_output=True, text=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_db(d, name="app.db", wal=False, rows=3, big=0):
    d.mkdir(parents=True, exist_ok=True)
    helper("""
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
if sys.argv[2] == '1': c.execute('PRAGMA journal_mode=WAL')
c.execute('create table t(id integer primary key, v)')
c.executemany('insert into t(v) values (?)', [('r%d' % i,) for i in range(int(sys.argv[3]))])
if int(sys.argv[4]): c.executemany('insert into t(v) values (?)', [('x' * 200,) for i in range(int(sys.argv[4]))])
c.commit(); c.close()
""", d / name, "1" if wal else "0", rows, big)
    return d / name


def case(fn):
    try:
        st, msg = fn()
    except Exception as e:
        st, msg = "ERROR", f"{e.__class__.__name__}: {e}"
    print(f"{st} {fn.__name__}: {msg}", flush=True)


def g01_parent_created_then_refused():
    ds = ROOT / "g01" / "ds"
    make_db(ds)
    fd = os.open(ds / LOCK, os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)  # another recovery holds the dataset
    try:
        rc, out, _ = tool("snapshot", ds, "--out", ROOT / "g01" / "snapshots" / "s1")
    finally:
        os.close(fd)
    left = (ROOT / "g01" / "snapshots").exists()
    return ("FINDING" if rc != 0 and left else "OK"), f"snapshot refused (exit {rc}: {out[:90]!r}); missing parent snapshots/ created anyway: {left}"


def g02_parent_via_symlinked_grandparent():
    base = ROOT / "g02"
    ds = base / "ds"
    make_db(ds)
    (base / "elsewhere").mkdir()
    os.symlink(base / "elsewhere", base / "link")
    rc, out, _ = tool("snapshot", ds, "--out", base / "link" / "snapshots" / "s1")
    made = list((base / "elsewhere").iterdir())
    return ("OK" if rc != 0 and not made else "FINDING"), f"--out link/snapshots/s1 with link -> elsewhere: exit {rc}; created under the link target: {[m.name for m in made]}"


def g03_fallback_concurrency():
    ds = ROOT / "g03" / "ds"
    db = make_db(ds, wal=True, rows=50)
    for s in ("-wal", "-shm"):
        if (ds / ("app.db" + s)).exists():
            os.unlink(ds / ("app.db" + s))
    before = sha(db)
    jobs = [("health", ds, "--expect", "app.db")] * 8 + [("snapshot", ds, "--out", ROOT / "g03" / f"snap{i}") for i in range(4)]
    with cf.ThreadPoolExecutor(12) as ex:
        res = list(ex.map(lambda j: tool(*j), jobs))
    rcs = [r[0] for r in res]
    snaps = [ROOT / "g03" / f"snap{i}" for i in range(4) if (ROOT / "g03" / f"snap{i}").exists()]
    ver = [tool("verify", s)[0] for s in snaps]
    after = sha(db)
    busy = sum(1 for r in res if r[0] != 0 and "busy" in r[1].lower())
    bad = [r[1][:100] for r in res if r[0] != 0 and "busy" not in r[1].lower()]
    side = sorted(p.name for p in ds.iterdir())
    ok = after == before and not bad and all(v == 0 for v in ver)
    return ("OK" if ok else "FINDING"), (f"quiescent WAL DB without sidecars, 8 health + 4 snapshot at once: exits {rcs} "
            f"(busy {busy}), other failures {bad}, snapshots verify {ver}, main file unchanged {after == before}, dataset now {side}")


def g04_health_lock_timeout():
    ds = ROOT / "g04" / "ds"
    db = make_db(ds)
    ready = ROOT / "g04" / "ready"
    holder = subprocess.Popen([PY, "-c", """
import sqlite3, sys, time, pathlib
c = sqlite3.connect(sys.argv[1], isolation_level=None); c.execute('BEGIN EXCLUSIVE')
pathlib.Path(sys.argv[2]).write_text('1'); time.sleep(30)
""", db, ready])
    while not ready.exists():
        time.sleep(0.05)
    try:
        r1 = tool("health", ds, "--expect", "app.db", "--lock-timeout", "1")
        r2 = tool("health", ds, "--expect", "app.db", "--lock-timeout", "0.2")
    finally:
        holder.kill(); holder.wait()
    bad_vals = {v: tool("health", ds, "--expect", "app.db", "--lock-timeout", v)[0] for v in ("nan", "inf", "-1", "0", "601")}
    ok = r1[0] == 1 and "busy" in r1[1] and r1[2] < 3 and r2[2] < 2 and all(v == 2 for v in bad_vals.values())
    return ("OK" if ok else "FINDING"), (f"exclusive holder: --lock-timeout 1 -> exit {r1[0]} in {r1[2]:.1f}s ({r1[1][:80]!r}); 0.2 -> {r2[2]:.1f}s; "
            f"bad values exit {bad_vals}")


def g05_journal_temp_cleanup_scope():
    ds = ROOT / "g05" / "ds"
    make_db(ds)
    names = {"match": f".{JOURNAL}.0123456789abcdef.tmp", "upper_hex": f".{JOURNAL}.ABCDEF0123456789.tmp",
             "short_hex": f".{JOURNAL}.0123456789abcde.tmp", "one_dot": f"{JOURNAL}.0123456789abcdef.tmp",
             "user_file": "notes.0123456789abcdef.tmp"}
    for n in names.values():
        (ds / n).write_text("x")
    (ds / f".{JOURNAL}.fedcba9876543210.tmp").mkdir()  # a directory with a matching name
    (ROOT / "g05" / "outside").write_text("keep")
    os.symlink(ROOT / "g05" / "outside", ds / f".{JOURNAL}.aaaaaaaaaaaaaaaa.tmp")  # symlink with a matching name
    rcd, outd, _ = tool("recover", ds, "--dry-run", "--json")
    after_dry = sorted(p.name for p in ds.iterdir())
    rc, out, _ = tool("recover", ds, "--json")
    left = sorted(p.name for p in ds.iterdir())
    gone = [k for k, n in names.items() if n not in left]
    ok = gone == ["match"] and (ds / f".{JOURNAL}.fedcba9876543210.tmp").is_dir() and (ROOT / "g05" / "outside").read_text() == "keep" \
        and f".{JOURNAL}.aaaaaaaaaaaaaaaa.tmp" in left and len(after_dry) == len(left) + 1
    return ("OK" if ok else "FINDING"), f"dry run exit {rcd} removed nothing: {len(after_dry) == len(left) + 1}; recover exit {rc} removed {gone}; dir, symlink and outside file kept: {ok}"


def g06_recover_races_restore():
    base = ROOT / "g06"
    ds = base / "ds"
    make_db(ds, rows=10, big=40000)
    rc, out, _ = tool("snapshot", ds, "--out", base / "snap", "--json")
    sid = json.loads(out[out.index("{"):])["snapshot_id"]
    helper("import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"update t set v='LIVE' where id=1\"); c.commit()", ds / "app.db")
    results = []
    for rnd in range(10):
        r = subprocess.Popen([PY, TOOL, "restore", ds, "--snapshot", base / "snap", "--confirm", sid], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        rec = []
        while r.poll() is None:
            rec.append(tool("recover", ds)[0])
        rout = r.stdout.read()
        h = tool("health", ds, "--expect", "app.db", "--snapshot", base / "snap")
        live = helper("import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('select v from t where id=1').fetchone()[0])", ds / "app.db").stdout.strip()
        if r.returncode == 0:
            verdict = "restored" if h[0] == 0 and live == "r0" else f"BAD restored but health {h[0]} value {live!r}"
        elif "busy" in rout.lower():
            verdict = "busy-untouched" if live == "LIVE" else f"BAD busy but value {live!r}"
        else:
            verdict = f"BAD exit {r.returncode}: {rout[:80]!r}"
        results.append(verdict)
        helper("import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"update t set v='LIVE' where id=1\"); c.commit()", ds / "app.db")
    debris = sorted(p.name for p in ds.iterdir() if p.name.endswith(".tmp") or p.name == JOURNAL)
    ok = not any(v.startswith("BAD") for v in results) and not debris
    return ("OK" if ok else "FINDING"), (f"10 restores each raced by back-to-back recover: restored {results.count('restored')}, "
            f"refused busy with live values untouched {results.count('busy-untouched')}, bad {[v for v in results if v.startswith('BAD')]}; debris {debris}")


def g07_restore_into_fallback_sidecars():
    """On 3.9 the fallback leaves an empty -wal/-shm; a restore must still install exact values."""
    base = ROOT / "g07"
    ds = base / "ds"
    db = make_db(ds, wal=True, rows=5)
    for s in ("-wal", "-shm"):
        if (ds / ("app.db" + s)).exists():
            os.unlink(ds / ("app.db" + s))
    rc, out, _ = tool("snapshot", ds, "--out", base / "snap", "--json")
    sid = json.loads(out[out.index("{"):])["snapshot_id"] if "{" in out else None
    helper("import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"update t set v='LIVE' where id=1\"); c.commit(); c.close()", db)
    tool("health", ds, "--expect", "app.db")  # leaves fallback sidecars on Apple 3.54.0
    side_before = sorted(p.name for p in ds.iterdir())
    rr = tool("restore", ds, "--snapshot", base / "snap", "--confirm", sid)
    v = helper("import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('select v from t where id=1').fetchone()[0])", db).stdout.strip()
    h = tool("health", ds, "--expect", "app.db", "--snapshot", base / "snap")
    ok = rr[0] == 0 and v == "r0" and h[0] == 0
    return ("OK" if ok else "FINDING"), f"snapshot exit {rc}; dataset before restore {side_before}; restore exit {rr[0]}; id=1 value now {v!r} (want 'r0'); health vs snapshot exit {h[0]}"


try:
    print(f"# python {sys.version.split()[0]}? helper/tool interpreter: " + subprocess.run([PY, "-c", "import sys,sqlite3;print(sys.version.split()[0], sqlite3.sqlite_version)"], capture_output=True, text=True).stdout.strip())
    for f in (g01_parent_created_then_refused, g02_parent_via_symlinked_grandparent, g03_fallback_concurrency, g04_health_lock_timeout,
              g05_journal_temp_cleanup_scope, g06_recover_races_restore, g07_restore_into_fallback_sidecars):
        case(f)
finally:
    shutil.rmtree(ROOT, ignore_errors=True)
