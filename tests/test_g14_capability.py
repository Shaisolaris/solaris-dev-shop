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
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


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
        for target, want in ((TOOL, 'ACCEPTED: 12/12'), (EX / 'naive_stub.py', 'REJECTED'), (EX / 'noop_stub.py', 'REJECTED')):
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
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONDONTWRITEBYTECODE'}
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
