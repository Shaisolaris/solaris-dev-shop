"""G15: experiment and retention readout with fixed cohorts, leakage checks and uncertainty
(employees/data/data-scientist/experiment_readout.py). Real files and subprocesses; data is synthetic.
Expected counts come from the fixture generator's ground truth (examples/capabilities/G15/README.md)."""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / 'employees' / 'data' / 'data-scientist'
TOOL = DS / 'experiment_readout.py'
EX = ROOT / 'examples' / 'capabilities' / 'G15'
FIX = EX / 'fixtures'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def cli(*args, env=ENV):
    return subprocess.run([sys.executable, str(TOOL)] + [str(a) for a in args], capture_output=True, text=True, env=env, timeout=300)


def rep(path, want_rc=0):
    p = cli('analyse', path, '--json')
    assert p.returncode == want_rc, (p.returncode, p.stderr)
    return json.loads(p.stdout)


def oracle_module():
    sys.path.insert(0, str(EX))
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import readout_oracle
        return readout_oracle
    finally:
        sys.path.pop(0)
        sys.dont_write_bytecode = old


class G15Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g15-test-'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_oracle_accepts_tool_and_rejects_controls(self):
        for target, want in ((TOOL, 'ACCEPTED: 18/18'), (EX / 'naive_stub.py', 'REJECTED'), (EX / 'noop_stub.py', 'REJECTED')):
            p = subprocess.run([sys.executable, str(EX / 'readout_oracle.py')] + (['--quick'] if target != TOOL else []) + ['--', sys.executable, str(target)],
                               capture_output=True, text=True, env=ENV, timeout=600)
            self.assertIn(want, p.stdout.strip().splitlines()[-1], (target.name, p.stdout[-1500:], p.stderr[-800:]))

    def test_clean_aa_control(self):
        r = rep(FIX / 'clean-aa' / 'package.json')
        self.assertEqual({a: (v['units'], v['converted']) for a, v in r['arms'].items()}, {'control': (400, 100), 'treatment': (400, 100)})
        self.assertEqual(r['outcome'], 'no_detectable_difference')
        self.assertEqual(r['claims_allowed'], {'causal': False, 'significance': False})
        self.assertEqual(r['effect']['difference'], '0.000000')
        self.assertLess(float(r['effect']['ci_low']), 0)
        self.assertGreater(float(r['effect']['ci_high']), 0)

    def test_retention_lift_counts_units_once_and_names_leaks(self):
        r = rep(FIX / 'retention-lift' / 'package.json')
        self.assertEqual({a: (v['units'], v['converted']) for a, v in r['arms'].items()}, {'control': (600, 123), 'treatment': (600, 231)})
        ex = r['exclusions']
        self.assertEqual((ex['outside_cohort'], len(ex['multiple_arms']), ex['events_unassigned_units'], ex['immature']), (20, 6, 6, 0))
        self.assertGreater(ex['events_before_assignment'], 0)
        self.assertEqual(r['outcome'], 'difference_detected')
        self.assertTrue(r['claims_allowed']['causal'])
        self.assertLess(float(r['effect']['ci_low']), 0.18)
        self.assertGreater(float(r['effect']['ci_high']), 0.18)

    def test_sample_ratio_mismatch_blocks_any_effect_claim(self):
        r = rep(FIX / 'sample-ratio-mismatch' / 'package.json')
        self.assertTrue(r['srm']['mismatch'])
        self.assertEqual(r['outcome'], 'invalid_experiment')
        self.assertEqual(r['claims_allowed'], {'causal': False, 'significance': False})

    def test_allocation_drift_simpson_cases_invalid(self):
        o = oracle_module()
        c, t = 'control', 'treatment'
        # the Grok self-validation M15 X13 and X13b cases: variant 5 points better in both periods
        for plan, pooled_sign in (([(c, 100, 0.50, 0, 7), (t, 400, 0.55, 0, 7), (c, 400, 0.10, 7, 24), (t, 100, 0.15, 7, 24)], 1),
                                  ([(c, 400, 0.50, 0, 7), (t, 100, 0.55, 0, 7), (c, 100, 0.10, 7, 24), (t, 400, 0.15, 7, 24)], -1)):
            pkg, A, E = o.periods(random.Random(14), plan)
            r = rep(o.write(self.tmp / ('s%d' % pooled_sign), pkg, A, E))
            self.assertFalse(r['srm']['mismatch'])
            self.assertEqual(pooled_sign, 1 if float(r['effect']['difference']) > 0 else -1)
            self.assertEqual(r['outcome'], 'invalid_experiment')
            self.assertEqual(r['claims_allowed'], {'causal': False, 'significance': False})
            self.assertTrue(r['allocation_by_week']['mismatch'])
            self.assertEqual(r['allocation_by_week']['worst_week'], 0)
            self.assertIn('allocation drifted', r['trace'][0])
        for f in ('clean-aa', 'retention-lift', 'sample-ratio-mismatch'):
            self.assertFalse(rep(FIX / f / 'package.json')['allocation_by_week']['mismatch'], f)

    def test_one_day_burst_invalid_at_any_alignment(self):
        # M15 r2 O08: one day sends every unit to the variant inside healthy weeks; true effect zero
        o = oracle_module()
        weekly_missed = 0
        for k, h in enumerate((9 * 24, 9 * 24 + 13, 6 * 24 + 12)):
            pkg, A, E = o.bursty(random.Random(40 + k), 40, h)
            r = rep(o.write(self.tmp / ('b%d' % k), pkg, A, E))
            self.assertEqual(r['outcome'], 'invalid_experiment')
            self.assertEqual(r['claims_allowed'], {'causal': False, 'significance': False})
            self.assertTrue(r['allocation_scan']['mismatch'])
            self.assertEqual(r['allocation_scan']['worst']['units'], 40)
            weekly_missed += not r['allocation_by_week']['mismatch']
            self.assertTrue(any('allocation changed within the cohort' in x or 'allocation drifted' in x for x in r['trace']))
        self.assertGreaterEqual(weekly_missed, 1)  # the 7-day block test alone misses at least one of them

    def test_scan_independent_of_cohort_start(self):
        o = oracle_module()
        pkg, A, E = o.bursty(random.Random(3), 40, 6 * 24 + 12)
        seen = set()
        for sh in (0, 30, 150):
            pk = json.loads(json.dumps(pkg))
            pk['cohort']['start'] = o.iso(o.CS - o.dt.timedelta(hours=sh))
            r = rep(o.write(self.tmp / ('a%d' % sh), pk, A, E))
            self.assertEqual(r['outcome'], 'invalid_experiment')
            seen.add(json.dumps(r['allocation_scan'], sort_keys=True))
        self.assertEqual(len(seen), 1)

    def test_scan_exact_binomial_and_quiet_on_fixtures(self):
        sys.path.insert(0, str(DS))
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            import experiment_readout as er
        finally:
            sys.path.pop(0)
            sys.dont_write_bytecode = old
        self.assertEqual([round(x, 6) for x in er.binom_two_sided(4, 0.5)], [0.125, 0.625, 1.0, 0.625, 0.125])
        self.assertAlmostEqual(er.binom_two_sided(20, 0.5)[0], 2 * 0.5 ** 20, places=15)
        self.assertAlmostEqual(er.binom_two_sided(3, 0.7)[3], 0.343 + 0.189 + 0.027, places=12)  # P(3) and the less likely P(1), P(0)
        # hand-built runs: 20 consecutive treatment units at the start of 40, and at the very end of 45
        # (only the extra window ending at the last unit covers it whole); exact p = 2 * 0.5 ** 20
        t0 = er.dt.datetime(2026, 8, 1, tzinfo=er.dt.timezone.utc)
        for n, run_at in ((40, range(0, 20)), (45, range(25, 45))):
            units = {'u%02d' % i: {'arm': 'treatment' if (i in run_at or i % 2) else 'control',
                                   'at': t0 + er.dt.timedelta(hours=i)} for i in range(n)}
            sc = er.allocation_scan(units, ['control', 'treatment'], [0.5, 0.5])
            self.assertEqual(sc['window_units'], [20])
            self.assertEqual((sc['worst']['units'], sc['worst']['arm_counts'], sc['worst']['p_value']), (20, [0, 20], '1.907e-06'))
            self.assertEqual(sc['worst']['last_assigned'], (t0 + er.dt.timedelta(hours=run_at[-1])).isoformat())
        for f in ('clean-aa', 'retention-lift'):
            sc = rep(FIX / f / 'package.json')['allocation_scan']
            self.assertFalse(sc['mismatch'], f)
            self.assertEqual(sc['family_alpha'], 0.002)

    def test_chi2_tail(self):
        sys.path.insert(0, str(DS))
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            import experiment_readout as er
        finally:
            sys.path.pop(0)
            sys.dont_write_bytecode = old
        for x, df, want in ((3.841458820694124, 1, 0.05), (5.991464547107979, 2, 0.05), (16.26623619623813, 3, 0.001),
                            (11.070497693516351, 5, 0.05), (0.0, 3, 1.0)):
            self.assertAlmostEqual(er.chi2_sf(x, df), want, places=9)

    def test_observational_never_causal(self):
        d = self.tmp / 'obs'
        shutil.copytree(FIX / 'retention-lift', d)
        p = json.loads((d / 'package.json').read_text())
        p['assignment'] = 'observational'
        del p['randomization']  # a randomization rule is refused on observational data
        (d / 'package.json').write_text(json.dumps(p))
        r = rep(d / 'package.json')
        self.assertEqual(r['outcome'], 'association_only')
        self.assertEqual(r['claims_allowed'], {'causal': False, 'significance': True})

    def test_interleaved_burst_without_contract_never_causal(self):
        # root G15: zero true effect, a 40-unit all-variant burst interleaved with one day's traffic; the
        # allocation tests miss most of these, so without a declared randomization rule nothing is causal
        o = oracle_module()
        seen = set()
        for k in range(8):
            pkg, A, E = o.bursty(random.Random(4000 + k), 40, 9 * 24, interleave=True)
            r = rep(o.write(self.tmp / ('ib%d' % k), pkg, A, E))
            seen.add(r['outcome'])
            self.assertFalse(r['claims_allowed']['causal'], r['outcome'])
            self.assertNotEqual(r['outcome'], 'difference_detected')
            self.assertEqual(r['assignment_check'], {'contract': None, 'units_checked': 0, 'mismatched': None, 'examples': [], 'verified': False})
        self.assertIn('association_only', seen)  # the significant runs are reported, as associations

    def test_randomization_contract_verified_per_unit(self):
        o = oracle_module()
        pkg, A, E = o.bursty(random.Random(77), 30, 9 * 24, interleave=True, contract=True)
        r = rep(o.write(self.tmp / 'cb', pkg, A, E))
        self.assertEqual(r['outcome'], 'invalid_experiment')
        self.assertGreaterEqual(r['assignment_check']['mismatched'], 1)
        self.assertEqual(r['claims_allowed'], {'causal': False, 'significance': False})
        self.assertIn('does not follow the declared randomization', ' '.join(r['trace']))
        # the fixture: every cohort unit verified, causal claim allowed
        r = rep(FIX / 'retention-lift' / 'package.json')
        self.assertEqual(r['assignment_check']['units_checked'], 1200)
        self.assertTrue(r['assignment_check']['verified'])
        # one unit moved to the other arm invalidates; a wrong salt invalidates
        d = self.tmp / 'flip'
        shutil.copytree(FIX / 'retention-lift', d)
        rows = (d / 'assignments.csv').read_text().splitlines()
        u, arm, at = rows[1].split(',')
        rows[1] = ','.join([u, 'control' if arm == 'treatment' else 'treatment', at])
        (d / 'assignments.csv').write_text('\n'.join(rows) + '\n')
        r = rep(d / 'package.json')
        self.assertEqual((r['outcome'], r['assignment_check']['mismatched'], r['assignment_check']['examples']), ('invalid_experiment', 1, [u]))
        d2 = self.tmp / 'salt'
        shutil.copytree(FIX / 'retention-lift', d2)
        p = json.loads((d2 / 'package.json').read_text()); p['randomization']['salt'] = 'other'
        (d2 / 'package.json').write_text(json.dumps(p))
        self.assertEqual(rep(d2 / 'package.json')['outcome'], 'invalid_experiment')
        # without the rule the same data is significant but not causal
        del p['randomization']; (d2 / 'package.json').write_text(json.dumps(p))
        r = rep(d2 / 'package.json')
        self.assertEqual((r['outcome'], r['claims_allowed']), ('association_only', {'causal': False, 'significance': True}))
        for bad in ({'method': 'sha256_bucket'}, {'method': 'sha1', 'salt': 'x'}, {'method': 'sha256_bucket', 'salt': ''}, ['sha256_bucket', 'x'],
                    {'method': 'sha256_bucket', 'salt': 'x', 'tolerance': 1}):
            p['randomization'] = bad; (d2 / 'package.json').write_text(json.dumps(p))
            r2 = cli('analyse', d2 / 'package.json', '--json')
            self.assertEqual(r2.returncode, 2, bad)
            self.assertIn('randomization', r2.stderr)
        p['randomization'] = {'method': 'sha256_bucket', 'salt': 'x'}; p['assignment'] = 'observational'
        (d2 / 'package.json').write_text(json.dumps(p))
        r2 = cli('analyse', d2 / 'package.json', '--json')
        self.assertEqual(r2.returncode, 2)
        self.assertIn('only for assignment randomized', r2.stderr)

    def test_bucket_rule_matches_the_documented_formula(self):
        import hashlib
        sys.path.insert(0, str(DS)); old = sys.dont_write_bytecode; sys.dont_write_bytecode = True
        try:
            import experiment_readout as er
        finally:
            sys.path.pop(0); sys.dont_write_bytecode = old
        from fractions import Fraction
        arms = ['a', 'b']
        for split in ((0.5, 0.5), (0.3, 0.7), (0.9, 0.1)):
            for k in range(5000):
                u = 'unit-%d' % k
                frac = Fraction(int(hashlib.sha256(('s1:' + u).encode('utf-8')).hexdigest()[:15], 16), 16 ** 15)
                self.assertEqual(er.bucket_arm('s1', u, arms, split), 'a' if frac < Fraction(split[0]) else 'b', (u, split))

    def test_immature_units_excluded_not_failures(self):
        o = oracle_module()
        pkg, A, E, truth, _ = o.experiment(random.Random(5), n=(500, 500), p=(0.4, 0.4), exact=True)
        pkg['as_of'] = '2026-09-03T00:00:00Z'
        r = rep(o.write(self.tmp / 'imm', pkg, A, E))
        self.assertGreater(r['exclusions']['immature'], 0)
        units = sum(v['units'] for v in r['arms'].values())
        self.assertEqual(units + r['exclusions']['immature'], 1000)
        for v in r['arms'].values():
            self.assertAlmostEqual(float(v['rate']), 0.25, delta=0.03)

    def test_boundaries_and_rejected_rows_hand_worked(self):
        d = self.tmp / 'edge'
        d.mkdir()
        pkg = {'schema': 'solaris.experiment/1', 'experiment': 'edge', 'unit': 'unit_id', 'assignment': 'randomized',
               'arms': ['control', 'treatment'], 'planned_split': [0.5, 0.5], 'timezone': 'UTC',
               'cohort': {'start': '2026-08-01T00:00:00Z', 'end': '2026-08-10T00:00:00Z'}, 'as_of': '2026-09-01T00:00:00Z',
               'outcome': {'event': 'retained', 'horizon_days': 7}, 'min_sample_per_arm': 1,
               'assignments': {'file': 'a.csv'}, 'events': {'file': 'e.csv'}}
        (d / 'a.csv').write_text('unit_id,arm,assigned_at\n'
                                 'c1,control,2026-08-01T00:00:00Z\n'      # converted inside the 7 days
                                 'c2,control,2026-08-02T00:00:00Z\n'      # event exactly at +7d: not converted
                                 't1,treatment,2026-08-01T00:00:00Z\n'    # converted
                                 't2,treatment,2026-08-03T00:00:00Z\n'    # not converted
                                 'x1,control,2026-08-10T00:00:00Z\n'      # assigned at cohort.end: outside
                                 'h1,holdout,2026-08-02T00:00:00Z\n'      # unknown arm
                                 'm1,,2026-08-02T00:00:00Z\n'             # missing arm
                                 'm2,treatment,\n')                        # missing time
        (d / 'e.csv').write_text('unit_id,event,occurred_at,session_id\n'
                                 'c1,retained,2026-08-07T23:59:59Z,s1\n'
                                 'c2,retained,2026-08-09T00:00:00Z,s2\n'
                                 't1,retained,2026-08-05T00:00:00Z,s3\n'
                                 't1,retained,2026-08-06T00:00:00Z,s4\n'
                                 'x1,retained,2026-08-11T00:00:00Z,s5\n'
                                 'h1,retained,2026-08-03T00:00:00Z,s6\n')
        (d / 'package.json').write_text(json.dumps(pkg))
        r = rep(d / 'package.json')
        self.assertEqual({a: (v['units'], v['converted']) for a, v in r['arms'].items()}, {'control': (2, 1), 'treatment': (2, 1)})
        ex = r['exclusions']
        self.assertEqual((ex['outside_cohort'], ex['unknown_arm'], ex['missing_values'], ex['events_after_horizon']), (1, 1, 2, 1))
        (d / 'dup.json').write_text(json.dumps(pkg)[:-1] + ', "min_sample_per_arm": 1}')
        p = cli('analyse', d / 'dup.json')
        self.assertEqual(p.returncode, 2)
        self.assertIn('duplicate key', p.stderr)

    def test_invalid_refused_previous_report_kept(self):
        out = self.tmp / 'r.json'
        self.assertEqual(cli('analyse', FIX / 'clean-aa' / 'package.json', '--out', out).returncode, 0)
        before = out.read_bytes()
        d = self.tmp / 'drift'
        shutil.copytree(FIX / 'clean-aa', d)
        (d / 'events.csv').write_text((d / 'events.csv').read_text().replace('occurred_at', 'when', 1))
        p = cli('analyse', d / 'package.json', '--out', out)
        self.assertEqual(p.returncode, 2)
        self.assertIn('occurred_at', p.stderr)
        self.assertEqual(out.read_bytes(), before)

    def test_no_bytecode_left_in_data_engineer(self):
        root = self.tmp / 'repo'
        for rel in ('employees/data/data-scientist', 'employees/data/data-engineer', 'examples/capabilities/G15/fixtures/clean-aa'):
            shutil.copytree(ROOT / rel, root / rel, ignore=shutil.ignore_patterns('__pycache__'))
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONDONTWRITEBYTECODE'}
        p = subprocess.run([sys.executable, str(root / 'employees/data/data-scientist/experiment_readout.py'), 'analyse',
                            str(root / 'examples/capabilities/G15/fixtures/clean-aa/package.json')], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(str(x.relative_to(root)) for x in root.rglob('__pycache__')), [])

    def test_contracts_point_at_real_evidence(self):
        c = json.loads((DS / 'capability.contract.json').read_text())
        self.assertIn('experiment_readout.py', c['dependencies']['scripts'])
        self.assertIn('experiment-readout.md', c['dependencies']['references'])
        for ref in c['dependencies']['references'] + c['dependencies']['scripts']:
            self.assertTrue((DS / ref).is_file(), ref)
        self.assertIn('experiment-readout.md', json.loads((DS / 'plugin.json').read_text())['references'])
        self.assertIn('experiment_readout.py', (ROOT / 'employees/product-project/product-manager/SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()
