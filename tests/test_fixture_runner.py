"""Quality OS fixture runner (`run` / `suite`) must not report false passes.

A suite that evaluated nothing, a fixture kind or expectation that is misspelled,
or a non-assurance JSON file must not count as a passing assurance fixture.
Valid positive, negative, planted-defect, closure and legal fixtures keep their
existing outcomes. These tests drive the real CLI in temporary directories.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'employees/quality-security/assurance/quality_os.py'
sys.path.insert(0, str(ENGINE.parent))
import quality_os as q

RECEIPT = {'gate': 'security', 'role': 'security-auditor', 'summary': 'STRIDE review of auth change',
           'artifacts': ['reports/threat-model.md'], 'blocking_open': 0}
GATE_MISSING = {'risk_level': 'elevated', 'dimensions': ['security'], 'completed_gates': [], 'evidence': {}}
GATE_DONE = {'risk_level': 'elevated', 'dimensions': ['security'], 'completed_gates': ['security'],
             'evidence': {'security': RECEIPT}}
NO_GATE_NEEDED = dict(GATE_MISSING, risk_level='informational')
FINDING = {'finding_id': 'f-1', 'defect_kind': 'security', 'severity': 'S1', 'title': 'Reflected XSS',
           'evidence': ['scan: payload reflected'], 'accountable_role': 'security-auditor',
           'reporter_role': 'qa-engineer', 'status': 'open', 'verifier_role': 'code-reviewer'}


class FixtureRunner(unittest.TestCase):
    def cli(self, *args):
        proc = subprocess.run([sys.executable, str(ENGINE), *args], capture_output=True, text=True)
        self.assertNotIn('Traceback', proc.stderr)
        return proc.returncode, json.loads(proc.stdout)

    def run_fixture(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixture.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            return self.cli('run', str(path))

    def suite(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in files.items():
                (Path(tmp) / name).write_text(json.dumps(data), encoding='utf-8')
            return self.cli('suite', tmp)

    # -- suites that evaluated nothing are not passes ---------------------------------
    def test_missing_or_empty_suite_directory_fails(self):
        for args in (('suite',), ('suite', str(ROOT / 'no-such-fixture-dir'))):
            code, out = self.cli(*args)
            self.assertEqual((code, out['ok'], out['total']), (1, False, 0), args)
            self.assertIn('fixture directory not found', out['error'])
        code, out = self.suite({})
        self.assertEqual((code, out['ok'], out['total']), (1, False, 0))
        self.assertIn('no fixtures found', out['error'])
        code, out = self.suite({'_skipped.json': GATE_DONE})
        self.assertEqual((code, out['ok'], out['total']), (1, False, 0))

    def test_router_fixtures_are_not_assurance_passes(self):
        code, out = self.cli('suite', str(ROOT / 'fixtures'))
        self.assertEqual((code, out['ok'], out['passed']), (1, False, 0))
        self.assertGreater(out['total'], 0)
        self.assertTrue(all(r['gate_codes'] == ['INVALID_PACKET'] for r in out['results']))

    # -- misspelled contract fields fail closed --------------------------------------------
    def test_unknown_or_malformed_expectations_rejected(self):
        for packet, expectations in (
                (NO_GATE_NEEDED, {'outcome': 'fail-gate'}),
                (NO_GATE_NEEDED, {'outcome': 'fail'}),
                (NO_GATE_NEEDED, {'outcome': ['fail_gate']}),
                (NO_GATE_NEEDED, {'outcom': 'fail_gate'}),
                (GATE_MISSING, {'outcome': 'fail_gate', 'gate_code': ['INVALID_GATE_EVIDENCE']}),
                (GATE_DONE, {'outcome': 'pass', 'accountable_role': 7}),
                (GATE_DONE, {'outcome': 'pass', 'accountable_role': ' '})):
            with self.subTest(expectations=expectations):
                for data in ({'packet': packet, 'expectations': expectations},
                             dict(packet, expectations=expectations)):
                    code, out = self.run_fixture(data)
                    self.assertEqual((code, out['ok'], out['gate_codes']), (1, False, ['INVALID_PACKET']))

    def test_unknown_fixture_kind_rejected(self):
        for data in ({'fixture_kind': 'closre', 'finding': FINDING, 'closer_role': 'security-auditor'},
                     {'fixture_kind': ['closure'], 'finding': FINDING},
                     {'fixture_kind': '', 'finding': FINDING},
                     {'kind': 'security', 'severity': 'S1', 'title': 'planted XSS'}):
            with self.subTest(data=data):
                code, out = self.run_fixture(data)
                self.assertEqual((code, out['ok'], out['gate_codes']), (1, False, ['INVALID_PACKET']))

    # -- legitimate fixtures keep their outcomes ----------------------------------------------
    def test_valid_fixtures_unchanged(self):
        cases = [
            ({'packet': GATE_MISSING, 'expectations': {'outcome': 'fail_gate',
                                                         'gate_codes': ['MISSING_SPECIALIST_GATE']}}, 0),
            (dict(GATE_DONE, expectations={'outcome': 'pass'}), 0),
            (GATE_DONE, 0),
            ({'fixture_kind': 'packet', 'packet': GATE_DONE}, 0),
            ({'fixture_kind': 'planted_defect', 'defect': {'defect_kind': 'security', 'severity': 'S1'},
              'expectations': {'accountable_role': 'security-auditor'}}, 0),
            ({'kind': 'defect', 'defect': {'defect_kind': 'security'}}, 0),
            ({'fixture_kind': 'closure', 'finding': FINDING, 'closer_role': 'security-auditor'}, 0),
            ({'fixture_kind': 'legal', 'text': 'I am your attorney; file this lawsuit now.'}, 0),
            ({'packet': GATE_MISSING, 'expectations': {'outcome': 'pass'}}, 1),
            ({'packet': NO_GATE_NEEDED, 'expectations': {'outcome': 'fail_gate'}}, 1),
        ]
        for data, want in cases:
            with self.subTest(data=data):
                code, out = self.run_fixture(data)
                self.assertEqual((code, out['ok']), (want, want == 0))

    def test_suite_of_valid_fixtures_passes(self):
        code, out = self.suite({'neg.json': {'packet': GATE_MISSING, 'expectations': {'outcome': 'fail_gate'}},
                                'pos.json': GATE_DONE, '_note.json': {'not': 'a fixture'}})
        self.assertEqual((code, out['ok'], out['total'], out['passed']), (0, True, 2, 2))
        self.assertNotIn('error', out)

    def test_direct_packet_api_unchanged(self):
        # The fixture contract does not change evaluate_artifact_packet decisions.
        self.assertTrue(q.evaluate_artifact_packet(GATE_DONE).ok)
        blocked = q.evaluate_artifact_packet(dict(GATE_MISSING, expectations={'outcome': 'fail_gate'}))
        self.assertEqual((blocked.ok, blocked.gate_codes), (False, ['MISSING_SPECIALIST_GATE']))


if __name__ == '__main__':
    unittest.main()
