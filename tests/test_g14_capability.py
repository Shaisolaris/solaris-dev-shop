"""G14: invoice, payment and credit reconciliation, recognized revenue versus cash
(employees/leadership/cfo/cash_revenue_reconcile.py). Real files and subprocesses; books are synthetic.
Expected values are worked by hand (README table) or from the oracle's independent journal."""
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
CFO = ROOT / 'employees' / 'leadership' / 'cfo'
TOOL = CFO / 'cash_revenue_reconcile.py'
EX = ROOT / 'examples' / 'capabilities' / 'G14'
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


def rep(path, want_rc):
    p = cli('reconcile', path, '--json')
    assert p.returncode == want_rc, (p.returncode, p.stderr)
    return json.loads(p.stdout)


def oracle_module():
    sys.path.insert(0, str(EX))
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import cash_oracle
        return cash_oracle
    finally:
        sys.path.pop(0)
        sys.dont_write_bytecode = old


class G14Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g14-test-'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_oracle_accepts_tool_and_rejects_controls(self):
        for target, want in ((TOOL, 'ACCEPTED: 13/13'), (EX / 'naive_stub.py', 'REJECTED'), (EX / 'noop_stub.py', 'REJECTED')):
            p = subprocess.run([sys.executable, str(EX / 'cash_oracle.py')] + (['--quick'] if target != TOOL else []) + ['--', sys.executable, str(target)],
                               capture_output=True, text=True, env=ENV, timeout=600)
            self.assertIn(want, p.stdout.strip().splitlines()[-1], (target.name, p.stdout[-1500:], p.stderr[-800:]))

    def test_clean_control(self):
        r = rep(FIX / 'clean' / 'package.json', 0)
        self.assertEqual(list(r['currencies']), ['USD'])
        u = r['currencies']['USD']
        self.assertEqual((u['billed'], u['recognized_revenue'], u['net_cash'], u['closing']['ar_net']), ('2250.50', '2250.50', '2250.50', '0.00'))
        self.assertEqual(r['result'], 'reconciled')

    def test_september_hand_worked_values(self):
        r = rep(FIX / 'september' / 'package.json', 1)
        u = r['currencies']['USD']
        self.assertEqual({k: u[k] for k in ('billed', 'credit_notes', 'recognized_revenue', 'cash_received', 'refunds_paid', 'net_cash')},
                         {'billed': '2550.00', 'credit_notes': '150.00', 'recognized_revenue': '2000.00', 'cash_received': '2195.00',
                          'refunds_paid': '0.00', 'net_cash': '2195.00'})
        self.assertEqual(u['opening']['ar_net'], '300.00')
        self.assertEqual(u['closing'], {'ar_net': '700.00', 'ar_owed': '700.00', 'customer_credit': '0.00', 'deferred': '400.00',
                                        'unbilled': '0.00', 'unapplied': '195.00'})
        e = r['currencies']['EUR']
        self.assertEqual((e['recognized_revenue'], e['cash_received'], e['refunds_paid'], e['closing']['ar_net']), ('400.00', '450.00', '50.00', '0.00'))
        self.assertEqual(r['currencies']['GBP']['closing']['unapplied'], '90.00')
        for c in r['currencies'].values():
            self.assertTrue(all(ch['ok'] for ch in c['checks'].values()))
        self.assertTrue(all(c['ok'] for c in r['controls'].values()))

    def test_exceptions_named(self):
        ex = rep(FIX / 'september' / 'package.json', 1)['exceptions']
        self.assertEqual([x['id'] for x in ex['late']], ['P10'])
        self.assertEqual([x['id'] for x in ex['conflicting_versions']], ['P12'])
        self.assertEqual(sorted((x['id'], x['reason']) for x in ex['unapplied']),
                         [('P11', 'invoice_void'), ('P8', 'unknown_invoice'), ('P9', 'currency_mismatch')])
        self.assertEqual([x['id'] for x in ex['undelivered']], ['I4'])

    def test_over_refund_and_over_credit_are_exceptions(self):
        d = self.tmp / 'k14'
        d.mkdir()
        (d / 'invoices.csv').write_text('invoice_id,customer_id,currency,amount,issued_at,delivered_at,status,loaded_at\n'
                                        'K1,c1,USD,100.00,2026-09-03T00:00:00Z,2026-09-04T00:00:00Z,issued,2026-09-03T00:00:00Z\n'
                                        'K2,c2,USD,80.00,2026-09-03T00:00:00Z,2026-09-04T00:00:00Z,issued,2026-09-03T00:00:00Z\n'
                                        'K3,c3,USD,60.00,2026-09-03T00:00:00Z,2026-09-04T00:00:00Z,issued,2026-09-03T00:00:00Z\n')
        (d / 'payments.csv').write_text('payment_id,invoice_id,currency,amount,received_at,loaded_at\n'
                                        'KP1,K1,USD,100.00,2026-09-05T00:00:00Z,2026-09-05T00:00:00Z\n'
                                        'KP2,K2,USD,80.00,2026-09-05T00:00:00Z,2026-09-05T00:00:00Z\n'
                                        'KP3,K3,USD,60.00,2026-10-01T12:00:00Z,2026-10-01T12:00:00Z\n')  # after the period, before as_of
        (d / 'credits.csv').write_text('credit_id,invoice_id,kind,currency,amount,issued_at,loaded_at\n'
                                       'KR1,K1,refund,USD,500.00,2026-09-07T00:00:00Z,2026-09-07T00:00:00Z\n'
                                       'KC1,K1,credit_note,USD,300.00,2026-09-08T00:00:00Z,2026-09-08T00:00:00Z\n'
                                       'KR2,K2,refund,USD,80.00,2026-09-07T00:00:00Z,2026-09-07T00:00:00Z\n'
                                       'KR3,K3,refund,USD,15.00,2026-09-20T00:00:00Z,2026-09-20T00:00:00Z\n')  # refund before its payment: timing, not an excess
        pkg = json.loads((FIX / 'clean' / 'package.json').read_text())
        pkg.pop('bank', None)
        pkg['invoices'] = {'file': 'invoices.csv'}
        (d / 'package.json').write_text(json.dumps(pkg))
        r = rep(d / 'package.json', 1)
        self.assertEqual(r['exceptions']['over_refunded'], [{'id': 'K1', 'currency': 'USD', 'paid': '100.00', 'refunded': '500.00', 'excess': '400.00'}])
        self.assertEqual(r['exceptions']['over_credited'], [{'id': 'K1', 'currency': 'USD', 'invoice_amount': '100.00', 'credit_notes': '300.00', 'excess': '200.00'}])
        self.assertEqual(r['result'], 'reconciled_with_exceptions')
        self.assertEqual(r['currencies']['USD']['recognized_revenue'], '-60.00')  # 100 - 300 + 80 + 60, as booked

    def test_documented_reasons_match_emitted(self):
        doc = (CFO / 'cash-revenue-reconciliation.md').read_text()
        r = rep(FIX / 'september' / 'package.json', 1)
        emitted = {x['reason'] for k in ('unapplied', 'unlinked_credits') for x in r['exceptions'][k]}
        self.assertTrue(emitted)
        for why in emitted:
            self.assertIn('`%s`' % why, doc)
        src = TOOL.read_text()
        for why in ('no_invoice_reference', 'unknown_invoice', 'currency_mismatch', 'credit_note_before_invoice'):
            self.assertIn('"%s"' % why, src)
            self.assertIn('`%s`' % why, doc)

    def test_matches_independent_journal(self):
        o = oracle_module()
        b = o.random_book(random.Random(7), n=200)
        p = o.write_book(self.tmp / 'book', b)
        r = rep(p, 1)
        self.assertEqual(o.view(r), o.journal(b))

    def test_invalid_refused_previous_report_kept(self):
        out = self.tmp / 'r.json'
        cli('reconcile', FIX / 'september' / 'package.json', '--out', out)
        before = out.read_bytes()
        d = self.tmp / 'drift'
        shutil.copytree(FIX / 'september', d)
        (d / 'credits.csv').write_text((d / 'credits.csv').read_text().replace('kind,', 'type,', 1))
        p = cli('reconcile', d / 'package.json', '--out', out)
        self.assertEqual(p.returncode, 2)
        self.assertIn('kind', p.stderr)
        self.assertEqual(out.read_bytes(), before)

    def test_no_bytecode_left_in_data_engineer(self):
        root = self.tmp / 'repo'
        for rel in ('employees/leadership/cfo', 'employees/data/data-engineer', 'examples/capabilities/G14'):
            shutil.copytree(ROOT / rel, root / rel, ignore=shutil.ignore_patterns('__pycache__'))
        env = {name: os.environ[name] for name in (
                  'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                  'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                  'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                  'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                  'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                  'GITHUB_ACTIONS',
              ) if name in os.environ}
        p = subprocess.run([sys.executable, str(root / 'employees/leadership/cfo/cash_revenue_reconcile.py'), 'reconcile',
                            str(root / 'examples/capabilities/G14/fixtures/clean/package.json')], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(str(x.relative_to(root)) for x in root.rglob('__pycache__')), [])

    def test_contracts_point_at_real_evidence(self):
        c = json.loads((CFO / 'capability.contract.json').read_text())
        self.assertIn('cash_revenue_reconcile.py', c['dependencies']['scripts'])
        self.assertIn('cash-revenue-reconciliation.md', c['dependencies']['references'])
        self.assertNotIn('leadership-operations/cfo', json.dumps(c))
        self.assertIn('cash-revenue-reconciliation.md', json.loads((CFO / 'plugin.json').read_text())['references'])
        self.assertIn('cash_revenue_reconcile.py', (ROOT / 'employees/data/data-analyst/SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()
