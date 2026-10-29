"""Ambient credentials must not flow into unrelated helper subprocesses."""
import ast
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / 'tests/fixtures/subprocess-environment-scope.json'


class ChildEnvironmentScopeTests(unittest.TestCase):
    def test_all_reviewed_ambient_environment_constructors_refuse_unrelated_secrets(self):
        scope = json.loads(SCOPE.read_text())
        synthetic = {'PATH': '/synthetic/bin', 'HOME': '/synthetic/home',
                     'TMPDIR': '/synthetic/tmp', 'SystemRoot': 'C:/SyntheticWindows',
                     'NVIDIA_API_KEY': 'synthetic-no-authority',
                     'AWS_SECRET_ACCESS_KEY': 'synthetic-no-authority',
                     'UNRELATED_APPLICATION_TOKEN': 'synthetic-no-authority',
                     'PIP_INDEX_URL': 'https://synthetic.invalid/simple',
                     'PYTHONPATH': '/synthetic/untrusted-imports',
                     'PYTHONPYCACHEPREFIX': '/synthetic/unwanted-cache'}
        fake_os = types.SimpleNamespace(environ=synthetic)
        seen = 0
        for name, expected in scope['files'].items():
            source = (ROOT / name).read_text()
            tree = ast.parse(source)
            expressions = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict' and node.args:
                    argument = node.args[0]
                    if isinstance(argument, ast.Attribute) and ast.unparse(argument) in ('os.environ', '_os.environ'):
                        expressions[(argument.lineno, argument.col_offset)] = argument
                if isinstance(node, ast.DictComp):
                    text = ast.get_source_segment(source, node)
                    iterator = node.generators[0].iter
                    literal_keys = {part.value for part in iterator.elts if isinstance(part, ast.Constant)} if isinstance(iterator, (ast.Tuple, ast.List)) else set()
                    inherited_items = isinstance(iterator, ast.Call) and ast.unparse(iterator.func) in ('os.environ.items', '_os.environ.items')
                    reviewed_allowlist = {'PYTHONUTF8', 'CURL_CA_BUNDLE'}.issubset(literal_keys)
                    if '.environ' in text and (inherited_items or reviewed_allowlist):
                        expressions[(node.lineno, node.col_offset)] = node
            self.assertEqual(len(expressions), expected, name + ': source scope drift')
            for (line, _), expression in expressions.items():
                with self.subTest(source=name, line=line):
                    seen += 1
                    # Evaluate only the environment expression against synthetic data.
                    # No product function, import, command, or real environment runs.
                    for call in (n for n in ast.walk(expression) if isinstance(n, ast.Call)):
                        self.assertIn(ast.unparse(call.func), ('os.environ.items', '_os.environ.items'))
                    result = eval(compile(ast.Expression(expression), name, 'eval'),
                                  {'os': fake_os, '_os': fake_os, '__builtins__': {}}, {})
                    for key in ('PATH', 'HOME', 'TMPDIR', 'SystemRoot'):
                        self.assertEqual(result.get(key), synthetic[key])
                    for key in ('NVIDIA_API_KEY', 'AWS_SECRET_ACCESS_KEY', 'UNRELATED_APPLICATION_TOKEN',
                                'PIP_INDEX_URL', 'PYTHONPATH', 'PYTHONPYCACHEPREFIX'):
                        self.assertNotIn(key, result)
        self.assertEqual(seen, scope['callCount'])

    def test_video_concat_uses_owned_private_list_and_cleans_up_on_success_and_failure(self):
        document = (ROOT / 'employees/creative-media/video-editor/SKILL.md').read_text()
        section = document.split('### Same codec (no re-encode)\n', 1)[1].split('\n### ', 1)[0]
        block = re.search(r'```bash\n([\s\S]*?)\n```', section).group(1)
        with tempfile.TemporaryDirectory(prefix='solaris-concat-scope-') as temporary:
            workspace = Path(temporary)
            binaries = workspace / 'bin'
            binaries.mkdir(mode=0o700)
            fake = binaries / 'ffmpeg'
            fake.write_text('#!' + sys.executable + '\n'
                            'import json,os,pathlib,stat,sys\n'
                            'args=sys.argv[1:];p=pathlib.Path(args[args.index("-i")+1])\n'
                            'data={"args":args,"content":p.read_text(),"mode":stat.S_IMODE(p.parent.stat().st_mode)}\n'
                            'pathlib.Path(os.environ["CONCAT_CAPTURE"]).write_text(json.dumps(data))\n'
                            'sys.exit(int(os.environ["FAKE_FFMPEG_EXIT"]))\n')
            fake.chmod(0o700)
            sentinel = workspace / 'concat_list.txt'
            sentinel.write_text('unrelated pre-existing content\n')
            for exit_code in (0, 7):
                with self.subTest(ffmpeg_exit=exit_code):
                    capture = workspace / ('capture-' + str(exit_code) + '.json')
                    outer = workspace / ('outer-' + str(exit_code))
                    environment = {'PATH': str(binaries) + ':/usr/bin:/bin',
                                   'OUTPUT': str(workspace / 'output.mp4'),
                                   'CONCAT_CAPTURE': str(capture), 'FAKE_FFMPEG_EXIT': str(exit_code),
                                   'OUTER_TRAP': str(outer)}
                    result = subprocess.run(
                        [shutil.which('bash') or '/bin/bash', '--noprofile', '--norc'],
                        input='set -eu\ntrap \'touch "$OUTER_TRAP"\' EXIT\n' + block + '\n',
                        text=True, capture_output=True, cwd=workspace, env=environment, timeout=10)
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    data = json.loads(capture.read_text())
                    self.assertEqual(data['content'], "file '../file1.mp4'\nfile '../file2.mp4'\nfile '../file3.mp4'\n")
                    self.assertEqual(data['mode'], 0o700)
                    self.assertEqual(list(workspace.glob('.solaris-concat.*')), [])
                    self.assertTrue(outer.is_file(), 'The caller trap was replaced')
                    self.assertEqual(sentinel.read_text(), 'unrelated pre-existing content\n')


if __name__ == '__main__':
    unittest.main()
