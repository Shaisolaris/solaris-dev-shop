"""Coordinate an append/head-update gap without sleeps or relaxed chain checks."""
import hashlib
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
import fcntl

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees/product-project/delivery-lead/delivery_evidence.py'
ROLE = 'data/data-engineer'
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}

SHIM = '''import importlib.util,sys,fcntl
spec=importlib.util.spec_from_file_location("delivery_under_test",sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original_read=module.read_ledger;original_lock=fcntl.flock;first=True
def observed_read(root):
 global first
 try:return original_read(root)
 finally:
  if first:
   first=False;print("PREFLIGHT_READ_FINISHED",flush=True)
def observed_lock(fd,flags):
 if flags & fcntl.LOCK_SH:print("PREFLIGHT_SHARED_ATTEMPT",flush=True)
 return original_lock(fd,flags)
module.read_ledger=observed_read;fcntl.flock=observed_lock
raise SystemExit(module.main(sys.argv[2:]))
'''


def arguments(root, output, no_wait=False):
    command = [sys.executable, '-B', '-c',
               'import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("synthetic output")', output]
    return ['record', str(root), '--role', ROLE, '--outputs', output] + (
        ['--no-wait'] if no_wait else []) + ['--'] + command


class DeliveryLedgerPreflightTests(unittest.TestCase):
    def seeded(self, root):
        result = subprocess.run([sys.executable, '-B', str(TOOL)] + arguments(root, 'seed.txt'),
                                env=ENV, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        head = root / '.delivery/head.json'
        return head, head.read_bytes()

    def test_in_progress_append_is_waited_for_before_preflight(self):
        with tempfile.TemporaryDirectory(prefix='solaris-ledger-gap-') as temporary:
            root = Path(temporary)
            head, committed_head = self.seeded(root)
            shim = root / 'observe_preflight.py'
            shim.write_text(SHIM)
            lock = (root / '.delivery/ledger.lock').open('rb')
            process = None
            try:
                fcntl.flock(lock, fcntl.LOCK_EX)
                head.unlink()  # exact first-append gap, while the writer owns LOCK_EX
                process = subprocess.Popen(
                    [sys.executable, '-B', str(shim), str(TOOL)] + arguments(root, 'second.txt'),
                    env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                ready, _, _ = select.select([process.stdout], [], [], 10)
                self.assertTrue(ready, 'Child did not reach the coordinated preflight')
                marker = process.stdout.readline().strip()
                self.assertIn(marker, ('PREFLIGHT_READ_FINISHED', 'PREFLIGHT_SHARED_ATTEMPT'))
                self.assertFalse((root / 'second.txt').exists())
                head.write_bytes(committed_head)
                fcntl.flock(lock, fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertTrue((root / 'second.txt').is_file())
                lines = (root / '.delivery/contributions.jsonl').read_bytes().splitlines()
                self.assertEqual(len(lines), 2)
                previous = '0' * 64
                for sequence, line in enumerate(lines):
                    record = json.loads(line)
                    self.assertEqual((record['seq'], record['prev']), (sequence, previous))
                    previous = hashlib.sha256(line).hexdigest()
                self.assertEqual(json.loads(head.read_text()), {'seq': 1, 'sha256': previous})
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                head.write_bytes(committed_head) if not head.exists() else None
                lock.close()

    def test_no_wait_refuses_busy_preflight_without_running_command(self):
        with tempfile.TemporaryDirectory(prefix='solaris-ledger-busy-') as temporary:
            root = Path(temporary)
            head, committed_head = self.seeded(root)
            with (root / '.delivery/ledger.lock').open('rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                head.unlink()
                try:
                    result = subprocess.run(
                        [sys.executable, '-B', str(TOOL)] + arguments(root, 'never.txt', True),
                        env=ENV, capture_output=True, text=True, timeout=10)
                finally:
                    head.write_bytes(committed_head)
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertFalse((root / 'never.txt').exists())
            self.assertEqual(len((root / '.delivery/contributions.jsonl').read_bytes().splitlines()), 1)

    def test_committed_corruption_still_blocks_before_command(self):
        with tempfile.TemporaryDirectory(prefix='solaris-ledger-broken-') as temporary:
            root = Path(temporary)
            head, _ = self.seeded(root)
            head.unlink()
            result = subprocess.run(
                [sys.executable, '-B', str(TOOL)] + arguments(root, 'never.txt'),
                env=ENV, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertFalse((root / 'never.txt').exists())


if __name__ == '__main__':
    unittest.main()
