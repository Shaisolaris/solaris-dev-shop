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


class M10Rework(Base):
    """G10 r3 (M10 Grok self-validation, FAIL at 6af7849): SAN spellings, suffix wildcards, non-ASCII
    folding, SNI, deep JSON, double trailing dot, timestamps, and the mutants M10 showed survive."""

    def codes(self, r):
        return [f['code'] for f in r['findings']]

    def alert(self, san, sni=H, host=H):
        tls = dict(TLS, sni=sni, cert=dict(CERT, san=san), result='alert', alert='bad_certificate')
        return self.diag(trace([dict(DNS, qname=host), TCP, tls], host=host))

    def test_f1_keytool_windows_and_one_line_openssl_spellings_cover(self):
        for san in (['DNSName: web.lab.example'], ['DNS Name=web.lab.example'], ['dns name = WEB.lab.example'],
                    ['DNS:other.example, DNS:web.lab.example, IP Address:192.0.2.40'],
                    ['IPAddress: 192.0.2.7', 'DNSName: *.lab.example']):
            with self.subTest(san=san):
                r = self.alert(san)
                self.assertEqual(self.codes(r), ['TLS_ALERT'], r['findings'])
        for san in (['IPAddress: 192.0.2.40'], ['IP Address=192.0.2.40'], ['DNS:a.example, IP Address:192.0.2.40']):
            with self.subTest(san=san):
                obs = [dict(TCP), dict(TLS, sni=None, cert=dict(CERT, san=san), result='alert', alert='bad_certificate')]
                self.assertEqual(self.codes(self.diag(trace(obs, host=IP))), ['TLS_ALERT'])
        r = self.alert(['DNSName: other.example', 'DNS Name=b.example'])
        self.assertIn('TLS_NAME_MISMATCH', self.codes(r))

    def test_f1_an_unknown_san_type_is_noted_not_turned_into_a_mismatch(self):
        r = self.alert(['URI:https://web.lab.example/', 'otherName:web.lab.example'])
        self.assertNotIn('TLS_NAME_MISMATCH', self.codes(r))
        self.assertTrue(any('not understood' in n for n in r['notes']), r['notes'])
        r = self.alert(['URI:https://web.lab.example/', 'DNS:web.lab.example'])
        self.assertEqual(self.codes(r), ['TLS_ALERT'])

    def test_f2_no_wildcard_over_a_tld_or_public_suffix(self):
        for host, san in (('shop.example', '*.example'), ('shop.com', 'DNS:*.com'), ('shop.co.uk', 'DNS:*.co.uk'),
                          ('a.github.io', '*.github.io')):
            with self.subTest(san=san):
                self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert([san], sni=host, host=host)))
        for host, san in (('www.shop.co.uk', '*.shop.co.uk'), ('a.lab.example', 'DNS:*.lab.example')):
            with self.subTest(san=san):
                self.assertEqual(self.codes(self.alert([san], sni=host, host=host)), ['TLS_ALERT'])

    def test_f3_non_ascii_text_is_never_folded_into_ascii(self):
        r = self.alert(['DNS:\u212aelvin.example'], sni='kelvin.example', host='kelvin.example')
        self.assertIn('TLS_NAME_MISMATCH', self.codes(r))
        self.assertEqual(self.diag(trace([TLS])), self.diag(trace([TLS])))
        t = nd.normalise(trace([dict(TLS, cert=dict(CERT, san=['DNS:\u212aelvin.example', 'DNS:ABC.example']))]))
        self.assertEqual(t['observations'][0]['cert']['san'], ['DNS:\u212aelvin.example', 'dns:abc.example'])

    def test_f4_sni_that_differs_from_the_target_is_flagged(self):
        r = self.alert(['DNS:www.other.example'], sni='www.other.example')
        self.assertIn('TLS_SNI_MISMATCH', self.codes(r))
        self.assertEqual(r['layer'], 'tls')
        ok = self.diag(trace([DNS, TCP, dict(TLS, sni='WEB.lab.example.'), HTTP]))
        self.assertEqual(ok['verdict'], 'healthy')

    def test_f5_deep_json_is_invalid_and_a_batch_continues(self):
        deep = '[' * 100000 + ']' * 100000
        self.write('a-deep.json', deep)
        rc, out = cli('diagnose', self.tmp / 'a-deep.json')
        self.assertEqual(rc, 2)
        self.write('b-good.json', trace([DNS, TCP, TLS, HTTP]))
        rc, out = cli('batch', self.tmp, '--json')
        rep = json.loads(out)
        self.assertEqual((rep['traces'], list(rep['reports']), list(rep['invalid'])), (2, ['b-good.json'], ['a-deep.json']))

    def test_f6_double_trailing_dot_never_covers(self):
        self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert(['DNS:web.lab.example..'])))
        self.assertEqual(self.codes(self.alert(['DNS:web.lab.example.'])), ['TLS_ALERT'])

    def test_f7_rfc3339_times_parse_the_same_on_every_interpreter(self):
        for ok in ('2026-10-18T12:00:00Z', '2026-10-18t12:00:00z', '2026-10-18 12:00:00+02:00', '2026-10-18T12:00:00.5Z',
                   '2026-10-18T12:00:00.123456-07:00'):
            with self.subTest(ok=ok):
                self.assertEqual(self.diag(trace([DNS, TCP, TLS, HTTP], captured=ok))['verdict'], 'healthy')
        self.assertEqual(nd._iso('2026-10-18T12:00:00.5Z'), nd._iso('2026-10-18T12:00:00.500000+00:00'))
        for bad in ('2026-10-18T12:00:00+0000', '2026-10-18T12:00:00+00', '20261018T120000Z', '2026-W42-7T12:00:00Z',
                    '2026-10-18T12:00:00.Z', '2026-10-18T12:00Z', '2026-10-18'):
            with self.subTest(bad=bad):
                self.assertEqual(cli('diagnose', self.write('t.json', trace([DNS], captured=bad)))[0], 2)

    def test_mutant_gaps_chain_case_ipv6_refused_and_answer_order(self):
        r = self.diag(trace([DNS, TCP, dict(TLS, cert=dict(CERT, chain_trusted=False), result='alert', alert='unknown_ca')]))
        self.assertIn('TLS_UNTRUSTED_CHAIN', self.codes(r))
        mixed = self.diag(trace([dict(DNS, qname='WEB.Lab.Example'), TCP, dict(TLS, sni='Web.LAB.example'), HTTP], host='Web.Lab.EXAMPLE'))
        self.assertEqual((mixed['verdict'], mixed['findings']), ('healthy', []))
        v6 = '2001:db8::1'
        obs = [dict(TCP, dst=v6), dict(TLS, dst=v6, sni=None, cert=dict(CERT, san=['IP:2001:db8:0:0:0:0:0:1'])), HTTP]
        self.assertEqual(self.diag(trace(obs, host=v6))['verdict'], 'healthy')
        r = self.diag(trace([DNS, dict(TCP, result='refused')]))
        self.assertEqual([(f['code'], f['layer']) for f in r['findings']], [('APP_NOT_LISTENING', 'application')])
        doc = trace([dict(DNS, answers=['192.0.2.9', '192.0.2.40', '192.0.2.1', '192.0.2.200']), TCP, TLS, HTTP])
        p = self.write('t.json', doc)
        outs = {cli('diagnose', p, '--json', env=dict(ENV, PYTHONHASHSEED=str(seed)))[1] for seed in range(6)}
        self.assertEqual(len(outs), 1)
        self.assertIn('NOERROR 192.0.2.1,192.0.2.200,192.0.2.40,192.0.2.9', outs.pop())


class M10R2Rework(Base):
    """G10 r4 (M10 r2 Grok self-validation of be36f86): non-host SAN types beside DNS entries (RG1),
    RFC 3339 fractions of any length (RG3, RG4), and wildcard depth tested apart from the suffix rule (E1)."""

    def codes(self, r):
        return [f['code'] for f in r['findings']]

    def alert(self, san, sni=H, host=H):
        tls = dict(TLS, sni=sni, cert=dict(CERT, san=san), result='alert', alert='bad_certificate')
        return self.diag(trace([dict(DNS, qname=host), TCP, tls], host=host))

    EXTRA = ('URI:spiffe://lab.example/ns/a/sa/b', 'email:ops@lab.example', 'othername:UPN::ops@lab.example',
             'DirName:/C=GB, O=Example Lab, CN=web', 'Registered ID:1.2.3.4', 'rfc822Name: ops@lab.example')

    def test_rg1_non_host_san_types_never_hide_a_real_mismatch(self):
        for extra in self.EXTRA:
            for san in (['DNS:other.example', extra], [f'DNS:other.example, {extra}'], [f'{extra}, DNS:other.example']):
                with self.subTest(san=san):
                    r = self.alert(san)
                    self.assertIn('TLS_NAME_MISMATCH', self.codes(r))
                    self.assertTrue(any('not host names were ignored' in n for n in r['notes']), r['notes'])
                    self.assertFalse(any('not understood' in n for n in r['notes']), r['notes'])

    def test_rg1_covering_dns_beside_non_host_types_and_controls(self):
        for extra in self.EXTRA:
            with self.subTest(extra=extra):
                self.assertEqual(self.codes(self.alert(['DNS:web.lab.example', extra])), ['TLS_ALERT'])
                self.assertEqual(self.codes(self.alert([f'{extra}, DNS:web.lab.example'])), ['TLS_ALERT'])
        self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert(['DNS:other.example'])))
        # only non-host types: no host entry to judge, so still "not understood" and no confident mismatch
        r = self.alert(['URI:spiffe://lab.example/a', 'email:ops@lab.example'])
        self.assertNotIn('TLS_NAME_MISMATCH', self.codes(r))
        self.assertTrue(any('not understood' in n for n in r['notes']), r['notes'])
        # an unrecognised typed spelling still blocks a confident mismatch
        r = self.alert(['DNS:other.example', 'Foo Name:web.lab.example'])
        self.assertNotIn('TLS_NAME_MISMATCH', self.codes(r))
        # a DirName value with commas is one entry; a host-like part inside it never covers
        self.assertEqual(nd._san_parts('DirName:/C=GB, O=web.lab.example, DNS:other.example'),
                         ['DirName:/C=GB, O=web.lab.example', 'DNS:other.example'])
        self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert(['DirName:/C=GB, O=web.lab.example, DNS:other.example'])))

    def test_rg3_any_fraction_length_is_accepted_and_truncated(self):
        for ts in ('2026-10-18T12:00:00.1234567Z', '2026-10-18T12:00:00.12345678Z', '2026-10-18T12:00:00.123456789Z',
                   '2026-10-18T12:00:00.123456789-07:00', '2026-10-18T12:00:00.000000001Z'):
            with self.subTest(ts=ts):
                self.assertEqual(self.diag(trace([DNS, TCP, TLS, HTTP], captured=ts))['verdict'], 'healthy')
                rc, _ = cli('diagnose', self.write('c.json', trace([DNS, TCP, TLS, HTTP], captured=ts)))
                self.assertEqual(rc, 0)
        self.assertEqual(nd._iso('2026-10-18T12:00:00.123456789Z'), nd._iso('2026-10-18T12:00:00.123456Z'))
        self.assertEqual(nd._iso('2026-10-18T12:00:00.9999999Z'), nd._iso('2026-10-18T12:00:00.999999Z'))
        for bad in ('2026-10-18T12:00:00.Z', '2026-10-18T12:00:00.12a3Z', '2026-10-18T12:00:00.123456789+0000'):
            with self.subTest(bad=bad):
                self.assertEqual(cli('diagnose', self.write('t.json', trace([DNS], captured=bad)))[0], 2)

    def test_rg4_nanosecond_not_after_before_capture_is_expired(self):
        cert = dict(CERT, not_after='2026-10-18T15:59:59.999999999Z')
        tls = dict(TLS, cert=cert, result='alert', alert='certificate_expired')
        r = self.diag(trace([DNS, TCP, tls], captured='2026-10-18T16:00:00Z'))
        self.assertIn('TLS_CERT_EXPIRED', self.codes(r))
        r = self.diag(trace([DNS, TCP, dict(TLS, cert=cert), HTTP], captured='2026-10-18T15:59:59.5Z'))
        self.assertEqual(r['verdict'], 'healthy')

    def test_e1_wildcard_depth_apart_from_the_suffix_rule(self):
        # *.lab.example is a legal wildcard (two labels after *.), so only depth decides these
        self.assertEqual(self.codes(self.alert(['DNS:*.lab.example'])), ['TLS_ALERT'])
        for host in ('a.web.lab.example', 'x.y.web.lab.example'):
            with self.subTest(host=host):
                self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert(['DNS:*.lab.example'], sni=host, host=host)))


class M10R3Rework(Base):
    """G10 r5 (M10 r3 Grok self-validation of 69c6081): keytool and certutil spellings of non-host SAN types
    (Q1), a bare name after a typed entry in one list (Q2), and the not-understood note's advice."""

    TOOL_EXTRA = ('URIName: spiffe://lab.example/ns/a/sa/b', 'OIDName: 1.2.3.4',
                  'Other-Name: Unrecognized ObjectIdentifier: 1.3.6.1.4.1.311.20.2.3', 'URL=spiffe://lab.example/a',
                  'DirectoryName: CN=web, O=Example Lab', 'URI Name: spiffe://lab.example/b')

    codes = M10R2Rework.codes
    alert = M10R2Rework.alert

    def test_q1_keytool_and_certutil_non_host_spellings_never_hide_a_mismatch(self):
        for extra in self.TOOL_EXTRA:
            for san in (['DNS:other.example', extra], [f'DNS:other.example, {extra}'], [f'{extra}, DNS:other.example'],
                        ['DNSName: other.example', extra]):
                with self.subTest(san=san):
                    r = self.alert(san)
                    self.assertIn('TLS_NAME_MISMATCH', self.codes(r))
                    self.assertTrue(any('not host names were ignored' in n for n in r['notes']), r['notes'])
                    self.assertFalse(any('not understood' in n for n in r['notes']), r['notes'])
            with self.subTest(cover=extra):
                self.assertEqual(self.codes(self.alert(['DNSName: web.lab.example', extra])), ['TLS_ALERT'])
            with self.subTest(alone=extra):
                r = self.alert([extra])
                self.assertNotIn('TLS_NAME_MISMATCH', self.codes(r))
                self.assertTrue(any('not understood' in n for n in r['notes']), r['notes'])

    def test_q1_note_never_advises_rewriting_a_uri_as_dns(self):
        r = self.alert(['URIName: spiffe://lab.example/a'])
        note = next(n for n in r['notes'] if 'not understood' in n)
        self.assertNotIn('paste them as DNS', note)
        self.assertIn('do not rewrite them as DNS', note)
        r = self.alert(['DNS:other.example', 'Foo Name:web.lab.example'])
        self.assertTrue(any('if one of them is really a host name' in n for n in r['notes']), r['notes'])

    def test_q2_bare_name_after_a_typed_entry_is_its_own_entry(self):
        self.assertEqual(nd._san_parts('DNS:a.example, web.lab.example'), ['DNS:a.example', 'web.lab.example'])
        self.assertEqual(nd._san_parts('DNS:a.example, web.lab.example, IP Address:192.0.2.1'),
                         ['DNS:a.example', 'web.lab.example', 'IP Address:192.0.2.1'])
        self.assertEqual(self.codes(self.alert(['DNS:a.example, web.lab.example'])), ['TLS_ALERT'])
        self.assertEqual(self.codes(self.alert(['DNSName: a.example, web.lab.example'])), ['TLS_ALERT'])
        self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert(['DNS:a.example, b.example'])))
        # non-host values keep their commas, so a host-like part inside them never covers
        self.assertEqual(nd._san_parts('DNS:a.example, DirName:/C=GB, O=web.lab.example'),
                         ['DNS:a.example', 'DirName:/C=GB, O=web.lab.example'])
        self.assertEqual(nd._san_parts('URI:spiffe://x.example/a,web.lab.example, DNS:a.example'),
                         ['URI:spiffe://x.example/a,web.lab.example', 'DNS:a.example'])
        self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert(['URI:spiffe://x.example/a,web.lab.example, DNS:a.example'])))

    def test_mismatch_detail_lists_parsed_host_names(self):
        r = self.alert(['DNS:other.example, URI:spiffe://lab.example/a'])
        detail = next(f['detail'] for f in r['findings'] if f['code'] == 'TLS_NAME_MISMATCH')
        self.assertIn("['other.example']", detail)
        self.assertNotIn('spiffe', detail)



class M10R4Rework(Base):
    """G10 r6 (M10 r4 Grok self-validation of 865734e): V1, a bare covering name after a non-host entry
    in one pasted line gave a false TLS_NAME_MISMATCH."""
    codes = M10R2Rework.codes
    alert = M10R2Rework.alert

    def test_v1_bare_name_after_a_non_host_entry_is_its_own_entry(self):
        for line in ('DNS:other.example, URI:spiffe://lab.example/x, web.lab.example',
                     'DNS:other.example, Registered ID:1.2.3.4, web.lab.example',
                     'DNSName: other.example, URIName: spiffe://x, web.lab.example',
                     'DNS:other.example, email:ops, web.lab.example',
                     'DNS:other.example, DirName:/C=GB, O=Shop, web.lab.example'):
            with self.subTest(line=line):
                self.assertEqual(self.codes(self.alert([line])), ['TLS_ALERT'])
        self.assertEqual(nd._san_parts('DNS:o.example, URI:spiffe://x, web.lab.example'),
                         ['DNS:o.example', 'URI:spiffe://x', 'web.lab.example'])

    def test_v1_controls_non_host_values_keep_their_own_commas(self):
        for line in ('DNS:other.example, URI:spiffe://x, DNS:other2.example',
                     'DNS:other.example, URI:spiffe://x, other2.example',
                     'DNS:other.example, DirName:/C=GB, O=Shop, CN=svc',
                     'DNS:other.example, DirName:/C=GB, O=web.lab.example',
                     'URI:spiffe://x.example/a,web.lab.example, DNS:a.example'):
            with self.subTest(line=line):
                self.assertIn('TLS_NAME_MISMATCH', self.codes(self.alert([line])))
        self.assertEqual(nd._san_parts('DNS:a.example, DirName:/C=GB, O=Shop, CN=svc'),
                         ['DNS:a.example', 'DirName:/C=GB, O=Shop, CN=svc'])
        self.assertEqual(nd._san_parts('DNS:a.example, DirName:/C=GB, O=Shop, Foo Name: x'),
                         ['DNS:a.example', 'DirName:/C=GB, O=Shop, Foo Name: x'])
        # an RDN in dotted-OID form (2.5.4.3 is CN) stays with its DirName too
        self.assertEqual(nd._san_parts('DNS:a.example, DirName:/C=GB, 2.5.4.3=svc'),
                         ['DNS:a.example', 'DirName:/C=GB, 2.5.4.3=svc'])


if __name__ == '__main__':
    unittest.main()
