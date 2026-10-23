"""Exercise setup instructions without contacting Docker, services or a network."""
import json
import copy
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

    def test_comma_in_mount_path_is_refused_before_docker(self):
        code = bash_block(ROOT / 'employees/engineering/devops-engineer/docker-skill.md',
                          '## Example: bounded offline analysis')
        for value in ('SOLARIS_INPUT_DIR', 'SOLARIS_OUTPUT_DIR'):
            extra = dict(SOLARIS_DEV_IMAGE='reviewed/image@sha256:' + '0'*64,
                         SOLARIS_INPUT_DIR=str(self.work), SOLARIS_OUTPUT_DIR=str(self.work / 'out'))
            extra[value] += ',readonly=false'
            result = self.run_bash(code, **extra)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.docker_calls(), [])

    def test_optional_mcp_examples_refuse_mutable_images(self):
        examples = [
            ('employees/engineering/unity-developer/unity-mcp-operator.md', '**Docker alternative**', 'SOLARIS_UNITY_MCP_IMAGE'),
            ('employees/engineering/unreal-developer/unreal-mcp-operator.md', '**Docker alternative', 'SOLARIS_UNREAL_MCP_IMAGE'),
            ('employees/leadership/cfo/filings-and-market-data-tooling.md', '## CONNECT', 'SOLARIS_SEC_MCP_IMAGE'),
        ]
        for path, heading, variable in examples:
            with self.subTest(path=path):
                code = bash_block(ROOT / path, heading)
                result = self.run_bash(code, **{variable: 'image:latest'})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.docker_calls(), [])

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

    def test_checkout_installs_and_runs_offline_without_dependency_setup(self):
        # These guards apply to every child Python process in this fixture.
        # The installer's old full developer suite runs network/pip smoke tests;
        # installation must instead remain a bounded offline routing check.
        sentinel = self.work / 'UNREQUESTED_SETUP'
        (self.bin / 'sitecustomize.py').write_text('''
import os, socket, subprocess
from pathlib import Path
def refuse_network(*args, **kwargs):
    Path(os.environ['SETUP_SENTINEL']).write_text('network')
    raise RuntimeError('Network disabled in installer fixture')
socket.socket = refuse_network
socket.create_connection = refuse_network
original_popen = subprocess.Popen
def checked_popen(args, *rest, **kwargs):
    if isinstance(args, (list, tuple)) and ('pip' in args or 'pip3' in args):
        Path(os.environ['SETUP_SENTINEL']).write_text('package installation')
        raise RuntimeError('Dependency installation disabled in installer fixture')
    return original_popen(args, *rest, **kwargs)
subprocess.Popen = checked_popen
''')
        env = dict(self.env, PYTHONPATH=str(self.bin), SETUP_SENTINEL=str(sentinel))
        output = self.work / 'commands'
        install = subprocess.run(['bash', str(ROOT / 'install.sh'), '--bin-dir', str(output)],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
        command = output / 'solaris-intake'
        self.assertTrue(command.is_file())
        result = subprocess.run([str(command), 'intake', 'review this code', '--json'],
                                cwd=self.work, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['assignment']['primary_capability'], 'solaris.code-reviewer')
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse(sentinel.exists(), 'Installer attempted network or dependency setup')

    def test_mobile_listener_requires_scope_and_auth_and_binds_only_loopback(self):
        path = ROOT / 'employees/engineering/mobile-developer/mobile-mcp-operator.md'
        code = bash_block(path, '### Authorized loopback HTTP example')
        log = self.work / 'mobile-call.json'
        self.stub('mobile tool', '''import json, os, sys
from pathlib import Path
Path(os.environ['MOBILE_LOG']).write_text(json.dumps({
    'args': sys.argv[1:], 'auth_length': len(os.environ.get('MOBILEMCP_AUTH', '')),
    'telemetry_disabled': os.environ.get('MOBILEMCP_DISABLE_TELEMETRY')}))
''')
        values = dict(MOBILE_MCP_BIN=str(self.bin / 'mobile tool'), MOBILE_LOG=str(log))
        for extra in ({}, {'SOLARIS_SERVICE_START_AUTHORIZED': 'yes'},
                      {'SOLARIS_SERVICE_START_AUTHORIZED': 'yes', 'MOBILEMCP_AUTH': 'secret'}):
            with self.subTest(extra=extra):
                result = self.run_bash(code, **dict(values, **extra))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(log.exists(), 'Unauthorized listener process was invoked')
        result = self.run_bash(code, **dict(values, SOLARIS_SERVICE_START_AUTHORIZED='yes',
                                           MOBILEMCP_AUTH='fixture-' * 6))
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(log.read_text())
        self.assertEqual(observed['args'], ['--listen', '127.0.0.1:3000'])
        self.assertEqual(observed['auth_length'], 48)
        self.assertEqual(observed['telemetry_disabled'], '1')


class LearningSourceReview(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'control-plane'))
        import meta_control_plane
        self.engine = meta_control_plane
        self.policy = self.engine.load_policy()
        self.roster = self.engine.load_roster()
        self.budgets = self.engine.load_budgets()

    def route(self, pending, budgets=None):
        return self.engine.intake('Review this code', policy=self.policy,
                                  roster=self.roster, budgets=budgets or self.budgets,
                                  budget_usage={'learning_promotions_pending': pending})

    def test_one_or_many_pending_promotions_require_a_real_review_envelope(self):
        for count in (1, 3, 4, 100):
            with self.subTest(count=count):
                result = self.route(count)
                self.assertEqual(result.decision, 'escalate')
                self.assertIsNone(result.assignment)
                self.assertFalse(result.performed_work)
                self.assertEqual(result.escalation.reason, 'permission_required')
                self.assertIn('learning_source_changes_require_review', result.escalation.evidence)

    def test_caller_budget_is_not_permission_to_rewrite_installed_skills(self):
        budgets = copy.deepcopy(self.budgets)
        budgets['defaults']['learning_promotions_auto_max'] = 999
        self.assertEqual(self.route(1, budgets).decision, 'escalate')

    def test_missing_learning_budget_does_not_restore_legacy_auto_allowance(self):
        budgets = copy.deepcopy(self.budgets)
        budgets['defaults'].pop('learning_promotions_auto_max')
        self.assertEqual(self.route(1, budgets).decision, 'escalate')

    def test_ordinary_work_remains_assignable_without_a_source_promotion(self):
        result = self.route(0)
        self.assertEqual(result.decision, 'assign')
        self.assertEqual(result.assignment.primary_capability, 'solaris.code-reviewer')
        self.assertFalse(result.performed_work)


if __name__ == '__main__':
    unittest.main()
