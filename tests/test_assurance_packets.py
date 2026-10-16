"""Receipt validation rejects malformed host handoffs without executing artifacts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'employees/quality-security/assurance'))
import quality_os as q


def packet():
    return {'risk_level': 'standard', 'dimensions': ['functional'],
            'completed_gates': ['functional'], 'evidence': {'functional': {
                'gate': 'functional', 'role': 'qa-engineer', 'summary': 'Local QA receipt',
                'artifacts': ['reports/qa.txt'], 'blocking_open': 0}}}


class AssurancePackets(unittest.TestCase):
    def blocked(self, data, code=None):
        result = q.evaluate_artifact_packet(data)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.status, 'blocked')
        if code:
            self.assertIn(code, result.gate_codes)
        return result

    def test_valid_documented_receipt_without_artifact_access(self):
        data = packet()
        data['evidence']['functional']['artifacts'] = ['https://example.invalid/no-request',
                                                       'missing/not-executed.sh']
        before = copy.deepcopy(data)
        result = q.evaluate_artifact_packet(data)
        self.assertTrue(result.ok)
        self.assertEqual(result.required_gates, ['functional'])
        self.assertEqual(data, before)

    def test_truthy_receipts_cannot_replace_evidence_objects(self):
        for value in ['ok', True, 1, ['report.txt']]:
            with self.subTest(value=value):
                data = packet(); data['evidence']['functional'] = value
                self.blocked(data, 'INVALID_GATE_EVIDENCE')

    def test_all_required_receipt_fields_are_enforced(self):
        for key in ['gate', 'role', 'summary', 'artifacts']:
            with self.subTest(field=key):
                data = packet(); del data['evidence']['functional'][key]
                self.blocked(data, 'INVALID_GATE_EVIDENCE')

    def test_blank_and_wrong_receipt_field_types(self):
        for key, values in {'gate': ['security', ' functional ', None],
                            'role': ['', ' \t', 1, []],
                            'summary': ['', '\n', {}, True],
                            'artifacts': ['report.txt', [], [''], [' \t'], [1], [None]]}.items():
            for value in values:
                with self.subTest(field=key, value=value):
                    data = packet(); data['evidence']['functional'][key] = value
                    self.blocked(data, 'INVALID_GATE_EVIDENCE')

    def test_reported_open_findings_block_and_are_counted(self):
        data = packet(); data['evidence']['functional']['blocking_open'] = 2
        result = self.blocked(data, 'OPEN_BLOCKING_FINDINGS')
        self.assertEqual(result.evidence['blocking_open'], 2)

    def test_invalid_blocker_counts_and_optional_metadata(self):
        for key, values in {'blocking_open': [True, False, -1, 1.0, '0', None],
                            'schema_version': ['unknown', 1, None],
                            'timestamp': [None, 1, []]}.items():
            for value in values:
                with self.subTest(field=key, value=value):
                    data = packet(); data['evidence']['functional'][key] = value
                    self.blocked(data, 'INVALID_GATE_EVIDENCE')

    def test_malformed_roots_and_containers_are_diagnostics(self):
        for value in [None, [], 'packet', 1, False]:
            with self.subTest(root=value):
                self.blocked(value, 'INVALID_PACKET')
        for key in ['completed_gates', 'dimensions', 'evidence']:
            values = [None, 'functional', 1, False, [None]]
            if key != 'evidence':
                values.append({})
            for value in values:
                with self.subTest(field=key, value=value):
                    data = packet(); data[key] = value
                    self.blocked(data, 'INVALID_PACKET')

    def test_missing_unknown_and_orphan_gates_block(self):
        data = packet(); data['evidence'] = {}
        self.blocked(data, 'MISSING_GATE_EVIDENCE')
        data = packet(); data['completed_gates'] = []; data['evidence'] = {}
        self.blocked(data, 'MISSING_SPECIALIST_GATE')
        data = packet(); data['completed_gates'].append('invented')
        self.blocked(data, 'UNKNOWN_GATE')
        # An unlisted receipt cannot hide its declared blocker.
        data = packet(); data['completed_gates'] = []
        data['evidence']['functional']['blocking_open'] = 1
        self.blocked(data, 'INVALID_PACKET')

    def test_declared_risk_and_dimensions_use_known_types(self):
        for key, value in [('risk_level', 'unknown'), ('data_sensitivity', []),
                           ('blast_radius', 'unknown'), ('mutates_external', 'false'),
                           ('user_facing', 1), ('dimensions', ['unknown'])]:
            with self.subTest(field=key):
                data = packet(); data[key] = value
                self.blocked(data, 'INVALID_PACKET')
        # A direct gate dimension must not silently disappear from policy routing.
        data = packet(); data['risk_level'] = 'elevated'; data['dimensions'] = ['design']
        result = self.blocked(data, 'MISSING_SPECIALIST_GATE')
        self.assertIn('design', result.required_gates)

    def test_nested_defects_cannot_suppress_blocking_findings(self):
        data = packet(); data['planted_defects'] = [{'defect_kind': 'functional',
                                                   'severity': 'S2'}]
        result = self.blocked(data, 'OPEN_BLOCKING_FINDINGS')
        self.assertTrue(result.orders)
        data['planted_defects'][0]['severity'] = 'nonsense'
        self.blocked(data, 'INVALID_PACKET')
        data['planted_defects'] = [{'defect_kind': 'invented'}]
        self.blocked(data, 'UNKNOWN_DEFECT_KIND')
        for field in ['defect_kind', 'severity', 'title', 'evidence']:
            data['planted_defects'] = [{field: {'bad': 'shape'}}]
            self.blocked(data, 'INVALID_PACKET')

    def test_legal_boundaries_and_malformed_sources_preserved(self):
        data = packet(); data['legal_text'] = 'I am your attorney; file this lawsuit now.'
        self.blocked(data, 'LEGAL_BINDING_PROHIBITED')
        for source in [['bad'], [{'retrieved_at': 42}],
                       [{'retrieved_at': '2026-10-16', 'max_age_days': []}]]:
            data = packet(); data['sources'] = source
            self.blocked(data, 'INVALID_PACKET')

    def cli(self, data, raw=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'packet.json'
            path.write_text(data if raw else json.dumps(data), encoding='utf-8')
            return subprocess.run([sys.executable, str(ROOT / 'employees/quality-security/assurance/quality_os.py'),
                                   'run', str(path)], capture_output=True, text=True)

    def test_cli_malformed_packets_fail_without_tracebacks(self):
        for data in [[], {'packet': []}, {'packet': None}, {'evidence': ['bad']},
                     {'expectations': ['bad']}, '{invalid json']:
            with self.subTest(data=data):
                result = self.cli(data, raw=isinstance(data, str))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(json.loads(result.stdout)['status'], 'blocked')
                self.assertNotIn('Traceback', result.stderr)

    def test_negative_fixture_success_is_not_packet_acceptance(self):
        data = packet(); data['evidence']['functional'] = 'not a receipt'
        self.blocked(data, 'INVALID_GATE_EVIDENCE')
        result = self.cli({'packet': data, 'expectations': {
            'outcome': 'fail_gate', 'gate_codes': ['INVALID_GATE_EVIDENCE']}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('fail_gate expectation met', json.loads(result.stdout)['notes'])
        # The direct packet decision is still blocked, even if a producer includes expectations.
        data['expectations'] = {'outcome': 'fail_gate'}
        self.blocked(data, 'INVALID_GATE_EVIDENCE')


if __name__ == '__main__':
    unittest.main()
