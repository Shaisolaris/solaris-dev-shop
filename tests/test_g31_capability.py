"""G31: customer scope, estimate and delivery acceptance (employees/product-project/business-analyst/scope_acceptance.py).
Real files and subprocesses on synthetic packages; expected figures are worked by hand in the G31 README or
planted by the oracle's generator."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees' / 'product-project' / 'business-analyst' / 'scope_acceptance.py'
EX = ROOT / 'examples' / 'capabilities' / 'G31'
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')


def cli(*args):
    return subprocess.run([sys.executable, str(TOOL)] + [str(a) for a in args], capture_output=True, text=True,
                          env=ENV, timeout=300)


class G31Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g31-test-'))
        self.d = self.tmp / 'fx'
        shutil.copytree(str(EX / 'fixtures'), str(self.d))
        self.p = json.loads((self.d / 'portal.json').read_text())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def req(self, k):
        return [r for r in self.p['requirements'] if r['id'] == k][0]

    def com(self, k):
        return [c for c in self.p['proposal']['commitments'] if c['id'] == k][0]

    def check(self, rc):
        f = self.d / 'pkg.json'
        f.write_text(json.dumps(self.p))
        r = cli('check', f, '--json')
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return json.loads(r.stdout) if rc != 2 else r

    def codes(self, r):
        return {(f['code'], f['ref']) for f in r['findings']}

    def test_clean_fixture_figures(self):
        r = self.check(0)
        self.assertEqual(r['status'], 'ready')
        self.assertEqual(r['estimate']['hours'], {'low': '230', 'likely': '310', 'high': '440'})
        self.assertEqual(r['estimate']['price'], {'low': '34500.00', 'high': '66000.00'})
        self.assertEqual(r['conditions'], ['A2'])
        self.assertEqual(r['excluded'], ['R5'])
        self.assertEqual(r['capacity_finish'], '2027-02-07')
        m = {x['commitment']: x for x in r['trace_matrix']}
        self.assertEqual(m['C3']['sources'], ['A1', 'A2', 'IN1', 'IN2', 'IN3', 'IN4'])
        self.assertEqual(m['C4'], {'commitment': 'C4', 'kind': 'feature', 'refs': ['R3'], 'sources': ['IN3'], 'conditional_on': [], 'qualified_by': []})
        self.assertTrue(r['read_only'])

    def test_invented_and_out_of_scope_commitments(self):
        self.p['proposal']['commitments'] += [{'id': 'C8', 'kind': 'sla', 'text': '99.9% uptime', 'refs': []},
                                              {'id': 'C9', 'kind': 'feature', 'text': 'board reports', 'refs': ['R5']},
                                              {'id': 'C7', 'kind': 'other', 'text': 'free training', 'refs': ['IN8']},
                                              {'id': 'C6', 'kind': 'other', 'text': 'priority support', 'refs': []}]
        r = self.check(1)
        self.assertEqual(self.codes(r), {('invented_commitment', 'C8'), ('out_of_scope_commitment', 'C9'),
                                         ('invented_commitment', 'C9'), ('invented_commitment', 'C7'), ('invented_commitment', 'C6')})

    def test_input_only_commitment_is_traced(self):
        self.p['proposal']['commitments'].append({'id': 'C9', 'kind': 'other', 'text': 'weekly status call', 'refs': ['IN2']})
        r = self.check(0)
        self.assertEqual([x['sources'] for x in r['trace_matrix'] if x['commitment'] == 'C9'], [['IN2']])

    def test_estimate_reconciles_exactly(self):
        self.p['proposal']['estimate']['price']['low'] = '34500.01'
        self.req('R4')['estimate_hours']['high'] = '50.5'
        r = self.check(1)
        self.assertEqual(self.codes(r), {('estimate_mismatch', 'price.low'), ('estimate_mismatch', 'hours.high'),
                                         ('estimate_mismatch', 'price.high')})
        self.assertEqual(r['estimate']['price']['high'], '66075.00')

    def test_rate_rounds_half_up_to_cents(self):
        self.p['rate']['per_hour'] = '150.0015'
        self.p['proposal']['estimate']['price'] = {'low': '34500.35', 'high': '66000.66'}
        self.check(0)
        self.p['proposal']['estimate']['price']['low'] = '34500.34'
        self.assertEqual(self.codes(self.check(1)), {('estimate_mismatch', 'price.low')})

    def test_fixed_estimate_support(self):
        self.p['proposal']['estimate'] = {'type': 'fixed', 'hours': '440', 'price': '66000.00'}
        r = self.check(1)
        self.assertEqual(self.codes(r), {('unsupported_fixed_estimate', 'estimate'), ('unsupported_fixed_estimate', 'C2')})
        self.assertIn('unconfirmed assumption A2', [f for f in r['findings'] if f['ref'] == 'estimate'][0]['detail'])
        self.p['assumptions'][1]['confirmed'] = True
        self.check(0)
        self.p['proposal']['estimate'] = {'type': 'fixed', 'hours': '439.75', 'price': '65962.50'}
        r = self.check(1)
        self.assertIn('below the high estimate', [f for f in r['findings'] if f['ref'] == 'estimate'][0]['detail'])
        self.p['proposal']['estimate'] = {'type': 'fixed', 'hours': '440', 'price': '65000.00'}
        self.assertIn(('estimate_mismatch', 'price.fixed'), self.codes(self.check(1)))
        self.p['proposal']['estimate'] = {'type': 'fixed', 'hours': '440', 'price': '66000.00'}
        self.p['ambiguities'].append({'id': 'AMB2', 'about': ['R1'], 'question': 'q', 'escalated_to': 'x', 'status': 'open'})
        self.assertIn('open ambiguity', [f for f in self.check(1)['findings'] if f['ref'] == 'estimate'][0]['detail'])

    def test_ambiguity_must_be_escalated_and_resolved(self):
        self.p['ambiguities'] = []
        r = self.check(1)
        self.assertEqual(self.codes(r), {('unescalated_ambiguity', 'R2'), ('commitment_on_blocked_requirement', 'C1'),
                                         ('commitment_on_blocked_requirement', 'C2'), ('commitment_on_blocked_requirement', 'C3')})
        self.assertEqual(r['findings'][-1]['detail'], 'real-time')
        self.p['ambiguities'] = [{'id': 'AMB1', 'about': ['AC3'], 'question': 'q', 'escalated_to': 'ops', 'status': 'open'}]
        r = self.check(1)
        self.assertIn(('open_ambiguity', 'R2'), self.codes(r))
        self.assertEqual(r['escalations'], [{'id': 'AMB1', 'about': ['AC3'], 'question': 'q', 'escalated_to': 'ops'}])

    def test_vague_criterion_and_missing_measure(self):
        self.req('R4')['acceptance'][0]['measure'] = None
        self.req('R1')['acceptance'][1]['criterion'] = 'booking is fast under load'
        r = self.check(1)
        self.assertIn(('unescalated_ambiguity', 'R4'), self.codes(r))
        self.assertIn(('unescalated_ambiguity', 'R1'), self.codes(r))
        self.req('R1')['acceptance'] = []
        self.assertIn(('no_acceptance_criteria', 'R1'), self.codes(self.check(1)))

    def test_vague_word_boundaries(self):
        self.req('R1')['text'] = 'Breakfast-time quickstep: bestow fastidious, steadfast and unsimple booking'
        self.check(0)

    def add_r6(self, r6, inp, r1=None):
        self.p['inputs'].append({'id': 'IN9', 'text': inp, 'source': 'ops email 2026-10-02', 'date': '2026-10-02'})
        self.p['requirements'].append({'id': 'R6', 'text': r6, 'traces': ['IN9'], 'depends_on': ['R1'], 'capability': 'CAP-booking',
                                       'estimate_hours': {'low': '4', 'likely': '6', 'high': '8'},
                                       'acceptance': [{'id': 'AC6', 'criterion': 'the rule is enforced', 'measure': '3 of 3 scripted attempts'}]})
        if r1:
            self.req('R1')['text'] = r1
        self.p['proposal']['scope'].append('R6')
        est = self.p['proposal']['estimate']
        for t, n in (('low', 4), ('likely', 6), ('high', 8)):
            est['hours'][t] = str(int(est['hours'][t]) + n)
        est['price'] = {b: '%d.00' % (int(est['hours'][b]) * 150) for b in ('low', 'high')}
        for c in self.p['proposal']['commitments'][:2]:
            c['refs'].append('R6')

    def test_contradictory_requirements_never_plain_commitments(self):
        # root G31: the M31 O12 package (24/7 vs closed outside office hours) must not be ready
        self.add_r6('Booking closed outside office hours (08:00 to 18:00)', 'Booking must be closed outside office hours',
                    'Online booking, moving and cancelling of appointments at any hour, 24/7')
        r = self.check(1)
        self.assertTrue({('unresolved_conflict', 'R1'), ('unresolved_conflict', 'R6'), ('commitment_on_blocked_requirement', 'C1'),
                         ('commitment_on_blocked_requirement', 'C2')} <= self.codes(r))
        self.assertEqual([(c['between'], c['status']) for c in r['conflicts']], [(['R1', 'R6'], 'unescalated')])
        self.assertIn('availability: requirement R1 vs requirement R6', r['conflicts'][0]['evidence'])
        # escalated and open: blocked, listed with its owner
        self.p['ambiguities'].append({'id': 'AMB9', 'about': ['R1', 'R6'], 'question': '24/7 or office hours?', 'escalated_to': 'Clinic owner', 'status': 'open'})
        r = self.check(1)
        self.assertIn(('open_ambiguity', 'R6'), self.codes(r))
        self.assertNotIn('unresolved_conflict', {f['code'] for f in r['findings']})
        self.assertEqual([(c['status'], c['ambiguities'], c['owner']) for c in r['conflicts']], [('open', ['AMB9'], ['Clinic owner'])])
        self.assertEqual({x['commitment']: x['qualified_by'] for x in r['trace_matrix']}['C1'], [])
        self.assertIn({'id': 'AMB9', 'about': ['R1', 'R6'], 'question': '24/7 or office hours?', 'escalated_to': 'Clinic owner'}, r['escalations'])
        # an ambiguity about only one side does not settle it
        self.p['ambiguities'][-1]['about'] = ['R6']; self.p['ambiguities'][-1]['status'] = 'resolved'
        self.p['ambiguities'][-1]['resolution'] = {'text': 'office hours govern', 'source': 'owner email 2026-10-03', 'date': '2026-10-03'}
        self.assertIn(('unresolved_conflict', 'R1'), self.codes(self.check(1)))
        # resolved by the owner about both: ready, and the commitments carry the qualification
        self.p['ambiguities'][-1]['about'] = ['R1', 'R6']
        r = self.check(0)
        m = {x['commitment']: x['qualified_by'] for x in r['trace_matrix']}
        self.assertEqual(m, {'C1': ['AMB9'], 'C2': ['AMB9'], 'C3': ['AMB9'], 'C4': []})
        self.assertEqual(r['conflicts'][0]['owner'], ['Clinic owner'])
        out = cli('check', self.d / 'pkg.json').stdout
        self.assertIn('[qualified by owner resolution AMB9]', out)
        self.assertIn('CONFLICT R1 vs R6 resolved', out)
        self.assertIn('NOT CHECKED: general consistency of free text', out)

    def test_commitment_on_a_traced_input_of_a_resolved_conflict_is_qualified(self):
        """G31 r4 (M31 r2 P4-1): a commitment that rests only on an input a conflicting requirement traces had an empty
        qualified_by, so the proposal did not state the owner's resolution for it."""
        self.add_r6('Front desk takes calls during office hours only', 'Front desk works office hours only')
        self.req('R6')['conflicts_with'] = ['R1']
        self.p['ambiguities'].append({'id': 'AMB7', 'about': ['R1', 'R6'], 'question': 'online any time or office hours?',
                                      'escalated_to': 'Clinic owner', 'status': 'resolved',
                                      'resolution': {'text': 'booking online any time', 'source': 'owner call 2026-10-03', 'date': '2026-10-03'}})
        self.p['proposal']['commitments'].append({'id': 'C8', 'kind': 'other', 'text': 'Booking flow as in the brief', 'refs': ['IN1']})
        self.p['proposal']['commitments'].append({'id': 'C9', 'kind': 'other', 'text': 'Reminders as in the brief', 'refs': ['IN3']})
        r = self.check(0)
        m = {x['commitment']: x['qualified_by'] for x in r['trace_matrix']}
        self.assertEqual(m['C8'], ['AMB7'])
        self.assertEqual(m['C9'], [])
        self.assertEqual(m['C4'], [])

    def test_every_opposite_family_and_its_input(self):
        sys.path.insert(0, str(TOOL.parent)); old = sys.dont_write_bytecode; sys.dont_write_bytecode = True
        try:
            import scope_acceptance as sa
        finally:
            sys.path.pop(0); sys.dont_write_bytecode = old
        base = json.loads(json.dumps(self.p))
        for name, a, b in sa.OPPOSITES:
            for ta, tb in ((a[0], b[0]), (a[-1], b[-1])):
                self.p = json.loads(json.dumps(base))
                self.add_r6('Patients can book ' + ta.upper(), 'The owner wants booking ' + tb.upper())
                r = self.check(1)
                self.assertIn(('unresolved_conflict', 'R6'), self.codes(r), (name, ta, tb))
                self.assertTrue(any(name + ': requirement R6 vs input IN9' == e for c in r['conflicts'] for e in c['evidence']), (name, r['conflicts']))
        # a contradiction that sits only in an acceptance criterion
        self.p = json.loads(json.dumps(base))
        self.add_r6('Booking rules for the front desk', 'Front desk wants booking rules')
        self.req('R6')['acceptance'][0]['criterion'] = 'bookings are refused outside office hours'
        self.req('R1')['acceptance'][0]['measure'] = 'booking works 24/7 in 12 of 12 scripted steps'
        r = self.check(1)
        self.assertIn(('unresolved_conflict', 'R1'), self.codes(r))
        self.assertTrue(any('criterion AC1 vs criterion AC6' in e or 'criterion AC6 vs criterion AC1' in e for c in r['conflicts'] for e in c['evidence']), r['conflicts'])
        # a commitment text against an in-scope requirement
        self.p = json.loads(json.dumps(base))
        self.add_r6('Booking only during business hours', 'Booking only during business hours')
        self.p['proposal']['commitments'].append({'id': 'C9', 'kind': 'sla', 'text': 'Booking open around the clock', 'refs': ['R1']})
        r = self.check(1)
        self.assertIn(('conflicting_commitment', 'C9'), self.codes(r))
        self.p['ambiguities'].append({'id': 'AMB8', 'about': ['C9', 'R6'], 'question': 'which?', 'escalated_to': 'Clinic owner', 'status': 'resolved',
                                      'resolution': {'text': 'support line only', 'source': 'owner call 2026-10-03', 'date': '2026-10-03'}})
        self.assertNotIn(('conflicting_commitment', 'C9'), self.codes(self.check(0)))

    def test_commitments_contradicting_each_other(self):
        # two commitment texts of the same proposal on opposite sides of a family, requirements silent (M31 r2 P2-1)
        self.p['proposal']['commitments'].append({'id': 'C8', 'kind': 'sla', 'text': 'Support desk answers 24/7', 'refs': ['R2']})
        self.p['proposal']['commitments'].append({'id': 'C9', 'kind': 'sla', 'text': 'Support desk answers during office hours only', 'refs': ['R2']})
        r = self.check(1)
        self.assertTrue({('conflicting_commitment', 'C8'), ('conflicting_commitment', 'C9')} <= self.codes(r))
        self.assertTrue(any(f['detail'] == 'availability: commitment text vs commitment C9' for f in r['findings'] if f['ref'] == 'C8'), r['findings'])
        # an open ambiguity about both commitments does not settle it
        self.p['ambiguities'].append({'id': 'AMB8', 'about': ['C8', 'C9'], 'question': 'which hours?', 'escalated_to': 'Clinic owner', 'status': 'open'})
        self.assertIn(('conflicting_commitment', 'C8'), self.codes(self.check(1)))
        # a resolved ambiguity about both commitments does
        self.p['ambiguities'][-1]['status'] = 'resolved'
        self.p['ambiguities'][-1]['resolution'] = {'text': 'office hours; 24/7 is the answering machine', 'source': 'owner call 2026-10-03', 'date': '2026-10-03'}
        self.check(0)
        # same side twice is not a contradiction
        self.p = json.loads((self.d / 'portal.json').read_text())
        self.p['proposal']['commitments'].append({'id': 'C8', 'kind': 'sla', 'text': 'Support desk answers 24/7', 'refs': ['R2']})
        self.p['proposal']['commitments'].append({'id': 'C9', 'kind': 'sla', 'text': 'Booking open around the clock', 'refs': ['R1']})
        self.check(0)

    def test_declared_conflict_and_word_boundaries(self):
        self.add_r6('Front desk can block days for staff training', 'Front desk wants to block days')
        self.req('R6')['conflicts_with'] = ['R3']
        self.assertTrue({('unresolved_conflict', 'R3'), ('unresolved_conflict', 'R6')} <= self.codes(self.check(1)))
        self.req('R6')['conflicts_with'] = ['R6']
        self.check(2)
        self.req('R6')['conflicts_with'] = ['R99']
        self.check(2)
        # declared against a requirement that is not in scope is not a conflict in this proposal
        self.req('R6')['conflicts_with'] = ['R5']
        self.check(0)
        # look-alikes are not terms
        self.p = json.loads((self.d / 'portal.json').read_text())
        self.req('R1')['text'] = 'Online booking with an onboarding call, anonymously-rated SaaSy offlinedata kept-forward, on-premiums and online-onlyness, billed through a SaaS partner'
        r = self.check(0)
        self.assertEqual(r['conflicts'], [])
        self.assertIn('not_checked', r['coherence'])

    def test_demo_evidence_required(self):
        (self.d / 'demos' / 'CAP-import.json').write_text('{"capability": "CAP-import", "exit_code": 0, "result": "pass", "ran_at": "2026-09-30"}')
        r = self.check(1)
        self.assertIn(('undemonstrated_capability', 'R4'), self.codes(r))
        self.assertIn('changed since it was recorded', [f['detail'] for f in r['findings'] if f['ref'] == 'R4'][0])

    def test_demo_record_contents(self):
        import hashlib
        f = self.d / 'demos' / 'CAP-sms.json'
        for rec, why in (({'capability': 'CAP-sms', 'exit_code': 1, 'result': 'pass', 'ran_at': '2026-09-30'}, 'did not pass'),
                         ({'capability': 'CAP-sms', 'exit_code': 0, 'result': 'fail', 'ran_at': '2026-09-30'}, 'did not pass'),
                         ({'capability': 'CAP-booking', 'exit_code': 0, 'result': 'pass', 'ran_at': '2026-09-30'}, 'different capability'),
                         ({'capability': 'CAP-sms', 'exit_code': 0, 'result': 'pass', 'ran_at': '2026-10-07'}, 'after engagement.as_of')):
            f.write_text(json.dumps(rec))
            self.p['capabilities'][2]['demo']['sha256'] = hashlib.sha256(f.read_bytes()).hexdigest()
            r = self.check(1)
            self.assertIn(why, [x['detail'] for x in r['findings'] if x['ref'] == 'R3'][0])
        rec['ran_at'] = '2026-10-06'
        f.write_text(json.dumps(rec)); self.p['capabilities'][2]['demo']['sha256'] = hashlib.sha256(f.read_bytes()).hexdigest()
        self.check(0)

    def test_dependencies_and_exclusions(self):
        self.p['proposal']['scope'].remove('R1'); self.p['proposal']['exclusions'].append('R1')
        for c in self.p['proposal']['commitments']:
            c['refs'] = [x for x in c['refs'] if x != 'R1']
        self.p['proposal']['estimate'] = {'type': 'range', 'hours': {'low': '110', 'likely': '150', 'high': '220'}, 'price': {'low': '16500.00', 'high': '33000.00'}}
        r = self.check(1)
        self.assertEqual(self.codes(r), {('missing_dependency', 'R2'), ('missing_dependency', 'R3')})
        self.p['proposal']['exclusions'].remove('R1')
        self.assertIn(('silent_exclusion', 'R1'), self.codes(self.check(1)))
        self.p['proposal']['exclusions'] = ['R1']
        self.assertEqual(self.codes(self.check(1)), {('missing_dependency', 'R2'), ('missing_dependency', 'R3')})

    def test_untraced_requirement(self):
        self.req('R4')['traces'] = ['IN9']
        self.assertEqual([f['detail'] for f in self.check(1)['findings'] if f['code'] == 'untraced_requirement'], ['traces to unknown IN9'])
        self.req('R4')['traces'] = ['A2']
        self.req('R3')['traces'] = []
        r = self.check(1)
        self.assertIn(('untraced_requirement', 'R3'), self.codes(r))
        self.assertIn(('commitment_on_blocked_requirement', 'C4'), self.codes(r))

    def test_delivery_date_backed_by_g17(self):
        self.com('C3')['value'] = '2027-02-06'
        r = self.check(1)
        self.assertEqual(self.codes(r), {('unsupported_date', 'C3')})
        self.assertIn('2027-02-07 is after the committed 2027-02-06', r['findings'][0]['detail'])
        self.com('C3')['value'] = '2027-02-07'
        self.check(0)
        res = self.d / 'capacity' / 'studio-result.json'
        j = json.loads(res.read_text()); j['options'][0]['label'] += ' (edited)'; res.write_text(json.dumps(j))
        self.assertIn('does not match a rerun', self.check(1)['findings'][0]['detail'])

    def test_infeasible_g17_option_or_missing_capacity(self):
        self.p['capacity']['option'] = 'contractors'
        self.assertIn('not feasible in the downside', self.check(1)['findings'][0]['detail'])
        self.p.pop('capacity')
        self.assertIn('no capacity evidence', self.check(1)['findings'][0]['detail'])
        self.p['proposal']['commitments'] = [c for c in self.p['proposal']['commitments'] if c['kind'] != 'date']
        self.check(0)

    def test_acceptance(self):
        f = self.d / 'portal.json'; dl = self.d / 'delivery.json'
        r = cli('accept', f, dl, '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['status'], 'accepted')
        d = json.loads(dl.read_text()); d['results'][4]['outcome'] = 'fail'; d['results'].pop(0)
        dl2 = self.d / 'd2.json'; dl2.write_text(json.dumps(d))
        r = json.loads(cli('accept', f, dl2, '--json').stdout)
        self.assertEqual({(x['code'], x['ref']) for x in r['findings']}, {('criterion_failed', 'AC5'), ('missing_evidence', 'AC1')})
        self.assertEqual([x['status'] for x in r['requirements']], ['not_accepted', 'accepted', 'accepted', 'not_accepted'])
        (self.d / 'evidence' / 'AC3.txt').write_text('changed\n')
        r = json.loads(cli('accept', f, dl, '--json').stdout)
        self.assertEqual(r['findings'], [{'code': 'evidence_mismatch', 'ref': 'AC3', 'detail': 'hash differs'}])
        (self.d / 'evidence' / 'AC3.txt').unlink()
        r = json.loads(cli('accept', f, dl, '--json').stdout)
        self.assertEqual(r['findings'][0]['detail'], 'missing')
        d = json.loads(dl.read_text()); d['results'][0]['date'] = '2027-03-01'
        dl2.write_text(json.dumps(d)); self.assertEqual(cli('accept', f, dl2).returncode, 2)
        d = json.loads(dl.read_text()); d['results'].append(d['results'][0])
        dl2.write_text(json.dumps(d)); self.assertEqual(cli('accept', f, dl2).returncode, 2)

    def test_not_ready_scope_cannot_be_accepted(self):
        self.com('C3')['value'] = '2027-01-01'
        f = self.d / 'pkg.json'; f.write_text(json.dumps(self.p))
        r = cli('accept', f, self.d / 'delivery.json', '--json')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)['findings'], [{'code': 'scope_not_ready', 'ref': 'check', 'detail': '1 check finding(s)'}])

    def test_invalid_inputs_refused(self):
        cases = [lambda p: self.req('R1').update(depends_on=['R2']), lambda p: self.req('R1')['estimate_hours'].update(low=120),
                 lambda p: p['inputs'][0].update(date='2026-10-07'), lambda p: p['assumptions'][1].update(date='2026-10-07'),
                 lambda p: p['proposal']['commitments'][0].update(kind='promise'),
                 lambda p: p['rate'].update(per_hour='-1'), lambda p: p['ambiguities'][0]['resolution'].update(date='2026-12-01'),
                 lambda p: p['capabilities'][0]['demo'].update(path='/etc/hosts'), lambda p: p['requirements'][0]['acceptance'].append({'id': 'AC2', 'criterion': 'x'}),
                 lambda p: p['proposal']['scope'].append('R99'), lambda p: p['engagement'].pop('owner')]
        base = json.dumps(self.p)
        for mutate in cases:
            self.p = json.loads(base); mutate(self.p)
            r = self.check(2)
            self.assertIn('INVALID', r.stderr)
            self.assertIn('Nothing was written', r.stderr)

    def test_out_verify_and_recovery(self):
        f = self.d / 'portal.json'; o = self.tmp / 'res.json'
        self.assertEqual(cli('check', f, '--out', o).returncode, 0)
        r = cli('verify', o, f); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn('IDENTICAL', r.stdout)
        keep = o.read_bytes()
        bad = self.tmp / 'bad.json'; bad.write_text('{')
        self.assertEqual(cli('check', bad, '--out', o).returncode, 2)
        self.assertEqual(o.read_bytes(), keep)
        j = json.loads(keep); j['status'] = 'blocked'; o.write_text(json.dumps(j))
        r = cli('verify', o, f); self.assertEqual(r.returncode, 1); self.assertIn('status', r.stdout)
        o.write_text(keep.decode()[:100]); self.assertEqual(cli('verify', o, f).returncode, 2)
        self.assertEqual(cli('check', f, '--out', f).returncode, 2)
        self.assertEqual(json.loads(f.read_text())['schema'], 'solaris.scope-package/1')
        dl = self.d / 'delivery.json'
        self.assertEqual(cli('accept', f, dl, '--out', dl).returncode, 2)
        self.assertEqual(json.loads(dl.read_text())['schema'], 'solaris.scope-delivery/1')
        a = self.tmp / 'acc.json'
        self.assertEqual(cli('accept', f, dl, '--out', a).returncode, 0)
        self.assertEqual(cli('verify', a, f, dl).returncode, 0)
        self.assertEqual(cli('verify', a, f).returncode, 1)
        self.assertEqual([x.name for x in self.tmp.iterdir() if x.name.startswith('.g31-')], [])

    def test_text_report(self):
        r = cli('check', self.d / 'portal.json')
        self.assertEqual(r.returncode, 0)
        self.assertIn('C3 (date) -> A1, A2, IN1, IN2, IN3, IN4 [conditional on A2]', r.stdout)

    def test_oracle_and_controls(self):
        run = lambda *a: subprocess.run([sys.executable, str(EX / 'scope_oracle.py')] + list(a), capture_output=True, text=True, env=ENV, timeout=600)
        r = run()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.strip().splitlines()[-1], 'ACCEPTED 12/12')
        for t in ('naive_scope.py', 'noop_scope.py'):
            r = run('--tool', str(EX / t))
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout.strip().splitlines()[-1], 'REJECTED 1/12')

    def test_contracts_declare_tool(self):
        c = json.loads((ROOT / 'employees/product-project/business-analyst/capability.contract.json').read_text())
        self.assertIn('scope_acceptance.py', c['dependencies']['scripts'])
        self.assertIn('scope-estimate-acceptance.md', c['dependencies']['references'])
        for role in ('sales-outreach/sales-engineer', 'sales-outreach/proposal-writer'):
            s = (ROOT / 'employees' / role / 'SKILL.md').read_text()
            self.assertIn('scope_acceptance.py', s)


if __name__ == '__main__':
    unittest.main()
