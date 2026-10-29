"""G38: repository and legal authority consistency (security-auditor provenance_check.py, blockchain-developer
event_chain.py). Real files, subprocesses and locks on synthetic fixtures; worked figures in the G38 README."""
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PC = ROOT / 'employees' / 'quality-security' / 'security-auditor' / 'provenance_check.py'
EC = ROOT / 'employees' / 'engineering' / 'blockchain-developer' / 'event_chain.py'
EX = ROOT / 'examples' / 'capabilities' / 'G38'
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')
PJ = 'employees/demo/report-writer/plugin.json'


def run(tool, *a, timeout=300):
    return subprocess.run([sys.executable, str(tool)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=timeout)


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def ehash(e):
    return hashlib.sha256(canon({k: e[k] for k in ('seq', 'prev', 'at', 'claimed_by', 'body')}).encode()).hexdigest()


def chain(n):
    out, prev = [], '0' * 64
    for i in range(n):
        e = {'seq': i, 'prev': prev, 'at': '2026-10-01T09:%02d:00-07:00' % i, 'claimed_by': 'Desk %d (synthetic)' % (i % 2), 'body': {'n': i}}
        e['hash'] = ehash(e); prev = e['hash']; out.append(e)
    return out


def dump(evs):
    return ''.join(canon(e) + '\n' for e in evs).encode()


class G38Provenance(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g38-test-'))
        self.r = self.tmp / 'repo'
        shutil.copytree(str(EX / 'fixtures' / 'repo-clean'), str(self.r))

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def check(self, rc, *a, root=None):
        r = run(PC, 'check', root or self.r, '--json', *a)
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return json.loads(r.stdout) if rc != 2 else r

    def codes(self, j):
        return sorted((f['code'], f.get('path')) for f in j['findings'])

    def test_clean_fixture_and_actual_repository(self):
        j = self.check(0, '--manifest', self.r / 'MANIFEST.sha256')
        self.assertEqual((j['result'], j['license'], j['declarations'], j['declared_values']), ('consistent', 'MIT', 4, ['MIT']))
        self.assertEqual(j['upstream_license_files'], ['vendor/parser/LICENSE-upstream'])
        rows = dict(reversed(l.split('  ', 1)) for l in (self.r / 'MANIFEST.sha256').read_text().splitlines())
        self.assertEqual(j['integrity'], {'listed': 8, 'matching': 8, 'subject': {'digests': {k: hashlib.sha256((self.r / k).read_bytes()).hexdigest() for k in rows}}})
        self.assertEqual(j['integrity']['subject']['digests'], rows)
        self.assertIn('not a legal opinion', j['statement']); self.assertIn('no identity is authenticated', j['statement'])
        a = self.check(0, '--exclude', 'examples/capabilities/G38/fixtures', root=ROOT)
        self.assertEqual((a['license'], a['declared_values']), ('MIT', ['MIT']))
        self.assertGreaterEqual(a['declarations'], 60)
        self.assertEqual(a['excluded'], {'examples/capabilities/G38/fixtures': ['examples/capabilities/G38/fixtures/repo-clean/LICENSE',
                                                                             'examples/capabilities/G38/fixtures/repo-clean/vendor/parser/LICENSE-upstream']})
        b = self.check(1, root=ROOT)
        self.assertEqual({f['code'] for f in b['findings']}, {'upstream_license_unlisted'})

    def test_license_drifts(self):
        orig = {p: (self.r / p).read_text() for p in ('README.md', 'pyproject.toml', PJ, 'NOTICE.md', 'LICENSE')}
        cases = [
            (PJ, '{"license": "Apache-2.0"}', [('license_mismatch', PJ)]),
            (PJ, '{"license": "MIT License"}', []),
            (PJ, '{"license": " mit "}', []),
            (PJ, '{"name": "x"}', [('license_undeclared', PJ)]),
            (PJ, '{"license": 3}', [('license_undeclared', PJ)]),
            (PJ, '[1]', [('license_undeclared', PJ)]),
            (PJ, '{bad json', [('plugin_unreadable', PJ)]),
            ('pyproject.toml', '[project]\nlicense = "GPL-3.0-only"\n', [('license_mismatch', 'pyproject.toml')]),
            ('pyproject.toml', '[project]\nlicense = "MIT"\n', []),
            ('pyproject.toml', '[project]\nname = "x"\n', [('license_undeclared', 'pyproject.toml')]),
            ('README.md', orig['README.md'].replace('license-MIT-green', 'license-GPL-red'), [('license_mismatch', 'README.md')]),
            ('README.md', orig['README.md'].replace('\nMIT. See', '\nApache-2.0. See'), [('license_mismatch', 'README.md')]),
            ('NOTICE.md', '# Notice\n', [('upstream_license_unlisted', 'vendor/parser/LICENSE-upstream')]),
            ('NOTICE.md', orig['NOTICE.md'] + '- `third/LICENSE-other`\n', [('notice_path_missing', 'NOTICE.md')]),
        ]
        for path, text, want in cases:
            for p, t in orig.items():
                (self.r / p).write_text(t)
            (self.r / path).write_text(text)
            j = self.check(1 if want else 0)
            self.assertEqual(self.codes(j), want, (path, text[:40]))
        for p, t in orig.items():
            (self.r / p).write_text(t)
        for name in ('COPYING', 'LICENCE.txt', 'license-extra'):
            (self.r / 'src' / name).write_text('x')
            self.assertEqual(self.codes(self.check(1)), [('upstream_license_unlisted', 'src/' + name)])
            (self.r / 'src' / name).unlink()
        (self.r / 'LICENSE').unlink()
        self.assertEqual(self.codes(self.check(1)), [('license_missing', 'LICENSE')])

    def test_unrecognized_or_other_license_text(self):
        (self.r / 'LICENSE').write_text('All rights reserved (synthetic).')
        j = self.check(1)
        self.assertEqual(self.codes(j), [('license_unrecognized', 'LICENSE')])
        self.assertEqual(j['license'], 'unrecognized')
        # a license header alone, or MIT with added terms, is not the license (M38 proposed fix)
        (self.r / 'LICENSE').write_text('Apache License\n  Version 2.0, January 2004\nTERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION')
        self.assertEqual(self.codes(self.check(1)), [('license_unrecognized', 'LICENSE')])
        mit0 = (EX / 'fixtures' / 'repo-clean' / 'LICENSE').read_text()
        (self.r / 'LICENSE').write_text(mit0 + '\nThe Software may not be used for commercial purposes.\n')
        self.assertEqual(self.codes(self.check(1)), [('license_unrecognized', 'LICENSE')])
        both = (EX / 'fixtures' / 'repo-clean' / 'LICENSE').read_text() + '\nApache License\nVersion 2.0, January 2004\nTerms and conditions for use, reproduction, and distribution'
        (self.r / 'LICENSE').write_text(both)
        self.assertEqual(self.codes(self.check(1)), [('license_unrecognized', 'LICENSE')])
        mit = (EX / 'fixtures' / 'repo-clean' / 'LICENSE').read_text()
        (self.r / 'LICENSE').write_text(mit.replace('"AS IS"', '\u201cAS IS\u201d').replace(' ', '  '))
        self.assertEqual(self.check(0)['license'], 'MIT')

    def test_append_after_lost_newline_keeps_both(self):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True); log = d / 'nl.jsonl'
        log.write_bytes((EX / 'fixtures' / 'events.jsonl').read_bytes().rstrip(b'\n'))
        p = run(EC, 'append', log, '--claimed-by', 'x', '--body', '{}')
        self.assertEqual(p.returncode, 0, p.stderr)
        v = run(EC, 'verify', log, '--json')
        self.assertEqual((v.returncode, json.loads(v.stdout)['verified']), (0, 7))

    def test_readme_comma_license_section_and_root_plugin(self):
        # P3-2: "GPL, see LICENSE." must be read; P3-1: plugin.json outside employees/ is checked
        (self.r / 'README.md').write_text('# X\n\n## License\n\nGPL, see LICENSE.\n')
        j = self.check(1)
        self.assertIn(('license_mismatch', 'README.md'), self.codes(j))
        cos = self.r / 'chief-of-staff'; cos.mkdir(); (cos / 'plugin.json').write_text('{"name": "chief-of-staff", "license": "Apache-2.0"}')
        j = self.check(1)
        self.assertIn(('license_mismatch', 'chief-of-staff/plugin.json'), self.codes(j))

    def test_out_missing_folder_is_invalid(self):
        # P4-1: missing --out folder -> exit 2, no traceback
        missing = self.tmp / 'no-such-dir' / 'report.json'
        r = run(PC, 'check', self.r, '--out', missing)
        self.assertEqual(r.returncode, 2); self.assertIn('Nothing was written', r.stderr); self.assertNotIn('Traceback', r.stderr)
        log = self.tmp / 'e.jsonl'
        (self.tmp / 'e.jsonl').write_bytes((EX / 'fixtures' / 'events.jsonl').read_bytes())
        r = run(EC, 'recover', log, '--out', self.tmp / 'no-such-dir' / 'out.jsonl')
        self.assertEqual(r.returncode, 2); self.assertIn('Nothing was written', r.stderr); self.assertNotIn('Traceback', r.stderr)

    def test_copyright_lines_and_apache_appendix_carry_no_terms(self):
        # M38 r2 P2-1: a "copyright" line or the Apache appendix may not carry added terms
        mit = (EX / 'fixtures' / 'repo-clean' / 'LICENSE').read_text()
        cl = [l for l in mit.splitlines() if l.lower().startswith('copyright')][0]
        for bad in (cl + ' Commercial use of the Software is prohibited.', cl + '\n(c) The Software may not be used for commercial purposes.',
                    cl + '\nCopyright holders forbid any commercial use of the Software.', 'Copyright (c) 2026 Acme no commercial use',
                    'Copyright (c) 2026 Acme. Attribution to Acme is required in every copy.'):
            (self.r / 'LICENSE').write_text(mit.replace(cl, bad))
            self.assertEqual(self.codes(self.check(1)), [('license_unrecognized', 'LICENSE')], bad)
        for ok in ('Copyright 2019-2026 Acme, Inc. All rights reserved.', '\u00a9 2020, 2021 Jane Doe', cl + '\nCopyright (c) 2026 Second Holder'):
            (self.r / 'LICENSE').write_text(mit.replace(cl, ok))
            self.assertEqual(self.check(0)['license'], 'MIT', ok)
        ap = (EX / 'fixtures' / 'apache-2.0.txt').read_text()
        ph = 'Copyright {yyyy} {name of copyright owner}'
        self.assertIn(ph, ap)
        cut = ap[:ap.index('APPENDIX:')]
        good = (ap, cut, ap.replace(ph, 'Copyright 2026 Acme Corp'),
                ap.replace('brackets "{}"', 'brackets "[]"').replace(ph, 'Copyright [yyyy] [name of copyright owner]'))
        bad = (ap.replace(ph, ph + '\n\n   NOTWITHSTANDING THE ABOVE, NO COMMERCIAL USE IS PERMITTED.'),
               ap.replace('limitations under the License.', 'limitations under the License.\n   Additional term: no commercial use.\n   limitations under the License.'),
               ap.replace(ph, 'Copyright 2026 Acme. No commercial use.'), ap.replace(ph, 'Copyright 2026 Acme, commercial use prohibited'),
               ap.replace('brackets "{}"', 'brackets "[]"'), ap.replace('governing permissions and', 'governing prohibition and'),
               ap.replace(ph, 'Copyright 2026 Acme. Attribution required in every copy.'))
        self.assertEqual(ap.count('governing permissions and'), 1)  # appendix only: a same-length edit after the copyright line
        for i, txt in enumerate(good):
            (self.r / 'LICENSE').write_text(txt)
            self.assertEqual(self.check(1)['license'], 'Apache-2.0', i)  # 1: the fixture declares MIT
        for i, txt in enumerate(bad):
            (self.r / 'LICENSE').write_text(txt)
            self.assertEqual(self.check(1)['license'], 'unrecognized', i)

    def test_restrictions_worded_without_guard_words_are_not_mit(self):
        # M38 r3 P2-1: ordinary restrictive wording in the copyright line still read as MIT, consistent
        mit = (EX / 'fixtures' / 'repo-clean' / 'LICENSE').read_text()
        cl = [l for l in mit.splitlines() if l.lower().startswith('copyright')][0]
        h = 'Copyright (c) 2026 Oracle Test Holdings'
        for bad in (h + ', noncommercial purposes', h + ', which cannot be resold', h + ', for academic research purposes exclusively',
                    h + ', personal usage', h + ', redistribution never allowed', 'Copyright 2026 Acme noncommercial',
                    'Copyright 2026 Acme for personal use', 'Copyright 2026 Acme, resale forbidden'):
            (self.r / 'LICENSE').write_text(mit.replace(cl, bad))
            self.assertEqual(self.codes(self.check(1)), [('license_unrecognized', 'LICENSE')], bad)
        for ok in ('Copyright (c) 2026 Acme, Inc.', 'Copyright 2026 Acme Corp, LLC', 'Copyright 2026 Jane Doe and contributors',
                   'Copyright 2026 Acme GmbH', 'Copyright 2026 The Solaris Authors', 'Copyright 2026 Acme Research Labs, Ltd.'):
            (self.r / 'LICENSE').write_text(mit.replace(cl, ok))
            r = self.check(0)
            self.assertEqual(r['license'], 'MIT', ok)
            self.assertEqual(r['license_copyright_lines'], [ok], ok)  # listed so a person can read what was set aside
        ap = (EX / 'fixtures' / 'apache-2.0.txt').read_text()
        ph = 'Copyright {yyyy} {name of copyright owner}'
        (self.r / 'LICENSE').write_text(ap.replace(ph, 'Copyright 2026 Acme, which cannot be resold'))
        self.assertEqual(self.check(1)['license'], 'unrecognized')

    def test_each_copyright_guard_catches_on_its_own(self):
        # each case trips exactly one guard, so weakening any one of them is seen
        mit = (EX / 'fixtures' / 'repo-clean' / 'LICENSE').read_text()
        cl = [l for l in mit.splitlines() if l.lower().startswith('copyright')][0]
        for bad in ('Copyright 2026 Acme, for students',          # comma clause that is not a company suffix
                    'Copyright 2026 Acme never transferable',      # cannot / never
                    'Copyright 2026 Acme personal usage',          # usage
                    'Copyright 2026 Acme. Attribution required'):  # a sentence inside the holder
            (self.r / 'LICENSE').write_text(mit.replace(cl, bad))
            self.assertEqual(self.check(1)['license'], 'unrecognized', bad)

    def test_out_existing_folder_is_invalid(self):
        # M38 r2 P4-1: --out naming an existing folder -> exit 2, nothing written, no traceback
        (self.tmp / 'outdir').mkdir()
        r = run(PC, 'check', self.r, '--out', self.tmp / 'outdir')
        self.assertEqual(r.returncode, 2); self.assertIn('Nothing was written', r.stderr); self.assertNotIn('Traceback', r.stderr)
        self.assertEqual(list((self.tmp / 'outdir').iterdir()), [])

    def test_pyproject_license_forms(self):
        # M38 r2 P4-2: file =, single-quoted and [project.license] table forms are declarations
        head = '[project]\nname = "x"\nversion = "0.1.0"\n'
        for body, rc, want in ((head + 'license = { file = "LICENSE" }\n', 0, []), (head + "license = 'MIT'\n", 0, []),
                               (head + '\n[project.license]\ntext = "MIT"\n', 0, []),
                               (head + '\n[project.license]\nfile = "LICENSE"\n', 0, []),
                               (head + '\n[project.license]\ntext = "Apache-2.0"\n', 1, [('license_mismatch', 'pyproject.toml')]),
                               (head + 'license = { file = "NOPE.txt" }\n', 1, [('license_undeclared', 'pyproject.toml')]),
                               (head + 'license = { file = "../OUTSIDE.txt" }\n', 1, [('license_undeclared', 'pyproject.toml')]),
                               (head + 'license = { file = "docs/APACHE.txt" }\n', 1, [('license_mismatch', 'pyproject.toml')]),
                               ('[tool.other]\nlicense = "MIT"\n' + head, 1, [('license_undeclared', 'pyproject.toml')])):
            (self.r / 'docs').mkdir(exist_ok=True)
            shutil.copy(str(self.r / 'LICENSE'), str(self.tmp / 'OUTSIDE.txt'))  # a real MIT file outside ROOT
            shutil.copy(str(EX / 'fixtures' / 'apache-2.0.txt'), str(self.r / 'docs' / 'APACHE.txt'))
            (self.r / 'pyproject.toml').write_text(body)
            self.assertEqual(self.codes(self.check(rc)), want, body)

    def test_manifest_cases(self):
        m = self.r / 'MANIFEST.sha256'; good = m.read_text()
        (self.r / 'src' / 'app.py').write_text('changed\n')
        j = self.check(1, '--manifest', m)
        self.assertEqual(self.codes(j), [('digest_mismatch', 'src/app.py')]); self.assertEqual(j['integrity']['matching'], 7)
        # mismatched digests stay out of the integrity subject (M38 P3-3)
        self.assertNotIn('src/app.py', (j['integrity']['subject'] or {}).get('digests', {}))
        self.assertEqual(len(j['integrity']['subject']['digests']), 7)
        (self.r / 'src' / 'app.py').unlink()
        self.assertEqual(self.codes(self.check(1, '--manifest', m)), [('artifact_missing', 'src/app.py')])
        out = self.tmp / 'o.py'; out.write_text('x'); os.symlink(str(out), str(self.r / 'src' / 'app.py'))
        self.assertEqual(self.codes(self.check(1, '--manifest', m)), [('artifact_refused', 'src/app.py')])
        for extra, path in (('%s  ../o.py\n', '../o.py'), ('%s  /etc/hosts\n', '/etc/hosts'), ('%s  vendor\n', 'vendor')):
            m.write_text(good + extra % ('0' * 64))
            j = self.check(1, '--manifest', m)
            self.assertIn(('artifact_refused', path), self.codes(j))
        m.write_text(good + 'not a manifest line\n')
        self.assertEqual(run(PC, 'check', self.r, '--manifest', m).returncode, 2)
        m.write_text('%s *src/app.py\n' % ('0' * 64))
        os.unlink(str(self.r / 'src' / 'app.py')); (self.r / 'src' / 'app.py').write_text('y')
        self.assertEqual(self.codes(self.check(1, '--manifest', m)), [('digest_mismatch', 'src/app.py')])
        rep = self.tmp / 'report.json'
        m.write_text(good.replace(good.split('  ')[0], hashlib.sha256((self.r / 'LICENSE').read_bytes()).hexdigest(), 1))
        r0 = run(PC, 'check', self.r, '--manifest', m, '--out', rep)
        self.assertEqual(r0.returncode, 1)
        before = rep.read_bytes(); ino = rep.stat().st_ino
        self.assertEqual(json.loads(before)['schema'], 'solaris.provenance-check/1')
        self.assertEqual(run(PC, 'check', self.r, '--manifest', m, '--out', rep).returncode, 1)
        self.assertNotEqual(rep.stat().st_ino, ino)  # replaced as a new file, never rewritten in place
        self.assertEqual(rep.read_bytes(), before)
        for bad in ('nonsense\n', '', '%s  a\n%s  a\n' % ('0' * 64, '1' * 64), '%s  a\n' % ('A' * 64)):
            m.write_text(bad)
            r = run(PC, 'check', self.r, '--manifest', m, '--out', rep)
            self.assertEqual(r.returncode, 2, bad); self.assertIn('Nothing was written', r.stderr)
            self.assertEqual(rep.read_bytes(), before)
        self.assertEqual(run(PC, 'check', self.r, '--manifest', self.tmp / 'none.txt').returncode, 2)
        self.assertEqual(run(PC, 'check', self.tmp / 'no-such-dir').returncode, 2)

    def test_exclude_rules_and_reads_only(self):
        for bad in ('../x', '/tmp', 'missing', ''):
            self.assertEqual(run(PC, 'check', self.r, '--exclude', bad).returncode, 2, bad)
        j = self.check(0, '--exclude', 'vendor')
        self.assertEqual(j['excluded'], {'vendor': ['vendor/parser/LICENSE-upstream']})
        self.assertEqual(self.codes(j), [])  # a NOTICE entry under an excluded folder must still exist on disk
        before = {p: p.read_bytes() for p in self.r.rglob('*') if p.is_file()}
        r = run(PC, 'check', self.r, '--manifest', self.r / 'MANIFEST.sha256')
        self.assertEqual(r.returncode, 0)
        self.assertIn('8 of 8 listed file(s) match', r.stdout); self.assertIn('not a legal opinion', r.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in self.r.rglob('*') if p.is_file()})
        cache = self.tmp / 'g05copy'
        shutil.copytree(str(ROOT / 'employees' / 'quality-security'), str(cache / 'employees' / 'quality-security'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        env = {name: os.environ[name] for name in (
                  'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                  'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                  'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                  'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                  'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                  'GITHUB_ACTIONS',
              ) if name in os.environ}
        r = subprocess.run([sys.executable, str(cache / 'employees/quality-security/security-auditor/provenance_check.py'), 'check', self.r,
                            '--manifest', self.r / 'MANIFEST.sha256'], capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(cache.rglob('__pycache__')), [])  # loading G05 by path leaves no bytecode cache
        (self.r / 'employees' / 'demo' / 'node_modules').mkdir()
        (self.r / 'employees' / 'demo' / 'node_modules' / 'plugin.json').write_text('{"license": "GPL"}')
        self.assertEqual(self.check(0)['declarations'], 4)



class G38EventChain(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g38-chain-'))

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def verify(self, raw, rc, *a):
        p = self.tmp / 'v.jsonl'; p.write_bytes(raw)
        r = run(EC, 'verify', p, '--json', *a)
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return json.loads(r.stdout) if rc != 2 else r

    def code(self, j):
        return [(f['code'], f.get('at')) for f in j['findings']]

    def test_fixture_and_anchor(self):
        evs = [json.loads(l) for l in (EX / 'fixtures' / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(evs, [dict(e, hash=ehash(e)) for e in evs])
        j = self.verify((EX / 'fixtures' / 'events.jsonl').read_bytes(), 0, '--anchor', '2:' + evs[2]['hash'])
        self.assertEqual((j['verified'], j['head'], j['anchor']), (6, {'seq': 5, 'hash': evs[5]['hash']}, 'matches seq 2'))
        self.assertEqual(j['claimed_by'], {'counts': {'Build bot (synthetic)': 3, 'Release desk (synthetic)': 3}, 'identity': 'claimed in plain text, not authenticated'})
        self.assertIn('no signature, wallet, transaction or legal effect', j['statement'])
        self.assertEqual(self.verify(dump(evs), 0)['anchor'], 'none (self-consistent only)')
        r = run(EC, 'verify', EX / 'fixtures' / 'events.jsonl')
        self.assertIn('claimed_by (not authenticated)', r.stdout)

    def test_tamper_kinds(self):
        evs = chain(12)
        t = json.loads(json.dumps(evs)); t[5]['body']['n'] = 50
        j = self.verify(dump(t), 1); self.assertEqual(self.code(j), [('hash_mismatch', 'line 6')]); self.assertEqual((j['verified'], j['unverified_after_break']), (5, 7))
        t = json.loads(json.dumps(evs)); t[5]['prev'] = '1' * 64; t[5]['hash'] = ehash(t[5])
        self.assertEqual(self.code(self.verify(dump(t), 1)), [('broken_link', 'line 6')])
        self.assertEqual(self.code(self.verify(dump(evs[:5] + evs[6:]), 1)), [('seq_gap', 'line 6')])
        self.assertEqual(self.code(self.verify(dump(evs[:6] + evs[5:]), 1)), [('seq_repeat', 'line 7')])
        self.assertEqual(self.code(self.verify(dump(evs)[:-3], 1)), [('torn_tail', 'line 12')])
        self.assertEqual(self.code(self.verify(dump(evs[:3]) + b'garbage\n' + dump(evs[3:]), 1)), [('line_not_json', 'line 4')])
        t = json.loads(json.dumps(evs)); t[4]['at'] = '2026-10-01T08:00:00-07:00'; t[4]['hash'] = ehash(t[4])
        for e in t[5:]:
            e['prev'] = t[e['seq'] - 1]['hash']; e['hash'] = ehash(e)
        self.assertEqual(self.code(self.verify(dump(t), 1)), [('time_regression', 'line 5')])
        for mut in (lambda e: e.update(extra=1), lambda e: e.pop('at'), lambda e: e.update(seq='3'), lambda e: e.update(claimed_by=' '),
                    lambda e: e.update(body=[1]), lambda e: e.update(seq=True)):
            t = json.loads(json.dumps(evs)); mut(t[3])
            self.assertEqual(self.code(self.verify(dump(t), 1))[0][0], 'fields_wrong' if 'at' in t[3] else 'fields_wrong')
        t = json.loads(json.dumps(evs)); t[3]['at'] = '2026-10-01T09:03:00'; t[3]['hash'] = ehash(t[3])
        self.assertEqual(self.code(self.verify(dump(t), 1)), [('time_invalid', 'line 4')])
        self.assertEqual(self.code(self.verify(b'', 1)), [('chain_empty', None)])
        self.assertEqual(self.code(self.verify(b'{"x":' + b'1' * (1 << 20) + b'}\n', 1)), [('line_too_long', 'line 1')])

    def test_anchor_rewrite_and_truncation(self):
        evs = chain(10); anc = '9:' + evs[9]['hash']
        t = json.loads(json.dumps(evs)); t[4]['body']['n'] = -4
        for e in t[4:]:
            e['prev'] = t[e['seq'] - 1]['hash'] if e['seq'] else '0' * 64; e['hash'] = ehash(e)
        self.verify(dump(t), 0)  # self-consistent: verify alone cannot see a rewrite
        self.assertEqual(self.code(self.verify(dump(t), 1, '--anchor', anc)), [('anchor_mismatch', None)])
        self.assertEqual(self.verify(dump(t), 0, '--anchor', '3:' + evs[3]['hash'])['anchor'], 'matches seq 3')
        self.assertEqual(self.code(self.verify(dump(evs[:6]), 1, '--anchor', anc)), [('anchor_not_reached', None)])
        for bad in ('9', 'x:' + evs[9]['hash'], '9:' + evs[9]['hash'].upper(), '9:abc'):
            self.verify(dump(evs), 2, '--anchor', bad)
        self.assertEqual(run(EC, 'verify', self.tmp / 'missing.jsonl').returncode, 2)

    def test_recover(self):
        evs = chain(15); t = json.loads(json.dumps(evs)); t[9]['body']['n'] = 0
        log = self.tmp / 'log.jsonl'; raw = dump(t) + b'{"seq":15,'; log.write_bytes(raw); out = self.tmp / 'new.jsonl'
        r = run(EC, 'recover', log, '--out', out, '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['recovered'], {'kept': 9, 'dropped': 7, 'out': 'new.jsonl'})
        self.assertEqual(out.read_bytes(), dump(evs[:9])); self.assertEqual(log.read_bytes(), raw)
        r = run(EC, 'recover', log, '--out', log)
        self.assertEqual(r.returncode, 2); self.assertIn('never rewrites the log in place', r.stderr)
        self.assertEqual(run(EC, 'recover', log, '--out', out).returncode, 2)
        self.assertEqual(out.read_bytes(), dump(evs[:9])); self.assertEqual(log.read_bytes(), raw)
        r = run(EC, 'recover', log, '--out', self.tmp / 'text.jsonl')
        self.assertIn('the original log is unchanged', r.stdout)
        bad = self.tmp / 'bad.jsonl'; bad.write_bytes(b'nope\n')
        self.assertEqual(run(EC, 'recover', bad, '--out', self.tmp / 'b2.jsonl').returncode, 1); self.assertFalse((self.tmp / 'b2.jsonl').exists())
        t2 = json.loads(json.dumps(evs)); t2[2]['body']['n'] = 7
        for e in t2[2:]:
            e['prev'] = t2[e['seq'] - 1]['hash']; e['hash'] = ehash(e)
        rw = self.tmp / 'rw.jsonl'; rw.write_bytes(dump(t2))
        self.assertEqual(run(EC, 'recover', rw, '--out', self.tmp / 'rw2.jsonl', '--anchor', '5:' + evs[5]['hash']).returncode, 1)
        self.assertFalse((self.tmp / 'rw2.jsonl').exists())
        self.assertEqual(run(EC, 'recover', rw, '--out', self.tmp / 'rw3.jsonl', '--anchor', '1:' + evs[1]['hash']).returncode, 0)
        self.assertEqual(len((self.tmp / 'rw3.jsonl').read_text().splitlines()), 15)
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith('.')], [])

    def test_append_rules(self):
        log = self.tmp / 'a.jsonl'
        for a in (('--body', '[1]'), ('--body', 'nope'), ('--body', '{}', '--claimed-by', ' '), ('--body', '{}', '--at', '2026-10-01T09:00:00')):
            args = ['append', log] + list(a) + ([] if '--claimed-by' in a else ['--claimed-by', 'x'])
            r = run(EC, *args); self.assertEqual(r.returncode, 2, a); self.assertFalse(log.exists(), a)
        self.assertEqual(run(EC, 'append', log, '--claimed-by', ' Ops (synthetic) ', '--body', '{"k":1}', '--at', '2026-10-01T10:00:00-07:00').returncode, 0)
        self.assertEqual(run(EC, 'append', log, '--claimed-by', 'Ops (synthetic)', '--body', '{"k":2}', '--at', '2026-10-01T09:00:00-07:00').returncode, 0)
        self.assertEqual(run(EC, 'append', log, '--claimed-by', 'Ops (synthetic)', '--body', '{"k":3}').returncode, 0)
        evs = [json.loads(l) for l in log.read_text().splitlines()]
        self.assertEqual([e['seq'] for e in evs], [0, 1, 2]); self.assertEqual(evs[0]['prev'], '0' * 64)
        self.assertEqual(evs[1]['at'], evs[0]['at'])  # an earlier clock never goes backwards in the log
        self.assertEqual(evs[0]['claimed_by'], 'Ops (synthetic)')
        self.assertTrue(all(e['hash'] == ehash(e) and (i == 0 or e['prev'] == evs[i - 1]['hash']) for i, e in enumerate(evs)))
        raw = log.read_bytes(); log.write_bytes(raw.replace(b'"k":2', b'"k":9'))
        before = log.read_bytes()
        r = run(EC, 'append', log, '--claimed-by', 'x', '--body', '{}'); self.assertEqual(r.returncode, 2); self.assertIn('recover it', r.stderr)
        self.assertEqual(log.read_bytes(), before)

    def test_lock_and_concurrency(self):
        log = self.tmp / 'c.jsonl'; log.write_bytes(b'')
        fd = os.open(str(log), os.O_RDWR); fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            r = run(EC, 'append', log, '--claimed-by', 'x', '--body', '{}', timeout=60)
            self.assertEqual(r.returncode, 4); self.assertEqual(log.read_bytes(), b'')
        finally:
            os.close(fd)
        code = ("import subprocess,sys\nfor i in range(15):\n    r=subprocess.run([sys.executable,%r,'append',%r,'--claimed-by','w%%s'%%sys.argv[1],'--body','{\"i\":%%d}'%%i])\n"
                "    sys.exit(r.returncode) if r.returncode else None\n") % (str(EC), str(log))
        ps = [subprocess.Popen([sys.executable, '-c', code, str(w)], env=ENV, stdout=subprocess.DEVNULL) for w in range(6)]
        self.assertEqual([p.wait(timeout=600) for p in ps], [0] * 6)
        j = self.verify(log.read_bytes(), 0)
        self.assertEqual(j['verified'], 90); self.assertEqual(sorted(j['claimed_by']['counts'].values()), [15] * 6)


class G38Wiring(unittest.TestCase):
    def test_concurrency_oracle_rejects_invalid_chain_when_writers_serialize(self):
        import types
        from unittest import mock
        sys.path.insert(0, str(ROOT))
        try:
            from examples.capabilities.G38 import authority_oracle as oracle
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory(prefix='g38-serialized-control-') as tmp:
            root = Path(tmp)
            log = root / 'log.jsonl'
            worker = [0]
            class SerializedNaiveWriter:
                def __init__(self, *_args, **_kwargs):
                    number = worker[0]
                    worker[0] += 1
                    with log.open('a') as out:
                        for i in range(25):
                            out.write(json.dumps({'seq': number * 25 + i, 'prev': '', 'hash': '',
                                                  'at': '', 'claimed_by': 'worker %d (synthetic)' % number,
                                                  'body': {'i': i}}) + '\n')
                def wait(self, timeout):
                    return 0
            candidate = types.SimpleNamespace(
                dir=lambda: root, ec=EX / 'naive/event_chain.py',
                verify=lambda _path: (0, {'verified': 200, 'claimed_by': {
                    'counts': {'worker %d (synthetic)' % w: 25 for w in range(8)}}}, ''))
            # Serialized scheduling is legitimate. Counts from a selected verifier
            # cannot establish that the bytes form a valid hash chain.
            with mock.patch.object(oracle, 'subprocess', types.SimpleNamespace(
                    Popen=SerializedNaiveWriter, DEVNULL=subprocess.DEVNULL)):
                self.assertFalse(oracle.e4(candidate)[0])

    def test_oracle_and_controls(self):
        o = lambda *a: subprocess.run([sys.executable, str(EX / 'authority_oracle.py')] + list(a), capture_output=True, text=True, env=ENV, timeout=900)
        r = o(); self.assertEqual(r.stdout.strip().splitlines()[-1], 'ACCEPTED 8/8', r.stdout)
        for t in ('naive', 'noop'):
            self.assertEqual(o('--tools', str(EX / t)).stdout.strip().splitlines()[-1], 'REJECTED 1/8')

    def test_roles_declare_and_bound_the_tools(self):
        for role, script, ref in (('quality-security/security-auditor', 'provenance_check.py', 'provenance-integrity.md'),
                                  ('engineering/blockchain-developer', 'event_chain.py', 'immutable-event-validation.md')):
            c = json.loads((ROOT / 'employees' / role / 'capability.contract.json').read_text())
            self.assertIn(script, c['dependencies']['scripts']); self.assertIn(ref, c['dependencies']['references'])
            self.assertIn(ref, json.loads((ROOT / 'employees' / role / 'plugin.json').read_text())['references'])
            self.assertIn(script, (ROOT / 'employees' / role / 'SKILL.md').read_text())
            self.assertTrue((ROOT / 'employees' / role / ref).is_file())
        sk = (ROOT / 'employees/quality-security/security-auditor/SKILL.md').read_text()
        self.assertIn('UNAVAILABLE, never as verified', sk); self.assertIn('no cosign binary, no signature claim', sk)
        la = (ROOT / 'employees/legal-compliance/legal-advisor/SKILL.md').read_text()
        self.assertIn('provenance_check.py', la); self.assertIn('not proof of who authored or approved', la)
        doc = (ROOT / 'employees/engineering/blockchain-developer/immutable-event-validation.md').read_text()
        self.assertIn('self-consistent', doc); self.assertIn('not authenticated', doc)
        self.assertIn('not a legal opinion', (ROOT / 'employees/quality-security/security-auditor/provenance-integrity.md').read_text())


if __name__ == '__main__':
    unittest.main()
