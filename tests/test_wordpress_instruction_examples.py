"""Execute the maintained WordPress snippets only against disposable local fixtures."""
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
DIAGNOSTICS = ROOT / 'employees/specialized/wordpress-master/diagnostics'


def snippet(skill, heading):
    text = (DIAGNOSTICS / skill / 'SKILL.md').read_text()
    section = text.split(heading, 1)[1]
    return re.search(r'```bash\n(.*?)```', section, re.S).group(1)


@unittest.skipUnless(shutil.which('bash') and shutil.which('git'), 'Bash/Git instruction examples')
class WordPressInstructionExamples(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix='solaris-wp-examples-')
        self.addCleanup(self.fixture.cleanup)
        self.work = Path(self.fixture.name)
        self.env = {key: os.environ[key] for key in ('HOME', 'PATH', 'TMPDIR', 'TEMP', 'SYSTEMROOT') if key in os.environ}
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + self.env.get('PATH', '')
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0')

    def git(self, folder, *args):
        result = subprocess.run(['git', '-C', str(folder), *args], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def build(self, name, initialized='true'):
        target = self.work / name
        target.mkdir()
        self.git(target, 'init', '--quiet', '--initial-branch=main')
        (target / 'content.txt').write_text('fixture\n')
        self.git(target, 'add', 'content.txt')
        self.git(target, '-c', 'user.name=Local QA', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'fixture')
        env = dict(self.env, BUILD_DIR=str(target), GIT_INITIALIZED=initialized)
        result = subprocess.run(['bash', '-e'], input=snippet('build-git', '## Section 7: Build Manifest Update'),
                                cwd=self.work, env=env, capture_output=True, text=True, timeout=20)
        return target, result

    def test_build_manifest_works_with_ordinary_and_quoted_paths(self):
        for name in ('ordinary', 'build with space and "quotes"'):
            with self.subTest(name=name):
                target, result = self.build(name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads((target / 'build.json').read_text())['git'],
                                 {'initialized': True, 'branch': 'main', 'commits': 1})

    def test_directory_name_is_data_and_recovery_remains_useful(self):
        name = 'bad");__import__("pathlib").Path("INJECTED").touch();#'
        target, result = self.build(name)
        self.assertFalse((self.work / 'INJECTED').exists(), 'Directory text executed as Python')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((target / 'build.json').read_text())['git']['commits'], 1)
        recovered, result = self.build('recovery', initialized='false')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((recovered / 'build.json').read_text())['git'],
                         {'initialized': False, 'branch': 'main', 'commits': 0})

    def test_invalid_boolean_is_refused_before_manifest_write(self):
        target, result = self.build('invalid-flag', initialized='False or __import__("pathlib").Path("INJECTED").touch()')
        self.assertFalse((self.work / 'INJECTED').exists(), 'Flag text executed as Python')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((target / 'build.json').exists())

    def test_manifest_reader_does_not_import_project_modules(self):
        marker = self.work / 'IMPORTED_PROJECT_CODE'
        (self.work / 'json.py').write_text(
            'from pathlib import Path\nPath("IMPORTED_PROJECT_CODE").touch()\n'
            'raise RuntimeError("project import executed")\n')
        target, result = self.build('isolated-reader')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(json.loads((target / 'build.json').read_text())['git']['commits'], 1)

    def test_security_source_search_covers_spaced_calls_without_executing_them(self):
        document = DIAGNOSTICS / 'security-analysis/SKILL.md'
        command = next(line for line in document.read_text().splitlines()
                       if line.startswith('grep ') and 'eval' in line)
        self.assertEqual(command.count('/path/to/plugin'), 1)
        command = command.replace('/path/to/plugin', '"$1"')
        root = self.work / 'PHP source with "quotes"'
        root.mkdir()
        (root / 'positive.php').write_text('<?php\neval($value);\neval ($value);\neval\t($value);\n')
        (root / 'negative.php').write_text('<?php\nmy_eval($value);\nevaluate($value);\n')
        result = subprocess.run(['bash', '-c', command, 'search', str(root)],
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 3)
        self.assertNotIn('negative.php', result.stdout)

    def test_remote_config_directory_is_quoted_as_data(self):
        # The ssh executable is replaced only inside this fixture. It runs the
        # captured remote command locally, never contacts an SSH server.
        binary = self.work / 'bin'
        binary.mkdir()
        ssh = binary / 'ssh'
        ssh.write_text('#!/bin/sh\nfor argument do last=$argument; done\nexec /bin/sh -c "$last"\n')
        ssh.chmod(0o700)
        for number, name in enumerate(('ordinary', 'site with "quotes"', 'site; touch INJECTED; #')):
            with self.subTest(name=name):
                case = self.work / ('case-' + str(number))
                case.mkdir()
                target = case / name
                target.mkdir()
                self.git(target, 'init', '--quiet')
                config = target / 'wp-config.php'
                config.write_text('<?php // synthetic fixture\n')
                self.git(target, 'add', 'wp-config.php')
                env = dict(self.env, CONFIG_PATH=str(config), HOST='fixture.invalid')
                env['PATH'] = str(binary) + os.pathsep + env['PATH']
                self.assertEqual(shutil.which('ssh', path=env['PATH']), str(ssh))
                result = subprocess.run(['bash', '-e'],
                                        input=snippet('diagnostic-config-security', '### Check 5: Database Credentials in Version Control'),
                                        cwd=case, env=env, capture_output=True, text=True, timeout=20)
                self.assertFalse((case / 'INJECTED').exists(), 'Directory text executed by remote shell')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('wp-config.php', result.stdout)


if __name__ == '__main__':
    unittest.main()
