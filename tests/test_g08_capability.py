"""G08 local deployment preflight and safe rollback: real processes on disposable worlds.

Runs the G08 oracle against local_deploy.py and two controls, and checks the details it relies on directly.
Nothing uses the network, a cloud account or a path outside a temporary directory.
"""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees/engineering/devops-engineer/local_deploy.py'
EX = ROOT / 'examples/capabilities/G08'
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0, str(EX))
sys.path.insert(0, str(TOOL.parent))
import make_world  # noqa: E402
import local_deploy as ld  # noqa: E402


def oracle(tool):
    p = subprocess.run([sys.executable, str(EX / 'deploy_oracle.py'), '--tool', str(tool), '--json'],
                       capture_output=True, text=True, env=ENV, timeout=600)
    return p.returncode, {c['id']: c['ok'] for c in json.loads(p.stdout)['checks']}


class G08Deploy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g08-test-'))
        self.w = make_world.build(self.tmp / 'w')

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(TOOL)] + list(args), capture_output=True, text=True, env=ENV,
                           cwd=str(self.w), timeout=300)
        return p.returncode, p.stdout, p.stderr

    def deploy(self, name, *extra):
        return self.cli('deploy', 'plan-%s.json' % name, '--approval', 'approval-%s.json' % name, *extra)

    def test_oracle_passes_on_the_tool(self):
        code, res = oracle(TOOL)
        self.assertEqual(code, 0, res)

    def test_oracle_rejects_the_naive_control(self):
        code, res = oracle(EX / 'naive_deploy.py')
        self.assertEqual(code, 1)
        self.assertEqual({k for k, v in res.items() if v}, {'o1', 'o12', 's1'})

    def test_oracle_rejects_the_noop_control(self):
        code, res = oracle(EX / 'noop_deploy.py')
        self.assertEqual({k for k, v in res.items() if v}, {'s1'})

    def test_digest_matches_the_world_builder(self):
        for d in self.w.glob('artifact-*'):
            self.assertEqual(ld.tree_digest(d)[0], make_world.digest(d))
        code, out, _ = self.cli('digest', 'artifact-r1')
        self.assertIn(make_world.digest(self.w / 'artifact-r1'), out)

    def test_preflight_names_each_failed_check(self):
        code, out, _ = self.cli('preflight', 'plan-r1.json', '--json')
        self.assertEqual(code, 2)
        checks = {c['check']: c['ok'] for c in json.loads(out)['checks']}
        self.assertEqual(checks, {'environment': True, 'artifact': True, 'authority': False, 'health': True,
                                  'rollback': True})
        (self.w / 'env/ENVIRONMENT.json').write_text(json.dumps({'schema': 'solaris.local-environment/1',
                                                                 'name': 'staging-local', 'kind': 'cloud'}))
        code, out, _ = self.cli('preflight', 'plan-r1.json', '--approval', 'approval-r1.json', '--json')
        self.assertEqual({c['check'] for c in json.loads(out)['checks'] if not c['ok']}, {'environment'})

    def test_failed_release_is_kept_for_inspection_and_history_says_why(self):
        self.assertEqual(self.deploy('r1')[0], 0)
        self.assertEqual(self.deploy('r3-broken')[0], 1)
        failed = [p.name for p in (self.w / 'env/releases').iterdir() if p.name.startswith('.failed-r3-')]
        self.assertEqual(len(failed), 1)
        hist = [json.loads(x) for x in (self.w / 'env/.deploy/history.jsonl').read_text().splitlines()]
        self.assertEqual(hist[-1]['event'], 'rolled_back')
        self.assertIn('index.html missing or empty', hist[-1]['reason'])
        self.assertFalse((self.w / 'env/.deploy/journal.json').exists())

    def test_migration_is_one_transaction(self):
        self.assertEqual(self.deploy('r1')[0], 0)
        self.assertEqual(self.deploy('r2')[0], 0)
        self.assertEqual(self.deploy('r3-badmigration')[0], 1)
        con = sqlite3.connect(str(self.w / 'env/data/app.db'))
        self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(con.execute('SELECT sum(total_cents) FROM orders').fetchone()[0], 1250 + 4800 + 990)
        con.close()

    def tree(self):
        out = {}
        for p in sorted((self.w / 'env').rglob('*')):
            out[str(p)] = os.readlink(str(p)) if p.is_symlink() else p.read_bytes() if p.is_file() else None
        return out

    def test_held_lock_refuses_every_mutating_command(self):
        import fcntl
        self.assertEqual(self.deploy('r1')[0], 0)
        self.assertEqual(self.deploy('r2')[0], 0)
        before = self.tree()
        fd = os.open(str(self.w / 'env'), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for args in (('deploy', 'plan-r3-broken.json', '--approval', 'approval-r3-broken.json'),
                         ('rollback', 'plan-r2.json', '--approval', 'approval-rollback-to-r1.json'),
                         ('recover', 'plan-r2.json')):
                code, _, err = self.cli(*args)
                self.assertEqual(code, 2, args)
                self.assertIn('holds the lock', err)
            self.assertEqual(self.cli('preflight', 'plan-r2.json', '--approval', 'approval-r2.json')[0], 2)  # no lock taken
            self.assertEqual(self.tree(), before)
        finally:
            os.close(fd)
        self.assertEqual(self.deploy('r3-broken')[0], 1)  # released: the next caller runs
        self.assertEqual(self.deploy('r3-broken', '--fail-at', 'switched')[0], 75)
        self.assertEqual(self.cli('recover', 'plan-r2.json')[0], 1)  # a crashed holder leaves no stale lock

    def test_repeat_deploy_needs_approval_and_health(self):
        self.assertEqual(self.deploy('r1')[0], 0)
        before = self.tree()
        code, out, _ = self.cli('deploy', 'plan-r1.json', '--json')
        self.assertEqual(self.tree(), before)
        self.assertEqual(code, 2)
        self.assertEqual([c['check'] for c in json.loads(out)['checks'] if not c['ok'] and c['check'] != 'rollback'], ['authority'])
        code, out, _ = self.deploy('r1')
        self.assertEqual(code, 0)
        self.assertIn('approved and healthy', out)
        con = sqlite3.connect(str(self.w / 'env/data/app.db'))
        con.execute('PRAGMA user_version = 7')
        con.commit()
        con.close()
        code, out, _ = self.deploy('r1')
        self.assertEqual(code, 2)
        self.assertIn('health failed', out)
        os.remove(str(self.w / 'env/releases/r1/index.html'))
        before = self.tree()
        self.assertEqual(self.deploy('r1')[0], 2)
        self.assertEqual(self.tree(), before)

    def test_secret_like_names(self):
        for n in ('.env', 'config/.env.production', 'deploy.pem', 'id_rsa', 'gcp/credentials.json', 'x.key'):
            self.assertTrue(ld.SECRET_RE.search(n), n)
        for n in ('index.html', 'environment.md', 'keys.txt', 'monkey.html'):
            self.assertFalse(ld.SECRET_RE.search(n), n)

    def test_symlink_in_artifact_refused(self):
        os.symlink('/etc/hosts', str(self.w / 'artifact-r1' / 'hosts'))
        code, out, _ = self.cli('preflight', 'plan-r1.json', '--approval', 'approval-r1.json')
        self.assertEqual(code, 2)
        self.assertIn('symlink', out)

    def test_readme_demo(self):
        demo = (EX / 'README.md').read_text().split('```bash\n')[1].split('```')[0]
        lines = [c for c in demo.splitlines() if c.startswith('python3 $T ')]
        codes = [self.cli(*c.split('#')[0].split()[2:])[0] for c in lines]
        self.assertEqual(len(lines), 9)
        self.assertEqual(codes, [int(x.split('# exit ')[1].split(':')[0]) for x in lines])


if __name__ == '__main__':
    unittest.main()
