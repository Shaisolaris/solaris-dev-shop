"""G05 revision-bound assurance evidence: stale receipts, carried-forward review, reopened findings.

Runs the G05 oracle against the engine and two controls and checks the pieces it relies on directly:
legacy packets unchanged, schema and code agreement, caller diagnostics, the digest command's refusals.
Nothing named in a receipt is opened or executed; files are only read from temporary directories.
"""
import hashlib
import io
import json
import os
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSURANCE = ROOT / 'employees/quality-security/assurance'
EX = ROOT / 'examples/capabilities/G05'
sys.path.insert(0, str(ASSURANCE))
import quality_os as q  # noqa: E402

ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')
R1 = '4f1c2a9e0b7d3c5a1e8f6b2d9c0a7e3f5b1d8c2a'
R2 = '9b3e7d1c5a2f8e0b6d4c1a9f7e3b5d2c8a0f6e1b'


def oracle(tool):
    p = subprocess.run([sys.executable, str(EX / 'binding_oracle.py'), '--tool', str(tool), '--json'],
                       capture_output=True, text=True, env=ENV, timeout=300)
    return p.returncode, {c['id']: c['ok'] for c in json.loads(p.stdout)['checks']}


def receipt(gate='functional', reviewed=None):
    r = {'gate': gate, 'role': 'qa-engineer', 'summary': 'QA pass', 'artifacts': ['reports/qa.txt'],
         'blocking_open': 0}
    if reviewed is not None:
        r['reviewed'] = reviewed
    return r


class G05Binding(unittest.TestCase):
    def test_oracle_passes_on_the_engine(self):
        code, res = oracle(ASSURANCE / 'quality_os.py')
        self.assertEqual(code, 0, res)
        self.assertEqual(len(res), 16)
        self.assertTrue(all(res.values()), res)

    def test_oracle_rejects_the_naive_control(self):
        code, res = oracle(EX / 'naive_engine.py')
        self.assertEqual(code, 1)
        self.assertEqual({k for k, v in res.items() if not v},
                         {'o1', 'o2', 'o3', 'o5', 'o6', 'o8', 'o9', 'o10', 'o13', 'o14'})

    def test_oracle_rejects_the_noop_control(self):
        code, res = oracle(EX / 'noop_engine.py')
        self.assertEqual(code, 1)
        self.assertEqual({k for k, v in res.items() if v}, {'o0', 'o4', 's1'})

    def test_unbound_packets_keep_their_previous_result_shape(self):
        p = {'risk_level': 'standard', 'dimensions': ['functional'], 'completed_gates': ['functional'],
             'evidence': {'functional': receipt()}}
        res = q.evaluate_artifact_packet(p)
        self.assertTrue(res.ok)
        self.assertEqual(sorted(res.evidence), ['blocking_open', 'completed_gates', 'missing_gates'])
        self.assertEqual(res.gate_codes, [])

    def test_stale_diagnostic_names_files_revisions_and_the_rerun(self):
        sub = {'revision': R2, 'digests': {'src/a.py': 'b' * 64, 'docs/x.md': 'c' * 64}}
        p = {'completed_gates': ['functional'], 'subject': sub,
             'evidence': {'functional': receipt(reviewed={'revision': R1, 'digests': {'src/a.py': 'a' * 64}})}}
        res = q.evaluate_artifact_packet(p)
        self.assertEqual(res.gate_codes, ['STALE_GATE_EVIDENCE'])
        d = res.evidence['revision_binding']['gates']['functional']
        self.assertEqual((d['state'], d['changed'], d['reviewed_revision'], d['subject_revision']),
                         ('stale', ['src/a.py'], R1, R2))
        self.assertIn('re-run the functional gate on ' + R2, d['action'])
        self.assertIn('src/a.py', res.messages[0])

    def test_same_revision_label_with_changed_content_is_stale(self):
        p = {'completed_gates': ['functional'], 'subject': {'revision': R2, 'digests': {'a.txt': 'b' * 64}},
             'evidence': {'functional': receipt(reviewed={'revision': R2, 'digests': {'a.txt': 'a' * 64}})}}
        self.assertEqual(q.evaluate_artifact_packet(p).gate_codes, ['STALE_GATE_EVIDENCE'])

    def test_revision_matching_rules(self):
        self.assertTrue(q.same_revision(R1[:7], R1))
        self.assertFalse(q.same_revision(R1[:6], R1))
        self.assertFalse(q.same_revision('sha256:' + 'a' * 64, 'a' * 64))
        self.assertTrue(q.same_revision('sha256:' + 'a' * 64, 'sha256:' + 'a' * 64))
        for bad in ('HEAD', 'ABCDEF0', 'abc', 'sha256:' + 'a' * 63, 12, None):
            self.assertIsNotNone(q.revision_error(bad), bad)

    def test_schemas_agree_with_the_code(self):
        fs = json.loads((ASSURANCE / 'finding.schema.json').read_text())
        self.assertEqual(set(fs['properties']), set(q.Finding.__dataclass_fields__))
        es = json.loads((ASSURANCE / 'evidence.schema.json').read_text())
        self.assertEqual(es['properties']['reviewed']['properties']['revision']['pattern'], q.REVISION_RE.pattern)
        self.assertEqual(es['properties']['reviewed']['properties']['digests']['maxProperties'], q.MAX_BOUND_ARTIFACTS)

    def test_digest_refuses_symlinks_and_oversize_files(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'p'
            (root / 'src').mkdir(parents=True)
            (root / 'src' / 'a.py').write_bytes(b'print(1)\n')
            outside = Path(t) / 'outside.txt'
            outside.write_text('x')
            self.assertEqual(q.artifact_digests(root, ['src']),
                             {'src/a.py': hashlib.sha256(b'print(1)\n').hexdigest()})
            (root / 'src' / 'link.txt').symlink_to(outside)
            with self.assertRaises(ValueError):
                q.artifact_digests(root, ['src'])
            (root / 'src' / 'link.txt').unlink()
            old = q.MAX_DIGEST_FILE_BYTES
            q.MAX_DIGEST_FILE_BYTES = 4
            try:
                with self.assertRaises(ValueError):
                    q.artifact_digests(root, ['src/a.py'])
            finally:
                q.MAX_DIGEST_FILE_BYTES = old
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(q.main(['digest', str(root), 'src', '--revision', R1]), 0)
                self.assertEqual(q.main(['digest', str(root), '../p/src']), 2)
            self.assertEqual(json.loads(out.getvalue())['revision'], R1)
            self.assertIn('error:', err.getvalue())

    def test_closure_fixture_and_self_test_commands(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(q.main(['self-test']), 0)
        f = q.create_finding(defect_kind='security', severity='S1', title='t', evidence=['e'],
                             reporter_role='qa-engineer', finding_id='fnd-x')
        closed, codes = q.close_finding(f, closer_role='code-reviewer', independent_evidence=['v'])
        self.assertEqual((codes, closed.closed_at_revision), ([], ''))
        self.assertEqual(q.closure_is_current(closed, R1), (False, ['UNBOUND_CLOSURE']))
        self.assertEqual(q.closure_is_current(closed, 'HEAD'), (False, ['INVALID_REVISION']))

    def test_doc_lists_every_new_code(self):
        doc = (ASSURANCE / 'ASSURANCE.md').read_text()
        for code in ('STALE_GATE_EVIDENCE', 'UNBOUND_GATE_EVIDENCE', 'REVISION_CONFLICT', 'STALE_CLOSURE_EVIDENCE',
                     'MISSING_VERIFIED_REVISION', 'INVALID_REVISION', 'STALE_CLOSURE', 'UNBOUND_CLOSURE',
                     'REOPEN_REASON_REQUIRED', 'NOT_CLOSED', 'carried_forward', 'digest'):
            self.assertIn(code, doc)


if __name__ == '__main__':
    unittest.main()
