#!/usr/bin/env python3
"""M03 adversarial cases (unseen by the builder's tests/oracle). Each case prints
OK (behaved safely), FINDING (defect, see VALIDATION.md) or NOTE (observation).
Usage: python m03_adversarial.py -- <candidate prefix...>"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m03_oracle as M  # noqa: E402  (helpers: fixture, mutate, vals, values, sql, tree, run, snap_id)

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def tb(out):
    return "Traceback (most recent call last)" in out


@case
def a01_sqlite_prefixed_user_table(tmp):
    base, ds = M.fixture(tmp, "a01")
    M.sql(ds / "app.db", "CREATE TABLE sqlitedata(k TEXT, v TEXT); INSERT INTO sqlitedata VALUES ('plan','GOOD');"
          "CREATE TABLE SQLiteLog(id INTEGER PRIMARY KEY, msg TEXT); INSERT INTO SQLiteLog(msg) VALUES ('ok');")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    good = M.values(ds / "app.db")
    M.sql(ds / "app.db", "UPDATE sqlitedata SET v='LIVE-CHANGED'; DELETE FROM SQLiteLog;")
    h, hout, _ = M.run("health", ds, "--expect", "app.db", "--snapshot", snap)
    r, rout, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid)
    after = M.values(ds / "app.db")
    if after != good:
        return "FINDING", (f"user tables sqlitedata/SQLiteLog changed after snapshot: health --snapshot rc={h}, restore rc={r} "
                           f"({rout.strip().splitlines()[-1][:120]}); values NOT restored")
    return "OK", "sqlite-prefixed user tables restored"


@case
def a02_user_version_only(tmp):
    base, ds = M.fixture(tmp, "a02")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    M.sql(ds / "app.db", "PRAGMA user_version = 9; PRAGMA application_id = 77;")
    h, _, _ = M.run("health", ds, "--expect", "app.db", "--snapshot", snap)
    r, rout, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid)
    c = sqlite3.connect(f"file:{ds / 'app.db'}?mode=ro", uri=True)
    uv, aid = c.execute("PRAGMA user_version").fetchone()[0], c.execute("PRAGMA application_id").fetchone()[0]
    c.close()
    if (uv, aid) != (3, 0):
        return "FINDING", f"user_version/application_id changed 3/0 -> 9/77: health --snapshot rc={h}, restore rc={r}; after restore {uv}/{aid}"
    return "OK", "header pragmas restored"


@case
def a03_zero_byte_expected_db(tmp):
    base, ds = M.fixture(tmp, "a03")
    (ds / "app.db").write_bytes(b"")
    h, out, _ = M.run("health", ds, "--expect", "app.db")
    h2, out2, _ = M.run("health", ds, "--expect", "app.db", "--snapshot", base / "nosnap")
    if h == 0:
        return "FINDING", f"0-byte app.db (all tables gone) reported healthy without --snapshot: rc=0 '{out.strip()[:80]}'"
    return "OK", f"0-byte db rejected rc={h}"


@case
def a04_tables_dropped_health_no_snapshot(tmp):
    base, ds = M.fixture(tmp, "a04")
    M.sql(ds / "app.db", "DROP TABLE customers; DROP TABLE ledger;")
    h, out, _ = M.run("health", ds, "--expect", "app.db")
    return "NOTE", f"health without --snapshot after dropping every user table: rc={h} (only --snapshot checks content)"


@case
def a05_case_alias_expect(tmp):
    base, ds = M.fixture(tmp, "a05")
    h, out, _ = M.run("health", ds, "--expect", "App.db")
    os.unlink(ds / "audit.db")
    h2, out2, _ = M.run("health", ds, "--expect", "Audit.db")
    return "NOTE", f"case-insensitive FS: --expect App.db with app.db present rc={h}; --expect Audit.db with audit.db absent rc={h2}"


@case
def a06_manifest_missing_tables_key(tmp):
    base, ds = M.fixture(tmp, "a06")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    man = json.loads((snap / "manifest.json").read_text())
    dbs = man.get("databases")
    entry = dbs["app.db"] if isinstance(dbs, dict) else None
    if entry is None or "tables" not in entry:
        return "NOTE", "manifest shape differs; case not applicable"
    del entry["tables"]
    (snap / "manifest.json").write_text(json.dumps(man))
    before = M.tree(ds)
    res = []
    for args in (["verify", snap], ["health", ds, "--expect", "app.db", "--snapshot", snap],
                 ["restore", ds, "--snapshot", snap, "--confirm", sid]):
        rc, out, _ = M.run(*args)
        res.append((args[0], rc, tb(out)))
    bad = [r for r in res if r[2] or (r[0] != "health" and r[1] == 0)]
    if bad or M.tree(ds) != before:
        return "FINDING", f"manifest entry without 'tables': {res} (cmd, rc, traceback); dataset unchanged={M.tree(ds) == before}"
    return "OK", f"manifest without 'tables' refused cleanly: {res}"


@case
def a07_journal_traversal(tmp):
    base, ds = M.fixture(tmp, "a07")
    victim = base / "outside" / "keep.txt"
    before_out = M.tree(base / "outside")
    before = M.tree(ds)
    j = {"schema": "solaris-recovery-journal/1", "state": "swapping", "snapshot_id": "x", "tag": "t", "started": "now",
         "steps": [{"kind": "set_aside", "from": "../outside/keep.txt", "to": "stolen.txt"}],
         "staged_sha256": {}}
    for schema in ("solaris-recovery-journal/1",):
        (ds / ".solaris-recovery.json").write_text(json.dumps(j))
        rc, out, _ = M.run("recover", ds)
    ok = victim.exists() and M.tree(base / "outside") == before_out and not (ds / "stolen.txt").exists()
    if not ok or tb(out):
        return "FINDING", f"forged journal with ../ step: recover rc={rc}, outside intact={ok}, traceback={tb(out)}"
    return "OK", f"forged traversal journal refused rc={rc}, outside untouched: {out.strip().splitlines()[0][:100]}"


@case
def a08_journal_onto_existing_file(tmp):
    base, ds = M.fixture(tmp, "a08")
    before = M.tree(ds)
    rc0, out0, _ = M.run("recover", ds, "--dry-run", "--json")
    # read the real schema string from a genuine interrupted run's journal
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    M.mutate(ds, "1")
    M.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--simulate-crash-after", "1")
    jf = ds / ".solaris-recovery.json"
    if not jf.exists():
        return "NOTE", "no journal after --simulate-crash-after 1; case not applicable"
    j = json.loads(jf.read_text())
    j["steps"].append({"kind": "set_aside", "from": "app.db", "to": "notes.txt"})
    jf.write_text(json.dumps(j))
    notes = (ds / "notes.txt").read_bytes()
    rc, out, _ = M.run("recover", ds)
    if (ds / "notes.txt").read_bytes() != notes or tb(out):
        return "FINDING", f"journal step renaming onto notes.txt: rc={rc}, notes.txt clobbered or traceback"
    return "OK", f"tampered journal (rename onto an existing file) changed nothing rc={rc}"


@case
def a09_journal_traversal_real_schema(tmp):
    base, ds = M.fixture(tmp, "a09")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    M.mutate(ds, "1")
    M.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--simulate-crash-after", "1")
    jf = ds / ".solaris-recovery.json"
    if not jf.exists():
        return "NOTE", "no journal; case not applicable"
    j = json.loads(jf.read_text())
    before_out = M.tree(base / "outside")
    for s in j["steps"]:
        if s["kind"] == "install":
            s["to"] = "../outside/keep.txt"
            break
    jf.write_text(json.dumps(j))
    rc, out, _ = M.run("recover", ds)
    if M.tree(base / "outside") != before_out or tb(out):
        return "FINDING", f"journal install step pointed at ../outside/keep.txt: rc={rc}, outside changed or traceback"
    return "OK", f"real-schema journal with ../ target refused rc={rc}; outside untouched"


@case
def a10_symlinked_live_db(tmp):
    base, ds = M.fixture(tmp, "a10")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    real = base / "outside" / "real-app.db"
    os.rename(ds / "app.db", real)
    os.symlink(real, ds / "app.db")
    M.sql(real, "UPDATE customers SET name='EXTERNAL' WHERE id=1;")
    outside = M.tree(base / "outside")
    rc, out, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid)
    h, hout, _ = M.run("health", ds, "--expect", "app.db")
    if M.tree(base / "outside") != outside or tb(out):
        return "FINDING", f"live app.db symlink to outside: restore rc={rc} wrote outside or tracebacked"
    return "OK", f"symlinked live DB: restore rc={rc}, outside target untouched; health rc={h}"


@case
def a11_lock_symlink_outside(tmp):
    base, ds = M.fixture(tmp, "a11")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    tgt = base / "outside" / "keep.txt"
    os.symlink(tgt, ds / ".solaris-recovery.lock")
    before = tgt.read_bytes()
    rc, out, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid)
    rc2, out2, _ = M.run("snapshot", ds, "--out", base / "snap2")
    if tgt.read_bytes() != before or tb(out + out2):
        return "FINDING", f"lock path symlinked outside: restore rc={rc}, snapshot rc={rc2}; outside changed or traceback"
    return "OK", f"symlinked lock file refused (restore rc={rc}, snapshot rc={rc2}); outside untouched"


@case
def a12_stale_rollback_journal_sidecar(tmp):
    base, ds = M.fixture(tmp, "a12")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    v_snap = M.vals(ds)
    M.mutate(ds, "1")
    (ds / "app.db-journal").write_bytes(b"\0" * 512)
    rc, out, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid)
    left = (ds / "app.db-journal").exists()
    if rc != 0 or left or M.vals(ds) != v_snap:
        return "FINDING", f"stray app.db-journal: restore rc={rc}, journal left next to restored DB={left}"
    return "OK", "app.db-journal sidecar set aside with the old copy; restored values exact"


@case
def a13_open_reader_during_restore(tmp):
    base, ds = M.fixture(tmp, "a13")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    M.mutate(ds, "1")
    v_live = M.vals(ds)
    holder = subprocess.Popen([sys.executable, "-c",
                               "import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1],isolation_level=None);"
                               "c.execute('BEGIN');c.execute('SELECT count(*) FROM customers').fetchone();"
                               "print('held',flush=True);time.sleep(30)", str(ds / "app.db")], stdout=subprocess.PIPE, text=True)
    try:
        holder.stdout.readline()
        rc, out, el = M.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--lock-timeout", "1", timeout=30)
    finally:
        holder.kill()
        holder.wait()
    return "NOTE", (f"open read transaction on app.db: restore rc={rc} in {el:.1f}s, values "
                    f"{'unchanged' if M.vals(ds) == v_live else 'restored'} (doc: probe refuses while another connection holds the DB)")


@case
def a14_nan_and_inf_timeout(tmp):
    base, ds = M.fixture(tmp, "a14")
    snap = base / "snap"
    sid = M.snap_id(ds, snap)
    res = []
    for v in ("nan", "inf", "-1", "0", "601", "1e-9"):
        rc, out, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--lock-timeout", v, "--dry-run")
        res.append(f"{v}:rc={rc}")
    return "NOTE", "--lock-timeout values (dry run): " + ", ".join(res)


@case
def a15_health_locked_wording(tmp):
    base, ds = M.fixture(tmp, "a15")
    holder = subprocess.Popen([sys.executable, "-c",
                               "import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1],isolation_level=None);"
                               "c.execute('BEGIN EXCLUSIVE');print('held',flush=True);time.sleep(30)", str(ds / "app.db")],
                              stdout=subprocess.PIPE, text=True)
    try:
        holder.stdout.readline()
        rc, out, el = M.run("health", ds, "--expect", "app.db", timeout=40)
    finally:
        holder.kill()
        holder.wait()
    line = [l for l in out.splitlines() if "app.db" in l]
    return "NOTE", f"health on an exclusively locked DB: rc={rc} after {el:.1f}s: {line[0].strip()[:110] if line else out[:110]}"


@case
def a16_snapshot_inside_dataset(tmp):
    base, ds = M.fixture(tmp, "a16")
    rc, out, _ = M.run("snapshot", ds, "--out", ds / "snaps" / "s1", "--json")
    if rc != 0:
        return "OK", f"snapshot into the dataset refused rc={rc}"
    sid = json.loads(out)["snapshot_id"]
    M.mutate(ds, "1")
    rc2, out2, _ = M.run("restore", ds, "--snapshot", ds / "snaps" / "s1", "--confirm", sid)
    rc3, out3, _ = M.run("snapshot", ds, "--out", ds / "snaps" / "s2", "--json")
    return "NOTE", f"snapshot inside the dataset accepted rc=0; restore from it rc={rc2}; second snapshot rc={rc3}"


@case
def a17_kill_on_every_write_open(tmp):
    """SIGKILL at each write-open under the dataset (staging copies, journal writes), then recover."""
    results, leftovers = [], []
    for n in range(1, 30):
        base, ds = M.fixture(tmp, f"a17-{n}")
        snap = base / "snap"
        sid = M.snap_id(ds, snap)
        M.mutate(ds, "1")
        v_live = M.vals(ds)
        v_snap = {k: M.values(snap / k) for k in ("app.db", "audit.db")}
        names_before = set(os.listdir(ds))
        rc, out, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid,
                           extra={"M03_KILL_ROOT": str(ds), "M03_KILL_WRITE_AT": str(n), "PYTHONPATH": str(M.INJECT)})
        if rc != -9:
            break
        r, rout, _ = M.run("recover", ds)
        cur = M.vals(ds)
        state = "live" if cur == v_live else "snap" if cur == v_snap else "MIXED"
        h, _, _ = M.run("health", ds, "--expect", "app.db", "--expect", "audit.db")
        extra = sorted(set(os.listdir(ds)) - names_before)
        # doc: "Snapshot and restore of a WAL database may create -wal/-shm files"; values() reads -wal too
        junk = [e for e in extra if ".pre-restore-" not in e and not e.endswith(("-wal", "-shm"))]
        if junk:
            leftovers.append((n, junk))
        results.append(f"w{n}:{state}/recover={r}/health={h}")
    bad = [r for r in results if "MIXED" in r or "health=0" not in r]
    if bad:
        return "FINDING", f"write-open kills: {bad}"
    if leftovers:
        return "FINDING", f"write-open kills recovered cleanly but left non-recoverable debris: {leftovers}"
    return "OK", f"{len(results)} write-open kill points: all recovered to live or snapshot values, health ok, no debris: {results}"


def main(argv):
    i = argv.index("--")
    M.CMD = argv[i + 1:]
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv[:i] else None
    tmp = Path(tempfile.mkdtemp(prefix="m03-adv-")).resolve()
    counts = {}
    try:
        for fn in CASES:
            if only and fn.__name__.split("_")[0] not in only:
                continue
            try:
                st, msg = fn(tmp)
            except M.Fail as e:
                st, msg = "FINDING", f"harness Fail: {e}"
            except Exception as e:
                st, msg = "ERROR", f"{type(e).__name__}: {str(e)[:300]}"
            counts[st] = counts.get(st, 0) + 1
            print(f"{st} {fn.__name__}: {msg}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SUMMARY " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main(sys.argv[1:])
