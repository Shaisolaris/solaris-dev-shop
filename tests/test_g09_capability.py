"""G09 offline Kubernetes manifest check: oracle, controls and the behaviour it relies on.

Every manifest is synthetic and written to a temporary directory. Nothing contacts a cluster or the network.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees/infrastructure/kubernetes-specialist/k8s_manifest_check.py'
EX = ROOT / 'examples/capabilities/G09'
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0, str(TOOL.parent))
sys.dont_write_bytecode = True
import k8s_manifest_check as k  # noqa: E402


def oracle(tool):
    p = subprocess.run([sys.executable, str(EX / 'k8s_oracle.py'), '--tool', str(tool), '--json'],
                       capture_output=True, text=True, env=ENV, timeout=600)
    return p.returncode, {c['id']: c['ok'] for c in json.loads(p.stdout)['checks']}


class G09Check(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g09-test-'))

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text)
        return str(p)

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(TOOL), 'check'] + list(args) + ['--json'], capture_output=True,
                           text=True, env=ENV, timeout=120)
        return p.returncode, json.loads(p.stdout)

    def codes(self, js, sev='error'):
        return sorted((f['code'], f['line']) for f in js['findings'] if f['severity'] == sev)

    def test_oracle_passes_on_the_tool(self):
        code, res = oracle(TOOL)
        self.assertEqual(code, 0, res)

    def test_oracle_rejects_the_naive_control(self):
        code, res = oracle(EX / 'naive_check.py')
        self.assertEqual(code, 1)
        self.assertEqual({i for i, ok in res.items() if ok}, {'o1', 'o12', 's1'})

    def test_oracle_rejects_the_noop_control(self):
        code, res = oracle(EX / 'noop_check.py')
        self.assertEqual({i for i, ok in res.items() if ok}, {'o1', 's1'})

    def test_clean_and_broken_fixtures(self):
        rc, js = self.cli(str(EX / 'fixtures/clean'))
        self.assertEqual((rc, js['findings'], js['objects']), (0, [], 9))
        self.assertEqual({q['name']: q['qos'] for q in js['qos']},
                         {'web': 'Burstable', 'ledger': 'Guaranteed', 'nightly-report': 'Burstable'})
        rc, js = self.cli(str(EX / 'fixtures/broken'))
        self.assertEqual(rc, 1)
        self.assertEqual(self.codes(js), [('IMAGE_TAG_MUTABLE', 32), ('PDB_BLOCKS_EVICTION', 83),
                                          ('PROBE_PORT_NAME_UNKNOWN', 55), ('RESOURCES_MISSING', 38),
                                          ('SERVICE_SELECTOR_NO_MATCH', 66)])
        self.assertFalse(js['deployed'] or js['applied'] or js['cluster_contacted'])

    def test_quantities(self):
        q = k.quantity
        self.assertEqual(q('0.5Gi'), q('512Mi'))
        self.assertEqual(q('1'), q('1000m'))
        self.assertEqual(q(1), q('1000m'))
        self.assertEqual(q('1e3'), q('1k'))
        self.assertEqual(q('1E'), 10 ** 18)
        self.assertGreater(q('1Gi'), q('1G'))
        for bad in ('256MB', '-1', '1.2.3', 'Mi', '', None, True, '10 Mi'):
            self.assertIsNone(q(bad), bad)

    def test_selector_rules(self):
        m = k.selector_matches
        lb = {'app': 'web', 'tier': 'fe'}
        self.assertTrue(m({'matchLabels': {'app': 'web'}}, lb))
        self.assertFalse(m({'matchLabels': {'app': 'web', 'x': '1'}}, lb))
        self.assertTrue(m({'matchExpressions': [{'key': 'tier', 'operator': 'In', 'values': ['fe', 'be']}]}, lb))
        self.assertFalse(m({'matchExpressions': [{'key': 'tier', 'operator': 'NotIn', 'values': ['fe']}]}, lb))
        self.assertTrue(m({'matchExpressions': [{'key': 'gone', 'operator': 'DoesNotExist'}]}, lb))
        self.assertFalse(m({'matchExpressions': [{'key': 'app', 'operator': 'Bogus'}]}, lb))
        self.assertTrue(m({'app': 'web'}, lb))  # Service-style plain map

    def test_yaml_reader_values_and_lines(self):
        text = ('a: 1\nb: "x: y"\nc: [1, "two", {d: e}]\nf: yes\ng: ~\nh: |\n  line1\n  line2\n'
                'i:\n- j: 1\n  k: 2\n- 3\nl: 08:00 # comment\nm: \'it\'\'s\'\n')
        docs, dups = k.load_yaml(text, 'x.yaml')
        v = docs[0][0]
        self.assertEqual(v, {'a': 1, 'b': 'x: y', 'c': [1, 'two', {'d': 'e'}], 'f': True, 'g': None,
                             'h': 'line1\nline2\n', 'i': [{'j': 1, 'k': 2}, 3], 'l': '08:00', 'm': "it's"})
        self.assertEqual(v.lines['i'], 9)
        self.assertEqual(v['i'][0].lines['k'], 11)
        self.assertEqual(dups, [])

    @unittest.skipUnless(__import__('importlib').util.find_spec('yaml'), 'PyYAML not installed in this interpreter')
    def test_yaml_reader_agrees_with_pyyaml_on_fixtures(self):
        import yaml
        for f in sorted((EX / 'fixtures').rglob('*.yaml')):
            text = f.read_text()
            ours = [d for d, _ in k.load_yaml(text, str(f))[0]]
            ref = [d for d in yaml.safe_load_all(text) if d is not None]
            self.assertEqual(json.loads(json.dumps(ours)), json.loads(json.dumps(ref)), f.name)
        sys.path.insert(0, str(EX))
        import random
        import k8s_oracle
        extra = ['a: >\n  one\n  two\n\n  three\n    indented\n  four\nb: |+\n  kept\n\nc: |-\n  stripped\nd: x\n',
                 'list:\n- - nested\n  - seq\n- {k: [1, 2.5, "q"], j: null}\n- \'single\'\'quote\'\n- "esc\\tape\\u00e9"\n',
                 'k: v # trailing\n"quoted key": 1\nport: "8080"\nempty:\nflag: off\nf: 1.5\n']
        # deliberate difference: 1.5e3 is a float for the Kubernetes reader (YAML 1.1 in Go), a string for PyYAML
        for seed in range(20):
            L, _m, _i = k8s_oracle.gen_bundle(random.Random(seed), 'ns-%d' % seed)
            extra.append("\n".join(L) + "\n")
        for text in extra:
            ours = [d for d, _ in k.load_yaml(text, 'x.yaml')[0]]
            ref = [d for d in yaml.safe_load_all(text) if d is not None]
            self.assertEqual(json.loads(json.dumps(ours)), json.loads(json.dumps(ref)), text[:60])

    def test_unusable_inputs_are_refused_with_location(self):
        for text, code, line in (('a: &x 1\n', 'YAML_UNSUPPORTED', 1), ('a:\n  b: 1\n   c: 2\n', 'YAML_UNSUPPORTED', 3),
                                 ('kind: Pod\nimage: {{ .Values.x }}\n', 'TEMPLATE_UNRENDERED', 2),
                                 ('a: b\n  c\n', 'YAML_UNSUPPORTED', 2), ('', 'NO_OBJECTS', 0)):
            rc, js = self.cli(self.write('u.yaml', text))
            self.assertEqual((rc, js['unusable']['code'], js['unusable']['line']), (2, code, line), text)
            self.assertNotIn('summary', js)
        rc, js = self.cli(self.write('t.yaml', 'metadata:\n\tname: x\n'))
        self.assertEqual((rc, js['unusable']['line']), (2, 2))
        self.assertIn('tab', js['unusable']['reason'])
        rc, js = self.cli(str(self.tmp / 'missing.yaml'))
        self.assertEqual((rc, js['unusable']['code']), (2, 'INPUT_UNREADABLE'))
        deep = 'b: ' + '[' * 3000 + ']' * 3000 + '\n'
        p = subprocess.run([sys.executable, str(TOOL), 'check', self.write('d.yaml', deep)], capture_output=True,
                           text=True, env=ENV, timeout=120)
        self.assertEqual(p.returncode, 2, p.stderr[-300:])
        self.assertNotIn('Traceback', p.stderr)

    def test_anchor_alias_tag_on_a_sequence_item_names_its_own_line(self):
        # M09 P3-1: '- &c name: web' named the next line as a multi-line plain scalar
        for item in ('- &c name: web\n  image: x\n', '- *c\n', '- !t name: web\n  image: x\n', '- &c\n  name: web\n',
                     '- - &d x\n', '- &s plain\n'):
            text = 'apiVersion: v1\nkind: List\nitems:\n' + item
            rc, js = self.cli(self.write('s.yaml', text))
            self.assertEqual((rc, js['unusable']['code'], js['unusable']['line']), (2, 'YAML_UNSUPPORTED', 4), item)
            self.assertIn('anchors, aliases and tags are not read', js['unusable']['reason'], item)

    def test_json_manifest_and_list_kind(self):
        doc = {'apiVersion': 'v1', 'kind': 'List', 'items': [
            {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'p', 'labels': {'app': 'p'}},
             'spec': {'containers': [{'name': 'c', 'image': 'registry.example.test/p:1', 'resources': {
                 'requests': {'cpu': '2', 'memory': '1Gi'}, 'limits': {'cpu': '1', 'memory': '1Gi'}}}]}}]}
        rc, js = self.cli(self.write('l.json', json.dumps(doc)))
        self.assertEqual(rc, 1)
        self.assertEqual([f['code'] for f in js['findings'] if f['severity'] == 'error'], ['REQUEST_EXCEEDS_LIMIT'])

    def test_limitrange_defaults_downgrade_missing_resources(self):
        text = (EX / 'fixtures/clean/worker.yaml').read_text().replace(
            '            cpu: "1"\n            memory: 1Gi\n          limits:\n            cpu: 1000m\n            memory: 1Gi\n',
            '            cpu: "1"\n')
        lr = ('apiVersion: v1\nkind: LimitRange\nmetadata: {name: d, namespace: shop}\nspec:\n  limits:\n'
              '  - type: Container\n    default: {memory: 512Mi}\n    defaultRequest: {memory: 256Mi}\n')
        rc, js = self.cli(self.write('w.yaml', text))
        self.assertIn('RESOURCES_MISSING', [c for c, _ in self.codes(js)])
        rc, js = self.cli(self.write('w.yaml', text), self.write('lr.yaml', lr))
        self.assertEqual((rc, self.codes(js)), (0, []))
        self.assertIn('RESOURCES_DEFAULTED', [c for c, _ in self.codes(js, 'warning')])

    def test_api_rejected_shapes(self):
        base = (EX / 'fixtures/clean/shop.yaml').read_text()
        cases = [
            (base.replace('            - name: metrics\n              containerPort: 9090\n',
                          '            - name: http\n              containerPort: 9090\n'), 'CONTAINER_PORT_NAME_DUPLICATE'),
            (base.replace('name: metrics\n              containerPort', 'name: Metrics_Port\n              containerPort'),
             'PORT_NAME_INVALID'),
            (base.replace('    - name: metrics\n      port: 9090\n', '    - port: 9090\n'), 'SERVICE_PORT_NAME_REQUIRED'),
            (base.replace('  minReplicas: 3\n', '  minReplicas: 12\n'), 'HPA_MIN_GT_MAX'),
            (base.replace('  selector:\n    matchLabels:\n      app.kubernetes.io/name: web\n      tier: frontend\n', '', 1),
             'WORKLOAD_SELECTOR_MISSING'),
        ]
        for text, code in cases:
            rc, js = self.cli(self.write('s.yaml', text))
            self.assertEqual(rc, 1, code)
            self.assertIn(code, [c for c, _ in self.codes(js)])

    def test_service_alone_targetport_default_and_empty_probe(self):
        base = (EX / 'fixtures/clean/shop.yaml').read_text()
        svc = [d for d in base.split('---\n') if 'kind: Service' in d][0]
        rc, js = self.cli(self.write('svc.yaml', svc))
        self.assertEqual((rc, self.codes(js), self.codes(js, 'warning')), (0, [], [('SERVICE_SELECTOR_UNRESOLVED', 7)]))
        t = base.replace('    - name: metrics\n      port: 9090\n      targetPort: 9090\n', '    - name: metrics\n      port: 9091\n')
        rc, js = self.cli(self.write('p.yaml', t))
        self.assertEqual((rc, [c for c, _ in self.codes(js, 'warning')]), (0, ['SERVICE_TARGETPORT_UNDECLARED']))
        t = base.replace('            httpGet: {path: /livez, port: http}\n', '')
        rc, js = self.cli(self.write('e.yaml', t))
        self.assertEqual((rc, [c for c, _ in self.codes(js)]), (1, ['PROBE_HANDLER_INVALID']))

    def test_inputs_never_written_and_no_process_use(self):
        src = TOOL.read_text()
        for w in ('subprocess', 'socket', 'urllib', 'os.system', 'os.popen', "open(f, 'w", 'open(p, "w'):
            self.assertNotIn(w, src)

    def test_scale_two_hundred_namespaces(self):
        base = (EX / 'fixtures/clean/shop.yaml').read_text()
        files = [self.write('n%03d.yaml' % i, base.replace('namespace: shop', 'namespace: t%03d' % i)
                            .replace('name: shop', 'name: t%03d' % i)) for i in range(200)]
        rc, js = self.cli(*files)
        self.assertEqual((rc, js['objects'], js['findings']), (0, 1000, []))


if __name__ == '__main__':
    unittest.main()
