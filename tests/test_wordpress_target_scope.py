"""The documented build steps must preserve the scaffold's selected WP target.

Only one captured WP invocation per consumer runs, against a private fake wp.
These tests do not start WordPress, a database, Docker, or a network operation.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROLE = Path('employees/specialized/wordpress-master/diagnostics')


class WordPressTargetScopeTests(unittest.TestCase):
    def assert_selected_target(self, case_id, document, pattern):
        scaffold = (ROOT / ROLE / 'build-scaffold/SKILL.md').read_text()
        declaration = [line for line in scaffold.splitlines()
                       if line == 'WP=(wp "--path=$BUILD_DIR")']
        self.assertEqual(len(declaration), 1, 'Scaffold must declare the selected target once')
        source = (ROOT / ROLE / document).read_text()
        commands = [line.strip() for line in source.splitlines() if re.search(pattern, line)]
        self.assertEqual(len(commands), 1, f'{case_id}: missing or ambiguous source invocation')
        command = commands[0]
        if command.startswith('if ! '):
            self.assertTrue(command.endswith('; then'))
            command = command[len('if ! '):-len('; then')]
        self.assertTrue(command.startswith(('$WP ', '"${WP[@]}" ')))
        with tempfile.TemporaryDirectory(prefix='solaris-wp-target-') as temporary:
            workspace = Path(temporary)
            binaries = workspace / 'bin'
            binaries.mkdir(mode=0o700)
            fake_wp = binaries / 'wp'
            fake_wp.write_text('#!/bin/sh\nset -eu\nprintf "%s\\0" "$@" > "$WP_SCOPE_LOG"\n')
            fake_wp.chmod(0o700)
            for name, label in [('plain-build', 'PLAIN'),
                                ("build space;literal-$()-'quote", 'LITERAL')]:
                with self.subTest(case=case_id + '-' + label):
                    build = workspace / name
                    build.mkdir()
                    log = workspace / (label + '.argv')
                    title = 'Synthetic target title'
                    environment = {'PATH': str(binaries) + ':/usr/bin:/bin',
                                   'LANG': 'en_US.UTF-8', 'BUILD_DIR': str(build),
                                   'SITE_TITLE': title, 'WP_SCOPE_LOG': str(log)}
                    result = subprocess.run(
                        [shutil.which('bash') or '/bin/bash', '--noprofile', '--norc', '-c',
                         'set -eu\n' + declaration[0] + '\n' + command + '\n'],
                        cwd=workspace, env=environment, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertTrue(log.is_file(), 'Only the inert private WP may record the call')
                    arguments = [value.decode() for value in log.read_bytes().split(b'\0')[:-1]]
                    self.assertTrue(arguments)
                    self.assertEqual(arguments[0], '--path=' + str(build),
                                     'The selected target was dropped from the WP argument vector')
                    if 'blogname' in arguments:
                        self.assertEqual(arguments[-1], title)

    def test_theme_preserves_selected_target(self):
        self.assert_selected_target(
            'WP-ARG-THEME', 'build-theme/SKILL.md',
            r'^(?:\$WP|"\$\{WP\[@\]\}") option update blogname ')

    def test_content_preserves_selected_target(self):
        self.assert_selected_target(
            'WP-ARG-CONTENT', 'build-content/SKILL.md',
            r'^(?:\$WP|"\$\{WP\[@\]\}") option update show_on_front page')

    def test_mcp_preserves_selected_target(self):
        self.assert_selected_target(
            'WP-ARG-MCP', 'build-mcp/SKILL.md',
            r'^\s*if ! (?:\$WP|"\$\{WP\[@\]\}") plugin activate mcp-adapter ')

    def test_visual_preserves_selected_target(self):
        self.assert_selected_target(
            'WP-ARG-VISUAL', 'build-visual/SKILL.md',
            r'^(?:\$WP|"\$\{WP\[@\]\}") db export ')


if __name__ == '__main__':
    unittest.main()
