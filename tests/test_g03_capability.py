"""G03: bounded local SQLite recovery without data loss.

Every test uses a disposable directory and synthetic rows, and asserts real
values or bytes on disk. The rejected review findings are encoded as cases.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees' / 'infrastructure' / 'database-administrator' / 'sqlite_recovery.py'
sys.path.insert(0, str(TOOL.parent))
import sqlite_recovery as rec  # noqa: E402

SEED_ORDERS = [(1, 'old-a'), (2, 'old-b'), (3, 'old-c')]
SEED_CUSTOMERS = [(1, 'original')]


def one(directory, pattern):
    found = sorted(Path(directory).glob(pattern))
    assert len(found) == 1, (pattern, found)
    return found[0]


def tree(path):
    out = {}
    for p in sorted(Path(path).rglob('*')):
        rel = p.relative_to(path).as_posix()
        out[rel] = ('link:' + os.readlink(p) if p.is_symlink() else
                    hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'dir')
    return out


def rows(db, table):
    con = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        return con.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
    finally:
        con.close()


def execute(db, sql):
    con = sqlite3.connect(db)
    con.executescript(sql)
    con.commit()
    con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g03test-')).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ds = self.tmp / 'service'
        self.ds.mkdir()
        self.db = self.ds / 'service.db'
        execute(self.db, 'CREATE TABLE orders(id INTEGER PRIMARY KEY, value TEXT);'
                         'CREATE TABLE customers(id INTEGER PRIMARY KEY, value TEXT);'
                         "INSERT INTO orders VALUES (1,'old-a'),(2,'old-b'),(3,'old-c');"
                         "INSERT INTO customers VALUES (1,'original');")
        (self.ds / 'config.yaml').write_text('owner: keep\n')
        self.outside = self.tmp / 'outside'
        self.outside.mkdir()
        (self.outside / 'sentinel').write_text('KEEP')

    def snap(self, name='snap', **kw):
        r = rec.snapshot(str(self.ds), str(self.tmp / name), **kw)
        self.assertEqual(r['status'], 'ok', r)
        return self.tmp / name, r['snapshot_id']

    def assert_seed_values(self):
        self.assertEqual(rows(self.db, 'orders'), SEED_ORDERS)
        self.assertEqual(rows(self.db, 'customers'), SEED_CUSTOMERS)

    def assert_outside_untouched(self):
        self.assertEqual(tree(self.outside), {'sentinel': hashlib.sha256(b'KEEP').hexdigest()})


class CleanRestore(Base):
    def test_actual_values_restored_and_previous_file_kept(self):
        snap, sid = self.snap()
        execute(self.db, "DROP TABLE orders; UPDATE customers SET value='damaged';")
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'ok', r)
        self.assert_seed_values()
        kept = one(self.ds, f'service.db.pre-restore-{sid}-*')
        self.assertEqual(rows(kept, 'customers'), [(1, 'damaged')])
        self.assertEqual((self.ds / 'config.yaml').read_text(), 'owner: keep\n')
        self.assertEqual(rec.health(str(self.ds), ['service.db'], str(snap))['status'], 'ok')
        self.assertFalse((self.ds / rec.JOURNAL).exists() or (self.ds / rec.LOCK).exists())
        self.assert_outside_untouched()

    def test_wal_source_and_sidecars_are_handled(self):
        execute(self.db, 'PRAGMA journal_mode=WAL;')
        holder = sqlite3.connect(self.db)
        holder.execute("INSERT INTO customers VALUES (2,'in-wal')")
        holder.commit()  # stays in the -wal file while this connection is open
        snap, sid = self.snap()
        holder.close()
        self.assertEqual(rec.verify(str(snap))['status'], 'ok')
        execute(self.db, "DELETE FROM customers;")
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(rows(self.db, 'customers'), [(1, 'original'), (2, 'in-wal')])

    def test_missing_database_is_recreated(self):
        snap, sid = self.snap()
        self.db.unlink()
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'ok', r)
        self.assert_seed_values()


class InvalidSnapshots(Base):
    def assert_refused_and_untouched(self, snap, sid, status=('refused',)):
        execute(self.db, "UPDATE customers SET value='live-good';")
        before = tree(self.ds)
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertIn(r['status'], status, r)
        self.assertNotEqual(r['exit_code'], 0)
        self.assertEqual(tree(self.ds), before)
        self.assert_outside_untouched()
        return r

    def test_flipped_byte_in_database_copy(self):
        snap, sid = self.snap()
        data = bytearray((snap / 'service.db').read_bytes())
        data[len(data) // 2] ^= 0xFF
        (snap / 'service.db').write_bytes(bytes(data))
        self.assertEqual(rec.verify(str(snap))['status'], 'failed')
        self.assert_refused_and_untouched(snap, sid)

    def test_resigned_manifest_with_wrong_values_is_caught(self):
        snap, sid = self.snap()
        m = json.loads((snap / rec.MANIFEST).read_text())
        execute(snap / 'service.db', "UPDATE orders SET value='forged' WHERE id=1;")
        m['databases']['service.db']['sha256'] = rec._sha_file(snap / 'service.db')
        m['databases']['service.db']['size'] = (snap / 'service.db').stat().st_size
        (snap / rec.MANIFEST).write_text(json.dumps(m))
        r = self.assert_refused_and_untouched(snap, sid)
        self.assertIn('orders', ' '.join(r['messages']))

    def test_symlink_member_pointing_outside_is_never_followed(self):
        snap, sid = self.snap()
        (snap / 'service.db').unlink()
        (snap / 'service.db').symlink_to(self.outside / 'sentinel')
        self.assertEqual(rec.verify(str(snap))['status'], 'failed')
        self.assert_refused_and_untouched(snap, sid)

    def test_extra_member_hardlink_and_unsafe_manifest_names(self):
        snap, sid = self.snap()
        (snap / 'bridge').symlink_to(self.outside)
        self.assertIn('not in its manifest', ' '.join(rec.verify(str(snap))['messages']))
        (snap / 'bridge').unlink()
        os.link(snap / 'service.db', self.tmp / 'alias.db')
        self.assertIn('hardlinked', ' '.join(rec.verify(str(snap))['messages']))
        (self.tmp / 'alias.db').unlink()
        m = json.loads((snap / rec.MANIFEST).read_text())
        m['databases']['../outside/sentinel.db'] = m['databases']['service.db']
        (snap / rec.MANIFEST).write_text(json.dumps(m))
        self.assert_refused_and_untouched(snap, sid)

    def test_garbage_manifest_and_snapshot_inside_dataset(self):
        snap, sid = self.snap()
        (snap / rec.MANIFEST).write_text('{not json')
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'refused')
        r = rec.snapshot(str(self.ds), str(self.ds / 'inner'))
        self.assertEqual(r['status'], 'refused')
        self.assertFalse((self.ds / 'inner').exists())

    def test_symlinked_target_database_is_not_replaced(self):
        snap, sid = self.snap()
        real = self.outside / 'real.db'
        shutil.move(str(self.db), real)
        self.db.symlink_to(real)
        before = tree(self.outside)
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'refused')
        self.assertTrue(self.db.is_symlink())
        self.assertEqual(tree(self.outside), before)


class IntentAndDryRun(Base):
    def test_dry_run_is_byte_identical_and_reports_live_only_rows(self):
        snap, sid = self.snap()
        execute(self.db, "DELETE FROM orders WHERE id=3; INSERT INTO customers VALUES (2,'new-live');")
        before_ds, before_snap = tree(self.ds), tree(snap)
        mt = {p: p.stat().st_mtime_ns for p in self.ds.iterdir()}
        r = rec.restore(str(self.ds), str(snap), confirm=None, dry_run=True)
        self.assertEqual(r['status'], 'planned')
        self.assertEqual((tree(self.ds), tree(snap)), (before_ds, before_snap))
        self.assertEqual({p: p.stat().st_mtime_ns for p in self.ds.iterdir()}, mt)
        change = r['plan']['databases']['service.db']['changes']
        self.assertEqual(change['rows_only_in_target'], {'customers': 1})
        self.assertEqual(sorted(change['differing_tables']), ['customers', 'orders'])

    def test_newer_live_data_needs_explicit_intent_and_is_kept(self):
        snap, sid = self.snap()
        execute(self.db, "DELETE FROM orders WHERE id=3; INSERT INTO customers VALUES (2,'new-live');")
        before = tree(self.ds)
        for confirm in (None, 'wrong-id'):
            r = rec.restore(str(self.ds), str(snap), confirm=confirm)
            self.assertEqual(r['status'], 'refused')
            self.assertEqual(tree(self.ds), before)
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'ok')
        self.assert_seed_values()
        self.assertIn((2, 'new-live'), rows(one(self.ds, f'service.db.pre-restore-{sid}-*'), 'customers'))


class Interruption(Base):
    def crash(self, n, snap, sid):
        p = subprocess.run([sys.executable, str(TOOL), 'restore', str(self.ds), '--snapshot', str(snap),
                            '--confirm', sid, '--simulate-crash-after', str(n)], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(p.returncode, 137, p.stderr)

    def test_gap_after_set_aside_target_absent_recovers_without_snapshot(self):
        snap, sid = self.snap()
        execute(self.db, "UPDATE orders SET value='damaged';")
        self.crash(1, snap, sid)
        self.assertFalse(self.db.exists())
        shutil.rmtree(snap)  # the snapshot is gone: recovery must not need it
        r = rec.recover(str(self.ds))
        self.assertEqual((r['status'], r['decision']), ('ok', 'roll_forward'), r)
        self.assert_seed_values()
        self.assertEqual(rec.recover(str(self.ds))['status'], 'nothing_to_do')

    def test_gap_after_set_aside_with_damaged_stage_rolls_back(self):
        snap, sid = self.snap()
        execute(self.db, "UPDATE orders SET value='live';")
        self.crash(1, snap, sid)
        staged = one(self.ds, f'.service.db.restore-{sid}-*.staged')
        staged.write_bytes(b'damaged stage')
        r = rec.recover(str(self.ds))
        self.assertEqual((r['status'], r['decision']), ('failed', 'roll_back'), r)
        self.assertEqual(rows(self.db, 'orders'), [(1, 'live'), (2, 'live'), (3, 'live')])
        self.assertTrue(staged.exists(), 'staged copy kept for inspection')

    def test_gap_after_set_aside_with_vanished_stage_rolls_back(self):
        snap, sid = self.snap()
        execute(self.db, "UPDATE customers SET value='live';")
        self.crash(1, snap, sid)
        one(self.ds, f'.service.db.restore-{sid}-*.staged').unlink()
        r = rec.recover(str(self.ds))
        self.assertEqual(r['decision'], 'roll_back', r)
        self.assertEqual(rows(self.db, 'customers'), [(1, 'live')])  # the original came back

    def test_gap_after_install_before_journal_cleared(self):
        snap, sid = self.snap()
        execute(self.db, "UPDATE orders SET value='damaged';")
        self.crash(2, snap, sid)
        self.assertTrue((self.ds / rec.JOURNAL).exists())
        h = rec.health(str(self.ds), ['service.db'])  # data looks fine, but the open journal must be reported
        self.assertEqual(h['status'], 'unhealthy', h)
        self.assertTrue(any(rec.JOURNAL in m for m in h['messages']), h)
        r = rec.recover(str(self.ds))
        self.assertEqual((r['status'], r['decision']), ('ok', 'roll_forward'), r)
        self.assert_seed_values()

    def test_every_crash_point_with_two_databases_and_wal_sidecar(self):
        for n in range(1, 6):
            with self.subTest(crash_after=n):
                ds = self.tmp / f'multi{n}'
                ds.mkdir()
                execute(ds / 'a.db', "CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t VALUES (1,'a');")
                execute(ds / 'b.db', "CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t VALUES (1,'b');")
                r = rec.snapshot(str(ds), str(self.tmp / f'msnap{n}'))
                sid = r['snapshot_id']
                execute(ds / 'a.db', "UPDATE t SET v='x';")
                (ds / 'b.db-journal').write_bytes(b'')  # a leftover sidecar is set aside, not replayed
                p = subprocess.run([sys.executable, str(TOOL), 'restore', str(ds), '--snapshot',
                                    str(self.tmp / f'msnap{n}'), '--confirm', sid, '--simulate-crash-after', str(n)],
                                   capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                self.assertIn(p.returncode, (0, 137), p.stdout + p.stderr)
                r = rec.recover(str(ds))
                self.assertIn(r['status'], ('ok', 'nothing_to_do'), r)
                self.assertEqual(rows(ds / 'a.db', 't'), [(1, 'a')])
                self.assertEqual(rows(ds / 'b.db', 't'), [(1, 'b')])
                self.assertFalse((ds / rec.JOURNAL).exists())

    def test_crash_during_staging_discards_only_staged_copies(self):
        snap, sid = self.snap()
        execute(self.db, "UPDATE orders SET value='live';")
        before = rec._sha_file(self.db)
        (self.ds / rec.JOURNAL).write_text(json.dumps({
            'schema': rec.JOURNAL_SCHEMA, 'state': 'staging', 'snapshot_id': sid, 'tag': sid + '-ab12cd34',
            'staged_sha256': {f'.service.db.restore-{sid}-ab12cd34.staged': 'x'},
            'steps': [{'from': f'.service.db.restore-{sid}-ab12cd34.staged', 'to': 'service.db', 'kind': 'install'}]}))
        (self.ds / f'.service.db.restore-{sid}-ab12cd34.staged').write_bytes(b'half')
        r = rec.recover(str(self.ds))
        self.assertEqual(r['decision'], 'discard_staging')
        self.assertEqual(rec._sha_file(self.db), before)
        self.assertEqual(sorted(os.listdir(self.ds)), ['config.yaml', 'service.db'])

    def test_journal_dry_run_lock_and_corrupt_snapshot_never_mutate(self):
        # Rejected finding: journal handling ran before lock, dry-run and verification.
        snap, sid = self.snap()
        execute(self.db, "UPDATE customers SET value='live';")
        self.crash(1, snap, sid)
        (snap / 'service.db').write_bytes(b'CORRUPT')
        before = tree(self.ds)
        r = rec.restore(str(self.ds), str(snap), confirm=sid, dry_run=True)
        self.assertNotEqual(r['status'], 'ok')
        self.assertEqual(rec.recover(str(self.ds), dry_run=True)['decision'], 'roll_forward')
        self.assertEqual(tree(self.ds), before)
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'refused')
        self.assertEqual(tree(self.ds), before)

    def test_forged_journal_cannot_rename_owner_files(self):
        snap, sid = self.snap()
        (self.ds / rec.JOURNAL).write_text(json.dumps({
            'schema': rec.JOURNAL_SCHEMA, 'state': 'swapping', 'snapshot_id': sid, 'tag': sid + '-ab12cd34',
            'staged_sha256': {},
            'steps': [{'from': 'config.yaml', 'to': 'gone.txt', 'kind': 'set_aside'}]}))
        before = tree(self.ds)
        r = rec.recover(str(self.ds))
        self.assertEqual(r['status'], 'needs_human')
        self.assertEqual(tree(self.ds), before)


class LocksAndTimeouts(Base):
    def hold_exclusive(self):
        proc = subprocess.Popen([sys.executable, '-c',
                                 'import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1],isolation_level=None);'
                                 'c.execute("BEGIN EXCLUSIVE");print("held",flush=True);time.sleep(60)', str(self.db)],
                                stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (proc.kill(), proc.wait(), proc.stdout.close()))
        self.assertEqual(proc.stdout.readline().strip(), 'held')
        return proc

    def test_snapshot_of_locked_source_is_bounded(self):
        self.hold_exclusive()
        t = time.monotonic()
        r = rec.snapshot(str(self.ds), str(self.tmp / 'snap'), lock_timeout=1.0)
        self.assertLess(time.monotonic() - t, 10)
        self.assertEqual(r['status'], 'busy')
        self.assertFalse((self.tmp / 'snap').exists())
        self.assertEqual([p for p in os.listdir(self.tmp) if 'partial' in p], [])
        self.assertFalse((self.ds / rec.LOCK).exists())

    def test_restore_over_locked_target_is_bounded_and_untouched(self):
        snap, sid = self.snap()
        self.hold_exclusive()
        before = tree(self.ds)
        t = time.monotonic()
        r = rec.restore(str(self.ds), str(snap), confirm=sid, lock_timeout=1.0)
        self.assertLess(time.monotonic() - t, 10)
        self.assertEqual(r['status'], 'busy')
        self.assertEqual(tree(self.ds), before)

    def test_dataset_lock_blocks_restore_recover_and_dry_runs(self):
        snap, sid = self.snap()
        fd = rec._acquire_lock(self.ds)
        try:
            self.assertEqual(rec.restore(str(self.ds), str(snap), confirm=sid)['status'], 'busy')
            self.assertEqual(rec.restore(str(self.ds), str(snap), confirm=sid, dry_run=True)['status'], 'busy')
            self.assertEqual(rec.recover(str(self.ds))['status'], 'busy')
            self.assertEqual(rec.snapshot(str(self.ds), str(self.tmp / 's2'))['status'], 'busy')
        finally:
            os.close(fd)
        self.assertEqual(rec.restore(str(self.ds), str(snap), confirm=sid)['status'], 'ok')

    def test_concurrent_restores_leave_one_consistent_result(self):
        snap, sid = self.snap()
        execute(self.db, "UPDATE orders SET value='damaged';")
        procs = [subprocess.Popen([sys.executable, str(TOOL), 'restore', str(self.ds), '--snapshot', str(snap),
                                   '--confirm', sid, '--json'], stdout=subprocess.PIPE, text=True,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')) for _ in range(5)]
        results = [json.loads(p.communicate()[0]) for p in procs]
        did_work = [r for r in results if r.get('restored')]
        self.assertEqual(len(did_work), 1, results)
        self.assertTrue(all(r['status'] in ('ok', 'busy', 'refused') for r in results), results)
        self.assertEqual(len(list(self.ds.glob('service.db.pre-restore-*'))), 1)
        self.assert_seed_values()
        self.assertFalse((self.ds / rec.JOURNAL).exists() or (self.ds / rec.LOCK).exists())


class KnownGoodData(Base):
    def test_database_already_matching_is_left_in_place(self):
        execute(self.ds / 'audit.db', "CREATE TABLE log(id INTEGER PRIMARY KEY); INSERT INTO log VALUES (1);")
        snap, sid = self.snap()
        audit_before = rec._sha_file(self.ds / 'audit.db')
        execute(self.db, "UPDATE orders SET value='damaged';")
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['restored'], ['service.db'])
        self.assertEqual(rec._sha_file(self.ds / 'audit.db'), audit_before)
        self.assertEqual(list(self.ds.glob('audit.db.pre-restore-*')), [])
        self.assert_seed_values()

    def test_repeated_restores_from_one_snapshot_keep_every_copy(self):
        snap, sid = self.snap()
        for value in ('first-damage', 'second-damage'):
            execute(self.db, f"UPDATE orders SET value='{value}';")
            self.assertEqual(rec.restore(str(self.ds), str(snap), confirm=sid)['status'], 'ok')
            self.assert_seed_values()
        kept = sorted(self.ds.glob(f'service.db.pre-restore-{sid}-*'))
        self.assertEqual(sorted(rows(k, 'orders')[0][1] for k in kept), ['first-damage', 'second-damage'])

    def test_nothing_to_restore_changes_nothing(self):
        snap, sid = self.snap()
        before = tree(self.ds)
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual((r['status'], r['restored']), ('ok', []))
        self.assertEqual(tree(self.ds), before)


class HealthAndScale(Base):
    def test_exact_missing_database_check(self):
        execute(self.ds / 'audit.db', "CREATE TABLE log(id INTEGER PRIMARY KEY); INSERT INTO log VALUES (1);")
        snap, _ = self.snap()
        self.assertEqual(rec.health(str(self.ds), ['service.db', 'audit.db'])['status'], 'ok')
        (self.ds / 'audit.db').unlink()
        r = rec.health(str(self.ds), ['service.db', 'audit.db'])
        self.assertEqual(r['status'], 'unhealthy')
        self.assertIn('audit.db: expected database is missing', r['messages'])
        self.assertEqual(rec.health(str(self.ds), [], str(snap))['status'], 'unhealthy')
        self.assertEqual(rec.verify(str(snap), ['missing.db'])['status'], 'failed')
        self.assertEqual(rec.health(str(self.ds), [])['status'], 'invalid')

    def test_health_catches_changed_values_with_equal_counts(self):
        snap, _ = self.snap()
        execute(self.db, "UPDATE orders SET value='same-count' WHERE id=2;")
        r = rec.health(str(self.ds), ['service.db'], str(snap))
        self.assertEqual(r['status'], 'unhealthy')
        self.assertIn("['orders']", ' '.join(r['messages']))

    def test_larger_dataset_restores_exact_values(self):
        big = self.ds / 'events.db'
        con = sqlite3.connect(big)
        con.execute('CREATE TABLE ev(id INTEGER PRIMARY KEY, payload TEXT)')
        con.executemany('INSERT INTO ev VALUES (?, ?)', ((i, f'p{i}' * 5) for i in range(100000)))
        con.commit()
        con.close()
        snap, sid = self.snap()
        want = hashlib.sha256(repr(rows(big, 'ev')).encode()).hexdigest()
        execute(big, 'DELETE FROM ev WHERE id % 7 = 0;')
        r = rec.restore(str(self.ds), str(snap), confirm=sid)
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(hashlib.sha256(repr(rows(big, 'ev')).encode()).hexdigest(), want)


class Cli(Base):
    def cli(self, *args):
        p = subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertNotIn('Traceback', p.stderr)
        return p

    def test_cli_round_trip_and_exit_codes(self):
        p = self.cli('snapshot', self.ds, '--out', self.tmp / 'snap', '--json')
        self.assertEqual(p.returncode, 0)
        sid = json.loads(p.stdout)['snapshot_id']
        self.assertEqual(self.cli('verify', self.tmp / 'snap', '--expect', 'service.db').returncode, 0)
        execute(self.db, 'DROP TABLE orders;')
        self.assertEqual(self.cli('health', self.ds, '--snapshot', self.tmp / 'snap').returncode, 1)
        self.assertEqual(self.cli('restore', self.ds, '--snapshot', self.tmp / 'snap').returncode, 2)
        self.assertEqual(self.cli('restore', self.ds, '--snapshot', self.tmp / 'snap', '--dry-run').returncode, 0)
        self.assertEqual(self.cli('restore', self.ds, '--snapshot', self.tmp / 'snap', '--confirm', sid).returncode, 0)
        self.assert_seed_values()
        self.assertEqual(self.cli('recover', self.ds).returncode, 0)
        self.assertNotEqual(self.cli('restore', self.ds, '--snapshot', self.tmp / 'snap', '--lock-timeout', '0').returncode, 0)
        self.assertEqual(self.cli('restore', self.tmp / 'nope', '--snapshot', self.tmp / 'snap').returncode, 2)


if __name__ == '__main__':
    unittest.main()
