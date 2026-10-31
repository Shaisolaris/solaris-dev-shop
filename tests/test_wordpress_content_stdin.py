"""Exercise documented content transport with a private inert WP command."""
from pathlib import Path
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / 'employees/specialized/wordpress-master/diagnostics/build-content/SKILL.md'


class WordPressContentStdinTests(unittest.TestCase):
    def test_pages_and_post_preserve_literal_content_and_selected_target(self):
        source = DOCUMENT.read_text()
        blocks = re.findall(r'```bash\n([\s\S]*?)\n```', source)
        examples = [block for block in blocks if '"${WP[@]}" post create - ' in block
                    and "<< 'CONTENT_EOF'" in block]
        self.assertEqual(len(examples), 4)
        with tempfile.TemporaryDirectory(prefix='solaris-wp-stdin-') as temporary:
            workspace = Path(temporary)
            binaries = workspace / 'bin'
            binaries.mkdir(mode=0o700)
            fake = binaries / 'wp'
            fake.write_text('#!/bin/sh\nset -eu\nprintf "%s\\0" "$@" > "$STDIN_LOG.argv"\n'
                            'cat > "$STDIN_LOG.body"\nprintf "123\\n"\n')
            fake.chmod(0o700)
            for index, block in enumerate(examples):
                # Bash 3.2 misparses apostrophes in heredocs nested inside $(...).
                # Preserve this signal on CI hosts whose default Bash is newer.
                self.assertLess(block.index('\nCONTENT_EOF\n'), block.index('_ID=$('))
                original = block.split("<< 'CONTENT_EOF'", 1)[1].split('\n', 1)[1].split('\nCONTENT_EOF', 1)[0] + '\n'
                # A long literal payload exposes argument-vector transport and expansion.
                for large in (False, True):
                    with self.subTest(example=index, large=large):
                        content = ("Literal $HOME $(touch MUST_NOT_EXIST) `touch ALSO_MUST_NOT_EXIST` 'quote'\n"
                                   * 5000) if large else original
                        script = block.replace(original, content, 1)
                        build = workspace / "selected site;literal-$()-'quote"
                        log = workspace / f'{index}-{int(large)}'
                        environment = {'PATH': str(binaries) + ':/usr/bin:/bin',
                                       'BUILD_DIR': str(build), 'STDIN_LOG': str(log)}
                        result = subprocess.run(
                            [shutil.which('bash') or '/bin/bash', '--noprofile', '--norc'],
                            input='set -eu\nWP=(wp "--path=$BUILD_DIR")\n' + script,
                            text=True, capture_output=True, cwd=workspace,
                            env=environment, timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        arguments = Path(str(log) + '.argv').read_bytes().split(b'\0')[:-1]
                        self.assertEqual(arguments[:4], [('--path=' + str(build)).encode(),
                                                         b'post', b'create', b'-'])
                        self.assertFalse(any(arg.startswith(b'--post_content=') for arg in arguments))
                        self.assertEqual(Path(str(log) + '.body').read_bytes(), content.encode())
                        self.assertIn('123', result.stdout)
                        self.assertFalse((workspace / 'MUST_NOT_EXIST').exists())
                        self.assertFalse((workspace / 'ALSO_MUST_NOT_EXIST').exists())

    def test_image_script_runs_from_stdin_without_local_module_execution(self):
        source = DOCUMENT.read_text()
        blocks = re.findall(r'```bash\n([\s\S]*?)\n```', source)
        image = [block for block in blocks if "python3 -I - " in block]
        self.assertEqual(len(image), 1)
        with tempfile.TemporaryDirectory(prefix='solaris-wp-image-') as temporary:
            workspace = Path(temporary)
            binaries = workspace / 'bin'
            binaries.mkdir(mode=0o700)
            os.symlink(sys.executable, binaries / 'python3')
            (workspace / 'struct.py').write_text("raise RuntimeError('PROJECT MODULE EXECUTED')\n")
            build = workspace / 'selected site'
            result = subprocess.run(
                [shutil.which('bash') or '/bin/bash', '--noprofile', '--norc'],
                input=image[0], text=True, capture_output=True, cwd=workspace,
                env={'PATH': str(binaries) + ':/usr/bin:/bin',
                     'BUILD_DIR': str(build), 'THEME_PRIMARY_COLOR': '1a2b3c'}, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Generated 5 placeholder images', result.stdout)
            self.assertNotIn('WARNING:', result.stdout)
            output = build / 'wp-content/uploads/placeholders'
            expected = {'hero': (1200, 630), 'profile': (400, 400),
                        'gallery-landscape': (800, 600), 'thumbnail-square': (300, 300),
                        'banner': (1600, 400)}
            self.assertEqual(len(list(output.iterdir())), 5)
            for name, dimensions in expected.items():
                data = (output / f'placeholder-{name}.png').read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(struct.unpack('>II', data[16:24]), dimensions)


if __name__ == '__main__':
    unittest.main()
