"""G10: offline network failure localization (employees/infrastructure/network-engineer/netdiag.py).

Real files, real subprocesses; traces are synthetic (documentation address ranges, .example names).
"""
import copy
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees' / 'infrastructure' / 'network-engineer' / 'netdiag.py'
FIX = ROOT / 'examples' / 'capabilities' / 'G10' / 'fixtures'
sys.path.insert(0, str(TOOL.parent))
import netdiag as nd  # noqa: E402

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
H, IP, RES = 'web.lab.example', '192.0.2.40', '10.5.0.53'
CFG = {'resolvers': [RES], 'addresses': [{'dev': 'eth0', 'cidr': '10.5.0.20/24'}],
       'routes': [{'dst': 'default', 'via': '10.5.0.1', 'dev': 'eth0'}], 'expected_addresses': [IP]}
CERT = {'san': [H], 'not_before': '2026-01-01T00:00:00Z', 'not_after': '2027-01-01T00:00:00Z', 'chain_trusted': True}
DNS = {'stage': 'dns', 'qname': H, 'resolver': RES, 'rcode': 'NOERROR', 'answers': [IP]}
TCP = {'stage': 'tcp', 'dst': IP, 'port': 443, 'result': 'connected'}
TLS = {'stage': 'tls', 'dst': IP, 'sni': H, 'result': 'ok', 'cert': CERT}
HTTP = {'stage': 'http', 'status': 200, 'headers': {'Authorization': 'Bearer TEST-CANARY-42', 'Server': 'x'}}


def trace(obs, cfg=None, host=H, scheme='https', port=443, captured='2026-10-18T12:00:00Z'):
    d = {'schema': nd.TRACE_SCHEMA, 'target': {'host': host, 'scheme': scheme, 'port': port, 'path': '/'},
         'config': copy.deepcopy(CFG if cfg is None else cfg), 'observations': copy.deepcopy(obs)}
    if captured:
        d['captured_at'] = captured
    return d


def cli(*args, env=ENV):
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True, env=env, timeout=120)
    return p.returncode, p.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix='g10-test-')
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def write(self, name, doc):
        p = self.tmp / name
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        return p

    def diag(self, doc):
        return nd.diagnose_file(str(self.write('t.json', doc)))


class Fixtures(Base):
    EXPECT = {
        '01-clean-control.json': ('healthy', None, []),
        '02-dns-nxdomain.json': ('localized', 'dns', ['dns']),
        '03-dns-timeout-no-route-to-resolver.json': ('localized', 'route', ['route']),
        '04-route-blackhole.json': ('localized', 'route', ['route']),
        '05-route-path-loss.json': ('localized', 'route', ['route']),
        '06-tls-expired.json': ('localized', 'tls', ['tls']),
        '07-tls-name-mismatch-unverified-dns.json': ('probable', 'tls', ['dns', 'tls']),
        '08-app-not-listening.json': ('localized', 'application', ['application']),
        '09-app-upstream-503.json': ('localized', 'application', ['application']),
        '10-incomplete-dns-only.json': ('undetermined', None, ['route', 'tls', 'application']),
        '11-traceroute-filtered-but-healthy.json': ('healthy', None, []),
        '12-tls-fail-no-dns-evidence.json': ('probable', 'tls', ['dns', 'route', 'tls']),
    }

    def test_every_fixture_localizes_as_documented(self):
        self.assertEqual(sorted(p.name for p in FIX.glob('*.json')), sorted(self.EXPECT))
        for name, (verdict, layer, cands) in self.EXPECT.items():
            with self.subTest(fixture=name):
                r = nd.diagnose_file(str(FIX / name))
                self.assertEqual((r['verdict'], r['layer'], r['candidates']), (verdict, layer, cands), r['findings'])

    def test_clean_control_proves_every_layer(self):
        r = nd.diagnose_file(str(FIX / '01-clean-control.json'))
        self.assertEqual({l: v['state'] for l, v in r['layers'].items()},
                         {'dns': 'ok', 'route': 'ok', 'tls': 'ok', 'application': 'ok'})
        self.assertEqual((r['findings'], r['missing_evidence'], r['confidence']), ([], [], 'high'))
        self.assertTrue(all(r['layers'][l]['evidence'] for l in nd.LAYERS))

    def test_known_fault_names_the_specific_cause_and_read_only_next_step(self):
        r = nd.diagnose_file(str(FIX / '04-route-blackhole.json'))
        self.assertEqual([f['code'] for f in r['findings']], ['ROUTE_BLACKHOLE'])
        self.assertTrue(r['next_actions'])
        for a in sum((nd.render(nd.diagnose_file(str(p))).splitlines() for p in FIX.glob('*.json')), []):
            for verb in ('ip route add', 'ip route del', 'iptables -A', 'iptables -D', 'systemctl restart', 'rm -'):
                self.assertNotIn(verb, a)


class Localization(Base):
    def test_unseen_ipv6_and_plain_http_targets(self):
        v6 = '2001:db8::10'
        cfg = {'addresses': [{'dev': 'eth0', 'cidr': '2001:db8:1::5/64'}], 'routes': [{'dst': '2001:db8:1::/64', 'dev': 'eth0'}]}
        r = self.diag(trace([dict(DNS, answers=[v6]), dict(TCP, dst=v6, result='timeout')], cfg=cfg))
        self.assertEqual((r['verdict'], r['layer']), ('localized', 'route'))
        self.assertIn('ROUTE_NO_MATCH', [f['code'] for f in r['findings']])
        r = self.diag(trace([DNS, dict(TCP, port=80), dict(HTTP, status=200)], scheme='http', port=80))
        self.assertEqual((r['verdict'], r['layers']['tls']['state']), ('healthy', 'not_applicable'))

    def test_wildcard_certificate_rules(self):
        wild = dict(CERT, san=['*.lab.example'])
        self.assertEqual(self.diag(trace([DNS, TCP, dict(TLS, cert=wild), HTTP]))['verdict'], 'healthy')
        for host in ('lab.example', 'a.web.lab.example'):
            with self.subTest(host=host):
                obs = [dict(DNS, qname=host), TCP, dict(TLS, sni=host, cert=wild, result='alert', alert='bad_certificate')]
                r = self.diag(trace(obs, host=host))
                self.assertEqual(r['layer'], 'tls')
                self.assertIn('TLS_NAME_MISMATCH', [f['code'] for f in r['findings']])

    def test_intermittent_resolver_is_probable_not_certain(self):
        r = self.diag(trace([DNS, dict(DNS, resolver='10.5.0.54', rcode='SERVFAIL', answers=[])]))
        self.assertEqual((r['verdict'], r['layer'], r['layers']['dns']['state']), ('probable', 'dns', 'intermittent'))
        self.assertNotEqual(r['confidence'], 'high')

    def test_dns_timeout_with_route_present_keeps_both_candidates(self):
        r = self.diag(trace([dict(DNS, rcode='TIMEOUT', answers=[])]))
        self.assertEqual((r['verdict'], r['layer'], r['candidates']), ('probable', 'dns', ['dns', 'route']))

    def test_http_client_error_is_application_not_network(self):
        r = self.diag(trace([DNS, TCP, TLS, dict(HTTP, status=404)]))
        self.assertEqual((r['layer'], [f['code'] for f in r['findings']]), ('application', ['APP_CLIENT_ERROR']))
        self.assertEqual([r['layers'][l]['state'] for l in ('dns', 'route', 'tls')], ['ok', 'ok', 'ok'])

    def test_offlink_gateway_and_route_loop(self):
        cfg = dict(CFG, routes=[{'dst': 'default', 'via': '172.16.9.1', 'dev': 'eth0'}])
        r = self.diag(trace([DNS, dict(TCP, result='timeout')], cfg=cfg))
        self.assertIn('ROUTE_GATEWAY_OFFLINK', [f['code'] for f in r['findings']])
        hops = [{'ttl': i + 1, 'addr': a} for i, a in enumerate(['10.5.0.1', '198.51.100.1', '198.51.100.2', '198.51.100.1'])]
        r = self.diag(trace([DNS, {'stage': 'route', 'dst': IP, 'reached': False, 'hops': hops}]))
        self.assertEqual((r['layer'], [f['code'] for f in r['findings']]), ('route', ['ROUTE_LOOP']))

    def test_end_to_end_success_implies_lower_layers(self):
        r = self.diag(trace([HTTP]))
        self.assertEqual(r['verdict'], 'healthy')
        self.assertIn('implied', ' '.join(r['layers']['dns']['evidence']))


class SanForms(Base):
    """G10 rework (Muse finding on 3ebbe73): prefixed SAN entries were cut wrongly and reported as TLS_NAME_MISMATCH."""

    def codes(self, r):
        return [f['code'] for f in r['findings']]

    def test_prefixed_san_entries_cover_the_host(self):
        for san in (['DNS:web.lab.example'], ['dns:web.lab.example'], ['DNS:*.lab.example'],
                    ['  Dns : WEB.lab.example.'], ['IP:192.0.2.99', 'DNS:web.lab.example']):
            with self.subTest(san=san):
                r = self.diag(trace([DNS, TCP, dict(TLS, cert=dict(CERT, san=san)), HTTP]))
                self.assertEqual(r['verdict'], 'healthy', r['findings'])
                self.assertNotIn('TLS_NAME_MISMATCH', self.codes(r))

    def test_real_mismatch_is_still_reported(self):
        for san in (['DNS:other.example'], ['IP Address:192.0.2.40'], ['DNS:*.example'], ['dns:web.lab.example.other'],
                    ['IP:web.lab.example']):
            with self.subTest(san=san):
                obs = [DNS, TCP, dict(TLS, cert=dict(CERT, san=san), result='alert', alert='bad_certificate')]
                r = self.diag(trace(obs))
                self.assertEqual(r['layer'], 'tls')
                self.assertIn('TLS_NAME_MISMATCH', self.codes(r))

    def test_address_targets_need_an_address_entry(self):
        def run(san, result='ok'):
            obs = [dict(TCP), dict(TLS, sni=None, cert=dict(CERT, san=san), result=result)]
            if result == 'ok':
                obs.append(HTTP)
            return self.diag(trace(obs, host=IP))
        for san in (['IP:192.0.2.40'], ['IP Address:192.0.2.40'], ['192.0.2.40']):
            with self.subTest(san=san):
                self.assertNotIn('TLS_NAME_MISMATCH', self.codes(run(san)))
        for san in (['DNS:192.0.2.40'], ['IP:192.0.2.41'], ['DNS:web.lab.example']):
            with self.subTest(san=san):
                self.assertIn('TLS_NAME_MISMATCH', self.codes(run(san, result='alert')))


class Uncertainty(Base):
    def test_empty_trace_is_undetermined_over_every_layer(self):
        r = self.diag(trace([]))
        self.assertEqual((r['verdict'], r['layer'], r['confidence']), ('undetermined', None, 'low'))
        self.assertEqual(r['candidates'], list(nd.LAYERS))
        self.assertEqual(len(r['missing_evidence']), 4)

    def test_layers_with_positive_evidence_are_never_candidates(self):
        r = self.diag(trace([DNS, TCP]))
        self.assertEqual((r['verdict'], r['candidates']), ('undetermined', ['tls', 'application']))
        r = self.diag(trace([DNS, TCP, TLS]))
        self.assertEqual(r['candidates'], ['application'])

    def test_fault_after_unknown_layer_stays_probable(self):
        r = self.diag(trace([dict(TCP, result='refused')]))  # no DNS evidence: was it even the right host?
        self.assertEqual((r['verdict'], r['layer'], r['candidates']), ('probable', 'application', ['dns', 'application']))
        self.assertTrue(any('DNS lookup' in m for m in r['missing_evidence']))

    def test_expected_address_removes_the_dns_doubt_from_a_name_mismatch(self):
        obs = [DNS, TCP, dict(TLS, result='alert', alert='bad_certificate', cert=dict(CERT, san=['other.example']))]
        self.assertEqual(self.diag(trace(obs))['verdict'], 'localized')
        r = self.diag(trace(obs, cfg=dict(CFG, expected_addresses=[])))
        self.assertEqual((r['verdict'], r['candidates']), ('probable', ['dns', 'tls']))


class Reproducibility(Base):
    def test_same_trace_same_bytes_and_order_or_format_never_matter(self):
        doc = trace([DNS, TCP, TLS, dict(HTTP, status=502, via_proxy=True)])
        p = self.write('a.json', doc)
        a, b = cli('diagnose', p, '--json'), cli('diagnose', p, '--json')
        self.assertEqual(a, b)
        shuffled = dict(doc, observations=list(reversed(doc['observations'])))
        q = self.write('b.json', json.dumps(shuffled, separators=(',', ':'), sort_keys=True))
        ja, jb = json.loads(a[1]), json.loads(cli('diagnose', q, '--json')[1])
        self.assertNotEqual(ja.pop('input_sha256'), jb.pop('input_sha256'))
        self.assertEqual(ja, jb)

    def test_every_permutation_of_a_multi_resolver_trace_gives_one_report(self):
        import itertools
        obs = [dict(DNS, rcode='TIMEOUT', answers=[]), dict(DNS, resolver='10.5.0.54', rcode='TIMEOUT', answers=[]),
               dict(DNS, resolver='10.5.0.55', rcode='SERVFAIL', answers=[])]
        reports = set()
        for perm in itertools.permutations(obs):
            r = self.diag(trace(list(perm)))
            r.pop('input_sha256')
            reports.add(json.dumps(r, sort_keys=True))
        self.assertEqual(len(reports), 1)

    def test_certificate_dates_use_captured_at_never_the_wall_clock(self):
        old = dict(CERT, not_before='2001-01-01T00:00:00Z', not_after='2002-01-01T00:00:00Z')
        r = self.diag(trace([DNS, TCP, dict(TLS, cert=old), HTTP], captured='2001-06-01T00:00:00Z'))
        self.assertEqual(r['verdict'], 'healthy')
        future = dict(CERT, not_after='2090-01-01T00:00:00Z')
        r = self.diag(trace([DNS, TCP, dict(TLS, cert=future, result='alert', alert='certificate_expired')], captured='2091-01-01T00:00:00Z'))
        self.assertIn('TLS_CERT_EXPIRED', [f['code'] for f in r['findings']])
        r = self.diag(trace([DNS, TCP, dict(TLS, cert=old), HTTP], captured=None))
        self.assertEqual(r['verdict'], 'healthy')
        self.assertTrue(any('captured_at' in n for n in r['notes']))


class InvalidInput(Base):
    def assertInvalid(self, content, name='bad.json'):
        p = self.write(name, content) if not isinstance(content, Path) else content
        rc, out = cli('diagnose', p, '--json')
        self.assertEqual(rc, 2, out)
        self.assertEqual(json.loads(out)['verdict'], 'invalid')

    def test_malformed_and_ambiguous_traces_are_refused(self):
        good = trace([DNS])
        cases = {
            'garbage': '{"schema": ',
            'schema': json.dumps(dict(good, schema='solaris.net-trace/2')),
            'dupkey': '{"schema":"solaris.net-trace/1","target":{"host":"a.example","host":"b.example"}}',
            'nan': json.dumps(good)[:-1] + ',"x": NaN}',
            'bad_ip': json.dumps(trace([dict(TCP, dst='300.1.1.1')])),
            'bad_stage': json.dumps(trace([{'stage': 'smtp'}])),
            'bool_port': json.dumps(trace([dict(TCP, port=True)])),
            'naive_time': json.dumps(trace([DNS], captured='2026-10-18T12:00:00')),
            'shell_host': json.dumps(trace([DNS], host='web.example;reboot')),
            'not_object': '[1, 2]',
        }
        for k, v in cases.items():
            with self.subTest(case=k):
                self.assertInvalid(v)

    def test_size_symlink_and_count_limits(self):
        big = self.tmp / 'big.json'
        with open(big, 'w') as fh:
            fh.write('{"pad": "' + 'x' * (nd.MAX_BYTES + 10) + '"}')
        self.assertInvalid(big)
        link = self.tmp / 'link.json'
        os.symlink(self.write('real.json', trace([DNS])), link)
        self.assertInvalid(link)
        with self.assertRaises(nd.Invalid):
            nd.normalise(trace([DNS] * (nd.MAX_OBSERVATIONS + 1)))

    def test_previous_report_survives_bad_input_then_good_run_recovers(self):
        out = self.tmp / 'report.json'
        out.write_text('{"previous": true}\n')
        before = out.read_bytes()
        bad = self.write('bad.json', '{oops')
        self.assertEqual(cli('diagnose', bad, '--out', out)[0], 2)
        self.assertEqual(out.read_bytes(), before)
        good = self.write('good.json', trace([DNS, TCP, TLS, HTTP]))
        self.assertEqual(cli('diagnose', good, '--out', out)[0], 0)
        self.assertEqual(json.loads(out.read_text())['verdict'], 'healthy')
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.endswith('.tmp')], [])

    def test_out_never_follows_a_symlink_or_overwrites_the_input(self):
        good = self.write('good.json', trace([DNS]))
        victim = self.tmp / 'victim.txt'
        victim.write_text('keep')
        os.symlink(victim, self.tmp / 'r.json')
        self.assertEqual(cli('diagnose', good, '--out', self.tmp / 'r.json')[0], 2)
        self.assertEqual(victim.read_text(), 'keep')
        before = good.read_bytes()
        self.assertEqual(cli('diagnose', good, '--out', good)[0], 2)
        self.assertEqual(good.read_bytes(), before)


class SafetyAndScale(Base):
    def guard_env(self):
        g = self.tmp / 'guard'
        g.mkdir()
        audit = self.tmp / 'audit.txt'
        (g / 'sitecustomize.py').write_text(
            'import socket\n'
            f'def _d(*a, **k):\n    open({str(audit)!r}, "a").write("x")\n    raise OSError("network disabled")\n'
            'class _S:\n    def __init__(self, *a, **k): _d()\n'
            'socket.socket = _S; socket.getaddrinfo = _d; socket.create_connection = _d; socket.gethostbyname = _d\n')
        return dict(ENV, PYTHONPATH=str(g)), audit

    def test_offline_under_a_socket_denying_guard(self):
        env, audit = self.guard_env()
        d = self.tmp / 'many'
        d.mkdir()
        for i, name in enumerate(sorted(FIX.glob('*.json'))):
            (d / name.name).write_bytes(name.read_bytes())
        rc, out = cli('batch', d, '--json', '--workers', '2', env=env)
        self.assertEqual(rc, 1)
        self.assertEqual(len(json.loads(out)['reports']), 12)
        self.assertEqual(cli('diagnose', FIX / '01-clean-control.json', env=env)[0], 0)
        self.assertFalse(audit.exists(), 'the tool touched the socket API')

    def test_header_values_and_bodies_never_echoed(self):
        doc = trace([DNS, TCP, TLS, dict(HTTP, status=500, body_excerpt='password=hunter2')])
        p = self.write('s.json', doc)
        for args in (('diagnose', p), ('diagnose', p, '--json')):
            out = cli(*args)[1]
            self.assertNotIn('TEST-CANARY-42', out)
            self.assertNotIn('hunter2', out)

    def test_batch_scale_counts_and_worker_count_does_not_change_output(self):
        d = self.tmp / 'batch'
        d.mkdir()
        kinds = {'healthy': [DNS, TCP, TLS, HTTP], 'localized:dns': [dict(DNS, rcode='NXDOMAIN', answers=[])],
                 'localized:tls': [DNS, TCP, dict(TLS, result='alert', alert='unknown_ca', cert=dict(CERT, chain_trusted=False))],
                 'undetermined': [DNS]}
        names = list(kinds)
        for i in range(400):
            k = names[i % 4]
            obs = random.Random(i).sample(kinds[k], len(kinds[k]))
            (d / f'{i:04d}.json').write_text(json.dumps(trace(obs)))
        (d / 'broken.json').write_text('{')
        rc1, o1 = cli('batch', d, '--json')
        rc4, o4 = cli('batch', d, '--json', '--workers', '4')
        self.assertEqual((rc1, o1), (rc4, o4))
        j = json.loads(o1)
        self.assertEqual(j['counts'], {k: 100 for k in sorted(kinds)})
        self.assertEqual(list(j['invalid']), ['broken.json'])

    def test_concurrent_writers_to_one_report_leave_a_whole_report(self):
        out = self.tmp / 'shared.json'
        procs = [subprocess.Popen([sys.executable, str(TOOL), 'diagnose', str(FIX / name), '--out', str(out)],
                                  stdout=subprocess.DEVNULL, env=ENV)
                 for name in ['06-tls-expired.json', '02-dns-nxdomain.json'] * 4]
        for p in procs:
            p.wait(timeout=120)
        j = json.loads(out.read_text())
        self.assertIn(j['layer'], ('tls', 'dns'))
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.endswith('.tmp')], [])


class Cli(Base):
    def test_exit_codes_and_text_report(self):
        self.assertEqual(cli('diagnose', FIX / '01-clean-control.json')[0], 0)
        rc, out = cli('diagnose', FIX / '07-tls-name-mismatch-unverified-dns.json')
        self.assertEqual(rc, 1)
        self.assertIn('diagnosis: probable at tls (confidence medium)', out)
        self.assertIn('candidate layers: dns, tls', out)
        self.assertIn('next (read-only, not run):', out)
        self.assertEqual(cli('diagnose', self.tmp / 'missing.json')[0], 2)
        self.assertEqual(cli('batch', self.tmp, '--workers', '99')[0], 2)


if __name__ == '__main__':
    unittest.main()
