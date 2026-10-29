"""G04 restartable work-order handoff: real processes on disposable copies of the fixtures.

Runs the G04 oracle against the real runner and two controls, and checks the pieces the oracle relies on
(journal verification, delivery key, refusal paths) directly. Nothing launches a worker, uses the network or
touches a path outside a temporary directory.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees/infrastructure/fleet-dispatcher/handoff.py'
EX = ROOT / 'examples/capabilities/G04'
DOC = ROOT / 'employees/infrastructure/fleet-dispatcher/handoff-work-orders.md'
sys.path.insert(0, str(TOOL.parent))
import handoff as h  # noqa: E402

ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')


def oracle(tool, scale=24):
    p = subprocess.run([sys.executable, str(EX / 'handoff_oracle.py'), '--tool', str(tool), '--json',
                        '--scale', str(scale)], capture_output=True, text=True, env=ENV, timeout=600)
    return p.returncode, {c['id']: c['ok'] for c in json.loads(p.stdout)['checks']}


class G04Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='g04-test-')
        self.w = Path(self.tmp) / 'w'
        shutil.copytree(EX / 'fixtures', self.w)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cli(self, *args, order='order.json'):
        p = subprocess.run([sys.executable, str(TOOL), args[0], str(self.w / order)] + list(args[1:]),
                           capture_output=True, text=True, env=ENV, cwd=self.w, timeout=120)
        return p.returncode, p.stdout, p.stderr

    def ledger(self):
        p = self.w / 'outbox' / 'ledger.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []

    def test_oracle_passes_on_the_runner(self):
        code, res = oracle(TOOL)
        self.assertEqual(code, 0, res)
        self.assertTrue(all(res.values()), res)

    def test_oracle_rejects_the_naive_control(self):
        code, res = oracle(EX / 'naive_handoff.py')
        self.assertEqual(code, 1)
        failed = {k for k, v in res.items() if not v}
        self.assertEqual(failed, {'o3', 'o5', 'o7', 'o8', 'o10', 'o14', 'o15'})
        self.assertEqual(len(res), 16)

    def test_oracle_rejects_the_noop_control(self):
        code, res = oracle(EX / 'noop_handoff.py', scale=4)
        self.assertEqual(code, 1)
        self.assertEqual({k for k, v in res.items() if v}, {'s1'})

    def test_crash_after_delivery_then_resume_by_another_worker(self):
        c1, _, _ = self.cli('run', '--worker', 'ana', '--fail-at', 'deliver')
        self.assertEqual(c1, h.CRASH_EXIT)
        self.assertEqual(len(self.ledger()), 1)
        c2, out, _ = self.cli('run', '--worker', 'ben', '--json')
        rep = json.loads(out)
        self.assertEqual(c2, 0)
        self.assertEqual(rep['takeover_from'], 'ana')
        self.assertIn('duplicate suppressed', rep['steps']['deliver'])
        self.assertEqual(len(self.ledger()), 1)
        c3, out, _ = self.cli('status', '--json')
        self.assertEqual(json.loads(out)['steps'], {'activate': 'done by ana', 'brief': 'done by ana',
                                                    'deliver': 'done by ben'})

    def test_delivery_key_binds_order_revision_and_brief(self):
        self.assertEqual(self.cli('run', '--worker', 'ana')[0], 0)
        rec = self.ledger()[0]
        brief = self.w / '.handoff' / 'WO-HARBOR-1' / 'rev1' / 'HANDOFF-BRIEF.md'
        bsha = hashlib.sha256(brief.read_bytes()).hexdigest()
        self.assertEqual(rec['brief_sha256'], bsha)
        self.assertEqual(rec['key'], hashlib.sha256(('WO-HARBOR-1\n1\n' + bsha).encode()).hexdigest())

    def test_journal_edit_is_refused_and_status_reports_it(self):
        self.cli('run', '--worker', 'ana', '--stop-after', 'brief')
        j = self.w / '.handoff' / 'WO-HARBOR-1' / 'journal.jsonl'
        lines = j.read_text().splitlines()
        good = j.read_text()
        for edit in ('entry', 'extra-key', 'prev-field'):
            rec = json.loads(lines[1])
            if edit == 'entry':
                rec['entry']['worker'] = 'mallory'
            elif edit == 'extra-key':
                rec['note'] = 'added by hand'
            else:
                rec['prev'] = 'f' * 64
            bad = list(lines)
            bad[1] = json.dumps(rec, sort_keys=True, separators=(',', ':'))
            j.write_text('\n'.join(bad) + '\n')
            c, _, err = self.cli('run', '--worker', 'ben')
            self.assertEqual(c, 2, edit)
            self.assertIn('does not verify', err)
            self.assertEqual(self.ledger(), [])
            self.assertEqual(self.cli('status')[0], 2)
        j.write_text(good)
        self.assertEqual(self.cli('run', '--worker', 'ben')[0], 0)

    def test_journal_of_another_order_is_refused(self):
        self.cli('run', '--worker', 'ana', '--stop-after', 'activate')
        o = json.loads((self.w / 'order.json').read_text())
        o['order_id'] = 'WO-OTHER'
        (self.w / 'other.json').write_text(json.dumps(o))
        src = self.w / '.handoff' / 'WO-HARBOR-1'
        shutil.copytree(src, self.w / '.handoff' / 'WO-OTHER')
        c, _, err = self.cli('run', '--worker', 'ben', order='other.json')
        self.assertEqual(c, 2)
        self.assertIn('another order', err)

    def test_fresh_order_with_a_mismatched_intake_creates_nothing(self):
        (self.w / 'intake.json').write_text('{"name": "changed"}')
        c, _, err = self.cli('run', '--worker', 'ana')
        self.assertEqual(c, 2)
        self.assertIn('issue a new revision', err)
        self.assertFalse((self.w / '.handoff').exists())
        self.assertFalse((self.w / 'outbox').exists())

    def test_stale_receipt_not_yet_redone_shows_pending(self):
        self.cli('run', '--worker', 'ana', '--stop-after', 'brief')
        brief = self.w / '.handoff' / 'WO-HARBOR-1' / 'rev1' / 'HANDOFF-BRIEF.md'
        brief.write_text(brief.read_text() + 'edited\n')
        c, _, _ = self.cli('run', '--worker', 'ben', '--fail-at', 'brief')
        self.assertEqual(c, h.CRASH_EXIT)
        st = json.loads(self.cli('status', '--json')[1])
        self.assertEqual(st['steps'], {'activate': 'done by ana', 'brief': 'pending', 'deliver': 'pending'})
        self.assertTrue(st['interrupted'])
        self.assertEqual(self.cli('run', '--worker', 'cy')[0], 0)
        self.assertEqual(len(self.ledger()), 1)

    def test_torn_ledger_line_does_not_swallow_the_next_delivery(self):
        out = self.w / 'outbox'
        out.mkdir()
        (out / 'ledger.jsonl').write_bytes(b'{"key": "abc", "order_id": "WO-OTH')
        self.assertEqual(self.cli('run', '--worker', 'ana')[0], 0)
        lines = (out / 'ledger.jsonl').read_bytes().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[1])['order_id'], 'WO-HARBOR-1')
        self.assertEqual(self.cli('run', '--worker', 'ben')[0], 0)
        self.assertEqual(len((out / 'ledger.jsonl').read_bytes().splitlines()), 2)

    def test_status_of_a_fresh_order_lists_everything_pending(self):
        c, out, _ = self.cli('status', '--json')
        self.assertEqual(c, 0)
        self.assertEqual(set(json.loads(out)['steps'].values()), {'pending'})
        self.assertFalse((self.w / 'harbor-kiosk').exists())

    def test_usage_errors_exit_2(self):
        p = subprocess.run([sys.executable, str(TOOL), 'run', str(self.w / 'missing.json'), '--worker', 'a'],
                           capture_output=True, text=True, env=ENV)
        self.assertEqual(p.returncode, 2)
        self.assertTrue(p.stderr.startswith('error:'))
        p = subprocess.run([sys.executable, str(TOOL), 'run', str(self.w / 'order.json'), '--worker', ''],
                           capture_output=True, text=True, env=ENV)
        self.assertEqual(p.returncode, 2)

    def test_doc_matches_the_tool(self):
        doc = DOC.read_text()
        for code in ('`0`', '`1`', '`2`', '`3`', '`4`', '`75`'):
            self.assertIn(code, doc)
        self.assertEqual(h.CRASH_EXIT, 75)
        self.assertEqual(h.STEPS, ('activate', 'brief', 'deliver'))
        self.assertIn('does not launch', doc)
        for name in ('handoff-work-orders.md',):
            self.assertIn(name, (TOOL.parent / 'SKILL.md').read_text())
            self.assertIn(name, json.loads((TOOL.parent / 'plugin.json').read_text())['references'])


    def test_owner_change_does_not_reuse_old_brief(self):
        """Same revision, different owner must not keep a brief naming the previous owner (root G04)."""
        order_path = self.w / 'order.json'
        order = json.loads(order_path.read_text())
        old_owner = order['owner']
        env = dict(ENV)
        p1 = subprocess.run([sys.executable, str(TOOL), 'run', str(order_path), '--worker', 'ana',
                             '--stop-after', 'brief'],
                            cwd=str(self.w), capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(p1.returncode, 3, p1.stderr + p1.stdout)  # G04 r3: owner changes only before delivery
        briefs = list((self.w / '.handoff').rglob('HANDOFF-BRIEF.md'))
        self.assertEqual(len(briefs), 1)
        self.assertIn(old_owner, briefs[0].read_text())
        order['owner'] = 'support: Someone Else'
        order_path.write_text(json.dumps(order, indent=2) + '\n')
        p2 = subprocess.run([sys.executable, str(TOOL), 'run', str(order_path), '--worker', 'ben'],
                            cwd=str(self.w), capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(p2.returncode, 0, p2.stderr + p2.stdout)
        text = briefs[0].read_text()
        self.assertIn('support: Someone Else', text)
        self.assertNotIn(old_owner, text)
        # brief step must have been redone, not silently reused
        self.assertIn('brief', p2.stdout.lower())
        self.assertTrue('stale' in p2.stdout.lower() or 'done' in p2.stdout.lower())
        ledger = (self.w / 'outbox' / 'ledger.jsonl').read_text().strip().splitlines()
        self.assertEqual(len(ledger), 1)
        self.assertIn('Someone Else', ledger[0])

    def test_owner_change_after_delivery_is_refused_not_delivered_twice(self):
        """G04 r3 (M04 r2 P2): a delivered revision must not be delivered again under a new owner, also when the
        first worker crashed after the delivery and before its receipt."""
        def run(order_path, *extra):
            return subprocess.run([sys.executable, str(TOOL), 'run', str(order_path)] + list(extra),
                                  cwd=str(self.w), capture_output=True, text=True, env=dict(ENV), timeout=120)
        for first in (['--worker', 'ana'], ['--worker', 'ana', '--fail-at', 'deliver']):
            with self.subTest(first=first):
                shutil.rmtree(str(self.w / '.handoff'), True)
                shutil.rmtree(str(self.w / 'outbox'), True)
                order_path = self.w / 'order.json'
                order = json.loads(order_path.read_text())
                order['owner'] = 'delivery-lead: A. Example'
                order_path.write_text(json.dumps(order, indent=2) + '\n')
                self.assertIn(run(order_path, *first).returncode, (0, 75))
                journal = next((self.w / '.handoff').rglob('journal.jsonl'))
                before = journal.read_bytes()
                order['owner'] = 'support: Someone Else'
                order_path.write_text(json.dumps(order, indent=2) + '\n')
                p = run(order_path, '--worker', 'ben')
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn('already delivered with owner delivery-lead: A. Example', p.stderr)
                self.assertEqual(journal.read_bytes(), before)
                ledger = (self.w / 'outbox' / 'ledger.jsonl').read_text().strip().splitlines()
                self.assertEqual(len(ledger), 1)
                self.assertIn('A. Example', ledger[0])
        rev2 = json.loads((self.w / 'order-rev2.json').read_text())
        rev2['owner'] = 'support: Someone Else'
        (self.w / 'order-rev2.json').write_text(json.dumps(rev2, indent=2) + '\n')
        p = run(self.w / 'order-rev2.json', '--worker', 'cy')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(len((self.w / 'outbox' / 'ledger.jsonl').read_text().strip().splitlines()), 2)


    def test_refusal_in_a_new_state_folder_leaves_no_lock(self):
        """G04 r4 (M04 P4-1): an exit-2 refusal in a state folder the run created left an empty .worker.lock behind."""
        self.assertEqual(self.cli('run', '--worker', 'ana')[0], 0)
        order_path = self.w / 'order.json'
        order = json.loads(order_path.read_text())
        order['owner'] = 'support: Someone Else'
        order_path.write_text(json.dumps(order, indent=2) + '\n')
        fresh = Path(self.tmp) / 'fresh-state'
        c, _, err = self.cli('run', '--worker', 'ben', '--state', str(fresh))
        self.assertEqual(c, 2, err)
        self.assertIn('already delivered', err)
        self.assertFalse(fresh.exists(), sorted(str(p) for p in fresh.rglob('*')) if fresh.exists() else '')
        nested = Path(self.tmp) / 'parent-exists'
        nested.mkdir()
        c, _, err = self.cli('run', '--worker', 'ben', '--state', str(nested))
        self.assertEqual(c, 2, err)
        self.assertEqual(list(nested.iterdir()), [])
        # the original state folder keeps its lock, journal and receipts
        sdir = self.w / '.handoff' / 'WO-HARBOR-1'
        c, _, err = self.cli('run', '--worker', 'ben')
        self.assertEqual(c, 2, err)
        self.assertTrue((sdir / '.worker.lock').exists())
        self.assertTrue((sdir / 'journal.jsonl').exists())

if __name__ == '__main__':
    unittest.main()
