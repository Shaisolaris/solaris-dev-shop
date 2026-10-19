"""Quality OS fixture runner (`run` / `suite`) must not report false passes.

A suite that evaluated nothing, a fixture kind or expectation that is misspelled,
or a non-assurance JSON file must not count as a passing assurance fixture.
Valid positive, negative, planted-defect, closure and legal fixtures keep their
existing outcomes. These tests drive the real CLI in temporary directories.
"""
import json
import os
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


class M01Rework(unittest.TestCase):
    """G01 repair r1 (M01 Grok self-validation of the G01 handback): fixture-contract keys (F1),
    vacuous expectations (F2), legal fixtures without expectations (F3), malformed fields and
    deep JSON (F4), skipped files (F5) and the two builder-test gaps M01 found (F6)."""
    BAD_LEGAL = 'I am your attorney; file this lawsuit now.'
    CLEAN_LEGAL = 'General information about filing deadlines. Not legal advice.'
    cli = FixtureRunner.cli
    run_fixture = FixtureRunner.run_fixture

    def assert_invalid(self, data, raw=None, why=None):
        if raw is not None:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'fixture.json'
                path.write_text(raw, encoding='utf-8')
                code, out = self.cli('run', str(path))
        else:
            code, out = self.run_fixture(data)
        self.assertEqual((code, out['ok'], out['gate_codes']), (1, False, ['INVALID_PACKET']), data or raw[:80])
        if why is not None:
            # the named check refused it, not a later crash caught by the fail-closed wrapper
            self.assertIn(why, ' '.join(out.get('messages', [])))
        return out

    def test_f1_misspelled_fixture_contract_keys_are_invalid(self):
        for key in ('fixture-kind', 'Fixture_Kind', 'fixturekind', 'fixture_knid', 'fixtureKind'):
            with self.subTest(key=key):
                self.assert_invalid({key: 'closure', 'finding': FINDING, 'closer_role': 'security-auditor',
                                     'expect_blocked': False})
        for key in ('pakcet', 'Packet', 'packets'):
            with self.subTest(key=key):
                self.assert_invalid({key: GATE_MISSING, 'expectations': {'outcome': 'pass'}})
        for key in ('expectation', 'Expectations', 'expected'):
            with self.subTest(key=key):
                self.assert_invalid({'packet': GATE_DONE, key: {'outcome': 'fail_gate'}})
        for key in ('txt', 'Text', 'legal-text'):
            with self.subTest(key=key):
                self.assert_invalid({'fixture_kind': 'legal', key: self.BAD_LEGAL})
        self.assert_invalid({'fixture_kind': 'closure', 'finding': FINDING, 'closer_role': 'security-auditor',
                             'expect_blocked': False, 'closer_rol': 'x'})
        # an unwrapped packet that carries closure fields lost its fixture_kind
        self.assert_invalid(dict(GATE_DONE, finding=FINDING))

    def test_f1_duplicate_keys_are_invalid(self):
        raw = ('{"fixture_kind": "closure", "finding": %s, "closer_role": "security-auditor", '
               '"expect_blocked": false, "fixture_kind": "packet"}' % json.dumps(FINDING))
        out = self.assert_invalid(None, raw=raw)
        self.assertIn('duplicate key', ' '.join(out.get('messages', []) + out.get('notes', [])))
        self.assert_invalid(None, raw='{"packet": %s, "expectations": {"outcome": "pass", "outcome": "fail_gate"}}'
                            % json.dumps(GATE_DONE))

    def test_f2_expectations_that_cannot_be_checked_fail(self):
        for data in ({'packet': GATE_DONE, 'expectations': {'outcome': 'pass', 'accountable_role': 'nobody'}},
                     {'fixture_kind': 'legal', 'text': self.BAD_LEGAL,
                      'expectations': {'outcome': 'fail_gate', 'accountable_role': 'nobody'}}):
            with self.subTest(data=data):
                code, out = self.run_fixture(data)
                self.assertEqual((code, out['ok']), (1, False))
                self.assertIn('GATE_MISROUTE', out['gate_codes'])
        for exp in ({'outcome': 'pass', 'gate_codes': ['MISSING_SPECIALIST_GATE']},
                    {'gate_codes': ['MISSING_SPECIALIST_GATE']},
                    {'outcome': 'fail_gate', 'gate_codes': []}):
            with self.subTest(exp=exp):
                self.assert_invalid({'packet': GATE_DONE, 'expectations': exp})
        # every listed gate must fire
        code, out = self.run_fixture({'packet': GATE_MISSING, 'expectations': {
            'outcome': 'fail_gate', 'gate_codes': ['MISSING_SPECIALIST_GATE', 'SOME_OTHER_GATE']}})
        self.assertEqual((code, out['ok']), (1, False))
        code, out = self.run_fixture({'packet': GATE_MISSING, 'expectations': {
            'outcome': 'fail_gate', 'gate_codes': ['MISSING_SPECIALIST_GATE']}})
        self.assertEqual((code, out['ok']), (0, True))

    def test_f3_legal_fixture_without_expectations_must_be_blocked(self):
        self.assertEqual(self.run_fixture({'fixture_kind': 'legal', 'text': self.BAD_LEGAL})[0], 0)
        code, out = self.run_fixture({'fixture_kind': 'legal', 'text': self.CLEAN_LEGAL})
        self.assertEqual((code, out['ok']), (1, False))
        self.assertIn('EXPECTED_GATE_NOT_FIRED', out['gate_codes'])
        code, out = self.run_fixture({'fixture_kind': 'legal', 'text': self.CLEAN_LEGAL, 'expectations': {'outcome': 'pass'}})
        self.assertEqual((code, out['ok']), (0, True))

    def test_f4_malformed_fields_and_deep_json_are_invalid_not_a_crash(self):
        for data, why in (({'fixture_kind': 'legal', 'text': 'x', 'freshness_days': 'abc'}, 'freshness_days'),
                          ({'fixture_kind': 'legal', 'text': 'x', 'freshness_days': None}, 'freshness_days'),
                          ({'fixture_kind': 'legal', 'text': 'x', 'freshness_days': True}, 'freshness_days'),
                          ({'fixture_kind': 'legal', 'text': 'x', 'freshness_days': -1}, 'freshness_days'),
                          ({'fixture_kind': 'legal', 'text': ['x']}, 'text must be a string'),
                          ({'fixture_kind': 'legal', 'legal_text': 7}, 'legal_text must be a string'),
                          ({'fixture_kind': 'legal', 'text': 'x', 'requested_actions': 'legal_file'}, 'requested_actions'),
                          ({'fixture_kind': 'legal', 'text': 'x', 'sources': ['a']}, 'sources must be'),
                          ({'fixture_kind': 'legal', 'text': 'x', 'sources': {'url': 'a'}}, 'sources must be'),
                          ({'fixture_kind': 'planted_defect', 'defect': 'security'}, 'defect must be an object'),
                          ({'fixture_kind': 'planted_defect', 'defect': ['security']}, 'defect must be an object')):
            with self.subTest(data=data):
                self.assert_invalid(data, why=why)
        self.assert_invalid(None, raw='[' * 200000 + ']' * 200000)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'a.json').write_text(json.dumps(GATE_DONE))
            (Path(tmp) / 'z.json').write_text(json.dumps({'fixture_kind': 'planted_defect', 'defect': 'security'}))
            code, out = self.cli('suite', tmp)
        self.assertEqual((code, out['ok'], out['total'], out['passed']), (1, False, 2, 1))

    def test_f4_unexpected_engine_error_is_invalid_not_a_traceback(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixture.json'
            path.write_text(json.dumps(GATE_DONE))
            with mock.patch.object(q, '_evaluate_fixture', side_effect=KeyError('boom')):
                result = q.evaluate_path(path)
            with mock.patch.object(q, '_evaluate_fixture', side_effect=RecursionError()):
                deep = q.evaluate_path(path)
        self.assertEqual((result.ok, result.gate_codes), (False, ['INVALID_PACKET']))
        self.assertIn('KeyError', ' '.join(result.messages))
        self.assertEqual((deep.ok, deep.gate_codes), (False, ['INVALID_PACKET']))

    def test_f5_suite_counts_any_json_case_and_reports_symlinked_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fx'
            root.mkdir()
            (root / 'a.json').write_text(json.dumps(GATE_DONE))
            (root / 'B.JSON').write_text(json.dumps({'packet': GATE_MISSING, 'expectations': {'outcome': 'pass'}}))
            (root / 'C.Json').write_text(json.dumps({'fixture_kind': 'closre'}))
            (root / '_D.JSON').write_text('not json')
            code, out = self.cli('suite', str(root))
            self.assertEqual((code, out['ok'], out['total'], out['passed']), (1, False, 3, 1))
            for f in ('B.JSON', 'C.Json'):
                (root / f).unlink()
            ext = Path(tmp) / 'external'
            ext.mkdir()
            (ext / 'bad.json').write_text(json.dumps({'packet': GATE_MISSING, 'expectations': {'outcome': 'pass'}}))
            os.symlink(ext, root / 'linked')
            code, out = self.cli('suite', str(root))
            self.assertEqual((code, out['ok'], out['total'], out['passed']), (1, False, 2, 1))
            self.assertTrue(any('symlinked directory' in ' '.join(r['notes']) for r in out['results']))

    def test_f6_fixture_kind_takes_precedence_and_decision_is_not_an_expectation(self):
        # a valid fixture_kind wins over a contradicting legacy kind; reading kind first would refuse these
        code, out = self.run_fixture({'fixture_kind': 'legal', 'kind': 'closure', 'text': self.BAD_LEGAL,
                                      'expectations': {'outcome': 'fail_gate'}})
        self.assertEqual((code, out['ok']), (0, True))
        code, out = self.run_fixture({'fixture_kind': 'closure', 'kind': 'nonsense', 'finding': FINDING,
                                      'closer_role': 'security-auditor'})
        self.assertEqual((code, out['ok']), (0, True))
        self.assert_invalid({'fixture_kind': 'closre', 'kind': 'closure', 'finding': FINDING})
        # a present but empty or null fixture_kind still wins; it does not fall back to kind
        for blank in ('', None, False):
            with self.subTest(blank=blank):
                self.assert_invalid({'fixture_kind': blank, 'kind': 'closure', 'finding': FINDING,
                                     'closer_role': 'security-auditor'}, why='fixture_kind must be one of')
        self.assert_invalid({'kind': ''}, why='kind must be one of')
        # "decision" is the key that motivated G01; it is not an expectation key
        for data in ({'packet': GATE_MISSING, 'expectations': {'decision': 'pass'}},
                     dict(GATE_MISSING, expectations={'decision': 'fail_gate'})):
            with self.subTest(data=data):
                self.assert_invalid(data)



class M01R2Rework(unittest.TestCase):
    """G01 repair r2 (M01 r2 Grok self-validation of deb06f6): a legal fixture whose kind key is a
    synonym or missing must not pass (S1), and a suite must report a subfolder it cannot read (S2).
    The F3 reading (a legal fixture without expectations must be blocked) is kept."""
    BAD_LEGAL = M01Rework.BAD_LEGAL
    CLEAN_LEGAL = M01Rework.CLEAN_LEGAL
    cli = FixtureRunner.cli
    run_fixture = FixtureRunner.run_fixture
    assert_invalid = M01Rework.assert_invalid

    def test_s1_synonym_or_missing_kind_key_cannot_pass_blocked_legal_text(self):
        cases = {'y01 fixture_type': {'fixture_type': 'legal', 'text': self.BAD_LEGAL},
                 'y03 no kind key': {'text': self.BAD_LEGAL},
                 'type': {'type': 'legal', 'text': self.BAD_LEGAL},
                 'fixtureType': {'fixtureType': 'legal_boundary', 'text': self.BAD_LEGAL},
                 'requested_actions only': {'requested_actions': ['file the lawsuit']},
                 'sources only': {'sources': [{'url': 'https://example.com', 'age_days': 3}]},
                 'freshness_days only': {'freshness_days': 3},
                 'type names closure': {'type': 'closure'},
                 'subject_kind on a legal_text packet': {'subject_kind': 'legal', 'legal_text': self.BAD_LEGAL,
                                                         'expectations': {'outcome': 'pass'}},
                 'expectations pass': {'fixture_type': 'legal', 'text': self.BAD_LEGAL,
                                       'expectations': {'outcome': 'pass'}}}
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assert_invalid(data, why='fixture')
        # the y01 suite through the documented command: ok false, not 2/2
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'y01.json').write_text(json.dumps(cases['y01 fixture_type']))
            (root / 'neg.json').write_text(json.dumps({'packet': GATE_MISSING, 'expectations': {'outcome': 'fail_gate'}}))
            code, out = self.cli('suite', str(root))
            self.assertEqual((code, out['ok'], out['total'], out['passed']), (1, False, 2, 1))

    def test_s1_controls_still_behave(self):
        # y02: legal_text is a packet field and triggers the legal gate on an unwrapped packet
        code, out = self.run_fixture({'legal_text': self.BAD_LEGAL, 'expectations': {'outcome': 'fail_gate'}})
        self.assertEqual((code, out['ok']), (0, True))
        # the proper legal fixture: blocked text passes as a negative fixture, F3 kept
        code, out = self.run_fixture({'fixture_kind': 'legal', 'text': self.BAD_LEGAL})
        self.assertEqual((code, out['ok']), (0, True))
        code, out = self.run_fixture({'fixture_kind': 'legal', 'text': self.CLEAN_LEGAL})
        self.assertEqual((code, out['ok'], out['gate_codes']), (1, False, ['EXPECTED_GATE_NOT_FIRED']))
        code, out = self.run_fixture({'fixture_kind': 'legal', 'text': self.CLEAN_LEGAL, 'expectations': {'outcome': 'pass'}})
        self.assertEqual((code, out['ok']), (0, True))
        # note keys and packets whose other keys merely end in "type" with a non-kind value are untouched
        for data in ({'packet': GATE_DONE, 'description': 'legal review', 'expectations': {'outcome': 'pass'}},
                     dict(GATE_DONE, artifact_type='report', expectations={'outcome': 'pass'}),
                     dict(GATE_DONE, expectations={'outcome': 'pass'})):
            with self.subTest(data=sorted(data)):
                code, out = self.run_fixture(data)
                self.assertEqual((code, out['ok']), (0, True), out)

    @unittest.skipIf(hasattr(os, 'geteuid') and os.geteuid() == 0, 'root can read a mode-000 folder')
    def test_s2_suite_reports_an_unreadable_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fx'
            (root / 'locked').mkdir(parents=True)
            (root / 'a.json').write_text(json.dumps(GATE_DONE))
            (root / 'locked' / 'bad.json').write_text(json.dumps({'packet': GATE_MISSING, 'expectations': {'outcome': 'pass'}}))
            os.chmod(root / 'locked', 0)
            try:
                code, out = self.cli('suite', str(root))
            finally:
                os.chmod(root / 'locked', 0o755)
            self.assertEqual((code, out['ok'], out['total'], out['passed'], out['failed']), (1, False, 2, 1, 1))
            bad = [r for r in out['results'] if not r['ok']][0]
            self.assertEqual((Path(bad['path']).name, bad['gate_codes']), ('locked', ['INVALID_PACKET']))
            self.assertIn('could not be read', ' '.join(bad['notes']))
            code, out = self.cli('suite', str(root))  # readable again: the real fixture is evaluated and fails
            self.assertEqual((code, out['ok'], out['total'], out['passed']), (1, False, 2, 1))


if __name__ == '__main__':
    unittest.main()
