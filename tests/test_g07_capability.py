"""G07 fleet registration without duplicate ownership: real processes on disposable folders.

Runs the G07 oracle against registry.py and two controls, and checks the pieces it relies on (request
idempotency, compare-and-set ownership, crash settlement, the hash binding of registry.json, the G04 runner's
fleet gate) directly. Nothing contacts a machine, uses the network or touches a path outside a temp folder.
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
TOOL = ROOT / 'employees/infrastructure/fleet-provisioner/registry.py'
HANDOFF = ROOT / 'employees/infrastructure/fleet-dispatcher/handoff.py'
EX = ROOT / 'examples/capabilities/G07'
ENV = {k: v for k, v in os.environ.items() if k not in ('SOLARIS_FLEET_ROOT', 'SOLARIS_MACHINE_IDENTITY')}
ENV['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(0, str(TOOL.parent))
import registry as r  # noqa: E402


def oracle(tool, scale=16):
    p = subprocess.run([sys.executable, str(EX / 'registry_oracle.py'), '--tool', str(tool), '--json',
                        '--scale', str(scale)], capture_output=True, text=True, env=ENV, timeout=600)
    return p.returncode, {c['id']: c['ok'] for c in json.loads(p.stdout)['checks']}


class G07Registry(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g07-test-'))
        self.root = self.tmp / 'fleet'
        self.root.mkdir()
        shutil.copytree(str(EX / 'fixtures'), str(self.tmp / 'id'))

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def ident(self, n):
        return str(self.tmp / 'id' / ('identity-%s.json' % n))

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(TOOL), args[0], '--root', str(self.root)] + list(args[1:]),
                           capture_output=True, text=True, env=ENV, timeout=120)
        return p.returncode, p.stdout, p.stderr

    def register(self, alias='mini1', ident='mini1', owner='ana', req='r1'):
        return self.cli('register', '--alias', alias, '--identity', self.ident(ident), '--owner', owner,
                        '--request-id', req)[0]

    def transfer(self, frm, epoch, to, req, *extra):
        return self.cli('transfer', '--alias', 'mini1', '--from-owner', frm, '--expect-epoch', str(epoch),
                        '--to-owner', to, '--request-id', req, *extra)[0]

    def state(self):
        return json.loads((self.root / 'registry.json').read_text())['machines']

    def test_oracle_passes_on_the_registry(self):
        code, res = oracle(TOOL)
        self.assertEqual(code, 0, res)
        self.assertTrue(all(res.values()), res)

    def test_oracle_rejects_the_naive_control(self):
        code, res = oracle(EX / 'naive_registry.py')
        self.assertEqual(code, 1)
        # o10 races unlocked writers in the naive control, so whether it shows depends on scheduling
        self.assertEqual({k for k, v in res.items() if not v} - {'o10'},
                         {'o4', 'o5', 'o6', 'o7', 'o8', 'o9', 'o11', 'o12', 'o13', 'o14', 'o15', 'o16'})

    def test_oracle_rejects_the_noop_control(self):
        code, res = oracle(EX / 'noop_registry.py')
        self.assertEqual(code, 1)
        self.assertEqual({k for k, v in res.items() if v}, {'s1'})

    def test_repeated_and_duplicate_registration(self):
        self.assertEqual([self.register(req='r1') for _ in range(2)] + [self.register(req='r9')], [0, 0, 0])
        self.assertEqual(self.register(alias='spare', owner='ben', req='r2'), 2)
        self.assertEqual(len(self.state()), 1)
        intents = [json.loads(x) for x in (self.root / 'ops.jsonl').read_text().splitlines()]
        self.assertEqual([x['phase'] for x in intents], ['intent', 'commit'])
        self.assertEqual(self.register(alias='mini2', ident='mini2', req='r1'), 2)  # r1 reused for another change

    def test_crash_points_settle_on_next_command(self):
        self.register()
        self.assertEqual(self.transfer('ana', 1, 'ben', 't1', '--fail-at', 'before-replace'), 75)
        code, out, _ = self.cli('status')
        self.assertEqual((self.state()[0]['owner'], self.state()[0]['owner_epoch']), ('ana', 1))
        self.assertIn('rolled back change t1', out)
        self.assertEqual(self.transfer('ana', 1, 'ben', 't2', '--fail-at', 'after-replace'), 75)
        code, out, _ = self.cli('status')
        self.assertIn('finished change t2', out)
        self.assertEqual(self.transfer('ana', 1, 'ben', 't2'), 0)
        self.assertEqual((self.state()[0]['owner'], self.state()[0]['owner_epoch']), ('ben', 2))
        fleet = (self.root / 'FLEET.md').read_text()
        self.assertIn('| mini1 | mini-7f3a-0001 | ben | 2 | active |', fleet)

    def test_torn_ops_tail_is_cut_and_noted(self):
        self.register()
        with open(self.root / 'ops.jsonl', 'ab') as f:
            f.write(b'{"phase":"inte')
        code, out, _ = self.cli('status')
        self.assertEqual(code, 0)
        self.assertIn('torn last line', out)
        self.assertTrue((self.root / 'ops.jsonl').read_bytes().endswith(b'\n'))

    def test_unreadable_ops_line_and_outside_edit_refuse(self):
        self.register()
        reg = (self.root / 'registry.json').read_bytes()
        (self.root / 'registry.json').write_bytes(reg.replace(b'"ana"', b'"eve"'))
        code, _, err = self.cli('claim', '--alias', 'mini1', '--identity', self.ident('mini1'), '--owner', 'eve',
                                '--epoch', '1')
        self.assertEqual(code, 2)
        self.assertIn('edited outside', err)
        (self.root / 'registry.json').write_bytes(reg)
        with open(self.root / 'ops.jsonl', 'ab') as f:
            f.write(b'not json\n')
        self.assertEqual(self.cli('status')[0], 2)

    def test_changes_wait_for_the_registry_lock(self):
        import fcntl
        import time
        self.register()
        fd = os.open(str(self.root / '.registry.lock'), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            p = subprocess.Popen([sys.executable, str(TOOL), 'transfer', '--root', str(self.root), '--alias', 'mini1',
                                  '--from-owner', 'ana', '--expect-epoch', '1', '--to-owner', 'ben',
                                  '--request-id', 't1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ENV)
            time.sleep(1.0)
            self.assertIsNone(p.poll(), 'a change ran while another process held the registry lock')
            self.assertEqual(self.state()[0]['owner'], 'ana')
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        self.assertEqual(p.wait(timeout=60), 0)
        self.assertEqual(self.state()[0]['owner'], 'ben')

    def test_check_claim_names_the_reason(self):
        self.register()
        with self.assertRaisesRegex(r.Refused, 'wrong machine'):
            r.check_claim(str(self.root), 'mini1', self.ident('impostor'), 'ana', 1)
        with self.assertRaisesRegex(r.Refused, 'stale owner'):
            r.check_claim(str(self.root), 'mini1', self.ident('mini1'), 'ana', 2)
        self.assertEqual(r.check_claim(str(self.root), 'mini1', self.ident('mini1'), 'ana', 1)['owner_epoch'], 1)

    def test_handoff_fleet_gate(self):
        w = self.tmp / 'wo'
        shutil.copytree(str(ROOT / 'examples/capabilities/G04/fixtures'), str(w))
        order = json.loads((w / 'order.json').read_text())
        self.register(owner=order['owner'])
        order['fleet'] = {'machine': 'mini1', 'owner_epoch': 1}
        (w / 'order.json').write_text(json.dumps(order))
        env = dict(ENV, SOLARIS_FLEET_ROOT=str(self.root))

        def go(ident):
            return subprocess.run([sys.executable, str(HANDOFF), 'run', str(w / 'order.json'), '--worker', 'w',
                                   '--identity', self.ident(ident)], capture_output=True, text=True, env=env,
                                  timeout=300)
        p = go('impostor')
        self.assertEqual(p.returncode, 2)
        self.assertIn('wrong machine', p.stderr)
        self.assertFalse((w / '.handoff').exists())
        self.assertEqual(go('mini1').returncode, 0)
        self.assertEqual(len((w / 'outbox' / 'ledger.jsonl').read_text().splitlines()), 1)
        order['fleet']['bogus'] = 1
        (w / 'order.json').write_text(json.dumps(order))
        self.assertEqual(go('mini1').returncode, 2)

    def test_readme_demo(self):
        demo = (EX / 'README.md').read_text().split('```bash\n')[1].split('```')[0]
        lines = [c for c in demo.splitlines() if c.startswith('python3 $R ')]
        cmds = [c.split('#')[0].strip() for c in lines]
        os.makedirs(str(self.tmp / 'demo' / 'fleet'))
        shutil.copytree(str(EX / 'fixtures'), str(self.tmp / 'demo' / 'id'))
        codes = []
        for c in cmds:
            args = c.split()[2:]
            p = subprocess.run([sys.executable, str(TOOL)] + args, capture_output=True, text=True, env=ENV,
                               cwd=str(self.tmp / 'demo'), timeout=120)
            codes.append(p.returncode)
        expect = [int(x.split('# exit ')[1].split(':')[0]) for x in lines]
        self.assertEqual(len(codes), 9)
        self.assertEqual(codes, expect)


if __name__ == '__main__':
    unittest.main()
