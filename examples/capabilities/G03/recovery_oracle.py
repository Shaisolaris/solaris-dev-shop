#!/usr/bin/env python3
"""Adversarial oracle for G03 local SQLite recovery (stdlib, synthetic data, disposable dirs).

Checks real outcomes: row values read back with sqlite3, byte hashes of every dataset
file, outside sentinels, elapsed time and leftover files. Exit 0, echoed input or
"nothing changed" never pass on their own; a missing or crashing candidate fails.

Candidate interface (adapter), a command prefix accepting:
  snapshot DATASET --out SNAP --json          -> JSON with "snapshot_id"
  verify SNAP [--expect NAME]                 -> exit 0 only if usable
  health DATASET --expect NAME ...            -> exit 0 only if every NAME is a healthy DB
  restore DATASET --snapshot SNAP --confirm ID [--dry-run] [--lock-timeout S]
          [--simulate-crash-after N]          -> N-th rename then hard exit (drill)
  recover DATASET                             -> finish or roll back an interrupted restore
Usage: python recovery_oracle.py -- <candidate command prefix...>
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SEED = [(1, "alpha"), (2, "bravo"), (3, "charlie")]


class Fail(Exception):
    pass


def need(c, m):
    if not c:
        raise Fail(m)


def tree(d):
    d = Path(d)
    return {p.relative_to(d).as_posix(): ("link:" + os.readlink(p) if p.is_symlink() else
                                          hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir")
            for p in sorted(d.rglob("*"))}


def make_db(path, rows=SEED, table="items"):
    c = sqlite3.connect(path)
    c.execute(f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, v TEXT)")
    c.executemany(f"INSERT INTO {table} VALUES (?, ?)", rows)
    c.commit()
    c.close()


def values(path, table="items"):
    if not Path(path).is_file():
        return None
    try:
        c = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            return c.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return None


def sql(path, s):
    c = sqlite3.connect(path)
    c.executescript(s)
    c.commit()
    c.close()


def any_file_holds(d, row, table="items"):
    for p in Path(d).iterdir():
        if p.is_file() and not p.is_symlink():
            v = values(p, table)
            if v and row in v:
                return p.name
    return None


class Oracle:
    def __init__(self, cmd, base):
        self.cmd, self.base, self.n = cmd, base, 0
        self.outside = base / "outside"
        self.outside.mkdir()
        (self.outside / "sentinel.db").write_bytes(b"KEEP")

    def run(self, *a, timeout=60):
        p = subprocess.run(self.cmd + [str(x) for x in a], capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        need("Traceback" not in p.stderr, "candidate crashed: " + p.stderr.strip()[-300:])
        return p

    def fresh(self, name, dbs=("app.db",)):
        self.n += 1
        root = self.base / f"{self.n:02d}-{name}"
        ds = root / "data"
        ds.mkdir(parents=True)
        for d in dbs:
            make_db(ds / d)
        (ds / "notes.txt").write_text("owner notes, not a database\n")
        return root, ds

    def snap(self, root, ds, name="snap"):
        p = self.run("snapshot", ds, "--out", root / name, "--json")
        need(p.returncode == 0, f"snapshot exit {p.returncode}: {p.stdout.strip()[:200]}")
        try:
            sid = json.loads(p.stdout)["snapshot_id"]
        except (ValueError, KeyError, TypeError):
            raise Fail("snapshot --json gave no snapshot_id")
        need((root / name).is_dir() and any((root / name).iterdir()), "snapshot directory empty or missing")
        return root / name, sid

    def outside_ok(self):
        need(tree(self.outside) == {"sentinel.db": hashlib.sha256(b"KEEP").hexdigest()}, "outside sentinel changed")

    # C1
    def c1_values_restored(self):
        root, ds = self.fresh("clean")
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='damaged'; DELETE FROM items WHERE id=3;")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        need(p.returncode == 0, f"restore exit {p.returncode}: {p.stdout.strip()[:300]}")
        need(values(ds / "app.db") == SEED, f"values after restore {values(ds / 'app.db')}")
        need((ds / "notes.txt").read_text() == "owner notes, not a database\n", "unrelated file changed")
        need(any_file_holds(ds, (1, "damaged")), "the replaced live file was not kept as a recoverable copy")
        need(self.run("health", ds, "--expect", "app.db").returncode == 0, "health fails after a good restore")
        return "exact values back; previous file kept; neighbour untouched; health 0"

    # C2
    def c2_good_target_survives_invalid_snapshots(self):
        out = []
        for case in ("flipped-byte", "garbage-manifest", "link-member", "forged-values", "truncated", "extra-member"):
            root, ds = self.fresh("bad-" + case)
            snap, sid = self.snap(root, ds)
            sql(ds / "app.db", "UPDATE items SET v='live-good' WHERE id=1;")
            dbfile = next((p for p in snap.iterdir() if p.is_file() and values(p) is not None), None)
            need(dbfile is not None, "snapshot holds no readable database copy")
            if case == "flipped-byte":
                b = bytearray(dbfile.read_bytes()); b[len(b) // 2] ^= 0xFF; dbfile.write_bytes(bytes(b))
            elif case == "garbage-manifest":
                for p in snap.iterdir():
                    if p != dbfile and p.is_file():
                        p.write_text("{not json")
            elif case == "link-member":
                dbfile.unlink(); dbfile.symlink_to(self.outside / "sentinel.db")
            elif case == "extra-member":
                (snap / "extra.db").write_bytes(dbfile.read_bytes())
            elif case == "forged-values":
                sql(dbfile, "UPDATE items SET v='forged' WHERE id=2;")
            else:
                dbfile.write_bytes(dbfile.read_bytes()[:100])
            before = tree(ds)
            p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
            need(p.returncode != 0, f"{case}: invalid snapshot restored (exit 0)")
            need(tree(ds) == before, f"{case}: target directory changed")
            self.outside_ok()
            if case != "garbage-manifest":
                need(self.run("verify", snap).returncode != 0, f"{case}: verify accepted it")
            out.append(case)
        return "refused with target byte-identical: " + ", ".join(out)

    # C3
    def c3_dry_run_byte_identical(self):
        root, ds = self.fresh("dry")
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        before, sbefore = tree(ds), tree(snap)
        mt = {p.name: p.stat().st_mtime_ns for p in ds.iterdir()}
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--dry-run")
        need(p.returncode == 0, "dry run failed")
        need(tree(ds) == before and tree(snap) == sbefore, "dry run changed bytes or added files")
        need({p.name: p.stat().st_mtime_ns for p in ds.iterdir()} == mt, "dry run touched mtimes")
        need(values(ds / "app.db") == [(i, "live") for i in (1, 2, 3)], "dry run restored values")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        need(p.returncode == 0 and values(ds / "app.db") == SEED, "real restore after dry run did not restore")
        return "dataset and snapshot byte- and mtime-identical; a later real run restores"

    def _crash(self, n, name):
        root, ds = self.fresh(name)
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--simulate-crash-after", n)
        need(p.returncode not in (0,), f"crash drill after rename {n} exited 0")
        return root, ds, snap, sid

    # C4
    def c4_gap_target_absent(self):
        root, ds, snap, sid = self._crash(1, "gap1")
        need(values(ds / "app.db") is None, "after the first rename the target should be set aside")
        shutil.rmtree(snap)
        p = self.run("recover", ds)
        need(p.returncode == 0, f"recover exit {p.returncode}")
        need(values(ds / "app.db") == SEED, f"gap 1 not rolled forward: {values(ds / 'app.db')}")
        need(any_file_holds(ds, (1, "live")), "the live file was lost")
        root, ds, snap, sid = self._crash(1, "gap1-bad-stage")
        for p in ds.iterdir():
            if p.name.startswith(".") and values(p) == SEED:
                p.write_bytes(b"damaged stage")
        p = self.run("recover", ds, "--dry-run", "--json")
        try:
            preview = json.loads(p.stdout).get("decision")
        except ValueError:
            preview = None
        need(preview == "roll_back", f"recover --dry-run previews {preview!r} for a damaged stage, expected roll_back")
        self.run("recover", ds)
        need(values(ds / "app.db") == [(i, "live") for i in (1, 2, 3)], "damaged stage: original not put back")
        return "target absent + snapshot deleted -> rolled forward; damaged stage -> original back"

    # C5
    def c5_gap_after_install(self):
        root, ds, snap, sid = self._crash(2, "gap2")
        p = self.run("recover", ds)
        need(p.returncode == 0 and values(ds / "app.db") == SEED, "gap 2 not completed")
        need(self.run("recover", ds).returncode == 0 and values(ds / "app.db") == SEED, "second recover not stable")
        need(not [x for x in os.listdir(ds) if x.endswith((".json", ".lock", ".staged", ".tmp"))],
             "journal, lock or staged file left behind")
        return "installed-but-unfinished swap completed; second recover stable"

    # C6
    def c6_no_outside_writes(self):
        root, ds = self.fresh("contain")
        snap, sid = self.snap(root, ds)
        (snap / "bridge").symlink_to(self.outside)
        siblings = {p.name: tree(p) if p.is_dir() else p.read_bytes() for p in root.iterdir() if p.name != "data"}
        self.run("verify", snap)
        self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        self.outside_ok()
        need({p.name: tree(p) if p.is_dir() else p.read_bytes() for p in root.iterdir() if p.name != "data"}
             == siblings, "a file outside the dataset changed")
        return "link member never followed; sentinel and sibling dirs unchanged"

    # C7
    def c7_finite_timeout(self):
        root, ds = self.fresh("locked")
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        holder = subprocess.Popen([sys.executable, "-c", "import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1],"
                                   "isolation_level=None);c.execute('BEGIN EXCLUSIVE');print('held',flush=True);"
                                   "time.sleep(120)", str(ds / "app.db")], stdout=subprocess.PIPE, text=True)
        try:
            need(holder.stdout.readline().strip() == "held", "could not hold the lock")
            before = tree(ds)
            t = time.monotonic()
            try:
                p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--lock-timeout", "1", timeout=30)
            except subprocess.TimeoutExpired:
                raise Fail("restore over a locked target did not finish within 30s")
            dt = time.monotonic() - t
            need(p.returncode != 0, "restore over a locked target exited 0")
            need(tree(ds) == before, "locked target was changed")
            t = time.monotonic()
            try:
                p = self.run("snapshot", ds, "--out", root / "snap-locked", "--json", timeout=30)
            except subprocess.TimeoutExpired:
                raise Fail("snapshot of a locked source did not finish within 30s")
            dt2 = time.monotonic() - t
            need(p.returncode != 0 and not (root / "snap-locked").exists(), "snapshot of a locked source claimed success")
        finally:
            holder.kill(); holder.wait(); holder.stdout.close()
        return f"locked restore refused in {dt:.1f}s, locked snapshot refused in {dt2:.1f}s, target unchanged"

    # C8
    def c8_exact_missing_db(self):
        root, ds = self.fresh("multi", dbs=("app.db", "audit.db"))
        need(self.run("health", ds, "--expect", "app.db", "--expect", "audit.db").returncode == 0, "healthy pair rejected")
        snap, sid = self.snap(root, ds)
        (ds / "audit.db").unlink()
        need(self.run("health", ds, "--expect", "app.db", "--expect", "audit.db").returncode != 0, "missing audit.db reported healthy")
        need(self.run("verify", snap, "--expect", "ledger.db").returncode != 0, "snapshot lacking ledger.db verified")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        need(p.returncode == 0 and values(ds / "audit.db") == SEED, "missing database not restored")
        return "missing expected DB fails health and verify; restore brings it back"

    # C9
    def c9_explicit_intent(self):
        root, ds = self.fresh("intent")
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "INSERT INTO items VALUES (4,'newer-live');")
        before = tree(ds)
        for extra in ([], ["--confirm", "not-the-id"]):
            p = self.run("restore", ds, "--snapshot", snap, *extra)
            need(p.returncode != 0 and tree(ds) == before, f"restore without the right --confirm changed data ({extra})")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        need(p.returncode == 0 and values(ds / "app.db") == SEED, "confirmed restore failed")
        need(any_file_holds(ds, (4, "newer-live")), "newer live row is not kept anywhere")
        return "no or wrong confirm refused unchanged; confirmed restore keeps the newer row in a copy"

    # C12 (rework r2, from M03)
    def c12_links_and_journal(self):
        root, ds = self.fresh("links")
        real = self.base / "outside" / "real.db"
        shutil.copy(ds / "app.db", real)
        before_out = hashlib.sha256(real.read_bytes()).hexdigest()
        (ds / "app.db").unlink()
        (ds / "app.db").symlink_to(real)
        need(self.run("health", ds, "--expect", "app.db").returncode != 0, "a symlinked expected database was called healthy")
        need(self.run("snapshot", ds, "--out", root / "snap-link", "--json").returncode != 0 and not (root / "snap-link").exists(),
             "a symlinked database was snapshotted through the link")
        need(hashlib.sha256(real.read_bytes()).hexdigest() == before_out, "the link target outside the dataset changed")
        real.unlink()
        root, ds, snap, sid = self._crash(2, "journal-open")
        need(values(ds / "app.db") == SEED, "after the last rename the restored file should be in place")
        need(self.run("health", ds, "--expect", "app.db", "--snapshot", snap).returncode != 0,
             "health passed while the restore journal is still open")
        need(self.run("recover", ds).returncode == 0 and self.run("health", ds, "--expect", "app.db").returncode == 0,
             "recover did not close the journal")
        return "symlinked DB refused by health and snapshot, outside untouched; health fails while a journal is open"

    # C13 (rework r2, from M03)
    def c13_external_dataset_lock(self):
        root, ds = self.fresh("flock")
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        holder = subprocess.Popen([sys.executable, "-c", "import fcntl,os,sys,time;fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT);"
                                   "fcntl.flock(fd,fcntl.LOCK_EX);print('held',flush=True);time.sleep(120)",
                                   str(ds / ".solaris-recovery.lock")], stdout=subprocess.PIPE, text=True)
        try:
            need(holder.stdout.readline().strip() == "held", "could not hold the dataset lock")
            before = tree(ds)
            p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
            need(p.returncode != 0 and tree(ds) == before, "restore ran while another process held the dataset lock")
            p = self.run("restore", ds, "--snapshot", snap, "--dry-run")
            need(p.returncode != 0, "dry run did not report the held dataset lock")
        finally:
            holder.kill(); holder.wait(); holder.stdout.close()
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        need(p.returncode == 0 and values(ds / "app.db") == SEED, "restore after the lock was released failed")
        return "external flock holder: restore and dry run refuse, dataset byte-identical; works after release"

    # C14 (rework r2, from M03): needs a Python candidate; the drill patches os.replace in-process
    def c14_crash_after_staging(self):
        root, ds = self.fresh("staging")
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        inj = root / "inject"
        inj.mkdir()
        (inj / "sitecustomize.py").write_text(
            "import os, signal\n_r = os.replace\n_n = [0]\n"
            "def replace(a, b, *x, **k):\n"
            "    if os.path.basename(os.fspath(b)) == '.solaris-recovery.json':\n"
            "        _n[0] += 1\n"
            "        if _n[0] == 2:\n"
            "            os.kill(os.getpid(), signal.SIGKILL)\n"
            "    return _r(a, b, *x, **k)\n"
            "os.replace = replace\n")
        p = subprocess.run(self.cmd + ["restore", str(ds), "--snapshot", str(snap), "--confirm", sid], capture_output=True,
                           text=True, timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(inj)))
        need(p.returncode == -9, f"the drill did not stop the restore after staging (exit {p.returncode}); "
             "this check needs a Python candidate that writes .solaris-recovery.json with os.replace")
        p = self.run("recover", ds, "--dry-run", "--json")
        try:
            preview = json.loads(p.stdout).get("decision")
        except ValueError:
            preview = None
        need(preview == "discard_staging", f"a restore killed before any swap previews {preview!r}, expected discard_staging")
        p = self.run("recover", ds)
        need(p.returncode == 0 and values(ds / "app.db") == [(i, "live") for i in (1, 2, 3)],
             "recover after a staging-only crash changed the live values")
        left = sorted(x for x in os.listdir(ds) if x not in ("app.db", "notes.txt"))
        need(not left, f"leftovers after recover: {left}")
        return "killed after staging: recover discards the staged copies, originals untouched, no leftovers"

    # C15 (rework r2, from M03)
    def c15_value_fidelity(self):
        root, ds = self.fresh("fidelity")
        sql(ds / "app.db", "CREATE TABLE sqlitedata(k TEXT, v TEXT); INSERT INTO sqlitedata VALUES ('plan','GOOD');"
                           "PRAGMA user_version=4;")
        snap, sid = self.snap(root, ds)
        for change, undo, what in (("UPDATE sqlitedata SET v='LIVE';", "UPDATE sqlitedata SET v='GOOD';", "a row in table sqlitedata"),
                                   ("PRAGMA user_version=9;", "PRAGMA user_version=4;", "user_version"),
                                   ("PRAGMA application_id=7;", "PRAGMA application_id=0;", "application_id")):
            sql(ds / "app.db", change)
            need(self.run("health", ds, "--expect", "app.db", "--snapshot", snap).returncode != 0,
                 f"health missed a change in {what}")
            sql(ds / "app.db", undo)
        need(self.run("health", ds, "--expect", "app.db", "--snapshot", snap).returncode == 0, "health fails on the unchanged database")
        sql(ds / "app.db", "UPDATE sqlitedata SET v='LIVE'; PRAGMA user_version=9;")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
        c = sqlite3.connect(ds / "app.db")
        got = (c.execute("SELECT v FROM sqlitedata").fetchall(), c.execute("PRAGMA user_version").fetchone()[0])
        c.close()
        need(p.returncode == 0 and got == ([("GOOD",)], 4), f"after restore sqlitedata/user_version are {got}")
        return "changes to table sqlitedata, user_version and application_id each fail health; restore brings them back"

    # C16 (rework r3, from M03 r2 R-B/R-C): a second run while this tool holds the dataset lock.
    # Needs a Python candidate: an injected pause right after the lock file is claimed (os.ftruncate).
    def c16_lock_held_by_a_running_restore(self):
        root, ds = self.fresh("held", dbs=("app.db", "audit.db"))
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        inj, flag = root / "inject-pause", root / "flags"
        inj.mkdir()
        flag.mkdir()
        (inj / "sitecustomize.py").write_text(
            "import os, time\n_t = os.ftruncate\n_f = os.environ.get('G03_PAUSE_DIR')\n"
            "def ftruncate(fd, n):\n"
            "    r = _t(fd, n)\n"
            "    if _f and not os.path.exists(os.path.join(_f, 'paused')):\n"
            "        open(os.path.join(_f, 'paused'), 'w').close()\n"
            "        for _ in range(600):\n"
            "            if os.path.exists(os.path.join(_f, 'go')):\n                break\n"
            "            time.sleep(0.05)\n"
            "    return r\n"
            "os.ftruncate = ftruncate\n")
        a = subprocess.Popen(self.cmd + ["restore", str(ds), "--snapshot", str(snap), "--confirm", sid],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(inj), G03_PAUSE_DIR=str(flag)))
        try:
            for _ in range(400):
                if (flag / "paused").exists() or a.poll() is not None:
                    break
                time.sleep(0.05)
            need((flag / "paused").exists(), "the injected pause never fired; this check needs a Python candidate "
                 "that claims its lock file with os.ftruncate")
            before = tree(ds)
            p1 = self.run("snapshot", ds, "--out", root / "snapshots" / "x", "--json")
            p2 = self.run("restore", ds, "--snapshot", snap, "--confirm", sid)
            p3 = self.run("recover", ds)
            need(tree(ds) == before, "a second run changed the dataset while the first held the lock")
            need(p1.returncode != 0 and p2.returncode != 0 and p3.returncode != 0,
                 f"a second run did not see the held dataset lock: snapshot {p1.returncode}, restore {p2.returncode}, recover {p3.returncode}")
            need(not (root / "snapshots").exists(), "a refused snapshot still created its parent folder")
        finally:
            (flag / "go").touch()
            rc = a.wait(timeout=120)
        need(rc == 0 and values(ds / "app.db") == SEED, f"the paused restore did not finish (exit {rc})")
        return "while one restore holds the lock, snapshot, restore and recover all refuse and create nothing"

    # C17 (rework r3, from M03 r2 R-A): health during an interrupted restore must not open databases
    def c17_health_mid_swap_opens_nothing(self):
        root, ds = self.fresh("midswap", dbs=("app.db", "audit.db"))
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        (ds / "broken.db").write_bytes(b"not SQLite at all, and not empty")
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid, "--simulate-crash-after", "1")
        need(p.returncode != 0, "the crash drill did not stop the restore")
        before = tree(ds)
        p = self.run("health", ds, "--expect", "app.db", "--expect", "audit.db", "--expect", "broken.db")
        need(p.returncode != 0, "health passed during an interrupted restore")
        need("unreadable" not in p.stdout, "health opened databases during an interrupted restore (it judged broken.db)")
        need(tree(ds) == before, "health created or changed files during an interrupted restore")
        p = self.run("snapshot", ds, "--out", root / "snapshots" / "mid", "--json")
        need(p.returncode != 0 and not (root / "snapshots").exists(), "a snapshot was taken (or its folder made) during an interrupted restore")
        need(tree(ds) == before, "snapshot changed files during an interrupted restore")
        p = self.run("recover", ds)
        need(p.returncode == 0 and values(ds / "app.db") == SEED, f"recover after mid-swap health failed (exit {p.returncode})")
        return "health mid-swap names the journal, opens nothing, creates nothing; snapshot refuses; recover then completes"

    # C18 (rework r3, from M03 r2 R-D): the r2 fixes F4, F5 and F7, which the M03 oracle does not exercise
    def c18_empty_db_bad_manifest_bad_timeout(self):
        root, ds = self.fresh("f457")
        snap, sid = self.snap(root, ds)
        (ds / "empty.db").write_bytes(b"")
        need(self.run("health", ds, "--expect", "empty.db").returncode != 0, "a 0-byte database was called healthy")
        (ds / "empty.db").unlink()
        sql(ds / "tableless.db", "CREATE TABLE t(x); DROP TABLE t;")
        need(self.run("health", ds, "--expect", "tableless.db").returncode != 0, "a database with no tables was called healthy")
        m = json.loads((snap / "manifest.json").read_text())
        del m["databases"]["app.db"]["tables"]
        (snap / "manifest.json").write_text(json.dumps(m))
        p = self.run("health", ds, "--expect", "app.db", "--snapshot", snap)
        need(p.returncode == 2, f"health with a malformed manifest entry exit {p.returncode}, expected 2")
        need(self.run("verify", snap).returncode == 1, "verify accepted a manifest entry without tables")
        (ds / "garbage.db").write_bytes(b"garbage that is not SQLite")
        p = self.run("snapshot", ds, "--out", root / "snapshots" / "bad", "--json")
        need(p.returncode != 0 and not (root / "snapshots").exists(), "a failed snapshot left its new parent folder behind")
        (ds / "garbage.db").unlink()
        for bad in ("nan", "inf", "-1", "0", "601"):
            need(self.run("health", ds, "--expect", "app.db", "--lock-timeout", bad).returncode == 2, f"--lock-timeout {bad} accepted")
        return "0-byte and table-less DBs unhealthy; failed snapshot leaves no folder; malformed manifest refused (2) and not verified; nan/inf/-1/0/601 timeouts exit 2"

    # C10
    def c10_concurrent(self):
        root, ds = self.fresh("concurrent", dbs=("app.db", "audit.db"))
        snap, sid = self.snap(root, ds)
        sql(ds / "app.db", "UPDATE items SET v='live';")
        procs = [subprocess.Popen(self.cmd + ["restore", str(ds), "--snapshot", str(snap), "--confirm", sid],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1")) for _ in range(6)]
        codes = [p.wait(timeout=120) for p in procs]
        self.run("recover", ds)
        need(codes.count(0) >= 1, f"no concurrent restore succeeded {codes}")
        need(values(ds / "app.db") == SEED and values(ds / "audit.db") == SEED, "concurrent restores left wrong values")
        need(any_file_holds(ds, (1, "live")), "live data lost in the race")
        need(not [x for x in os.listdir(ds) if x.endswith((".staged", ".lock", ".tmp", ".partial"))], "leftovers")
        return f"6 concurrent restores exit {codes}; values exact; live copy kept"

    # C11
    def c11_scale(self):
        root, ds = self.fresh("scale", dbs=())
        for i in range(8):
            make_db(ds / f"shard{i}.db", rows=[(j, f"r{i}-{j}") for j in range(25000)])
        snap, sid = self.snap(root, ds)
        for i in range(8):
            sql(ds / f"shard{i}.db", "DELETE FROM items WHERE id % 3 = 0; UPDATE items SET v='x' WHERE id % 5 = 0;")
        t = time.monotonic()
        p = self.run("restore", ds, "--snapshot", snap, "--confirm", sid, timeout=300)
        dt = time.monotonic() - t
        need(p.returncode == 0, "restore of 8 x 25000 rows failed")
        for i in range(8):
            need(values(ds / f"shard{i}.db") == [(j, f"r{i}-{j}") for j in range(25000)], f"shard{i} values wrong")
        return f"8 databases x 25000 rows restored exactly in {dt:.2f}s"


def main(argv):
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        print(__doc__)
        return 2
    cmd = argv[argv.index("--") + 1:]
    exe = shutil.which(cmd[0]) or cmd[0]
    if not Path(exe).exists():
        print(f"FAIL candidate command not found: {cmd[0]}")
        return 1
    base = Path(tempfile.mkdtemp(prefix="g03-oracle-")).resolve()
    o = Oracle(cmd, base)
    checks = sorted((m for m in dir(o) if m[:1] == "c" and m[1:2].isdigit()), key=lambda m: int(m[1:].split("_")[0]))
    fails = 0
    try:
        for m in checks:
            try:
                print(f"PASS {m}: {getattr(o, m)()}", flush=True)
            except Fail as e:
                fails += 1
                print(f"FAIL {m}: {e}", flush=True)
            except Exception as e:
                fails += 1
                print(f"FAIL {m}: {type(e).__name__}: {e}", flush=True)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"SUMMARY {len(checks) - fails}/{len(checks)} pass; candidate {'ACCEPTED by oracle' if not fails else 'REJECTED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
