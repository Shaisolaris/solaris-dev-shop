"""Exercise the documented CSS-token call with private inputs and outputs."""
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROLE = Path('employees/specialized/wordpress-master/diagnostics/build-visual')


class WordPressVisualTokenTests(unittest.TestCase):
    def run_documented(self, workspace, export):
        document = (ROOT / ROLE / 'SKILL.md').read_text()
        blocks = re.findall(r'```bash\n([\s\S]*?)\n```', document)
        setup = [b for b in blocks if b.startswith('TOKENS_DIR=$(mktemp -d ') ]
        invoke = [b for b in blocks if b.startswith('if ! python3 -I ') ]
        self.assertEqual(len(setup), 1)
        self.assertEqual(len(invoke), 1)
        plugin = workspace / "plugin space 'quote"
        helper = plugin / ROLE / 'extract_design_tokens.py'
        helper.parent.mkdir(parents=True)
        helper.write_bytes((ROOT / ROLE / 'extract_design_tokens.py').read_bytes())
        binaries = workspace / 'bin'
        binaries.mkdir(mode=0o700)
        (binaries / 'python3').symlink_to(sys.executable)
        (workspace / 're.py').write_text("raise RuntimeError('LOCAL MODULE EXECUTED')\n")
        private_tmp = workspace / 'private-tmp'
        private_tmp.mkdir(mode=0o700)
        script = ('set -eu\nPLUGIN_DIR="$1"\nVISUAL_PATH="$2"\nTMPDIR="$3"\n' +
                  setup[0] + '\n' + invoke[0] + '\nprintf "%s\\n" "$TOKENS_FILE"\n')
        result = subprocess.run(
            [shutil.which('bash') or '/bin/bash', '--noprofile', '--norc', '-c', script,
             'token-test', str(plugin), str(export), str(private_tmp)],
            cwd=workspace, env={'PATH': str(binaries) + ':/usr/bin:/bin'},
            capture_output=True, text=True, timeout=15)
        return result, private_tmp

    def test_unexported_paths_reach_isolated_helper_and_private_json(self):
        with tempfile.TemporaryDirectory(prefix='solaris-visual-tokens-') as temporary:
            workspace = Path(temporary)
            export = workspace / "export space;literal-'quote"
            export.mkdir()
            (export / 'main.css').write_text(
                'a{color:#123456;background:#fff;font-family:"Playfair Display",serif;}\n'
                'b{color:rgb(1, 2, 3);font-family:DM Sans,sans-serif;}\n'
                'c{font-family:Arial;}\n')
            result, private_tmp = self.run_documented(workspace, export)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(result.stdout.strip())
            self.assertEqual(output.parent.parent, private_tmp)
            self.assertEqual(stat.S_IMODE(output.parent.stat().st_mode), 0o700)
            self.assertEqual(json.loads(output.read_text()), {
                'colors': ['#123456', '#fff', 'rgb(1, 2, 3)'],
                'fonts': ['DM Sans', 'Playfair Display']})

    def test_missing_export_cleans_up_the_owned_intermediate(self):
        with tempfile.TemporaryDirectory(prefix='solaris-visual-refusal-') as temporary:
            workspace = Path(temporary)
            result, private_tmp = self.run_documented(workspace, workspace / 'missing')
            self.assertEqual(result.returncode, 1)
            self.assertIn('Use a regular local CSS export directory', result.stderr)
            self.assertEqual(list(private_tmp.iterdir()), [])

    def test_symlinked_css_is_refused_without_json_output(self):
        with tempfile.TemporaryDirectory(prefix='solaris-visual-link-') as temporary:
            workspace = Path(temporary)
            export = workspace / 'export'
            export.mkdir()
            outside = workspace / 'outside.css'
            outside.write_text('a{color:#badbad;}')
            (export / 'linked.css').symlink_to(outside)
            result = subprocess.run(
                [sys.executable, '-I', str(ROOT / ROLE / 'extract_design_tokens.py'), str(export)],
                cwd=workspace, env={'PATH': '/usr/bin:/bin'},
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')
            self.assertIn('symbolic link', result.stderr)


if __name__ == '__main__':
    unittest.main()
