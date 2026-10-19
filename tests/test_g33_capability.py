"""G33: product choice from conflicting evidence (employees/product-project/product-manager/evidence_decision.py).
Real files and subprocesses on a synthetic package; figures are worked by hand in the G33 README."""
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
TOOL = ROOT / 'employees' / 'product-project' / 'product-manager' / 'evidence_decision.py'
EX = ROOT / 'examples' / 'capabilities' / 'G33'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def cli(*a):
    return subprocess.run([sys.executable, str(TOOL)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=300)


class G33Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g33-test-'))
        self.d = self.tmp / 'fx'
        shutil.copytree(str(EX / 'fixtures'), str(self.d))
        self.p = json.loads((self.d / 'choice.json').read_text())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def claim(self, k):
        return [c for c in self.p['claims'] if c['id'] == k][0]

    def src(self, k):
        return [s for s in self.p['sources'] if s['id'] == k][0]

    def decide(self, rc):
        f = self.d / 'pkg.json'; f.write_text(json.dumps(self.p))
        r = cli('decide', f, '--json')
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return json.loads(r.stdout) if rc != 2 else r

    def codes(self, r):
        return {(f['code'], f['ref']) for f in r['findings']}

    def test_fixture_worked_figures(self):
        r = self.decide(0)
        self.assertEqual((r['status'], r['preferred']), ('preferred', 'portal'))
        self.assertEqual(r['totals']['portal'], {'low': '3.5000', 'high': '3.9500', 'point': '3.8214', 'unknown_dimensions': []})
        self.assertEqual(r['totals']['ai-schedule'], {'low': '0.9500', 'high': '0.9500', 'point': '0.9500', 'unknown_dimensions': []})
        self.assertEqual(r['totals']['reports'], {'low': '1.0500', 'high': '2.3000', 'point': None, 'unknown_dimensions': ['proof']})
        cell = [c for c in r['cells'] if c['option'] == 'portal' and c['dimension'] == 'pain'][0]
        self.assertEqual((cell['mean'], cell['low'], cell['high'], cell['conflict']), ('4.7143', '4', '5', False))
        self.assertEqual(sorted(x['claim'] for x in r['excluded']), ['C10', 'C9'])
        self.assertEqual(r['verify_before_use'][0]['age_days'], 127)
        self.assertEqual(r['claim_confidence']['C8'], 'high')
        self.assertTrue(r['estimates_made'].startswith('none'))

    def test_quote_snapshot_and_value_checks(self):
        self.claim('C3')['quote'] = 'A day view that refreshes   within a MINUTE would cut the callbacks.'
        self.decide(0)  # whitespace and case do not matter
        self.claim('C3')['quote'] = 'A day view that refreshes instantly would cut the callbacks.'
        self.assertEqual(self.codes(self.decide(1)), {('quote_not_in_source', 'C3')})
        self.claim('C3')['quote'] = ''
        self.assertEqual(self.codes(self.decide(1)), {('quote_not_in_source', 'C3')})
        self.p = json.loads((self.d / 'choice.json').read_text())
        self.claim('C7')['value'] = '18%'
        self.assertEqual(self.codes(self.decide(1)), {('value_not_in_quote', 'C7')})
        self.p = json.loads((self.d / 'choice.json').read_text())
        (self.d / 'sources' / 'ben.txt').write_text('changed')
        r = self.decide(1)
        self.assertEqual(self.codes(r), {('snapshot_mismatch', 'C3'), ('snapshot_mismatch', 'C4'), ('snapshot_mismatch', 'C11')})
        self.assertIsNone(r['preferred'])
        (self.d / 'sources' / 'ben.txt').unlink()
        self.assertIn('missing', self.decide(1)['findings'][0]['detail'])

    def test_findings_clear_preferred_even_when_totals_win(self):
        # one invented quote blocks the package; portal would still win on remaining claims
        self.claim('C2')['quote'] = 'Invented quote that is not in any snapshot.'
        r = self.decide(1)
        self.assertEqual(r['status'], 'blocked_evidence')
        self.assertIsNone(r['preferred'])
        self.assertIn(('quote_not_in_source', 'C2'), self.codes(r))
        self.assertGreater(float(r['totals']['portal']['low']), float(r['totals']['ai-schedule']['high']))

    def test_atomic_out_uses_replace(self):
        src = (ROOT / 'employees/product-project/product-manager/evidence_decision.py').read_text()
        self.assertIn('os.replace(tmp, str(out))', src)
        self.assertIn('tempfile.mkstemp', src)

    def test_unknown_source_and_unscored(self):
        self.claim('C2')['source'] = 'S-none'
        self.claim('C13').pop('score')
        self.assertEqual(self.codes(self.decide(1)), {('unknown_source', 'C2'), ('unscored_claim', 'C13')})

    def test_g13_metric_rerun(self):
        self.claim('C8')['value'] = '6'
        self.assertIn('G13 rerun gives', self.decide(1)['findings'][0]['detail'])
        self.claim('C8')['value'] = '5'; self.claim('C8')['score'] = '2'
        self.decide(0)
        self.claim('C8')['score'] = '3'
        self.assertEqual(self.codes(self.decide(1)), {('stated_score_mismatch', 'C8')})
        self.claim('C8').pop('score'); self.src('S-g13')['metric'] = 'nope'
        self.assertEqual(self.codes(self.decide(1)), {('g13_unavailable', 'C8'), ('g13_unavailable', 'C12')})
        self.src('S-g13')['metric'] = 'orders'; self.src('S-g13')['group'] = {'currency': 'USD'}
        self.assertIn('has no group', self.decide(1)['findings'][0]['detail'])
        self.src('S-g13')['group'] = {}; self.src('S-g13')['contract'] = 'g13/missing.json'
        self.assertIn('refused', self.decide(1)['findings'][0]['detail'])

    def test_g13_with_gaps_is_low_confidence(self):
        self.src('S-g13')['contract'] = 'g13-gaps/contract.json'
        for k in ('C8', 'C12'):
            self.claim(k)['value'] = '8'
        r = self.decide(0)
        self.assertEqual((r['claim_confidence']['C8'], r['claim_confidence']['C12']), ('low', 'low'))

    def test_metric_scale_thresholds(self):
        self.src('S-mkt')['retrieved_at'] = '2026-09-20'
        c = self.claim('C10'); c.pop('score'); c['option'] = 'reports'
        r = self.decide(0)
        self.assertEqual([x for x in r['cells'] if x['option'] == 'reports' and x['dimension'] == 'proof'][0]['mean'], '5.0000')
        self.p['dimensions'][2]['metric_scale']['thresholds'] = ['1', '5', '10', '50', '18001']
        r = self.decide(0)
        self.assertEqual([x for x in r['cells'] if x['option'] == 'reports' and x['dimension'] == 'proof'][0]['mean'], '4.0000')
        c['value'] = 'many'; c['quote'] = 'Headline figure: addressable clinics in North America: 18,000. many'
        (self.d / 'sources' / 'market.txt').write_text('Headline figure: addressable clinics in North America: 18,000. many\n')
        self.src('S-mkt')['snapshot']['sha256'] = hashlib.sha256((self.d / 'sources' / 'market.txt').read_bytes()).hexdigest()
        self.assertIn('not a number', self.decide(1)['findings'][0]['detail'])
        c.pop('value')
        self.assertIn('scored from a stated value', self.decide(1)['findings'][0]['detail'])

    def test_quantity_dimension_needs_the_number(self):
        self.p['dimensions'][0]['quantity'] = True
        self.claim('C1')['quote'] = 'I would pay about 40 dollars per provider per month for that alone.'
        # r2: every claim on a quantity dimension needs a numeric value from its quote, not only quotes with digits
        self.assertEqual(self.codes(self.decide(1)), {('value_not_in_quote', k) for k in ('C1', 'C2', 'C5', 'C11')})
        r = self.decide(1)
        why = {f['ref']: f['detail'] for f in r['findings']}
        self.assertIn('quote states no number', why['C5'])
        self.assertNotIn('quote states no number', why['C1'])
        self.claim('C1')['value'] = '40'
        self.claim('C5')['value'] = 'ten minutes'  # in the quote, but not a number
        r = self.decide(1)
        self.assertEqual(self.codes(r), {('value_not_in_quote', k) for k in ('C2', 'C5', 'C11')})
        self.assertIn('is not a number', {f['ref']: f['detail'] for f in r['findings']}['C5'])
        self.p['claims'] = [c for c in self.p['claims'] if c['id'] not in ('C2', 'C5', 'C11')]
        r = self.decide(0)
        self.assertNotIn('C1', {x['claim'] for x in r.get('excluded', [])})
        self.assertEqual(r['findings'], [])
        # quantity off (false) keeps the r1 behaviour for qualitative claims
        self.p = json.loads((self.d / 'choice.json').read_text()); self.p['dimensions'][0]['quantity'] = False
        self.decide(0)

    def test_numeric_value_needs_whole_number_boundaries(self):
        """Root G33: 4 never matches 40 and 18 never matches 18,000; the whole number still matches."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('g33_ed', str(TOOL)); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertFalse(m._value_in_quote('18', 'North America: 18,000.'))
        self.assertTrue(m._value_in_quote('18,000', 'North America: 18,000.'))
        self.assertTrue(m._value_in_quote('18000', 'North America: 18,000.'))
        self.assertFalse(m._value_in_quote('4', 'about 40 dollars'))
        self.assertFalse(m._value_in_quote('40', 'about 1400 dollars'))
        self.assertTrue(m._value_in_quote('40', 'about 40 dollars'))
        self.assertFalse(m._value_in_quote('12%', 'grew 12 points'))
        self.assertTrue(m._value_in_quote('12%', 'grew 12% last year'))
        self.assertTrue(m._value_in_quote('ten minutes', 'saves ten minutes a day'))
        self.p['dimensions'][0]['quantity'] = True
        self.p['claims'] = [c for c in self.p['claims'] if c['id'] not in ('C2', 'C5', 'C11')]
        self.claim('C1')['quote'] = 'I would pay about 40 dollars per provider per month for that alone.'
        self.claim('C1')['value'] = '4'
        self.assertIn(('value_not_in_quote', 'C1'), self.codes(self.decide(1)))
        self.claim('C1')['value'] = '40'
        self.assertEqual(self.decide(0)['findings'], [])

    def test_staleness_boundary(self):
        self.src('S-mkt')['max_age_days'] = 127
        self.claim('C10')['score'] = '5'  # matches the metric scale for 18,000
        r = self.decide(0)
        self.assertEqual(r['verify_before_use'], [])
        self.assertIn('C10', r['claim_confidence'])
        self.src('S-mkt')['max_age_days'] = 126
        self.assertEqual(len(self.decide(0)['verify_before_use']), 1)
        self.src('S-mkt')['mutable'] = False
        self.assertEqual(self.decide(0)['verify_before_use'], [])

    def test_icp_exclusion_applies_to_metric_claims(self):
        self.claim('C12')['segment'] = 'enterprise'
        r = self.decide(0)
        self.assertIn({'claim': 'C12', 'reason': 'segment enterprise is outside the ICP mid-size clinics'}, r['excluded'])
        self.assertEqual(r['totals']['ai-schedule']['unknown_dimensions'], ['proof'])

    def test_decision_moves_with_evidence(self):
        for k, s in (('C1', '1'), ('C5', '2'), ('C6', '1')):
            self.claim(k)['score'] = s
        r = self.decide(1)
        self.assertEqual(r['status'], 'no_robust_choice')
        self.assertEqual(r['deciding_evidence'][0], {'option': 'reports', 'dimension': 'proof', 'weighted_range': '1.2500', 'why': 'no evidence'})
        self.assertIn({'option': 'portal', 'dimension': 'pain', 'weighted_range': '0.4500', 'why': 'evidence spans 1 to 2'}, r['deciding_evidence'])
        self.p['claims'].append({'id': 'C20', 'option': 'reports', 'dimension': 'proof', 'source': 'S-ana', 'segment': 'mid-size clinics',
                                 'confidence': 'high', 'value': '1', 'quote': 'Nice to have. Booking is the pain. 1'})
        self.assertIn(('quote_not_in_source', 'C20'), self.codes(self.decide(1)))

    def test_contrary_evidence_and_ties(self):
        self.p['claims'].append({'id': 'C99', 'option': 'portal', 'dimension': 'pain', 'source': 'S-ana', 'segment': 'mid-size clinics',
                                 'confidence': 'high', 'score': '0', 'quote': 'Double bookings happen twice a week.'})
        r = self.decide(1)
        self.assertEqual(r['contrary_evidence'], [{'option': 'portal', 'dimension': 'pain', 'claim': 'C99', 'score': '0', 'against': 'cell mean 3.3000'}])
        self.p['claims'] = [c for c in self.p['claims'] if c['id'] != 'C99']
        self.claim('C2')['score'] = '2.5'
        r = self.decide(0)
        self.assertEqual(r['contrary_evidence'], [])

    def test_robust_needs_strictly_greater(self):
        # identical totals: low == other.high, so not a robust win
        self.p['options'] = [{'id': 'A', 'label': 'A'}, {'id': 'B', 'label': 'B'}]
        self.p['dimensions'] = [{'id': 'pain', 'label': 'Pain', 'weight': '1'}]
        self.p['claims'] = [
            {'id': 'CA', 'option': 'A', 'dimension': 'pain', 'source': 'S-ana', 'segment': 'mid-size clinics', 'confidence': 'high', 'score': '3', 'quote': 'Double bookings happen twice a week.'},
            {'id': 'CB', 'option': 'B', 'dimension': 'pain', 'source': 'S-ana', 'segment': 'mid-size clinics', 'confidence': 'high', 'score': '3', 'quote': 'Double bookings happen twice a week.'},
        ]
        r = self.decide(1)
        self.assertEqual((r['status'], r['preferred'], r['totals']['A']['low'], r['totals']['B']['high']),
                         ('no_robust_choice', None, '3.0000', '3.0000'))

    def test_invalid_packages(self):
        muts = [lambda p: p.update(schema='x'), lambda p: p['dimensions'][0].update(weight='0.46'),
                lambda p: p['claims'][0].update(score='5.5'), lambda p: p['claims'][0].update(score=5),
                lambda p: p['claims'][0].update(dimension='cost'), lambda p: p['claims'][0].update(confidence='sure'),
                lambda p: p['sources'][0].update(kind='blog'), lambda p: p['sources'][0].update(retrieved_at='2026-10-07'),
                lambda p: p['sources'][3].update(max_age_days='90'), lambda p: p['sources'][3].pop('url'),
                lambda p: p.update(market_size='18000'), lambda p: p.update(adoption='35%'),
                lambda p: p.update(adoption_rate='0.2'), lambda p: p.update(assumed_adoption=0.35), lambda p: p.update(tam='1'),
                lambda p: p['dimensions'][0].update(quantity='yes'), lambda p: p['dimensions'][0].update(quantity=1),
                lambda p: p['decision']['icp'].pop('segment'),
                lambda p: p['dimensions'][2]['metric_scale'].update(thresholds=['5', '1', '10', '50', '100']),
                lambda p: p['claims'].append(dict(p['claims'][0]))]
        orig = json.dumps(self.p)
        for m in muts:
            self.p = json.loads(orig); m(self.p)
            r = self.decide(2)
            self.assertIn('Nothing was written', r.stderr)

    def test_out_and_verify(self):
        f = self.d / 'choice.json'; o = self.tmp / 'r.json'
        self.assertEqual(cli('decide', f, '--out', o).returncode, 0)
        self.assertEqual(cli('verify', o, f).returncode, 0)
        keep = o.read_bytes()
        self.assertEqual(cli('decide', self.tmp / 'missing.json', '--out', o).returncode, 2)
        self.assertEqual(o.read_bytes(), keep)
        j = json.loads(keep); j['totals']['portal']['low'] = '3.6000'; o.write_text(json.dumps(j))
        r = cli('verify', o, f); self.assertEqual(r.returncode, 1); self.assertIn('totals', r.stdout)
        o.write_text('{'); self.assertEqual(cli('verify', o, f).returncode, 2)
        self.assertEqual(cli('decide', f, '--out', f).returncode, 2)
        self.assertEqual(json.loads(f.read_text())['schema'], 'solaris.evidence-decision/1')

    def test_text_report(self):
        r = cli('decide', self.d / 'choice.json')
        self.assertIn('PREFERRED portal', r.stdout)
        self.assertIn('VERIFY S-mkt (https://analyst.example.invalid/market/clinic-software) is 127 days old, max 30', r.stdout)

    def test_oracle_and_controls(self):
        run = lambda *a: subprocess.run([sys.executable, str(EX / 'evidence_oracle.py')] + list(a), capture_output=True, text=True, env=ENV, timeout=600)
        r = run()
        self.assertEqual(r.stdout.strip().splitlines()[-1], 'ACCEPTED 11/11', r.stdout)
        for t in ('naive_decision.py', 'noop_decision.py'):
            self.assertEqual(run('--tool', str(EX / t)).stdout.strip().splitlines()[-1], 'REJECTED 1/11')

    def test_contracts_declare_tool(self):
        text = (ROOT / 'employees/product-project/product-manager/capability.contract.json').read_text()
        self.assertIn('evidence_decision.py', text)
        self.assertIn('evidence-product-decision.md', text)
        for role in ('marketing/market-researcher', 'leadership/cmo', 'product-project/product-manager'):
            self.assertIn('evidence_decision.py', (ROOT / 'employees' / role / 'SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()
