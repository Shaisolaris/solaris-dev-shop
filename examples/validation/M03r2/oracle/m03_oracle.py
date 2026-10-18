#!/usr/bin/env python3
"""M03 recovery oracle (written for M03; independent of the builder's recovery_oracle.py and tests).

Derived from the G03/M03 acceptance text: actual values restored; good target survives invalid
backup; dry-run byte-identical; both rename gaps recover; no outside writes; finite timeout; exact
missing-DB check; plus keep known good data and recoverable copies, row-count-independent
freshness and the documented dataset flock.

Black-box interface from database-administrator/sqlite-recovery.md only:
  <cmd> snapshot DATASET --out SNAPDIR --json        (prints snapshot_id)
  <cmd> verify SNAPDIR [--expect NAME]
  <cmd> health DATASET --expect NAME ... [--snapshot SNAPDIR]
  <cmd> restore DATASET --snapshot SNAPDIR [--confirm ID] [--dry-run] [--lock-timeout S]
  <cmd> recover DATASET [--dry-run]
Exit 0 ok, non-zero otherwise. Values are read by this oracle from COPIES of the database files
(every user table, sorted rows, schema SQL, user_version, application_id), never from tool output.
Nothing can SKIP into a pass. Usage: python m03_oracle.py [--only K1,K4] -- <candidate prefix...>
"""
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INJECT = HERE / "inject"
CMD = []


class Fail(Exception):
    pass


def need(c, m):
    if not c:
        raise Fail(m)


def env(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("M03_")}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def run(*args, extra=None, timeout=120):
    t0 = time.time()
    try:
        p = subprocess.run(CMD + [str(a) for a in args], capture_output=True, text=True, env=env(extra), timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Fail(f"candidate did not finish within {timeout}s: {args[:1]}")
    return p.returncode, p.stdout + p.stderr, time.time() - t0


def snap_id(ds, out):
    rc, out_, _ = run("snapshot", ds, "--out", out, "--json")
    need(rc == 0, f"snapshot rc={rc}: {out_[-200:]}")
    try:
        sid = json.loads(out_)["snapshot_id"]
    except (ValueError, KeyError, TypeError):
        raise Fail("snapshot printed no snapshot_id")
    need(isinstance(sid, str) and sid, "empty snapshot_id")
    need(Path(out).is_dir(), "snapshot directory not created")
    return sid


def tree(base, exclude=None):
    out = {}
    for dp, dn, fn in os.walk(base):
        for n in dn + fn:
            p = Path(dp) / n
            rel = p.relative_to(base).as_posix()
            if exclude and (rel == exclude or rel.startswith(exclude + "/")):
                continue
            out[rel] = ("L:" + os.readlink(p)) if p.is_symlink() else (
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "d")
    return out


def values(db):
    """All user values of one SQLite file, read from a private copy (with sidecars)."""
    db = Path(db)
    if not db.is_file() or db.stat().st_size == 0:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="m03v-"))
    try:
        for suf in ("", "-wal", "-journal"):
            if Path(str(db) + suf).is_file():
                shutil.copyfile(str(db) + suf, tmp / ("x.db" + suf))
        c = sqlite3.connect(tmp / "x.db")
        try:
            out = {"__user_version__": c.execute("PRAGMA user_version").fetchone()[0],
                   "__application_id__": c.execute("PRAGMA application_id").fetchone()[0],
                   "__schema__": sorted(r[0] or "" for r in c.execute("SELECT sql FROM sqlite_master"))}
            for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
                if t.startswith("sqlite_"):
                    continue  # reserved internal names only (case-sensitive prefix)
                out[t] = sorted(repr(r) for r in c.execute(f'SELECT * FROM "{t}"'))
            return out
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return "unreadable"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def all_value_sets(ds):
    """values() of every regular file in the dataset that opens as SQLite."""
    out = {}
    for p in Path(ds).iterdir():
        if p.is_file() and not p.is_symlink() and not p.name.endswith(("-wal", "-shm", "-journal", ".lock")):
            v = values(p)
            if isinstance(v, dict) and len(v) > 3:
                out[p.name] = v
    return out


def sql(db, script, wal=False):
    c = sqlite3.connect(db)
    if wal:
        c.execute("PRAGMA journal_mode=WAL")
    c.executescript(script)
    c.commit()
    c.close()


def fixture(tmp, label):
    base = Path(tempfile.mkdtemp(prefix=label + "-", dir=tmp)).resolve()
    ds = base / "data"
    ds.mkdir()
    (base / "outside").mkdir()
    (base / "outside" / "keep.txt").write_text("OUTSIDE - must not change\n")
    sql(ds / "app.db", """
        CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, balance REAL, avatar BLOB, note);
        CREATE TABLE ledger(k TEXT PRIMARY KEY, amount INTEGER) WITHOUT ROWID;
        CREATE INDEX cust_name ON customers(name);
        CREATE TRIGGER t_aud AFTER UPDATE ON customers BEGIN SELECT 1; END;
        INSERT INTO customers(name, balance, avatar, note) VALUES
          ('Ada', 10.5, x'00ff10', NULL), ('Bj\u00f6rk \u4e2d', -0.25, x'', ''), ('Cy', 1e300, NULL, 'x');
        INSERT INTO ledger VALUES ('a', 1), ('b', 2), ('c', 3);
        PRAGMA user_version = 3;""")
    sql(ds / "audit.db", "CREATE TABLE ev(id INTEGER PRIMARY KEY, what TEXT);"
        "INSERT INTO ev(what) VALUES ('boot'), ('login');", wal=True)
    (ds / "notes.txt").write_text("owner notes\n")
    (ds / "sub").mkdir()
    (ds / "sub" / "keep.md").write_text("owner sub file\n")
    return base, ds


def mutate(ds, tag="1"):
    sql(ds / "app.db", f"INSERT INTO customers(name, balance) VALUES ('New{tag}', 99);"
        f"UPDATE customers SET balance = balance + {tag} WHERE name = 'Ada';"
        "DELETE FROM ledger WHERE k = 'b';"
        f"INSERT INTO ledger VALUES ('z{tag}', 26);")
    sql(ds / "audit.db", f"INSERT INTO ev(what) VALUES ('after-snapshot-{tag}');")


def vals(ds):
    return {n: values(ds / n) for n in ("app.db", "audit.db")}


# --------------------------------------------------------------------------------- checks

def k1_restore_values(tmp):
    base, ds = fixture(tmp, "k1")
    v_snap = vals(ds)
    snap = base / "snap"
    sid = snap_id(ds, snap)
    rc, out, _ = run("verify", snap, "--expect", "app.db", "--expect", "audit.db")
    need(rc == 0, f"verify of a fresh snapshot failed rc={rc}")
    mutate(ds, "1")
    v_live = vals(ds)
    need(v_live != v_snap, "fixture mutation had no effect")
    out_before = tree(base / "outside")
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(rc == 0, f"restore rc={rc}: {out[-300:]}")
    need(vals(ds) == v_snap, "restored values differ from the snapshot-time values")
    need((ds / "notes.txt").read_text() == "owner notes\n" and (ds / "sub" / "keep.md").exists(), "other dataset files changed")
    sets = all_value_sets(ds)
    need(any(v == v_live["app.db"] for v in sets.values()), "pre-restore live app.db values not kept anywhere")
    need(any(v == v_live["audit.db"] for v in sets.values()), "pre-restore live audit.db values not kept anywhere")
    rc, out, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db", "--snapshot", snap)
    need(rc == 0, f"health after restore rc={rc}")
    # repeat: change again and restore again; both earlier live copies must survive
    mutate(ds, "2")
    v_live2 = vals(ds)
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(rc == 0 and vals(ds) == v_snap, "second restore did not restore snapshot values")
    sets = list(all_value_sets(ds).values())
    need(v_live["app.db"] in sets and v_live2["app.db"] in sets, "a repeat restore lost an earlier recoverable copy")
    need(tree(base / "outside") == out_before, "outside tree changed")
    # missing target database is recreated
    os.unlink(ds / "audit.db")
    for s in ("-wal", "-shm"):
        if (ds / ("audit.db" + s)).exists():
            os.unlink(ds / ("audit.db" + s))
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(rc == 0 and vals(ds) == v_snap, "missing audit.db not recreated with snapshot values")
    return "values restored exactly (3 types of change), old values kept, repeat keeps both copies, missing DB recreated"


def _variants(base, snap, ds):
    """Yield (label, broken_snapshot_dir, confirm_id or None). Each is a fresh copy of snap."""
    man = json.loads((snap / "manifest.json").read_text())
    sid = man.get("snapshot_id")
    other = base / "otherdb.db"
    sql(other, "CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT); INSERT INTO customers VALUES (1,'EVIL');")

    def copy(label):
        d = base / f"bad-{label}"
        shutil.copytree(snap, d, symlinks=True)
        return d

    d = copy("byteflip"); b = bytearray((d / "app.db").read_bytes()); b[len(b) // 2] ^= 0xFF
    (d / "app.db").write_bytes(bytes(b)); yield "byteflip", d, sid
    d = copy("truncated"); b = (d / "app.db").read_bytes(); (d / "app.db").write_bytes(b[: len(b) // 2]); yield "truncated", d, sid
    d = copy("swapped-db"); shutil.copyfile(other, d / "app.db"); yield "swapped-db", d, sid
    d = copy("forged-hash")
    shutil.copyfile(other, d / "app.db")
    m = json.loads((d / "manifest.json").read_text())
    entry = (m.get("databases") or {}).get("app.db")
    need(isinstance(entry, dict) and "sha256" in entry, "manifest has no per-file sha256: tamper detection unprovable")
    entry["sha256"] = hashlib.sha256((d / "app.db").read_bytes()).hexdigest()
    if "size" in entry:
        entry["size"] = (d / "app.db").stat().st_size
    (d / "manifest.json").write_text(json.dumps(m)); yield "forged-hash", d, sid
    d = copy("extra-member"); shutil.copyfile(other, d / "evil.db"); yield "extra-member", d, sid
    d = copy("symlink-member"); os.unlink(d / "app.db"); os.symlink(other, d / "app.db"); yield "symlink-member", d, sid
    d = copy("hardlink-member"); os.link(d / "app.db", base / f"hl-{time.time_ns()}"); yield "hardlink-member", d, sid
    d = copy("manifest-not-json"); (d / "manifest.json").write_text("{nope"); yield "manifest-not-json", d, sid
    d = copy("manifest-missing"); os.unlink(d / "manifest.json"); yield "manifest-missing", d, sid
    d = copy("traversal-name"); m = json.loads((d / "manifest.json").read_text())
    m["databases"]["../escape.db"] = m["databases"]["app.db"]; (d / "manifest.json").write_text(json.dumps(m))
    yield "traversal-name", d, sid
    d = copy("member-missing"); os.unlink(d / "audit.db"); yield "member-missing", d, sid
    yield "wrong-confirm", snap, "0" * 16
    yield "no-confirm", snap, None


def k2_invalid_backup(tmp):
    base, ds = fixture(tmp, "k2")
    snap = base / "snap"
    snap_id(ds, snap)
    mutate(ds, "1")
    before, out_before = tree(ds), tree(base / "outside")
    done = []
    for label, d, sid in _variants(base, snap, ds):
        args = ["restore", ds, "--snapshot", d] + (["--confirm", sid] if sid else [])
        rc, out, _ = run(*args)
        need(rc != 0, f"{label}: invalid snapshot restore exited 0")
        need(tree(ds) == before, f"{label}: dataset changed (good target not preserved byte-for-byte)")
        need(tree(base / "outside") == out_before, f"{label}: outside changed")
        rc2, _, _ = run("verify", d) if label not in ("wrong-confirm", "no-confirm") else (1, "", 0)
        need(rc2 != 0, f"{label}: verify accepted the broken snapshot")
        done.append(label)
    return f"{len(done)} invalid snapshots refused; dataset byte-identical; verify rejects each"


def k3_dry_run(tmp):
    base, ds = fixture(tmp, "k3")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    mutate(ds, "1")
    # leave a real -wal/-shm behind: a writer killed with autocheckpoint off
    code = ("import sqlite3,os;c=sqlite3.connect(%r);c.execute('PRAGMA wal_autocheckpoint=0');"
            "c.execute(\"INSERT INTO ev(what) VALUES ('uncheckpointed')\");c.commit();os._exit(0)") % str(ds / "audit.db")
    subprocess.run([sys.executable, "-c", code], check=True)
    need((ds / "audit.db-wal").exists(), "fixture: no -wal left")
    b_ds, b_snap, b_out = tree(ds), tree(snap), tree(base / "outside")
    st_before = {n: os.lstat(ds / n).st_mtime_ns for n in os.listdir(ds)}
    for args in (["restore", ds, "--snapshot", snap, "--dry-run"], ["restore", ds, "--snapshot", snap, "--dry-run", "--confirm", sid],
                 ["recover", ds, "--dry-run"], ["verify", snap]):
        rc, out, _ = run(*args)
        need(tree(ds) == b_ds, f"{args[0]} {' '.join(map(str, args[3:]))}: dataset bytes or names changed")
        need(tree(snap) == b_snap, f"{args[0]}: snapshot changed")
        need(tree(base / "outside") == b_out, f"{args[0]}: outside changed")
    need({n: os.lstat(ds / n).st_mtime_ns for n in os.listdir(ds)} == st_before, "a read-only command touched mtimes")
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--dry-run", "--confirm", sid)
    need(rc == 0, "dry run with --confirm exited non-zero")
    # health is a normal SQLite reader: it may refresh the derived -shm index, nothing else
    run("health", ds, "--expect", "app.db", "--snapshot", snap)
    strip = lambda t: {k: v for k, v in t.items() if not k.endswith("-shm")}
    need(strip(tree(ds)) == strip(b_ds), "health changed a database, -wal or other file")
    return "dry runs (with and without --confirm), recover --dry-run, verify: dataset (incl. -wal/-shm), snapshot, outside byte-identical, mtimes unchanged; health changes only -shm"


def _old_and_new_kept(ds, v_live, v_snap):
    cur = vals(ds)
    sets = list(all_value_sets(ds).values())
    if cur == v_snap:
        return "forward", all(v_live[n] in sets for n in v_live)
    if cur == v_live:
        return "back", True
    return "mixed", False


def k4_rename_gaps(tmp):
    """SIGKILL before every rename/unlink event of a restore, then recover; plus a forced roll-back."""
    seen = {"db_missing": 0, "installed_unfinished": 0, "forward": 0, "back": 0}
    events = 0
    for n in range(1, 25):
        base, ds = fixture(tmp, f"k4-{n}")
        snap = base / "snap"
        sid = snap_id(ds, snap)
        mutate(ds, "1")
        v_snap_now, v_live = None, vals(ds)
        v_snap = {k: values(snap / k) for k in ("app.db", "audit.db")}
        log = base / "events.log"
        rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid,
                         extra={"M03_KILL_ROOT": str(ds), "M03_KILL_AT": str(n), "M03_EVENT_LOG": str(log),
                                "PYTHONPATH": str(INJECT)})
        if rc != -9:
            events = n - 1
            break
        cur = vals(ds)
        if cur["app.db"] is None or cur["audit.db"] is None:
            seen["db_missing"] += 1
        elif cur == v_snap:
            seen["installed_unfinished"] += 1
        if cur != v_live:
            rc, out, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db")
            need(rc != 0, f"kill@{n}: dataset is mid-swap but health says ok")
        rc, out, _ = run("recover", ds)
        need(rc in (0, 1), f"recover after kill@{n} rc={rc}: {out[-200:]}")
        state, kept = _old_and_new_kept(ds, v_live, v_snap)
        need(state != "mixed", f"kill@{n}: recover left a mixed state")
        need(kept, f"kill@{n}: rolled forward but the old live values were not kept")
        seen[state] += 1
        rc, out, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        need(rc == 0, f"kill@{n}: health still failing after recover")
        rc, out, _ = run("recover", ds)
        need(rc == 0, f"kill@{n}: second recover rc={rc}")
        if state == "back":  # a later restore must still work
            rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
            need(rc == 0 and vals(ds) == v_snap, f"kill@{n}: restore after roll-back failed")
    need(events >= 3, f"restore made only {events} rename/unlink events: nothing to interrupt")
    need(seen["db_missing"] >= 1, "no kill landed in the gap where a database was set aside but not installed")
    need(seen["installed_unfinished"] >= 1, "no kill landed after install but before the restore finished")
    # forced roll-back: kill in the db-missing gap, then damage the staged copy
    rolled = 0
    for n in range(1, events + 1):
        base, ds = fixture(tmp, f"k4rb-{n}")
        snap = base / "snap"
        sid = snap_id(ds, snap)
        mutate(ds, "1")
        v_live = vals(ds)
        snap_bytes = {(snap / k).read_bytes() for k in ("app.db", "audit.db")}
        run("restore", ds, "--snapshot", snap, "--confirm", sid,
            extra={"M03_KILL_ROOT": str(ds), "M03_KILL_AT": str(n), "PYTHONPATH": str(INJECT)})
        cur = vals(ds)
        if cur["app.db"] is not None and cur["audit.db"] is not None:
            continue
        staged = [p for p in ds.iterdir() if p.is_file() and p.read_bytes() in snap_bytes and p.name not in ("app.db", "audit.db")]
        need(staged, f"rb@{n}: database missing but no staged copy found")
        for p in staged:
            with open(p, "r+b") as fh:
                fh.seek(100)
                fh.write(b"\xde\xad\xbe\xef")
        # the doc: recover rolls forward only when every staged copy verifies; the preview must say so
        rc, out, _ = run("recover", ds, "--dry-run", "--json")
        need("roll_back" in out and "roll_forward" not in out,
             f"rb@{n}: staged copy does not verify, but recover --dry-run does not plan a roll-back: {out[-200:]}")
        rc, out, _ = run("recover", ds)
        need(vals(ds) == v_live, f"rb@{n}: damaged staged copy, yet originals were not put back exactly")
        rc, out, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        need(rc == 0, f"rb@{n}: health failing after roll-back")
        rolled += 1
    need(rolled >= 1, "forced roll-back never exercised")
    return (f"{events} kill points; gaps hit: db-missing {seen['db_missing']}, installed-unfinished "
            f"{seen['installed_unfinished']}; recovered forward {seen['forward']}, back {seen['back']}; "
            f"forced roll-back with damaged staged copy x{rolled}: originals exact")


def k5_recover_killed(tmp):
    """Kill the recover itself, then recover again."""
    done = 0
    for n in range(1, 8):
        base, ds = fixture(tmp, f"k5-{n}")
        snap = base / "snap"
        sid = snap_id(ds, snap)
        mutate(ds, "1")
        v_live = vals(ds)
        v_snap = {k: values(snap / k) for k in ("app.db", "audit.db")}
        run("restore", ds, "--snapshot", snap, "--confirm", sid,
            extra={"M03_KILL_ROOT": str(ds), "M03_KILL_AT": "3", "PYTHONPATH": str(INJECT)})
        rc, _, _ = run("recover", ds, extra={"M03_KILL_ROOT": str(ds), "M03_KILL_AT": str(n), "PYTHONPATH": str(INJECT)})
        rc, out, _ = run("recover", ds)
        need(rc in (0, 1), f"recover after killed recover@{n} rc={rc}: {out[-200:]}")
        state, kept = _old_and_new_kept(ds, v_live, v_snap)
        need(state != "mixed" and kept, f"killed recover@{n}: state {state}, old values kept={kept}")
        rc, _, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        need(rc == 0, f"killed recover@{n}: health failing")
        done += 1
    return f"recover killed at 7 points, second recover consistent each time"


def k6_outside_writes(tmp):
    base, ds = fixture(tmp, "k6")
    (ds / "link.txt").symlink_to(base / "outside" / "keep.txt")
    other = base / "outside" / "ext.db"
    sql(other, "CREATE TABLE t(v); INSERT INTO t VALUES ('outside db');")
    out0 = tree(base / "outside")
    rc, out, _ = run("snapshot", ds, "--out", ds / "inner-snap", "--json")
    need(rc != 0 and not (ds / "inner-snap").exists(), "snapshot inside the dataset was not refused")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    mutate(ds, "1")
    run("restore", ds, "--snapshot", snap, "--confirm", sid)
    run("recover", ds)
    (ds / "ext.db").symlink_to(other)
    b = tree(ds)
    rc, out, _ = run("snapshot", ds, "--out", base / "snap2", "--db", "ext.db", "--json")
    rc2, out2, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(tree(base / "outside") == out0, "outside tree changed (symlinked file or database followed)")
    need((ds / "link.txt").is_symlink() and (ds / "ext.db").is_symlink(), "owner symlinks removed")
    return "snapshot inside dataset refused; symlinked file and database never followed; outside identical"


def k7_finite_timeout(tmp):
    base, ds = fixture(tmp, "k7")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    mutate(ds, "1")
    ready = base / "held"
    holder = subprocess.Popen([sys.executable, "-c",
                               "import sqlite3,time,sys;c=sqlite3.connect(sys.argv[1],isolation_level=None);"
                               "c.execute('BEGIN EXCLUSIVE');open(sys.argv[2],'w').close();time.sleep(120)",
                               str(ds / "app.db"), str(ready)])
    try:
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.05)
        need(ready.exists(), "fixture: lock holder did not start")
        v_live, b = vals(ds), {k: v for k, v in tree(ds).items()}
        rc, out, dt = run("restore", ds, "--snapshot", snap, "--confirm", sid, "--lock-timeout", "1", timeout=40)
        need(rc != 0, "restore succeeded while another connection held an exclusive lock")
        need(dt < 15, f"restore with --lock-timeout 1 took {dt:.1f}s")
        need(vals(ds) == v_live and tree(ds) == b, "busy restore changed the dataset")
        rc, out, dt2 = run("snapshot", ds, "--out", base / "snap-busy", "--lock-timeout", "1", "--json", timeout=40)
        need(dt2 < 15, f"snapshot with --lock-timeout 1 took {dt2:.1f}s")
        need(rc != 0 and not (base / "snap-busy").exists(), "snapshot of a locked db reported success or left a dir")
        rc, out, dt3 = run("health", ds, "--expect", "app.db", timeout=60)
        need(dt3 < 30, f"health on a locked db took {dt3:.1f}s")
    finally:
        holder.kill()
        holder.wait()
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(rc == 0, "restore after the lock was released failed")
    return f"held exclusive lock: restore {dt:.1f}s non-zero unchanged, snapshot {dt2:.1f}s non-zero no dir, health {dt3:.1f}s; works after release"


def k8_missing_db(tmp):
    base, ds = fixture(tmp, "k8")
    snap = base / "snap"
    snap_id(ds, snap)
    exp = ["--expect", "app.db", "--expect", "audit.db"]
    rc, out, _ = run("health", ds, *exp)
    need(rc == 0, f"healthy control failed rc={rc}")
    for s in ("-wal", "-shm"):
        if (ds / ("audit.db" + s)).exists():
            os.unlink(ds / ("audit.db" + s))
    cases = []
    os.rename(ds / "audit.db", ds / "audit.db.old")
    rc, out, _ = run("health", ds, *exp); need(rc != 0 and "audit.db" in out, "missing audit.db not reported by name"); cases.append("renamed")
    rc, out, _ = run("health", ds, "--snapshot", snap); need(rc != 0, "missing db not caught via --snapshot"); cases.append("via-snapshot")
    (ds / "audit.db").mkdir()
    rc, out, _ = run("health", ds, *exp); need(rc != 0, "directory named audit.db passed"); cases.append("directory")
    os.rmdir(ds / "audit.db"); (ds / "audit.db").symlink_to(ds / "audit.db.old")
    rc, out, _ = run("health", ds, *exp); need(rc != 0, "symlinked audit.db passed as the expected database"); cases.append("symlink")
    os.unlink(ds / "audit.db"); (ds / "audit.db").write_bytes(b"")
    rc, out, _ = run("health", ds, "--snapshot", snap); need(rc != 0, "0-byte audit.db passed health --snapshot"); cases.append("empty-vs-snapshot")
    (ds / "audit.db").write_bytes(b"not a database at all" * 50)
    rc, out, _ = run("health", ds, *exp); need(rc != 0, "garbage audit.db passed"); cases.append("garbage")
    rc, out, _ = run("health", ds, "--expect", "app.db"); need(rc == 0, "health of app.db alone failed (over-broad check)")
    return "missing/renamed/dir/symlink/empty/garbage expected DB fail by name; positive controls pass: " + ",".join(cases)


def k9_concurrency(tmp):
    """Races are probabilistic: six independent rounds of 8 concurrent restores, every round must be clean."""
    seen = []
    for r in range(6):
        seen.append(_k9_round(tmp, r))
    return "6 rounds x 8 concurrent restores, values exact and live values kept every round; exit codes " + "; ".join(seen)


def _k9_round(tmp, r):
    base, ds = fixture(tmp, f"k9-{r}")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    mutate(ds, "1")
    v_live = vals(ds)
    v_snap = {k: values(snap / k) for k in ("app.db", "audit.db")}
    procs = [subprocess.Popen(CMD + ["restore", str(ds), "--snapshot", str(snap), "--confirm", sid],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env()) for _ in range(8)]
    codes = [p.wait(timeout=120) for p in procs]
    need(any(c == 0 for c in codes), f"round {r}: no concurrent restore succeeded: {codes}")
    need(vals(ds) == v_snap, f"round {r}: concurrent restores did not end on snapshot values")
    need(all(v_live[k] in list(all_value_sets(ds).values()) for k in v_live), f"round {r}: concurrent restores lost the live values")
    rc, out, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db", "--snapshot", snap)
    need(rc == 0, f"round {r}: health after concurrent restores failed")
    need(not [x for x in os.listdir(ds) if x.endswith((".staged", ".tmp")) or x == ".solaris-recovery.json"],
         f"round {r}: concurrent restores left staging/journal debris")
    return "".join(str(c) for c in sorted(codes))


def k10_value_fidelity(tmp):
    """Values the oracle reads but an implementation might not compare: a user table whose name starts
    with 'sqlite' (not the reserved 'sqlite_' prefix) and the user_version header."""
    base, ds = fixture(tmp, "k10")
    sql(ds / "app.db", "CREATE TABLE sqlitedata(id INTEGER PRIMARY KEY, v TEXT); INSERT INTO sqlitedata(v) VALUES ('orig');"
        "CREATE TABLE SQLiteLog(id INTEGER PRIMARY KEY, v TEXT); INSERT INTO SQLiteLog(v) VALUES ('orig');")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    v_snap = vals(ds)
    results = []
    for label, change in (("table sqlitedata", "UPDATE sqlitedata SET v = 'changed';"),
                          ("table SQLiteLog", "DELETE FROM SQLiteLog;"),
                          ("user_version", "PRAGMA user_version = 99;")):
        sql(ds / "app.db", change)
        rc_h, _, _ = run("health", ds, "--snapshot", snap)
        rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
        ok = vals(ds) == v_snap
        results.append(f"{label}: health_rc={rc_h} restore_rc={rc} values_restored={ok}")
        if not ok:
            raise Fail(f"{label} changed after snapshot; restore rc={rc} but values not restored "
                       f"(health before restore rc={rc_h}). " + "; ".join(results))
        need(rc_h != 0, f"{label}: health --snapshot said ok while values differed")
    return "; ".join(results)



def k11_same_count_change(tmp):
    """Doc: 'Freshness is never guessed from row counts'. Change values only, same row counts, no sidecar."""
    base, ds = fixture(tmp, "k11")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    v_snap = vals(ds)
    sql(ds / "app.db", "UPDATE customers SET note = 'edited', balance = 0 WHERE name = 'Cy';"
        "UPDATE ledger SET amount = 999 WHERE k = 'a';")
    need(not (ds / "app.db-wal").exists(), "fixture left a -wal")
    v_live = vals(ds)
    need(v_live != v_snap and len(v_live["app.db"]) == len(v_snap["app.db"]), "fixture change ineffective")
    rc, out, _ = run("health", ds, "--expect", "app.db", "--expect", "audit.db", "--snapshot", snap)
    need(rc != 0, "health --snapshot says ok although values differ with equal row counts")
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(rc == 0 and vals(ds) == v_snap, f"equal-count value change not restored (rc={rc}): {out[-200:]}")
    need(v_live["app.db"] in list(all_value_sets(ds).values()), "edited values not kept")
    return "value-only change with equal row counts: health fails, restore restores exact values, edits kept"


HOLD = (
    "import fcntl, os, sys, time\n"
    "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
    "fcntl.flock(fd, fcntl.LOCK_EX)\n"
    "print('held', flush=True)\n"
    "time.sleep(60)\n")


def k12_external_flock(tmp):
    """Doc: 'snapshot, restore and recover hold an flock on .solaris-recovery.lock'. A holder must block restore."""
    base, ds = fixture(tmp, "k12")
    snap = base / "snap"
    sid = snap_id(ds, snap)
    mutate(ds, "1")
    v_live = vals(ds)
    holder = subprocess.Popen([sys.executable, "-c", HOLD, str(ds / ".solaris-recovery.lock")],
                              stdout=subprocess.PIPE, text=True)
    try:
        need(holder.stdout.readline().strip() == "held", "lock holder did not start")
        before = tree(ds)
        rc, out, el = run("restore", ds, "--snapshot", snap, "--confirm", sid, "--lock-timeout", "1", timeout=30)
        held_rc = rc
        need(rc != 0, f"restore succeeded while another process held the dataset lock (rc={rc})")
        need(vals(ds) == v_live and tree(ds) == before, "restore changed the dataset while the lock was held")
    finally:
        holder.kill()
        holder.wait()
    rc, out, _ = run("restore", ds, "--snapshot", snap, "--confirm", sid)
    need(rc == 0, f"restore after the lock was released rc={rc}")
    return f"external flock holder: restore refused rc={held_rc} in {el:.1f}s, dataset byte-identical; works after release"

CHECKS = [k1_restore_values, k2_invalid_backup, k3_dry_run, k4_rename_gaps, k5_recover_killed, k6_outside_writes,
          k7_finite_timeout, k8_missing_db, k9_concurrency, k10_value_fidelity,
          k11_same_count_change, k12_external_flock]


def main(argv):
    global CMD
    if "--" not in argv:
        print(__doc__)
        return 2
    i = argv.index("--")
    opts, CMD = argv[:i], argv[i + 1:]
    only = set(opts[opts.index("--only") + 1].split(",")) if "--only" in opts else None
    tmp = Path(tempfile.mkdtemp(prefix="m03-oracle-")).resolve()
    passed = failed = 0
    print(f"# m03_oracle candidate: {' '.join(CMD)}")
    try:
        for chk in CHECKS:
            key = chk.__name__.split("_")[0].upper()
            if only and key not in only:
                continue
            t0 = time.time()
            try:
                msg = chk(tmp)
                passed += 1
                print(f"PASS {chk.__name__} ({time.time() - t0:.1f}s): {msg}")
            except Fail as exc:
                failed += 1
                print(f"FAIL {chk.__name__}: {exc}")
            except Exception as exc:
                failed += 1
                print(f"FAIL {chk.__name__}: {type(exc).__name__}: {str(exc)[:300]}")
            sys.stdout.flush()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = passed + failed
    verdict = "ACCEPTS" if failed == 0 and total else "REJECTS"
    print(f"SUMMARY {passed}/{total} pass; oracle {verdict} candidate")
    return 0 if verdict == "ACCEPTS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
