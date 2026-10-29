"""Exercise the shipped recipes only on private files and inert command stubs."""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / 'employees/specialized/wordpress-master/diagnostics'


def fenced_blocks(source):
    """Honor CommonMark fence lengths, including literal nested triple fences."""
    opening = None
    lines = []
    for line in source.splitlines(keepends=True):
        if opening is None:
            match = re.match(r'^(`{3,})([^\n]*)\n?$', line)
            if match:
                opening = (len(match.group(1)), match.group(2).strip())
                lines = []
        elif re.fullmatch(r'`{%d,}[ \t]*\n?' % opening[0], line):
            yield opening[1], ''.join(lines)
            opening = None
        else:
            lines.append(line)


class WordPressScrapeInputs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='solaris-scrape-qa-')
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.bin = self.workspace / 'bin'
        self.bin.mkdir(mode=0o700)
        (self.bin / 'python3').symlink_to(sys.executable)
        self.environment = {'PATH': str(self.bin) + ':/usr/bin:/bin', 'PLUGIN_DIR': str(ROOT)}

    def run_shell(self, script, extra=None):
        return subprocess.run(['/bin/bash', '--noprofile', '--norc'], input=script,
                              cwd=self.workspace, env=dict(self.environment, **(extra or {})),
                              capture_output=True, text=True, timeout=20)

    def recipe(self, heading, following):
        document = (DIAGNOSTICS / 'build-scrape/SKILL.md').read_text()
        section = document.split(heading, 1)[1].split(following, 1)[0]
        blocks = [(language, body) for language, body in fenced_blocks(section) if language == 'bash']
        self.assertEqual(len(blocks), 1)
        return blocks[0][1]

    def test_css_path_and_project_imports_remain_data(self):
        directory = self.workspace / "scrape space 'quote; literal-$(touch MUST_NOT_EXIST)"
        (directory / 'styles').mkdir(parents=True)
        css = directory / 'styles/main.css'
        css.write_text('a{content:"Example text";color:#123} b{content:">icon"} c{content:""}')
        (self.workspace / 're.py').write_text("raise RuntimeError('PROJECT RE MODULE EXECUTED')\n")
        result = self.run_shell(self.recipe('### 3b:', '### 3c:'), {'SCRAPE_DIR': str(directory)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(css.read_text(), 'a{content: "";color:#123} b{content:">icon"} c{content:""}')
        self.assertIn('CSS content: declarations sanitised', result.stdout)
        self.assertFalse((self.workspace / 'MUST_NOT_EXIST').exists())

    def test_manifest_status_remains_data_and_preserves_other_fields(self):
        directory = self.workspace / "scrape 'quote space"
        directory.mkdir()
        path = directory / 'scrape.json'
        original = {'source_url': 'https://example.invalid/', 'unrelated': {'keep': [1, 2, 3]}}
        path.write_text(json.dumps(original))
        (self.workspace / 'json.py').write_text("raise RuntimeError('PROJECT JSON MODULE EXECUTED')\n")
        status = "allowed'; __import__('pathlib').Path('MUST_NOT_EXIST').touch(); #"
        result = self.run_shell(self.recipe('### 3c:', '## Section 4:'),
                                {'SCRAPE_DIR': str(directory), 'ROBOTS_STATUS': status})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text()), dict(original, robots_status=status))
        self.assertFalse((self.workspace / 'MUST_NOT_EXIST').exists())

    def test_scrape_helper_refuses_symlink_and_invalid_manifest_without_changes(self):
        helper = DIAGNOSTICS / 'build-scrape/update_scrape.py'
        outside = self.workspace / 'outside.json'
        outside.write_text('{"keep":"untouched"}')
        link = self.workspace / 'link.json'
        link.symlink_to(outside)
        malformed = self.workspace / 'not-an-object.json'
        malformed.write_text('[1, 2, 3]')
        for path in (link, malformed):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                result = subprocess.run([sys.executable, '-I', str(helper), 'robots', str(path), 'allowed'],
                                        env=self.environment, cwd=self.workspace,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(path.read_bytes(), before)
        self.assertEqual(outside.read_text(), '{"keep":"untouched"}')

    def test_nested_markdown_recipe_writes_complete_readme(self):
        document = (DIAGNOSTICS / 'build-mcp/SKILL.md').read_text()
        recipes = [body for language, body in fenced_blocks(document)
                   if language == 'bash' and '# Read adapter version' in body]
        self.assertEqual(len(recipes), 1)
        build = self.workspace / 'selected build'
        build.mkdir()
        result = self.run_shell(recipes[0], {'BUILD_DIR': str(build)})
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (build / 'README.md').read_text()
        match = re.search(r'```json\n([\s\S]*?)\n```', output)
        self.assertIsNotNone(match, 'The rendered recipe must retain the complete JSON fence')
        configuration = match.group(1)
        server = json.loads(configuration)['mcpServers']['wordpress']
        self.assertEqual(server['command'], '/path/to/local-wp/wpcli')
        self.assertEqual(server['args'][-1], '--user=admin')
        self.assertIn('## Admin Credentials', output)
        self.assertIn('**Adapter version:** vunknown', output)
        self.assertIn('**Transport:** STDIO via WP-CLI', output)

    def test_scrape_staging_is_private_and_cleanup_keeps_owner_files(self):
        node = self.bin / 'node'
        node.write_text('#!/bin/sh\n[ "$1" = -e ] || exit 91\n'
                        'case "$2" in "require(\'playwright\')"|"require(\'robots-parser\')") exit 0;; *) exit 92;; esac\n')
        node.chmod(0o700)
        temporary = self.workspace / "temporary 'quote"
        temporary.mkdir()
        sentinel = temporary / 'owner-file'
        sentinel.write_text('KEEP')
        document = (DIAGNOSTICS / 'build-scrape/SKILL.md').read_text()
        script = next(body for language, body in fenced_blocks(document) if language == 'bash')
        script += r"""
python3 -I -c 'import json,os,stat,sys;print("STAGING:"+json.dumps({"path":sys.argv[1],"mode":stat.S_IMODE(os.stat(sys.argv[1]).st_mode)}))' "$SCRAPE_DIR"
"""
        result = self.run_shell('umask 022\n' + script,
                                {'TMPDIR': str(temporary), 'SLUG': 'private-fixture',
                                 'JSON_FIELDS': str(DIAGNOSTICS / 'shared/json_fields.py')})
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(next(line[len('STAGING:'):] for line in result.stdout.splitlines()
                                 if line.startswith('STAGING:')))
        self.assertEqual(Path(record['path']).parent, temporary)
        self.assertEqual(record['mode'], 0o700)
        self.assertFalse(Path(record['path']).exists())
        self.assertEqual(sentinel.read_text(), 'KEEP')

    def test_visual_staging_is_private_and_copies_assets(self):
        visual = self.workspace / "visual files 'quote"
        visual.mkdir()
        (visual / 'theme.css').write_text('body{color:#123456}')
        (visual / 'index.html').write_text('<html></html>')
        (visual / 'image.png').write_bytes(b'synthetic-image')
        temporary = self.workspace / 'visual-temporaries'
        temporary.mkdir()
        document = (DIAGNOSTICS / 'build-visual/SKILL.md').read_text()
        recipes = [body for language, body in fenced_blocks(document)
                   if language == 'bash' and 'IMAGES_STAGE=' in body and 'CSS_FILES=' in body]
        self.assertEqual(len(recipes), 1)
        result = self.run_shell('umask 022\n' + recipes[0] + '\nprintf "STAGING:%s\\n" "$IMAGES_STAGE"\n',
                                {'TMPDIR': str(temporary), 'VISUAL_MODE': 'html-css',
                                 'VISUAL_PATH': str(visual), 'SLUG': 'private-fixture'})
        self.assertEqual(result.returncode, 0, result.stderr)
        stage = Path(next(line[len('STAGING:'):] for line in result.stdout.splitlines()
                          if line.startswith('STAGING:')))
        self.assertEqual(stage.parent, temporary)
        self.assertEqual(stat.S_IMODE(stage.stat().st_mode), 0o700)
        self.assertEqual((stage / 'image.png').read_bytes(), b'synthetic-image')
        self.assertIn('1 CSS, 1 HTML, 1 images', result.stdout)


if __name__ == '__main__':
    unittest.main()
