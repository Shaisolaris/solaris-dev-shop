"""Exercise setup instructions without contacting Docker, services or a network."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WP = ROOT / 'employees/specialized/wordpress-master/diagnostics'


def bash_block(path, heading):
    section = path.read_text().split(heading, 1)[1]
    return re.search(r'```bash\n(.*?)```', section, re.S).group(1)


@unittest.skipUnless(shutil.which('bash') and os.name == 'posix', 'Bash setup examples')
class ExplicitRuntimeSetup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='solaris-runtime-scope-')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.bin = self.work / 'bin'
        self.bin.mkdir()
        self.calls = self.work / 'calls.jsonl'
        self.env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'SYSTEMROOT') if key in os.environ}
        self.env.update(HOME=str(self.work / 'home'),
                        PATH=str(self.bin) + os.pathsep + self.env.get('PATH', ''),
                        CALL_LOG=str(self.calls), SOLARIS_PYTHON=sys.executable,
                        JSON_FIELDS=str(WP / 'shared/json_fields.py'), BUILD_DIR=str(self.work))
        self.stub('docker', '''import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:2] == ['run']: print('fixture-container')
''')
        self.stub('git', "raise SystemExit('Unexpected Git/network/update operation')\n")
        self.stub('wp', "import sys\nprint('synthetic-db-password' if sys.argv[-1:] == ['DB_PASSWORD'] else 'wp')\n")
        self.stub('lsof', 'raise SystemExit(1)\n')
        self.stub('id', 'import sys\nprint(501 if sys.argv[-1:] == ["-u"] else 20)\n')

    def stub(self, name, program):
        target = self.bin / name
        target.write_text('#!' + sys.executable + '\n' + program)
        target.chmod(0o700)

    def run_bash(self, program, **extra):
        return subprocess.run(['bash', '-eu'], input=program, cwd=self.work,
                              env=dict(self.env, **extra), text=True, capture_output=True, timeout=15)

    def docker_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def modify(self, suffix='', **extra):
        code = bash_block(WP / 'build-modify/SKILL.md', '## Section 0: Prerequisites and Setup')
        return self.run_bash(code + '\n' + suffix, **extra)

    def test_loading_modify_helpers_and_theme_work_do_not_contact_docker(self):
        result = self.modify('printf theme-only > theme-output.txt')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / 'theme-output.txt').read_text(), 'theme-only')
        self.assertEqual(self.docker_calls(), [])

    def test_modify_refuses_missing_scope_or_mutable_image_before_docker(self):
        for extra in ({}, {'SOLARIS_CONTAINER_START_AUTHORIZED': 'no'},
                      {'SOLARIS_CONTAINER_START_AUTHORIZED': 'yes', 'SOLARIS_MYSQL_IMAGE': 'mysql:8.0'},
                      {'SOLARIS_CONTAINER_START_AUTHORIZED': 'yes', 'SOLARIS_MYSQL_IMAGE': 'mysql@sha256:' + '0'*63}):
            with self.subTest(extra=extra):
                result = self.modify('ensure_docker_mysql', **extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.docker_calls(), [])

    def test_scaffold_refuses_missing_scope_and_image_before_docker(self):
        code = bash_block(WP / 'build-scaffold/SKILL.md', '## Section 1: Prerequisite Checks')
        for extra in ({}, {'SOLARIS_CONTAINER_START_AUTHORIZED': 'yes', 'SOLARIS_MYSQL_IMAGE': 'mysql:latest'}):
            with self.subTest(extra=extra):
                result = self.run_bash(code, **extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.docker_calls(), [])

    def test_missing_local_wp_cli_does_not_launch_a_fallback(self):
        (self.bin / 'wp').unlink()
        # Isolate PATH so a developer's host WP-CLI cannot satisfy the fixture.
        for name in ('bash',):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env['PATH'] = str(self.bin)
        code = bash_block(WP / 'build-scaffold/SKILL.md', '## Section 1: Prerequisite Checks')
        result = self.run_bash(code, SOLARIS_CONTAINER_START_AUTHORIZED='yes',
                               SOLARIS_MYSQL_IMAGE='mysql@sha256:' + '0'*64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('WP-CLI', result.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_explicit_modify_preserves_bounded_start_import_and_cleanup(self):
        (self.work / 'database.sql').write_text('-- disposable fixture\n')
        image = 'mysql@sha256:' + '0'*64
        result = self.modify('ensure_docker_mysql', SOLARIS_CONTAINER_START_AUTHORIZED='yes',
                             SOLARIS_MYSQL_IMAGE=image)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.docker_calls()
        start = next(args for args in calls if args[0] == 'run')
        self.assertIn('--pull=never', start)
        self.assertIn('--restart=no', start)
        self.assertIn('127.0.0.1:3307:3306', start)
        self.assertIn(image, start)
        self.assertFalse(any('host' == arg or 'docker.sock' in arg for arg in start))
        self.assertTrue(any(args[:2] == ['rm', '-f'] for args in calls))
        self.assertIn('Database imported', result.stdout)

    def test_optional_offline_container_rejects_mutable_image_and_root(self):
        code = bash_block(ROOT / 'employees/engineering/devops-engineer/docker-skill.md',
                          '## Example: bounded offline analysis')
        values = dict(SOLARIS_DEV_IMAGE='node:latest', SOLARIS_INPUT_DIR=str(self.work),
                      SOLARIS_OUTPUT_DIR=str(self.work / 'out'))
        result = self.run_bash(code, **values)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.docker_calls(), [])
        self.stub('id', 'print(0)\n')
        values['SOLARIS_DEV_IMAGE'] = 'reviewed/image@sha256:' + '0'*64
        result = self.run_bash(code, **values)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.docker_calls(), [])

    def test_optional_container_argument_boundaries_and_limits(self):
        code = bash_block(ROOT / 'employees/engineering/devops-engineer/docker-skill.md',
                          '## Example: bounded offline analysis')
        path = self.work / 'input with spaces; touch SHOULD_NOT_EXIST'
        image = 'reviewed/image@sha256:' + '0'*64
        result = self.run_bash(code, SOLARIS_DEV_IMAGE=image, SOLARIS_INPUT_DIR=str(path),
                               SOLARIS_OUTPUT_DIR=str(self.work / 'out'))
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.docker_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn('type=bind,src=' + str(path) + ',dst=/input,readonly', calls[0])
        for value in ('--pull=never', '--network=none', '--read-only', '--cap-drop=ALL',
                      '--security-opt=no-new-privileges', '--pids-limit=128'):
            self.assertIn(value, calls[0])
        self.assertFalse((self.work / 'SHOULD_NOT_EXIST').exists())

    def test_outside_checkout_installer_never_fetches_or_updates(self):
        target = Path(self.env['HOME']) / '.solaris-dev-shop'
        target.mkdir(parents=True)
        original = target / 'owner-content'
        original.write_text('retain me')
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--bin-dir', str(self.work / 'out')],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No code was downloaded or updated', result.stderr)
        self.assertEqual(original.read_text(), 'retain me')
        self.assertFalse((self.work / 'out').exists())
        self.assertEqual(self.docker_calls(), [])


if __name__ == '__main__':
    unittest.main()
