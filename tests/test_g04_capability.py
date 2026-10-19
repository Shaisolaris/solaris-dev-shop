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

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


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


if __name__ == '__main__':
    unittest.main()
