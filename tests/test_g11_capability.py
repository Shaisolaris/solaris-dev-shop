"""G11: incident timeline, SLO / error budget and rollback decision
(employees/infrastructure/site-reliability-engineer/incident_slo.py).

Real files and subprocesses; bundles are synthetic. Expected values are computed here with
decimal arithmetic from the fixture records, not read back from the tool.
"""
import copy
import decimal
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRE = ROOT / 'employees' / 'infrastructure' / 'site-reliability-engineer'
TOOL = SRE / 'incident_slo.py'
EX = ROOT / 'examples' / 'capabilities' / 'G11'
FIX = EX / 'fixtures'
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')


def cli(*args, env=ENV):
    return subprocess.run([sys.executable, str(TOOL)] + [str(a) for a in args], capture_output=True, text=True, env=env, timeout=300)


def report(path):
    p = cli('report', path, '--json')
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def expected(bundle):
    """Independent SLO arithmetic: per minute the sum over distinct sources, a source's exact repeats once,
    a source with two different counts makes the minute conflicting; conflicts, gaps and minutes missing an
    expected source out."""
    seen = {}
    for r in bundle['telemetry']:
        seen.setdefault(r['minute'], {}).setdefault(r.get('source'), set()).add((r['good'], r['total']))
    every = {k for srcs in seen.values() for k in srcs}  # expected: every source seen (no declared list here)
    keep = [(sum(next(iter(v))[0] for v in srcs.values()), sum(next(iter(v))[1] for v in srcs.values()))
            for srcs in seen.values() if all(len(v) == 1 for v in srcs.values()) and set(srcs) == every]
    good, total = sum(g for g, _ in keep), sum(t for _, t in keep)
    o = decimal.Decimal(str(bundle['slo']['objective']))
    q = decimal.Decimal('0.000001')
    ctx = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_EVEN)
    bad = total - good
    allowed = (1 - o) * total
    return {'good': good, 'total': total, 'bad': bad,
            'availability': str(ctx.divide(decimal.Decimal(good), total).quantize(q, context=ctx)),
            'budget_remaining': str(ctx.divide(allowed - bad, allowed).quantize(q, context=ctx)),
            'burn_rate': str(ctx.divide(decimal.Decimal(bad), total * (1 - o)).quantize(q, context=ctx))}


class G11Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g11-test-'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_oracle_accepts_the_tool_and_rejects_controls(self):
        for target, want in ((TOOL, 'ACCEPTED: 14/14'), (EX / 'naive_stub.py', 'REJECTED'), (EX / 'noop_stub.py', 'REJECTED')):
            p = subprocess.run([sys.executable, str(EX / 'incident_oracle.py'), '--', sys.executable, str(target)],
                               capture_output=True, text=True, env=ENV, timeout=600)
            self.assertIn(want, p.stdout.strip().splitlines()[-1], (target.name, p.stdout[-1500:], p.stderr[-800:]))

    def test_fixture_decisions_name_service_window_and_revision(self):
        want = {'01-clean-control.json': ('met', 'do_not_rollback'), '02-deploy-regression.json': ('breached', 'rollback'),
                '03-dns-fault-during-impact.json': ('breached', 'do_not_rollback'),
                '04-impact-before-change.json': ('breached', 'do_not_rollback'),
                '05-gap-after-change.json': ('insufficient_telemetry', 'insufficient_evidence'),
                '06-migration-without-snapshot.json': ('breached', 'rollback_blocked'),
                '07-conflicting-minutes.json': ('breached', 'rollback')}
        self.assertEqual(sorted(p.name for p in FIX.glob('*.json')), sorted(want))
        for name, (status, decision) in want.items():
            r = report(FIX / name)
            self.assertEqual((r['slo']['status'], r['decision']['decision']), (status, decision), name)
            reason = r['decision']['reason']
            for part in ('checkout-api', '2026-10-18T09:00:00Z/2026-10-18T10:00:00Z', 'r42'):
                self.assertIn(part, reason, name)

    def test_exact_slo_values_and_timeline(self):
        for name in ('01-clean-control.json', '02-deploy-regression.json', '05-gap-after-change.json', '07-conflicting-minutes.json'):
            b = json.loads((FIX / name).read_text())
            r = report(FIX / name)
            self.assertEqual({k: r['slo'][k] for k in expected(b)}, expected(b), name)
        r = report(FIX / '02-deploy-regression.json')
        self.assertEqual((r['impact']['start'], r['impact']['end']), ('2026-10-18T09:22:00Z', '2026-10-18T09:40:00Z'))
        self.assertEqual(r['response'], {'time_to_detect_s': 135, 'time_to_mitigate_s': 1120, 'time_to_resolve_s': 1800})
        kinds = [t['kind'] for t in r['timeline']]
        self.assertEqual(kinds, ['change', 'impact_start', 'detected', 'declared', 'impact_end', 'mitigated', 'resolved'])
        self.assertTrue([t for t in r['timeline'] if t['kind'] == 'declared'][0]['late'])
        self.assertEqual(r['import']['event_duplicates'], 1)

    def test_missing_and_conflicting_telemetry_labelled(self):
        r = report(FIX / '05-gap-after-change.json')
        self.assertEqual(r['missing_telemetry']['ranges'], [{'start': '2026-10-18T09:25:00Z', 'end': '2026-10-18T09:35:00Z', 'minutes': 10}])
        self.assertEqual(r['slo']['coverage'], '0.833333')
        self.assertTrue(any('missing for 10 minute' in x for x in r['labels']))
        self.assertIn('telemetry_missing', [t['kind'] for t in r['timeline']])
        r = report(FIX / '07-conflicting-minutes.json')
        self.assertEqual(r['missing_telemetry']['conflicting_ranges'], [{'start': '2026-10-18T09:50:00Z', 'end': '2026-10-18T09:52:00Z', 'minutes': 2}])

    def test_per_source_counts_summed_hand_worked(self):
        b = json.loads((FIX / '01-clean-control.json').read_text())
        start = b['window']['start']
        # two load balancers in every minute: lb-a carries the fixture's traffic, lb-b reports zero, except
        # in the first minute where both carry traffic
        others = sorted({r['minute'] for r in b['telemetry']} - {start})
        tel = [dict(r, source='lb-a') for r in b['telemetry'] if r['minute'] != start]
        tel += [{'minute': mm, 'good': 0, 'total': 0, 'source': 'lb-b'} for mm in others]
        tel += [{'minute': start, 'good': 300, 'total': 400, 'source': 'lb-a'},   # differing shares: summed
                {'minute': start, 'good': 600, 'total': 600, 'source': 'lb-b'},
                {'minute': start, 'good': 300, 'total': 400, 'source': 'lb-a'}]   # exact repeat: once
        d = Path(tempfile.mkdtemp(prefix='g11-src-'))
        try:
            p = d / 'b.json'
            p.write_text(json.dumps(dict(b, telemetry=tel)))
            r = report(p)
            self.assertEqual({k: r['slo'][k] for k in ('good', 'total', 'bad')}, {k: expected(dict(b, telemetry=tel))[k] for k in ('good', 'total', 'bad')})
            self.assertEqual(r['missing_telemetry']['conflicting_minutes'], 0)
            self.assertEqual(r['import']['telemetry_minutes_multi_source'], len(others) + 1)
            self.assertEqual(r['missing_telemetry']['partial_minutes'], 0)
            base = report(FIX / '01-clean-control.json')['slo']
            first = [x for x in b['telemetry'] if x['minute'] == start][0]
            self.assertEqual(r['slo']['total'], base['total'] - first['total'] + 1000)
            self.assertEqual(r['slo']['bad'], base['bad'] - (first['total'] - first['good']) + 100)
            # without a source, two different counts are one source reporting twice: a conflict
            tel2 = [r_ for r_ in b['telemetry'] if r_['minute'] != start] + \
                [{'minute': start, 'good': 990, 'total': 1000}, {'minute': start, 'good': 1000, 'total': 1000}]
            p.write_text(json.dumps(dict(b, telemetry=tel2)))
            self.assertEqual(report(p)['missing_telemetry']['conflicting_minutes'], 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_silent_source_hand_worked(self):
        # M11 r2: lb-b stops reporting for 30 of 60 minutes; r2 kept coverage 1.0 and halved traffic
        b = json.loads((FIX / '01-clean-control.json').read_text())
        mins = sorted({r['minute'] for r in b['telemetry']})
        tel = [dict(r, source='lb-a', good=0) if r['minute'] == mins[20] else dict(r, source='lb-a') for r in b['telemetry']]
        tel += [{'minute': mm, 'good': 1000, 'total': 1000, 'source': 'lb-b'} for k, mm in enumerate(mins) if not 10 <= k < 40]
        tel = [r for r in tel if r['minute'] != mins[50]]  # one minute with no record at all
        d = Path(tempfile.mkdtemp(prefix='g11-silent-'))
        try:
            p = d / 'b.json'
            p.write_text(json.dumps(dict(b, telemetry=tel)))
            r = report(p)
            self.assertEqual(r['slo']['status'], 'insufficient_telemetry')
            self.assertEqual((r['slo']['measured_minutes'], r['missing_telemetry']['partial_minutes'], r['missing_telemetry']['minutes']), (29, 30, 1))
            # lb-a's all-error minute 20 is partial: left out, not an impact minute (lb-b's share is unknown)
            self.assertEqual((r['impact']['minutes'], r['impact']['start']), (0, None))
            self.assertEqual(r['missing_telemetry']['partial_ranges'], [{'start': mins[10], 'end': mins[40], 'minutes': 30}])
            ps = {x['source']: x for x in r['sources']['per_source']}
            self.assertEqual((ps['lb-a']['reported_minutes'], ps['lb-b']['reported_minutes'], ps['lb-b']['silent_while_others_report']), (59, 29, 30))
            self.assertEqual(ps['lb-b']['coverage'], '0.483333')
            self.assertEqual({k: r['slo'][k] for k in ('good', 'total')}, {k: expected(dict(b, telemetry=tel))[k] for k in ('good', 'total')})
            self.assertTrue(any(x.startswith('source lb-b silent for 30 of 60') for x in r['labels']))
            self.assertIn('source_silent', [x['kind'] for x in r['timeline']])
            self.assertEqual(r['decision']['decision'], 'insufficient_evidence')  # no impact seen, lb-b silent after r42
            # declared sources: names trimmed and case-folded; a declared source that never reports is a gap
            b2 = dict(b, telemetry=[dict(r_, source=' LB-A') for r_ in b['telemetry']], telemetry_sources=['lb-a'])
            p.write_text(json.dumps(b2))
            r2 = report(p)
            self.assertEqual((r2['slo']['status'], r2['sources']['basis'], r2['sources']['expected']), ('met', 'declared', ['lb-a']))
            p.write_text(json.dumps(dict(b2, telemetry_sources=['lb-a', 'lb-c'])))
            r3 = report(p)
            self.assertEqual((r3['slo']['status'], r3['slo']['measured_minutes']), ('insufficient_telemetry', 0))
            for bad in (dict(b, telemetry=tel + [dict(tel[0], source='LB-A ')]),            # two spellings of one name
                        dict(b, telemetry=tel, telemetry_sources=['lb-a']),                 # lb-b not declared
                        dict(b, telemetry=tel, telemetry_sources=['lb-a', 'lb-b', 'LB-A']),  # declared twice
                        dict(b, telemetry=[{k: v for k, v in r_.items() if k != 'source'} for r_ in tel], telemetry_sources=['lb-a'])):
                p.write_text(json.dumps(bad))
                self.assertEqual(cli('report', p).returncode, 2)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_repeated_import_is_stable(self):
        b = json.loads((FIX / '02-deploy-regression.json').read_text())
        b2 = copy.deepcopy(b)
        b2['telemetry'] = list(reversed(b2['telemetry'])) * 3
        b2['events'] = b2['events'] * 2
        (self.tmp / 'again.json').write_text(json.dumps(b2))
        r1, r2 = report(FIX / '02-deploy-regression.json'), report(self.tmp / 'again.json')
        for k in ('slo', 'timeline', 'decision', 'impact', 'missing_telemetry', 'response'):
            self.assertEqual(r1[k], r2[k], k)
        self.assertEqual(cli('report', FIX / '02-deploy-regression.json', '--json').stdout,
                         cli('report', FIX / '02-deploy-regression.json', '--json').stdout)

    def test_invalid_input_refused_and_previous_report_kept(self):
        out = self.tmp / 'report.json'
        self.assertEqual(cli('report', FIX / '02-deploy-regression.json', '--out', out).returncode, 0)
        before = out.read_bytes()
        b = json.loads((FIX / '02-deploy-regression.json').read_text())
        b['events'].append(dict(b['events'][0], detail='another story'))
        (self.tmp / 'bad.json').write_text(json.dumps(b))
        p = cli('report', self.tmp / 'bad.json', '--out', out)
        self.assertEqual(p.returncode, 2)
        self.assertIn('different content', p.stderr)
        self.assertEqual(out.read_bytes(), before)
        self.assertEqual(sorted(x.name for x in self.tmp.iterdir()), ['bad.json', 'report.json'])

    def test_g10_trace_outside_bundle_refused(self):
        b = json.loads((FIX / '03-dns-fault-during-impact.json').read_text())
        b['diagnoses'] = ['../G10/fixtures/02-dns-nxdomain.json']
        (self.tmp / 'b.json').write_text(json.dumps(b))
        self.assertEqual(cli('report', self.tmp / 'b.json').returncode, 2)

    def test_unusable_g10_trace_never_dropped_before_a_rollback(self):
        """G18 x2 (M18): a supplied G10 trace that G10 refuses, or that has no capture time, must show in the
        decision trace and must not let a rollback through when it could place the fault outside the change."""
        b = json.loads((FIX / '02-deploy-regression.json').read_text())
        dns = json.loads((ROOT / 'examples/capabilities/G10/fixtures/02-dns-nxdomain.json').read_text())
        app = json.loads((ROOT / 'examples/capabilities/G10/fixtures/09-app-upstream-503.json').read_text())
        (self.tmp / 'traces').mkdir()
        traces = {'refused.json': dict(dns, captured_at='18/10/2026 09:30'), 'dns-untimed.json': dict(dns, captured_at=None),
                  'app-untimed.json': dict(app, captured_at=None), 'dns-before.json': dict(dns, captured_at='2026-10-18T09:05:00Z'),
                  'dns-during.json': dict(dns, captured_at='2026-10-18T09:30:00Z')}
        for name, t in traces.items():
            (self.tmp / 'traces' / name).write_text(json.dumps(t))

        def decide(*names):
            (self.tmp / 'b.json').write_text(json.dumps(dict(b, diagnoses=['traces/' + n for n in names])))
            d = report(self.tmp / 'b.json')['decision']
            return d['decision'], d['reason'], [t for t in d['trace'] if t['check'].startswith('G10')]

        self.assertEqual(decide()[0], 'rollback')  # the fixture without evidence still rolls back
        for name in ('refused.json', 'dns-untimed.json'):
            dec, reason, rows = decide(name)
            self.assertEqual(dec, 'insufficient_evidence', name)
            self.assertIn('traces/' + name, reason)
            self.assertIn('r42', reason)
            self.assertEqual([(r['result'], r['observed'].startswith('traces/' + name)) for r in rows], [('unusable', True)])
        dec, _, rows = decide('app-untimed.json')
        self.assertEqual(dec, 'rollback')  # untimed, but it does not exclude the application anyway
        self.assertEqual([r['result'] for r in rows], ['does not exclude the application'])
        self.assertIn('no capture time', rows[0]['observed'])
        dec, _, rows = decide('dns-before.json')
        self.assertEqual((dec, [r['result'] for r in rows]), ('rollback', ['outside the impact, not used']))
        dec, reason, rows = decide('dns-during.json', 'refused.json')  # a usable dns trace in the impact still decides
        self.assertEqual(dec, 'do_not_rollback')
        self.assertIn('dns layer', reason)

    def test_loading_g03_and_g10_leaves_no_bytecode_behind(self):
        """A caller without PYTHONDONTWRITEBYTECODE must not leave __pycache__ in sibling roles."""
        copy_root = self.tmp / 'repo'
        for rel in ('employees/infrastructure/site-reliability-engineer', 'employees/infrastructure/network-engineer',
                    'employees/infrastructure/database-administrator', 'examples/capabilities/G11', 'examples/capabilities/G10'):
            shutil.copytree(ROOT / rel, copy_root / rel, ignore=shutil.ignore_patterns('__pycache__'))
        env = {name: os.environ[name] for name in (
                  'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                  'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                  'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                  'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                  'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                  'GITHUB_ACTIONS',
              ) if name in os.environ}
        sys.path.insert(0, str(EX))
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            import incident_oracle as orc  # noqa: E402
        finally:
            sys.path.pop(0)
            sys.dont_write_bytecode = old
        d = copy_root / 'examples/capabilities/G11/fixtures'
        sid = orc.make_snapshot(d)
        b = json.loads((d / '06-migration-without-snapshot.json').read_text())
        b['change']['data'] = {'snapshot': 'snap', 'databases': ['app.db']}
        (d / 'mig.json').write_text(json.dumps(b))
        p = subprocess.run([sys.executable, str(copy_root / 'employees/infrastructure/site-reliability-engineer/incident_slo.py'),
                            'report', str(d / 'mig.json'), '--json'], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = json.loads(p.stdout)
        self.assertEqual(r['decision']['decision'], 'rollback')
        self.assertIn(sid, r['decision']['reason'])
        p = subprocess.run([sys.executable, str(copy_root / 'employees/infrastructure/site-reliability-engineer/incident_slo.py'),
                            'report', str(d / '03-dns-fault-during-impact.json')], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        left = sorted(str(x.relative_to(copy_root)) for x in copy_root.rglob('__pycache__'))
        self.assertEqual(left, [])

    def test_contract_declares_script_and_reference(self):
        c = json.loads((SRE / 'capability.contract.json').read_text())
        self.assertIn('incident_slo.py', c['dependencies']['scripts'])
        self.assertIn('incident-slo.md', c['dependencies']['references'])
        self.assertTrue((SRE / 'incident-slo.md').is_file())
        self.assertIn('incident-slo.md', json.loads((SRE / 'plugin.json').read_text())['references'])
        for role in ('product-project/delivery-lead', 'leadership/coo'):
            self.assertIn('incident_slo.py', (ROOT / 'employees' / role / 'SKILL.md').read_text(), role)


if __name__ == '__main__':
    unittest.main()
