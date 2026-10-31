"""G32: consent-aware customer success follow-through (employees/sales-outreach/customer-success/followthrough.py).
Real files, processes and locks on a synthetic account; expected outcomes are worked in the G32 README."""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees' / 'sales-outreach' / 'customer-success' / 'followthrough.py'
EX = ROOT / 'examples' / 'capabilities' / 'G32'
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')
N1, N2, N3 = '2026-10-02T12:00:00-07:00', '2026-10-05T12:00:00-07:00', '2026-10-08T12:00:00-07:00'
PRIYA, MORGAN = 'Priya (customer success lead, synthetic)', 'Morgan (customer success, synthetic)'


class G32Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g32-test-'))
        self.acc = json.loads((EX / 'fixtures' / 'account.json').read_text())
        self.ev = [json.loads(l) for l in (EX / 'fixtures' / 'events.jsonl').read_text().splitlines() if l.strip()]
        self.s = self.tmp / 'state'

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def files(self, extra=()):
        a = self.tmp / 'account.json'; a.write_text(json.dumps(self.acc))
        e = self.tmp / 'events.jsonl'; e.write_text(''.join(json.dumps(x) + '\n' for x in list(self.ev) + list(extra)))
        return a, e

    def run_(self, now, worker='w1', rc=0, *extra, events=()):
        a, e = self.files(events)
        r = subprocess.run([sys.executable, str(TOOL), 'run', str(self.s), '--account', str(a), '--events', str(e), '--now', now,
                            '--worker', worker, '--json'] + list(extra), capture_output=True, text=True, env=ENV, timeout=120)
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return json.loads(r.stdout) if rc == 0 else r

    def drafts(self):
        out = {}
        for f in (self.s / 'drafts').glob('*.json'):
            d = json.loads(f.read_text())
            self.assertNotIn((d['contact'], d['action'], d['trigger']), out)
            out[(d['contact'], d['action'], d['trigger'])] = d
        return out

    def acts(self, r, k):
        return sorted((x['contact'], x['action']) for x in r[k])

    def test_three_runs_worked_figures(self):
        r1 = self.run_(N1)
        self.assertEqual(self.acts(r1, 'drafted'), [('c-ana', 'welcome'), ('c-ben', 'ack'), ('c-ben', 'welcome'), ('c-dee', 'welcome')])
        self.assertEqual(self.acts(r1, 'suppressed'), [('c-cy', 'checkin'), ('c-cy', 'training'), ('c-cy', 'welcome')])
        r2 = self.run_(N2, 'w2')
        self.assertEqual(self.acts(r2, 'drafted'), [('c-ben', 'checkin'), ('c-ben', 'nudge')])
        self.assertEqual(self.acts(r2, 'cancelled'), [('c-ana', 'checkin'), ('c-ben', 'nudge')])
        self.assertEqual(self.acts(r2, 'withdrawn'), [('c-dee', 'welcome')])
        self.assertEqual(self.acts(r2, 'reassigned'), [('c-ana', 'welcome'), ('c-ben', 'ack'), ('c-ben', 'welcome')])
        r3 = self.run_(N3)
        self.assertEqual(self.acts(r3, 'drafted'), [('c-ana', 'training'), ('c-ben', 'feedback'), ('c-ben', 'training')])
        self.assertEqual(self.acts(r3, 'withdrawn'), [('c-ben', 'nudge')])
        self.assertEqual([n['note'] for n in r3['notes']], ['consent_review_required'])
        self.assertEqual(r3['suppressed_contacts'], ['c-dee'])
        d = self.drafts()
        self.assertEqual(len(d), 9)
        self.assertEqual(sorted(k for k, v in d.items() if v['status'] == 'withdrawn'), [('c-ben', 'nudge', 'E08'), ('c-dee', 'welcome', 'E04')])
        self.assertTrue(all(v['owner'] == PRIYA for v in d.values() if v['status'] == 'draft'))
        self.assertEqual(r1['sent'] + r2['sent'] + r3['sent'], 0)

    def test_draft_contents(self):
        self.run_(N1)
        d = self.drafts()
        w = d[('c-ana', 'welcome', 'E01')]
        self.assertEqual((w['status'], w['send'], w['owner'], w['kind']), ('draft', 'not performed; a person reviews and sends', MORGAN, 'onboarding'))
        self.assertIn('unsubscribe', w['body'])
        self.assertNotIn('unsubscribe', d[('c-ben', 'ack', 'E05')]['body'])
        self.assertEqual(w['due'], '2026-10-01T16:00:00+00:00')
        self.assertEqual(len(w['key']), 64)

    def test_rerun_and_redelivery_never_duplicate(self):
        for n in (N1, N2, N3):
            self.run_(n)
        before = {k: v['status'] for k, v in self.drafts().items()}
        r = self.run_(N3, 'w9', events=self.ev[:6])
        self.assertEqual(r['drafted'], [])
        self.assertEqual(len(r['duplicate_suppressed']), 7)
        self.assertEqual({k: v['status'] for k, v in self.drafts().items()}, before)
        keys = [json.loads(l)['key'] for l in (self.s / 'ledger.jsonl').read_text().splitlines() if json.loads(l)['event'] == 'drafted']
        self.assertEqual(len(keys), len(set(keys)))

    def test_conflicting_event_id_refused(self):
        bad = dict(self.ev[0]); bad['contact'] = 'c-ben'
        r = self.run_(N1, 'w1', 2, events=[bad])
        self.assertIn('appears twice with different content', r.stderr)
        self.assertFalse(self.s.exists())

    def test_marketing_opt_out_keeps_support_and_stays_suppressed(self):
        extra = [{'id': 'E30', 'type': 'ticket_opened', 'contact': 'c-dee', 'thread': 'T5', 'at': '2026-10-07T09:00:00-07:00'},
                 {'id': 'E31', 'type': 'ticket_closed', 'contact': 'c-dee', 'thread': 'T5', 'at': '2026-10-07T10:00:00-07:00'}]
        r = self.run_(N3, events=extra)
        d = self.drafts()
        self.assertIn(('c-dee', 'ack', 'E30'), d)
        self.assertNotIn(('c-dee', 'feedback', 'E31'), d)
        self.assertIn(('c-dee', 'feedback'), self.acts(r, 'suppressed'))
        self.assertNotIn(('c-dee', 'welcome', 'E04'), d)

    def test_opt_out_all_and_hard_bounce(self):
        extra = [{'id': 'E30', 'type': 'opt_out', 'contact': 'c-ben', 'scope': 'all', 'at': '2026-10-04T09:00:00-07:00'},
                 {'id': 'E31', 'type': 'bounce', 'contact': 'c-ana', 'kind': 'soft', 'at': '2026-10-04T09:00:00-07:00'}]
        self.run_(N1, events=extra)
        r = self.run_(N3, events=extra)
        d = self.drafts()
        self.assertTrue(all(v['status'] == 'withdrawn' for k, v in d.items() if k[0] == 'c-ben'))
        self.assertEqual(d[('c-ben', 'ack', 'E05')]['withdrawn_reason'], 'E30 (opt-out all)')
        self.assertEqual(d[('c-ana', 'welcome', 'E01')]['status'], 'draft')
        extra.append({'id': 'E32', 'type': 'bounce', 'contact': 'c-ana', 'kind': 'hard', 'at': '2026-10-08T09:00:00-07:00'})
        extra.append({'id': 'E33', 'type': 'opt_in', 'contact': 'c-ana', 'at': '2026-10-08T10:00:00-07:00'})
        r = self.run_(N3, events=extra)
        self.assertEqual(self.drafts()[('c-ana', 'welcome', 'E01')]['withdrawn_reason'], 'E32 (hard bounce)')
        self.assertIn('c-ana', [n['contact'] for n in r['notes'] if n['note'] == 'consent_review_required'])
        self.assertEqual(r['drafted'], [])

    def test_opt_in_without_prior_opt_out_is_not_flagged(self):
        r = self.run_(N1, events=[{'id': 'E30', 'type': 'opt_in', 'contact': 'c-ana', 'at': '2026-10-01T10:00:00-07:00'}])
        self.assertEqual(r['notes'], [])

    def test_future_events_ignored_until_due(self):
        r = self.run_('2026-10-01T09:07:00-07:00')
        self.assertEqual(self.acts(r, 'drafted'), [('c-ana', 'welcome'), ('c-ben', 'welcome')])
        self.assertIn(('c-ana', 'checkin'), self.acts(r, 'scheduled'))

    def test_reply_cancels_nudge_but_not_training(self):
        r = self.run_(N3)
        self.assertIn(('c-ana', 'checkin'), self.acts(r, 'cancelled'))
        self.assertIn(('c-ana', 'training'), self.acts(r, 'drafted'))
        self.assertIn(('c-ben', 'nudge'), self.acts(r, 'cancelled'))
        self.assertEqual([x['reason'] for x in r['cancelled'] if x['action'] == 'nudge'], ['customer replied', 'ticket closed'])

    def test_reply_before_response_does_not_cancel(self):
        ev = [{'id': 'E30', 'type': 'reply_received', 'contact': 'c-ben', 'thread': 'T7', 'at': '2026-10-02T09:00:00-07:00'},
              {'id': 'E31', 'type': 'agent_response', 'contact': 'c-ben', 'thread': 'T7', 'at': '2026-10-02T10:00:00-07:00'}]
        self.run_(N2, events=ev)
        self.assertIn(('c-ben', 'nudge', 'E31'), self.drafts())

    def test_crash_after_draft_and_after_ledger_resume(self):
        self.run_(N1, 'w1', 75, '--fail-at', 'drafted')
        self.assertEqual(len(list((self.s / 'drafts').glob('*.json'))), 1)
        self.assertFalse((self.s / 'journal.jsonl').exists())
        r = self.run_(N1, 'w2')
        self.assertEqual(len(r['drafted']), 4)
        self.run_(N2, 'w1', 75, '--fail-at', 'ledgered')
        r = self.run_(N2, 'w2')
        self.assertEqual(len(r['drafted']), 1)
        self.assertEqual(len(self.drafts()), 6)

    def test_lock_held_writes_nothing(self):
        self.s.mkdir()
        fd = os.open(str(self.s / '.lock'), os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            r = self.run_(N1, 'w1', 4)
            self.assertIn('BUSY', r.stderr)
        finally:
            os.close(fd)
        self.assertEqual(sorted(p.name for p in self.s.iterdir()), ['.lock'])

    def test_torn_ledger_and_tampered_journal(self):
        self.run_(N1)
        with open(self.s / 'ledger.jsonl', 'ab') as f:
            f.write(b'{"event": "drafted", "ke')
        self.run_(N2)
        lines = (self.s / 'ledger.jsonl').read_text().splitlines()
        self.assertEqual(sum(1 for l in lines if l.startswith('{"event": "drafted", "ke') and not l.endswith('}')), 1)
        self.assertEqual(len([l for l in lines if '"drafted"' in l and l.endswith('}')]), 6)
        j = self.s / 'journal.jsonl'
        j.write_text(j.read_text().replace('"worker":"w1"', '"worker":"wX"', 1))
        r = self.run_(N3, 'w1', 2)
        self.assertIn('does not verify', r.stderr)

    def test_other_account_state_refused(self):
        self.run_(N1)
        self.acc['account_id'] = 'another'
        self.assertIn('belongs to account northwind-clinic', self.run_(N2, 'w1', 2).stderr)

    def test_missing_draft_file_is_not_redrafted(self):
        self.run_(N1)
        f = [p for p in (self.s / 'drafts').glob('*-ack.json')][0]
        f.unlink()
        r = self.run_(N1)
        self.assertEqual(r['drafted'], [])
        self.assertEqual([n['note'] for n in r['notes']], ['draft_file_missing'])
        self.assertFalse(f.exists())

    def test_invalid_inputs(self):
        cases = [lambda: self.acc.update(schema='x'), lambda: self.acc.update(owner=' '), lambda: self.acc['contacts'][0].update(consent='yes'),
                 lambda: self.acc['contacts'].append(dict(self.acc['contacts'][0])), lambda: self.ev.append({'id': 'E9', 'type': 'sent', 'contact': 'c-ana', 'at': N1}),
                 lambda: self.ev.append({'id': 'E9', 'type': 'signup', 'contact': 'c-zz', 'at': N1}),
                 lambda: self.ev.append({'id': 'E9', 'type': 'signup', 'contact': 'c-ana', 'at': '2026-10-01T09:00:00'}),
                 lambda: self.ev.append({'id': 'E9', 'type': 'opt_out', 'contact': 'c-ana', 'at': N1}),
                 lambda: self.ev.append({'id': 'E9', 'type': 'bounce', 'contact': 'c-ana', 'at': N1}),
                 lambda: self.ev.append({'id': 'E9', 'type': 'agent_response', 'contact': 'c-ana', 'at': N1}),
                 lambda: self.ev.append({'id': 'E9', 'type': 'owner_change', 'at': N1})]
        acc, ev = json.dumps(self.acc), json.dumps(self.ev)
        for mutate in cases:
            self.acc, self.ev = json.loads(acc), json.loads(ev)
            mutate()
            r = self.run_(N1, 'w1', 2)
            self.assertIn('Nothing was written', r.stderr)
            self.assertFalse(self.s.exists())
        self.acc, self.ev = json.loads(acc), json.loads(ev)
        self.run_(N1, 'bad name', 2)

    def test_second_signup_and_withdrawn_never_redrafted(self):
        self.run_(N1)
        self.run_(N2, events=[{'id': 'E30', 'type': 'signup', 'contact': 'c-ana', 'at': '2026-10-01T10:00:00-07:00'}])
        self.assertEqual(sorted(k for k in self.drafts() if k[0] == 'c-ana'), [('c-ana', 'welcome', 'E01')])
        self.ev = [e for e in self.ev if e['id'] != 'E09']  # the opt-out line is later lost from the log
        r = self.run_(N2)
        # Durable person_suppressions keep the opt-out; no new draft for c-dee, withdrawn file kept.
        self.assertEqual(r['drafted'], [])
        self.assertEqual(self.drafts()[('c-dee', 'welcome', 'E04')]['status'], 'withdrawn')
        self.assertIn(('c-dee', 'welcome'), self.acts(r, 'suppressed') + self.acts(r, 'withdrawn'))

    def test_status(self):
        self.run_(N1, 'w1'); self.run_(N2, 'w2')
        r = subprocess.run([sys.executable, str(TOOL), 'status', str(self.s)], capture_output=True, text=True, env=ENV)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), 'status: 2 run(s); last by w2 at 2026-10-05T19:00:00+00:00; 5 open draft(s), 1 withdrawn; sent 0')

    def test_oracle_and_controls(self):
        run = lambda *a: subprocess.run([sys.executable, str(EX / 'followthrough_oracle.py')] + list(a), capture_output=True, text=True, env=ENV, timeout=600)
        r = run()
        self.assertEqual(r.stdout.strip().splitlines()[-1], 'ACCEPTED 11/11', r.stdout)
        for t in ('naive_followthrough.py', 'noop_followthrough.py'):
            self.assertEqual(run('--tool', str(EX / t)).stdout.strip().splitlines()[-1], 'REJECTED 1/11')

    def test_one_person_one_consent(self):
        # r2 (from the M32 validator's proposed patch, generalized): a second record for the same person is refused
        opt_out = {'id': 'E40', 'type': 'opt_out', 'contact': 'c-ana', 'scope': 'all', 'at': '2026-10-01T08:00:00-07:00'}
        signup2 = {'id': 'E41', 'type': 'signup', 'contact': 'c-ana2', 'at': '2026-10-01T09:00:00-07:00'}
        base = json.loads(json.dumps(self.acc))
        for h in ('contact-ana', ' Contact-Ana', 'CONTACT-ANA\t', '\uff43ontact-ana'):
            self.acc = json.loads(json.dumps(base))
            self.acc['contacts'].append({'id': 'c-ana2', 'name': 'Ana', 'handle': h, 'consent': 'granted'})
            r = self.run_(N1, 'w1', 2, events=[opt_out, signup2])
            self.assertIn('merge the duplicate import first', r.stderr + r.stdout)
            self.assertIn('c-ana and contacts.c-ana2', r.stderr + r.stdout)
            self.assertFalse((self.s / 'drafts').is_dir() and list((self.s / 'drafts').glob('*.json')))
        for extra in ({}, {'handle': ''}, {'handle': ' \t '}, {'handle': 7}):
            self.acc = json.loads(json.dumps(base))
            self.acc['contacts'].append(dict({'id': 'c-eve', 'name': 'Eve', 'consent': 'granted'}, **extra))
            r = self.run_(N1, 'w1', 2)
            self.assertIn('contacts.c-eve.handle is required', r.stderr + r.stdout)
        # different people whose handles only look alike are both kept
        self.acc = json.loads(json.dumps(base))
        self.acc['contacts'].append({'id': 'c-ana2', 'name': 'Ana B', 'handle': 'contact-ana-2', 'consent': 'granted'})
        r = self.run_(N1, 'w1', 0, events=[signup2])
        self.assertIn(('c-ana2', 'welcome'), self.acts(r, 'drafted'))

    def test_suppression_follows_the_person(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('g32_ft', str(TOOL)); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(m.person_key('  Contact\u3000 ANA\n'), m.person_key('contact ana'))
        self.assertNotEqual(m.person_key('contact-ana'), m.person_key('contact-ana2'))
        t0 = m._time('2026-10-01T08:00:00-07:00', 't'); now = m._time(N1, 'n')
        contacts = {'c-ana': {'id': 'c-ana', 'name': 'Ana', 'consent': 'granted', '_person': 'p'},
                    'c-ana2': {'id': 'c-ana2', 'name': 'Ana', 'consent': 'granted', '_person': 'p'},
                    'c-ben': {'id': 'c-ben', 'name': 'Ben', 'consent': 'granted', '_person': 'q'}}
        ev = [{'id': 'X1', 'type': 'opt_out', 'contact': 'c-ana', 'scope': 'all', '_t': t0},
              {'id': 'X2', 'type': 'signup', 'contact': 'c-ana2', '_t': t0 + m.dt.timedelta(hours=1)},
              {'id': 'X3', 'type': 'signup', 'contact': 'c-ben', '_t': t0 + m.dt.timedelta(hours=1)},
              {'id': 'X4', 'type': 'opt_in', 'contact': 'c-ana2', '_t': t0 + m.dt.timedelta(hours=2)}]
        acts, notes, _ = m.derive({'owner': 'o', 'account_id': 'a'}, contacts, ev, now)
        self.assertEqual({x['state'] for x in acts if x['contact'] == 'c-ana2'}, {'suppressed'})
        self.assertTrue(all('X1' in x['reason'] for x in acts if x['contact'] == 'c-ana2'))
        self.assertNotIn('suppressed', {x['state'] for x in acts if x['contact'] == 'c-ben'})
        self.assertEqual([(n['note'], n['contact']) for n in notes], [('consent_review_required', 'c-ana2')])

    def test_contracts_declare_tool(self):
        c = json.loads((ROOT / 'employees/sales-outreach/customer-success/capability.contract.json').read_text())
        self.assertIn('followthrough.py', c['dependencies']['scripts'])
        self.assertIn('consent-follow-through.md', c['dependencies']['references'])
        for role in ('sales-outreach/outreach-specialist', 'marketing/email-specialist'):
            self.assertIn('followthrough.py', (ROOT / 'employees' / role / 'SKILL.md').read_text())


    def test_format_chars_and_durable_suppression(self):
        """Format characters do not mint a new person; CRM merge without opt-out history stays suppressed."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('g32_ft', str(TOOL)); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(m.person_key('ana@clinic.example'), m.person_key('ana\u200b@clinic.example'))
        self.assertEqual(m.person_key('ana@clinic.example'), m.person_key('ana\u00ad@clinic.example'))
        self.acc = {"schema": "solaris.cs-account/1", "account_id": "ac1", "owner": "ops",
                    "contacts": [{"id": "c-ana", "name": "Ana", "handle": "ana@clinic.example", "consent": "granted"}]}
        self.ev = [
            {"id": "e1", "type": "signup", "contact": "c-ana", "at": "2026-05-01T00:00:00+00:00"},
            {"id": "e2", "type": "opt_out", "contact": "c-ana", "scope": "all", "at": "2026-05-02T00:00:00+00:00"},
        ]
        r1 = self.run_("2026-06-01T00:00:00+00:00")
        self.assertEqual(r1["drafted"], [])
        self.assertEqual(r1["suppressed_contacts"], ["c-ana"])
        self.assertTrue((self.s / "person_suppressions.jsonl").is_file())
        self.acc = {"schema": "solaris.cs-account/1", "account_id": "ac1", "owner": "ops",
                    "contacts": [{"id": "c-ana2", "name": "Ana", "handle": "ana\u200b@clinic.example", "consent": "granted"}]}
        self.ev = [{"id": "e3", "type": "signup", "contact": "c-ana2", "at": "2026-05-01T00:00:00+00:00"}]
        r2 = self.run_("2026-06-01T00:00:00+00:00", "w2")
        self.assertEqual(r2["drafted"], [])
        self.assertEqual(r2["suppressed_contacts"], ["c-ana2"])


    def test_invisible_characters_and_damaged_suppression_file(self):
        """M32 r3 P3-1: every invisible character is ignored in a handle; P3-2: a damaged suppression file refuses."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('g32_ft', str(TOOL)); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for ch in ('\u034f', '\ufe0f', '\u3164', '\u2800', '\u115f', '\u180b', '\U000e0041'):
            self.assertEqual(m.person_key('crm:ana-clinic'), m.person_key('crm:an' + ch + 'a-clinic'), repr(ch))
        self.assertNotEqual(m.person_key('crm:ana-clinic'), m.person_key('crm:\u0430na-clinic'))  # look-alikes not matched
        self.acc = {"schema": "solaris.cs-account/1", "account_id": "ac1", "owner": "ops",
                    "contacts": [{"id": "c-ana", "name": "Ana", "handle": "crm:ana-clinic", "consent": "granted"}]}
        self.ev = [{"id": "e1", "type": "signup", "contact": "c-ana", "at": "2026-05-01T00:00:00+00:00"},
                   {"id": "e2", "type": "opt_out", "contact": "c-ana", "scope": "all", "at": "2026-05-02T00:00:00+00:00"}]
        self.assertEqual(self.run_("2026-06-01T00:00:00+00:00")["drafted"], [])
        # the CRM merge drops the opt-out history and the handle gains a combining grapheme joiner: still suppressed
        self.acc = {"schema": "solaris.cs-account/1", "account_id": "ac1", "owner": "ops",
                    "contacts": [{"id": "c-ana2", "name": "Ana", "handle": "crm:an\u034fa-clinic", "consent": "granted"}]}
        self.ev = [{"id": "e3", "type": "signup", "contact": "c-ana2", "at": "2026-05-01T00:00:00+00:00"}]
        self.assertEqual(self.run_("2026-06-01T00:00:00+00:00")["drafted"], [])
        sup = self.s / "person_suppressions.jsonl"
        good = sup.read_bytes()
        for damage in (b"{not json\n", b'{"person": "x"}\n', b"[1, 2]\n", b'{"person": "p", "scope": "all", "reason": "r"}'):
            sup.write_bytes(good + damage)
            before = {f: f.read_bytes() for f in self.s.rglob('*') if f.is_file()}
            r = self.run_("2026-06-02T00:00:00+00:00", 'w1', 2)
            self.assertIn("person_suppressions.jsonl", r.stderr + r.stdout, damage)
            self.assertEqual({f: f.read_bytes() for f in self.s.rglob('*') if f.is_file()}, before, damage)
        sup.write_bytes(good)
        self.assertEqual(self.run_("2026-06-02T00:00:00+00:00")["drafted"], [])

    def test_stored_suppression_follows_the_handle_as_documented(self):
        """M32 r3 P4 (G32 r5): the stored suppression is keyed by handle. A merge that keeps the handle stays suppressed;
        a merge that changes the handle and drops the opt-out history is a new person, and the doc says so."""
        doc = (TOOL.parent / 'consent-follow-through.md').read_text()
        self.assertIn('it follows the handle, not the record id', doc)
        self.acc = {"schema": "solaris.cs-account/1", "account_id": "ac1", "owner": "ops",
                    "contacts": [{"id": "c-bo", "name": "Bo", "handle": "crm:bo-clinic", "consent": "granted"}]}
        self.ev = [{"id": "e1", "type": "signup", "contact": "c-bo", "at": "2026-05-01T00:00:00+00:00"},
                   {"id": "e2", "type": "opt_out", "contact": "c-bo", "scope": "all", "at": "2026-05-02T00:00:00+00:00"}]
        self.assertEqual(self.run_("2026-06-01T00:00:00+00:00")["drafted"], [])
        self.acc["contacts"] = [{"id": "c-bo-merged", "name": "Bo", "handle": "CRM:BO-Clinic", "consent": "granted"}]
        self.ev = [{"id": "e3", "type": "signup", "contact": "c-bo-merged", "at": "2026-05-01T00:00:00+00:00"}]
        r = self.run_("2026-06-01T00:00:00+00:00", "w2")
        self.assertEqual(r["drafted"], [])
        self.assertEqual(r["suppressed_contacts"], ["c-bo-merged"])
        self.acc["contacts"] = [{"id": "c-bo-new", "name": "Bo", "handle": "crm:bo-new-clinic", "consent": "granted"}]
        self.ev = [{"id": "e4", "type": "signup", "contact": "c-bo-new", "at": "2026-05-01T00:00:00+00:00"}]
        r = self.run_("2026-06-01T00:00:00+00:00", "w3")
        self.assertEqual(r["suppressed_contacts"], [])
        self.assertIn(("c-bo-new", "welcome"), self.acts(r, "drafted"))

if __name__ == '__main__':
    unittest.main()
