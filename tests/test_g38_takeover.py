"""Held-out authority checks: clause-bearing attribution and explicit README declarations."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PC = ROOT / 'employees/quality-security/security-auditor/provenance_check.py'
FIX = ROOT / 'examples/capabilities/G38/fixtures/repo-clean'
s = importlib.util.spec_from_file_location('root_provenance', PC)
p = importlib.util.module_from_spec(s)
s.loader.exec_module(p)

class AuthorityBoundaries(unittest.TestCase):
    def test_attribution_cannot_hide_a_condition_without_comma(self):
        mit = (FIX / 'LICENSE').read_text()
        for holder in ['Acme for students and teachers', 'Acme under academic rules', 'Acme subject to approval', 'Acme provided attribution', 'Acme as long as attribution is given', 'Acme contingent on annual renewal']:
            with self.subTest(holder=holder):
                candidate = re.sub(r'(?im)^copyright.*$', 'Copyright 2026 ' + holder, mit)
                self.assertIsNone(p.identify(candidate))

    def test_plain_holder_controls_remain_recognized(self):
        mit = (FIX / 'LICENSE').read_text()
        for holder in ['Acme Research Labs, Ltd.', 'Jane Doe and contributors', 'The Solaris Authors']:
            with self.subTest(holder=holder):
                candidate = re.sub(r'(?im)^copyright.*$', 'Copyright 2026 ' + holder, mit)
                self.assertEqual(p.identify(candidate), 'MIT')

    def test_wrapped_readme_declaration_is_compared(self):
        with tempfile.TemporaryDirectory(prefix='solaris-license-test-') as td:
            repo = Path(td) / 'repo'; shutil.copytree(FIX, repo)
            for wrap in ['**', '__', '`']:
                with self.subTest(wrap=wrap):
                    (repo / 'README.md').write_text('# Demo\n\n## License\n\n' + wrap + 'GPL-3.0' + wrap + '. See LICENSE.\n')
                    r = subprocess.run([sys.executable, '-B', str(PC), 'check', str(repo), '--json'], capture_output=True, text=True, timeout=30)
                    self.assertEqual(r.returncode, 1, r.stderr)
                    findings = json.loads(r.stdout)['findings']
                    self.assertTrue(any(x['code']=='license_mismatch' and x.get('path')=='README.md' for x in findings), findings)

    def test_license_heading_case_does_not_skip_conflict(self):
        with tempfile.TemporaryDirectory(prefix='solaris-license-case-') as td:
            repo = Path(td) / 'repo'; shutil.copytree(FIX, repo)
            for heading in ['license', 'LICENSE', 'LiCeNsE']:
                (repo / 'README.md').write_text('# Demo\n\n## '+heading+'\n\nGPL-3.0\n')
                r = subprocess.run([sys.executable, '-B', str(PC), 'check', str(repo), '--json'], capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertTrue(any(f['code']=='license_mismatch' for f in json.loads(r.stdout)['findings']))

    def test_unparseable_explicit_license_is_reported(self):
        with tempfile.TemporaryDirectory(prefix='solaris-license-test-') as td:
            repo = Path(td) / 'repo'; shutil.copytree(FIX, repo)
            (repo / 'README.md').write_text('# Demo\n\n## License\n\n**GPL-3.0\n')
            r = subprocess.run([sys.executable, '-B', str(PC), 'check', str(repo), '--json'], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertTrue(any(x['code']=='license_undeclared' and x.get('path')=='README.md' for x in json.loads(r.stdout)['findings']))
