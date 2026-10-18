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


HDR = 'order_id,customer_id,amount,currency,status,event_time,loaded_at,updated_at'


def row(i, cust='K1', amt='10.00', cur='USD', st='paid', ev='2026-09-10T12:00:00Z', la='2026-09-10T13:00:00Z', up='2026-09-10T12:00:00Z'):
    return ','.join([i, cust, amt, cur, st, ev, la, up])


BASE_ROWS = [row('A1', 'K1', '10.00'), row('A2', 'K2', '20.00'), row('A3', 'K1', '5.25', 'EUR')]
REPLACE_FAULT = (
    'import os, sys\n'
    '_real = os.replace\n'
    'def _replace(src, dst, *a, **k):\n'
    '    if str(dst).endswith(os.environ["G13_FAIL_REPLACE"]) and ".keep" not in str(src):\n'
    '        raise PermissionError(13, "Permission denied (injected)")\n'
    '    return _real(src, dst, *a, **k)\n'
    'os.replace = _replace\n')


class M13Rework(Base):
    """G13 r2: regression tests for the M13 Grok self-validation findings N1-N10 (on 7da20d4)."""

    def case(self, rows, header=HDR, control=None, **changes):
        f = self.tmp / f'case{len(list(self.tmp.iterdir()))}'
        shutil.copytree(FIX / 'clean', f)
        (f / 'orders.csv').write_text(header + '\n' + '\n'.join(rows) + '\n')
        if control is None:
            changes.setdefault('controls', None)
        else:
            (f / 'control.csv').write_text('file,rows,sum\norders.csv,%s,%s\n' % control)
        return self.contract(f, **changes)

    def reasons(self, contract):
        out = contract.parent / 'rejects.csv'
        cli('reconcile', contract, '--rejects', out)
        return [line.split(',')[2] for line in out.read_text().splitlines()[1:]]

    def test_n1_missing_loaded_at_under_as_of_is_a_gap_and_never_wins(self):
        for token in ('', 'NULL'):
            c = self.case(BASE_ROWS + [row('A4', amt='4.00', la=token)])
            code, rep = self.run_json(c)
            self.assertEqual(code, 1)
            self.assertIn('loaded_at_unknown', rep['gaps'])
            self.assertEqual(rep['coverage']['loaded_at_unknown'], 1)
            self.assertEqual(groups(rep, 'revenue')[('USD',)], '30.00')
            self.assertTrue(rep['coverage']['all_rows_accounted'])
            self.assertIn('loaded_at_unknown', self.reasons(c))
        # a newer version with no loaded_at must not replace the on-time version
        code, rep = self.run_json(self.case(BASE_ROWS + [row('A2', 'K2', '75.00', la='', up='2026-09-20T00:00:00Z')]))
        self.assertEqual((code, groups(rep, 'revenue')[('USD',)]), (1, '30.00'))
        self.assertEqual(rep['coverage']['duplicates']['superseded_versions'], 0)
        # without as_of nothing is judged on time, so a blank loaded_at is fine
        code, rep = self.run_json(self.case(BASE_ROWS + [row('A4', amt='4.00', la='')], as_of=None))
        self.assertEqual((code, rep['gaps'], groups(rep, 'revenue')[('USD',)]), (0, [], '34.00'))

    def test_n2_one_timestamp_grammar_on_every_python(self):
        ok = ['2026-09-10T12:00:00Z', '2026-09-10T12:00:00+00:00', '2026-09-10t12:00:00z', '2026-09-10T12:00:00.5Z',
              '2026-09-10T12:00Z', '2026-09-10 12:00:00', '2026-09-10', '2026-09-10T05:00:00.123456-07:00']
        bad = ['2026-09-10T12:00:00+0000', '2026-09-10T12:00:00+00', '20260910T120000Z', '2026-W37-4T12:00:00Z',
               '2026-09-10T12:00:00.1234567Z', '2026-09-10T12:00:00+00:60', '2026-09-31T12:00:00Z', '\u0662026-09-10T12:00:00Z']
        rows = BASE_ROWS + [row(f'T{i}', amt='1.00', ev=v) for i, v in enumerate(ok + bad)]
        code, rep = self.run_json(self.case(rows))
        self.assertEqual(rep['coverage']['rejected'], {'bad_timestamp': len(bad)}, sys.version)
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '%d.00' % (30 + len(ok)))
        code, rep = self.run_json(self.case(BASE_ROWS, as_of='2026-10-02T00:00:00+0000'))
        self.assertEqual((code, rep['status']), (2, 'invalid'))

    def test_n3_redelivery_differing_only_in_loaded_at_is_one_record(self):
        rows = BASE_ROWS + [row('A2', 'K2', '20.00', la='2026-09-11T08:00:00Z')]
        for changes in ({}, {'as_of': None}):
            c = self.case(rows, **changes)
            code, rep = self.run_json(c)
            self.assertEqual((code, groups(rep, 'revenue')[('USD',)], groups(rep, 'orders')[()]), (0, '30.00', 3))
            self.assertEqual(rep['coverage']['duplicates']['exact_copies'], 1)
            # the earliest load is kept: the later delivery (line 5) is the dropped copy
            out = c.parent / 'rejects.csv'
            cli('reconcile', c, '--rejects', out)
            self.assertEqual(out.read_text().splitlines()[1:], ['orders.csv,5,duplicate_exact,order_id'])
        # a real change in another column is still a version, not a copy
        code, rep = self.run_json(self.case(BASE_ROWS + [row('A2', 'K2', '21.00', la='2026-09-11T08:00:00Z')]))
        self.assertEqual(rep['coverage']['duplicates']['rows_unresolved'], 2)

    def test_n4_outputs_are_written_together_or_not_at_all(self):
        c = self.case(BASE_ROWS + [row('A4', amt='x')])
        ro = self.tmp / 'ro'
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            code, out = cli('reconcile', c, '--json', '--rejects', self.tmp / 'rej.csv', '--out', ro / 'r.json')
        finally:
            os.chmod(ro, 0o700)
        self.assertEqual(code, 2)
        self.assertFalse((self.tmp / 'rej.csv').exists())
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith('.')], [])
        # a failure while renaming the second file puts the first back as it was
        (self.tmp / 'rej.csv').write_text('OLD REJECTS\n')
        (self.tmp / 'r.json').write_text('OLD REPORT\n')
        guard = self.tmp / 'fault'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text(REPLACE_FAULT)
        env = dict(ENV, PYTHONPATH=str(guard), G13_FAIL_REPLACE='r.json')
        code, out = cli('reconcile', c, '--json', '--rejects', self.tmp / 'rej.csv', '--out', self.tmp / 'r.json', env=env)
        self.assertEqual(code, 2)
        self.assertEqual((self.tmp / 'rej.csv').read_text(), 'OLD REJECTS\n')
        self.assertEqual((self.tmp / 'r.json').read_text(), 'OLD REPORT\n')
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir() if p.name.startswith('.')), [])
        # a replaced report is a new file: a reader holding the old one never sees a partial write
        alias = self.tmp / 'alias.json'
        os.link(self.tmp / 'r.json', alias)
        code, out = cli('reconcile', c, '--out', self.tmp / 'r.json', '--rejects', self.tmp / 'rej.csv')
        self.assertEqual(code, 1)
        self.assertEqual(alias.read_text(), 'OLD REPORT\n')
        self.assertEqual(json.loads((self.tmp / 'r.json').read_text())['status'], 'reconciled_with_gaps')
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir() if p.name.startswith('.')), [])

    def test_n5_deeply_nested_contract_is_invalid_not_a_crash(self):
        p = self.tmp / 'contract.json'
        p.write_text('[' * 100000 + ']' * 100000)
        r = subprocess.run([sys.executable, str(TOOL), 'reconcile', str(p), '--json'], capture_output=True, text=True, env=ENV, timeout=120)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('nested too deeply', json.loads(r.stdout)['error'])

    def test_n6_dst_ambiguous_and_nonexistent_local_times_are_refused(self):
        rows = BASE_ROWS + [row('D1', ev='2026-11-01 01:30:00'), row('D2', ev='2026-03-08 02:30:00'),
                            row('D3', amt='1.00', ev='2026-11-01 03:30:00', la='2026-09-30T00:00:00Z')]
        code, rep = self.run_json(self.case(rows))
        self.assertEqual(rep['coverage']['rejected'], {'ambiguous_local_time': 1, 'nonexistent_local_time': 1})
        self.assertEqual(rep['coverage']['outside_window'], 1)  # an ordinary local time on the same day still parses
        self.assertTrue(any('DST' in n for n in rep['notes']))
        for v in ('2026-11-01 01:30:00', '2026-03-08 02:30:00'):
            code, rep = self.run_json(self.case(BASE_ROWS, window={'column': 'event_time', 'start': '2026-01-01', 'end': v}))
            self.assertEqual(code, 2, v)
        code, rep = self.run_json(self.case(BASE_ROWS, window={'column': 'event_time', 'start': '2026-09-01', 'end': '2026-11-01 01:30:00-07:00'}))
        self.assertEqual(code, 0)

    def test_n7_only_ascii_digits_count_as_numbers(self):
        hdr = HDR + ',rev'
        rows = [r + ',1' for r in BASE_ROWS] + [row('A2', 'K2', '70.00') + ',\u0663', row('A3', 'K1', '9.00', 'EUR') + ',\uff12']
        c = self.case(rows, header=hdr, facts__columns__rev='int', facts__duplicate_policy='latest:rev')
        code, rep = self.run_json(c)
        self.assertEqual(rep['coverage']['rejected'], {'bad_int': 2})
        self.assertEqual(groups(rep, 'revenue'), {('USD',): '30.00', ('EUR',): '5.25'})
        code, rep = self.run_json(self.case(BASE_ROWS + [row('A4', amt='\u0664.00')]))
        self.assertEqual(rep['coverage']['rejected'], {'bad_decimal': 1})
        code, rep = self.run_json(self.case(BASE_ROWS, control=('\u0663', '35.25')))
        self.assertEqual(code, 2)

    def test_n8_total_spelling_does_not_depend_on_row_order(self):
        a = BASE_ROWS + [row('A1', 'K1', '10.000')]
        b = [a[-1]] + a[:-1]
        reps = [self.run_json(self.case(r))[1] for r in (a, b)]
        self.assertEqual(reps[0]['metrics'], reps[1]['metrics'])
        self.assertEqual(groups(reps[0], 'revenue')[('USD',)], groups(reps[1], 'revenue')[('USD',)])

    def test_n10_boundaries_controls_and_nulls(self):
        # window is half-open [start, end) in the contract zone; as_of includes a row loaded exactly at the cutoff
        rows = BASE_ROWS + [row('W1', amt='1.00', ev='2026-09-01T07:00:00Z'), row('W2', amt='2.00', ev='2026-10-01T07:00:00Z'),
                            row('L1', amt='4.00', la='2026-10-02T00:00:00Z'), row('L2', amt='8.00', la='2026-10-02T00:00:01Z')]
        code, rep = self.run_json(self.case(rows))
        self.assertEqual(groups(rep, 'revenue')[('USD',)], '35.00')
        self.assertEqual((rep['coverage']['outside_window'], rep['coverage']['late_after_as_of']), (1, 1))
        # count_distinct counts distinct values, count counts non-null values, min skips nulls
        c = self.case(BASE_ROWS + [row('A4', 'K2', '')], facts__required=['currency', 'event_time'], metrics=[
            {'name': 'buyers', 'agg': 'count_distinct', 'column': 'customer_id'},
            {'name': 'priced', 'agg': 'count', 'column': 'amount'},
            {'name': 'smallest', 'agg': 'min', 'column': 'amount'}])
        code, rep = self.run_json(c)
        self.assertEqual((groups(rep, 'buyers')[()], groups(rep, 'priced')[()], groups(rep, 'smallest')[()]), (2, 3, '5.25'))
        self.assertIn('null_metric_values', rep['gaps'])
        # a rejected row makes the control a mismatch even when rows and the parsed sum agree
        code, rep = self.run_json(self.case(BASE_ROWS + [row('A4', amt='1.0x')], control=('4', '35.25')))
        self.assertEqual(rep['controls']['actual_sum_of_parsed'], '35.25')
        self.assertFalse(rep['controls']['match'])
        self.assertIn('control_mismatch', rep['gaps'])
        code, rep = self.run_json(self.case(BASE_ROWS, control=('3', '35.25')))
        self.assertEqual((code, rep['controls']['match']), (0, True))


class Oracle(Base):
    def oracle(self, tool):
        p = subprocess.run([sys.executable, str(G13 / 'reconcile_oracle.py'), '--tool', tool, '--json',
                            '--rows', '600', '--scale-rows', '6000'], capture_output=True, text=True, env=ENV, timeout=600)
        return json.loads(p.stdout)

    def test_tool_passes_and_stubs_fail(self):
        py = sys.executable
        self.assertEqual(self.oracle(f'"{py}" "{TOOL}"')['passed'], 13)
        self.assertEqual(self.oracle(f'"{py}" "{G13 / "noop_stub.py"}"')['passed'], 0)
        self.assertEqual(self.oracle(f'"{py}" "{G13 / "naive_stub.py"}"')['passed'], 0)


if __name__ == '__main__':
    unittest.main()
