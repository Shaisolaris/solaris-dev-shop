"""G17: resource and cash decision check (employees/leadership/coo/resource_decision.py).
Real files and subprocesses on synthetic packages; expected figures are worked from the fixture
(README) or from the oracle's independent reference model."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees' / 'leadership' / 'coo' / 'resource_decision.py'
EX = ROOT / 'examples' / 'capabilities' / 'G17'
FIX = EX / 'fixtures'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
STUDIO = json.loads((FIX / 'studio.json').read_text())


def cli(*args, cwd=None):
    return subprocess.run([sys.executable, str(TOOL)] + [str(a) for a in args], capture_output=True, text=True,
                          env=ENV, timeout=300, cwd=cwd)


def oracle(*args):
    return subprocess.run([sys.executable, str(EX / 'decision_oracle.py')] + [str(a) for a in args],
                          capture_output=True, text=True, env=ENV, timeout=600)


def opt(r, oid):
    return [o for o in r['options'] if o['id'] == oid][0]


class G17Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g17-test-'))
        for b in ('books-sept', 'books-unreconciled'):
            shutil.copytree(str(FIX / b), str(self.tmp / b))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pkg(self, p, name='pkg.json'):
        path = self.tmp / name
        path.write_text(json.dumps(p, indent=1))
        return path

    def ev(self, p, rc):
        r = cli('evaluate', self.pkg(p), '--json')
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return json.loads(r.stdout) if r.stdout.strip().startswith('{') else None

    def test_studio_fixture_figures(self):
        r = self.ev(STUDIO, 0)
        self.assertEqual(r['status'], 'feasible_options')
        self.assertEqual(r['feasible_in_downside'], ['descope-reporting'])
        d = opt(r, 'as-is')['cases']['downside']
        self.assertFalse(d['feasible'])
        self.assertEqual(d['binding_constraints'], ['capacity'])
        self.assertEqual(d['milestones'][0]['capacity_short_hours'], {'backend': '73.2'})
        self.assertEqual(d['cash']['lowest'], '337000.00')
        c = opt(r, 'contractors')['cases']['downside']
        self.assertIn('cash', c['binding_constraints'])
        self.assertEqual(c['cash']['buffer_breach']['week'], 17)
        h = opt(r, 'hire')['cases']['downside']
        self.assertFalse(opt(r, 'hire')['feasible_downside'])
        # one consistent downside world: the late hire start delays both capacity and cost
        self.assertEqual(h['milestones'][0]['capacity_short_hours'], {'backend': '8.4'})
        self.assertEqual(h['cash']['lowest'], '205000.00')
        self.assertEqual(h['cash']['buffer_breach']['week'], 18)
        self.assertTrue(r['read_only'])

    def test_decision_record_fields_and_no_invented_certainty(self):
        r = self.ev(STUDIO, 0)
        for k in ('facts', 'assumptions', 'options', 'risk', 'dissent', 'decision_owner', 'required_evidence'):
            self.assertIn(k, r)
        self.assertTrue(r['decision_owner'])
        self.assertTrue(r['dissent'])
        self.assertIn('not a forecast', r['certainty'])
        text = cli('evaluate', self.pkg(STUDIO)).stdout.lower()
        for bad in ('guarantee', 'we recommend', 'definitely', 'will succeed'):
            self.assertNotIn(bad, text)
        self.assertIn('decision owner', text)

    def test_literal_number_refused(self):
        p = copy.deepcopy(STUDIO)
        p['work'][1]['hours'] = 800
        self.assertIsNone(self.ev(p, 2))

    def test_assumption_needs_source_and_past_date(self):
        for mut in ({'source': ''}, {'dated': '2099-01-01'}):
            p = copy.deepcopy(STUDIO)
            p['assumptions']['api_h'].update(mut)
            self.ev(p, 2)

    def test_conflicting_adverse_use_needs_stated_downside(self):
        p = copy.deepcopy(STUDIO)
        p['assumptions']['hire_start'].pop('downside')
        r = cli('evaluate', self.pkg(p), '--json')
        self.assertEqual(r.returncode, 2)
        self.assertIn('hire_start', r.stderr + r.stdout)

    def test_missing_owner_invalid(self):
        p = copy.deepcopy(STUDIO)
        p['decision']['owner'] = ''
        self.ev(p, 2)

    def test_deadline_boundary(self):
        p = copy.deepcopy(STUDIO)
        p['options'] = [o for o in p['options'] if o['id'] == 'as-is']
        p['milestones'][0]['deadline_week'] = 17
        r = self.ev(p, 1)
        m = opt(r, 'as-is')['cases']['downside']['milestones'][0]
        self.assertEqual((m['finish_week'], m['met']), (18, False))
        p['milestones'][0]['deadline_week'] = 18
        r = self.ev(p, 0)
        self.assertTrue(opt(r, 'as-is')['cases']['downside']['milestones'][0]['met'])

    def test_impossible_deadline_rejected_with_dependency_cause(self):
        p = copy.deepcopy(STUDIO)
        p['milestones'][0]['deadline_week'] = 3
        r = self.ev(p, 1)
        self.assertEqual(r['status'], 'rejected_as_stated')
        self.assertEqual(r['feasible_in_downside'], [])
        for o in r['options']:
            self.assertIn('dependencies', o['cases']['downside']['binding_constraints'])
            self.assertIsNotNone(o['narrowed'])

    def test_unreconciled_books_block_the_decision(self):
        p = copy.deepcopy(STUDIO)
        p['assumptions']['inflow']['from_g14']['package'] = 'books-unreconciled/package.json'
        r = self.ev(p, 1)
        self.assertEqual(r['status'], 'blocked_evidence')
        self.assertTrue(r['required_evidence'])

    def test_reversible_first_and_irreversible_only(self):
        p = copy.deepcopy(STUDIO)
        p['milestones'][0]['deadline_week'] = 20
        p['assumptions']['buffer']['value'] = 1
        r = self.ev(p, 0)
        fe = r['feasible_in_downside']
        self.assertEqual(fe[-1], 'hire')
        self.assertGreaterEqual(len(fe), 3)
        p['options'] = [o for o in p['options'] if o['id'] == 'hire']
        r = self.ev(p, 0)
        self.assertEqual(r['status'], 'feasible_irreversible_only')
        self.assertEqual(r['feasible_in_downside'], ['hire'])

    def test_verify_round_trip_and_tamper(self):
        pk = self.pkg(STUDIO)
        out = self.tmp / 'r.json'
        self.assertEqual(cli('evaluate', pk, '--json', '--out', out).returncode, 0)
        self.assertEqual(cli('verify', pk, out).returncode, 0)
        r = json.loads(out.read_text())
        opt(r, 'as-is')['cases']['downside']['cash']['lowest'] = '999999.00'
        out.write_text(json.dumps(r))
        v = cli('verify', pk, out)
        self.assertEqual(v.returncode, 1)
        self.assertIn('lowest', v.stdout + v.stderr)

    def test_out_refuses_package_path(self):
        pk = self.pkg(STUDIO)
        before = pk.read_bytes()
        self.assertEqual(cli('evaluate', pk, '--json', '--out', pk).returncode, 2)
        self.assertEqual(pk.read_bytes(), before)

    def test_deterministic_and_inputs_untouched(self):
        pk = self.pkg(STUDIO)
        before = pk.read_bytes()
        a, b = cli('evaluate', pk, '--json').stdout, cli('evaluate', pk, '--json').stdout
        self.assertEqual(a, b)
        self.assertEqual(pk.read_bytes(), before)
        self.assertEqual(sorted(x.name for x in self.tmp.iterdir()), ['books-sept', 'books-unreconciled', 'pkg.json'])

    def test_oracle_accepts_tool_and_seeds(self):
        for args in ((), ('--seed', '3'), ('--seed', '7')):
            r = oracle(*args)
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            self.assertIn('ACCEPTED 12/12', r.stdout)

    def test_oracle_rejects_controls(self):
        for t in ('naive_decision.py', 'noop_decision.py'):
            r = oracle('--tool', EX / t)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('REJECTED', r.stdout)


if __name__ == '__main__':
    unittest.main()
