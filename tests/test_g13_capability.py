"""G13: reconciled metrics from dirty CSV (employees/data/data-engineer/csv_reconcile.py).

Real files, real subprocesses. Every dataset is synthetic; the September fixture's expected
numbers are worked out by hand in examples/capabilities/G13/README.md.
"""
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
TOOL = ROOT / 'employees' / 'data' / 'data-engineer' / 'csv_reconcile.py'
G13 = ROOT / 'examples' / 'capabilities' / 'G13'
FIX = G13 / 'fixtures'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def cli(*args, env=ENV):
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True, env=env, timeout=300)
    return p.returncode, p.stdout


def groups(rep, name):
    return {tuple(v for _, v in sorted(g['group'].items())): g['value'] for g in rep['metrics'][name]['groups']}


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix='g13-test-')
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def copy(self, name='september'):
        dst = self.tmp / name
        shutil.copytree(FIX / name, dst)
        return dst

    def contract(self, folder, **changes):
        p = folder / 'contract.json'
        c = json.loads(p.read_text())
        for path, value in changes.items():
            node = c
            keys = path.split('__')
            for k in keys[:-1]:
                node = node[k]
            if value is None:
                node.pop(keys[-1], None)
            else:
                node[keys[-1]] = value
        p.write_text(json.dumps(c))
        return p

    def run_json(self, contract, *extra):
        code, out = cli('reconcile', contract, '--json', *extra)
        return code, json.loads(out)


class SeptemberFixture(Base):
    """Hand-checked answer for the dirty fixture (20 data rows)."""

    @classmethod
    def setUpClass(cls):
        cls.code, out = cli('reconcile', FIX / 'september' / 'contract.json', '--json')
        cls.rep = json.loads(out)

    def test_exact_metrics(self):
        self.assertEqual(self.code, 1)
        self.assertEqual(self.rep['status'], 'reconciled_with_gaps')
        self.assertEqual(groups(self.rep, 'revenue'), {('EUR',): '155.00', ('USD',): '1425.50'})
        self.assertEqual(groups(self.rep, 'orders'), {(): 8})
        self.assertEqual(groups(self.rep, 'revenue_by_region'), {
            ('EUR', '(ambiguous)'): '70.00', ('USD', '(unmatched)'): '45.00', ('USD', 'east'): '1270.00',
            ('EUR', 'west'): '85.00', ('USD', 'west'): '110.50'})

    def test_every_row_in_one_bucket(self):
        cov = self.rep['coverage']
        self.assertEqual((cov['rows_read'], cov['accounted'], cov['included']), (20, 20, 8))
        self.assertTrue(cov['all_rows_accounted'])
        self.assertEqual(cov['rejected'], {'bad_decimal': 1, 'field_count': 1})
        self.assertEqual(cov['missing_required'], {'amount': 1})
        self.assertEqual((cov['late_after_as_of'], cov['excluded_status'], cov['outside_window']), (2, 1, 1))
        self.assertEqual(cov['duplicates'], {'exact_copies': 2, 'superseded_versions': 1, 'rows_unresolved': 2, 'keys_unresolved': 1})
        self.assertEqual(cov['quality_coverage'], '8/13')

    def test_join_never_fans_out(self):
        d = self.rep['dimension']
        self.assertEqual(d['join'], {'matched': 5, 'unmatched': 1, 'ambiguous': 1, 'fact_key_missing': 1})
        self.assertEqual(d['duplicates']['exact_copies'], 1)
        self.assertEqual(d['duplicates']['keys_unresolved'], 1)
        seg = sum(float(v) for v in groups(self.rep, 'revenue_by_region').values())
        tot = sum(float(v) for v in groups(self.rep, 'revenue').values())
        self.assertAlmostEqual(seg, tot)

    def test_naive_inflation_and_controls(self):
        n = self.rep['naive_comparison']
        self.assertEqual(n['sum_every_parsed_row'], {'EUR': '326.50', 'USD': '3135.00'})
        self.assertEqual(n['sum_after_inner_join'], {'EUR': '653.00', 'USD': '3090.00'})
        c = self.rep['controls']
        self.assertEqual((c['expected_rows'], c['actual_rows'], c['expected_sum'], c['actual_sum_of_parsed'], c['match']),
                         (20, 20, '3483.80', '3461.50', False))
        self.assertEqual(self.rep['gaps'], ['rejected_rows', 'missing_required', 'unresolved_duplicates', 'late_rows',
                                            'unmatched_or_missing_join_key', 'ambiguous_dimension_key', 'control_mismatch'])

    def test_honest_statements(self):
        self.assertIn('no warehouse', self.rep['execution'])
        self.assertTrue(self.rep['imputation'].startswith('none'))
        self.assertEqual(self.rep['timezone_for_naive_times'], 'America/Los_Angeles')
        self.assertIn('3 fact rows had timestamps without an offset', self.rep['notes'][0])

    def test_rejects_file_lists_every_excluded_row(self):
        out = self.tmp / 'rej.csv'
        code, _ = cli('reconcile', FIX / 'september' / 'contract.json', '--rejects', out)
        self.assertEqual(code, 1)
        lines = out.read_text().splitlines()
        self.assertEqual(lines[0], 'file,line,reason,detail')
        orders = [l for l in lines[1:] if l.startswith('orders.csv,')]
        self.assertEqual(len(orders), 12)  # 20 read - 8 included
        self.assertIn('orders.csv,4,duplicate_superseded,order_id', lines)
        self.assertIn('orders.csv,10,outside_window,event_time', lines)
        self.assertIn('orders.csv,14,late_after_as_of,loaded_at', lines)
        self.assertIn('orders.csv,21,duplicate_exact,order_id', lines)
        self.assertIn('customers.csv,6,duplicate_conflict_unresolved,customer_id', lines)

    def test_text_render(self):
        code, out = cli('reconcile', FIX / 'september' / 'contract.json')
        self.assertEqual(code, 1)
        self.assertIn('revenue [currency=USD] = 1425.50', out)
        self.assertIn('not a result', out)


class CleanControl(Base):
    def test_clean_reconciles_and_naive_matches(self):
        code, rep = self.run_json(FIX / 'clean' / 'contract.json')
        self.assertEqual((code, rep['status'], rep['gaps']), (0, 'reconciled', []))
        self.assertEqual(groups(rep, 'revenue'), {('EUR',): '13.00', ('USD',): '60.00'})
        self.assertEqual(rep['naive_comparison']['sum_every_parsed_row'], {'EUR': '13.00', 'USD': '60.00'})
        self.assertTrue(rep['controls']['match'])


class Rules(Base):
    def test_nullable_amount_is_skipped_and_counted_not_zero_filled(self):
        f = self.copy()
        code, rep = self.run_json(self.contract(f, facts__required=['currency', 'event_time']))
        self.assertEqual(groups(rep, 'revenue'), {('EUR',): '155.00', ('USD',): '1425.50'})
        self.assertEqual(groups(rep, 'orders'), {(): 9})  # O4 now included, amount unknown
        self.assertEqual(rep['metrics']['revenue']['null_values_skipped'], 1)
        self.assertIn('null_metric_values', rep['gaps'])

    def test_reject_policy_excludes_all_versions(self):
        f = self.copy()
        code, rep = self.run_json(self.contract(f, facts__duplicate_policy='reject'))
        self.assertEqual(groups(rep, 'revenue'), {('EUR',): '70.00', ('USD',): '1425.50'})
        self.assertEqual(rep['coverage']['duplicates']['keys_unresolved'], 2)
        self.assertTrue(rep['coverage']['all_rows_accounted'])

    def test_newer_void_version_cancels_the_order(self):
        f = self.copy()
        p = f / 'orders.csv'
        p.write_bytes(p.read_bytes() + b'O1,C1,100.00,USD,void,2026-09-03T10:00:00Z,2026-09-25T11:00:00Z,2026-09-25T10:00:00Z\r\n')
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '1325.50')
        cov = rep['coverage']
        self.assertEqual((cov['excluded_status'], cov['duplicates']['superseded_versions'], cov['duplicates']['exact_copies']), (2, 2, 2))
        self.assertTrue(cov['all_rows_accounted'])

    def test_newer_version_missing_a_value_is_not_papered_over(self):
        f = self.copy()
        p = f / 'orders.csv'
        p.write_bytes(p.read_bytes() + b'O1,C1,,USD,paid,2026-09-03T10:00:00Z,2026-09-25T11:00:00Z,2026-09-25T10:00:00Z\r\n')
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '1325.50')
        self.assertEqual(rep['coverage']['missing_required'], {'amount': 2})

    def test_without_as_of_the_late_version_wins(self):
        f = self.copy()
        code, rep = self.run_json(self.contract(f, as_of=None))
        # O2 999.00 supersedes 1250.00; O10 500.00 joins the window
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '1674.50')
        self.assertEqual(rep['coverage']['late_after_as_of'], 0)

    def test_window_uses_declared_zone(self):
        f = self.copy()
        code, rep = self.run_json(self.contract(f, timezone='UTC', window={
            'column': 'event_time', 'start': '2026-09-01T00:00:00Z', 'end': '2026-10-01T00:00:00Z'}))
        # In UTC, O7 (03:00Z Sep 1) is inside and O12 (22:00 naive, read as UTC) is still inside
        self.assertEqual(rep['coverage']['outside_window'], 0)
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '1485.50')

    def test_naive_timestamps_use_the_contract_zone(self):
        f = self.copy()
        p = f / 'orders.csv'
        # 03:00 local on Oct 1 is 10:00Z: outside the window; read as UTC it would wrongly be inside
        p.write_bytes(p.read_bytes().replace(b'2026-09-30 22:00:00', b'2026-10-01 03:00:00'))
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '1405.50')
        self.assertEqual(rep['coverage']['outside_window'], 2)

    def test_thousands_grouping_is_strict(self):
        f = self.copy()
        p = f / 'orders.csv'
        p.write_bytes(p.read_bytes().replace(b'"1,250.00"', b'"1,25.00"'))
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual(rep['coverage']['rejected']['bad_decimal'], 2)

    def test_too_many_digits_is_rejected_not_rounded(self):
        f = self.copy()
        p = f / 'orders.csv'
        p.write_bytes(p.read_bytes().replace(b'O8,C9,30.00', b'O8,C9,123456789012345678901.00'))
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual(rep['coverage']['rejected']['bad_decimal'], 2)

    def test_header_case_and_blank_lines(self):
        f = self.copy('clean')
        p = f / 'orders.csv'
        lines = p.read_text().splitlines()
        lines[0] = lines[0].replace('currency', 'Currency')
        p.write_text('\n'.join(lines[:3] + [''] + lines[3:]) + '\n')
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual((code, rep['inputs'][0]['blank_lines_skipped']), (0, 1))

    def test_malformed_quote_and_long_field(self):
        f = self.copy('clean')
        p = f / 'orders.csv'
        p.write_text(p.read_text() + 'A6,K1,' + 'x' * 5000 + ',USD,paid,2026-09-06T10:00:00Z,2026-09-06T11:00:00Z,2026-09-06T10:00:00Z\n'
                     'A7,K1,"1.00,USD\n')
        code, rep = self.run_json(f / 'contract.json')
        self.assertEqual(code, 1)
        self.assertEqual(rep['coverage']['rejected'].get('field_too_long'), 1)
        self.assertEqual(sum(rep['coverage']['rejected'].values()), 2)
        self.assertTrue(rep['coverage']['all_rows_accounted'])


class Invalid(Base):
    def assert_invalid(self, contract, out=None):
        args = ['reconcile', contract, '--json'] + (['--out', out] if out else [])
        code, stdout = cli(*args)
        self.assertEqual(code, 2, stdout)
        self.assertEqual(json.loads(stdout)['status'], 'invalid')
        return json.loads(stdout)['error']

    def test_schema_drift_keeps_previous_report_then_recovers(self):
        f = self.copy()
        out = self.tmp / 'report.json'
        self.assertEqual(cli('reconcile', f / 'contract.json', '--out', out)[0], 1)
        before = out.read_bytes()
        p = f / 'orders.csv'
        good = p.read_bytes()
        p.write_bytes(good.replace(b'currency', b'ccy', 1))
        self.assertIn('schema drift', self.assert_invalid(f / 'contract.json', out))
        self.assertEqual(out.read_bytes(), before)
        p.write_bytes(good)
        self.assertEqual(cli('reconcile', f / 'contract.json', '--out', out)[0], 1)
        self.assertEqual(out.read_bytes(), before)
        self.assertEqual([x.name for x in self.tmp.iterdir() if x.name.endswith('.tmp')], [])

    def test_contract_errors(self):
        f = self.copy()
        raw = (f / 'contract.json').read_text()
        (f / 'contract.json').write_text(raw.replace('{', '{"timezone": "UTC", ', 1))
        self.assertIn('duplicate key', self.assert_invalid(f / 'contract.json'))
        (f / 'contract.json').write_text(raw)
        self.assertIn('timezone', self.assert_invalid(self.contract(f, timezone=None)))
        (f / 'contract.json').write_text(raw)
        self.assertIn('grain', self.assert_invalid(self.contract(f, facts__grain=['nope'])))
        (f / 'contract.json').write_text(raw)
        self.assertIn('numeric', self.assert_invalid(self.contract(f, metrics=[{'name': 'x', 'agg': 'sum', 'column': 'currency'}])))

    def test_paths_are_confined(self):
        f = self.copy()
        raw = (f / 'contract.json').read_text()
        self.assertIn('outside', self.assert_invalid(self.contract(f, facts__file='../clean/orders.csv')))
        (f / 'contract.json').write_text(raw)
        self.assertIn('relative', self.assert_invalid(self.contract(f, facts__file=str(f / 'orders.csv'))))
        (f / 'contract.json').write_text(raw)
        (f / 'orders.csv').rename(f / 'real.csv')
        os.symlink('real.csv', f / 'orders.csv')
        self.assertIn('symlink', self.assert_invalid(f / 'contract.json'))

    def test_out_never_overwrites_an_input(self):
        f = self.copy()
        before = (f / 'orders.csv').read_bytes()
        self.assertIn('overwrite an input', self.assert_invalid(f / 'contract.json', f / 'orders.csv'))
        self.assertEqual((f / 'orders.csv').read_bytes(), before)
        code, out = cli('reconcile', f / 'contract.json', '--out', self.tmp / 'a.json', '--rejects', self.tmp / 'a.json')
        self.assertEqual(code, 2)
        self.assertFalse((self.tmp / 'a.json').exists())


class Determinism(Base):
    def test_rerun_identical_and_order_invariant(self):
        a = cli('reconcile', FIX / 'september' / 'contract.json', '--json')
        b = cli('reconcile', FIX / 'september' / 'contract.json', '--json')
        self.assertEqual(a, b)
        f = self.copy()
        p = f / 'orders.csv'
        text = p.read_bytes().decode('utf-8-sig').split('\r\n')
        head, body = text[0], [x for x in text[1:] if x]
        random.Random(7).shuffle(body)
        p.write_text(head + '\n' + '\n'.join(body) + '\n')
        code, rep = self.run_json(f / 'contract.json')
        ra = json.loads(a[1])
        self.assertEqual(rep['metrics'], ra['metrics'])
        cov_a, cov_b = dict(ra['coverage']), dict(rep['coverage'])
        self.assertEqual(cov_a, cov_b)

    def test_runs_offline(self):
        guard = self.tmp / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text(
            'import socket\n'
            'def _deny(*a, **k):\n    raise RuntimeError("network denied in G13 test")\n'
            'socket.socket = _deny\nsocket.create_connection = _deny\n')
        env = dict(ENV, PYTHONPATH=str(guard))
        code, out = cli('reconcile', FIX / 'september' / 'contract.json', '--json', env=env)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)['coverage']['included'], 8)


class Oracle(Base):
    def oracle(self, tool):
        p = subprocess.run([sys.executable, str(G13 / 'reconcile_oracle.py'), '--tool', tool, '--json',
                            '--rows', '600', '--scale-rows', '6000'], capture_output=True, text=True, env=ENV, timeout=600)
        return json.loads(p.stdout)

    def test_tool_passes_and_stubs_fail(self):
        py = sys.executable
        self.assertEqual(self.oracle(f'"{py}" "{TOOL}"')['passed'], 11)
        self.assertEqual(self.oracle(f'"{py}" "{G13 / "noop_stub.py"}"')['passed'], 0)
        self.assertEqual(self.oracle(f'"{py}" "{G13 / "naive_stub.py"}"')['passed'], 0)


if __name__ == '__main__':
    unittest.main()
