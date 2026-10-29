"""Exercise the bundled JSON reader as a subprocess from an untrusted cwd."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "employees/specialized/wordpress-master/diagnostics/shared/json_fields.py"


class DiagnosticJsonFields(unittest.TestCase):
    def run_reader(self, field, data, *args, raw=False, cwd=None):
        text = data if raw else json.dumps(data)
        return subprocess.run([sys.executable, "-I", str(SCRIPT), field, *args],
                              input=text, text=True, capture_output=True, cwd=cwd, timeout=10)

    def test_expected_fields_and_boolean_false(self):
        cases = [
            ("build-id", {"build_id": "site's build"}, "site's build\n"),
            ("theme-slug", {"theme": {"slug": "twentytwentyfive"}}, "twentytwentyfive\n"),
            ("creation-mode", {"mode": "import"}, "import\n"),
            ("creation-mode", {"creation_mode": "new", "mode": "old"}, "new\n"),
            ("modification-count", {"modifications": [{}, {}]}, "2\n"),
            ("robots-allowed", {"allowed": False}, "false\n"),
            ("robots-allowed", {"allowed": True}, "true\n"),
            ("scrape-success", {"success": False}, "false\n"),
            ("scrape-success", {"success": True}, "true\n"),
            ("scrape-error", {"error": "échec: not found"}, "échec: not found\n"),
        ]
        for field, data, expected in cases:
            with self.subTest(field=field, data=data):
                result = self.run_reader(field, data)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_plugin_identity_must_match(self):
        for data, expected in [({"slug": "woocommerce"}, 0), ({}, 1), ({"slug": "another-plugin"}, 1), ({"slug": ["woocommerce"]}, 1)]:
            result = self.run_reader("plugin-matches", data, "--expected-slug", "woocommerce")
            self.assertEqual(result.returncode, expected)
            self.assertEqual(result.stdout, "")

    def test_invalid_data_is_not_success_or_echoed(self):
        cases = [
            ("robots-allowed", {}), ("robots-allowed", {"allowed": "true"}),
            ("scrape-success", {"success": 1}), ("theme-slug", {"theme": []}),
            ("creation-mode", {"mode": {"secret": "do-not-print"}}),
            ("modification-count", {"modifications": "abc"}),
            ("scrape-error", {"error": ["do-not-print"]}), ("scrape-success", []),
        ]
        for field, data in cases:
            with self.subTest(field=field, data=data):
                result = self.run_reader(field, data)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("do-not-print", result.stderr)
        for raw in ["not-json private-marker", '{"success":true} trailing', "[" * 2000, "x" * (1024 * 1024 + 1)]:
            result = self.run_reader("scrape-success", raw, raw=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("private-marker", result.stderr)

    def test_data_and_project_imports_do_not_execute(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            marker = root / "executed"
            (root / "json.py").write_text("from pathlib import Path\nPath('executed').touch()\nraise RuntimeError('shadow import')\n")
            payload = "$(touch executed); `touch executed`; __import__('os').system('touch executed')"
            result = self.run_reader("scrape-error", {"error": payload}, cwd=work)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, payload + "\n")
            self.assertFalse(marker.exists())

    def test_unknown_commands_and_invalid_expected_slug_are_rejected(self):
        for field, args in [("eval", ()), ("plugin-matches", ()), ("plugin-matches", ("--expected-slug", "x;touch marker")), ("scrape-error", ("--expected-slug", "x"))]:
            result = self.run_reader(field, {}, *args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")

    def test_documented_plugin_check_rejects_unverified_installation(self):
        document = SCRIPT.parent.parent / "build-content/SKILL.md"
        match = re.search(r"^check_plugin_viable\(\) \{.*?^\}", document.read_text(), re.M | re.S)
        self.assertIsNotNone(match)
        # Replace only the network dependency; execute the actual documented function.
        shell = 'curl() { printf "%s" "$PROBE_JSON"; return "${PROBE_CURL_EXIT:-0}"; }\n' + match.group() + '\ncheck_plugin_viable woocommerce\n'
        for data, expected in [('{"slug":"woocommerce"}', 0), ('', 1), ('not-json', 1), ('{"slug":"another-plugin"}', 1), ('{}', 1)]:
            with self.subTest(data=data):
                result = subprocess.run(['bash', '-c', shell], env=dict({name: os.environ[name] for name in (
                                                                            'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                                                            'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                                                            'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                                                            'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                                                            'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                                                            'GITHUB_ACTIONS',
                                                                        ) if name in os.environ}, JSON_FIELDS=str(SCRIPT), PROBE_JSON=data),
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        result = subprocess.run(['bash', '-c', shell], env=dict({name: os.environ[name] for name in (
                                                                    'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                                                    'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                                                    'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                                                    'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                                                    'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                                                    'GITHUB_ACTIONS',
                                                                ) if name in os.environ}, JSON_FIELDS=str(SCRIPT),
                                PROBE_JSON='{"slug":"woocommerce"}', PROBE_CURL_EXIT='22'),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1, 'A failed HTTP response is not a verified plugin')

    def test_invalid_slug_is_refused_before_network(self):
        document = SCRIPT.parent.parent / "build-content/SKILL.md"
        function = re.search(r"^check_plugin_viable\(\) \{.*?^\}", document.read_text(), re.M | re.S).group()
        shell = 'curl() { printf called > "$PROBE_MARKER"; printf "{}"; }\n' + function + '\ncheck_plugin_viable "$PROBE_SLUG"\n'
        with tempfile.TemporaryDirectory() as work:
            marker = Path(work) / 'network-called'
            for slug in ['', '../plugin', '-plugin', 'plugin-', 'two--hyphens', 'x&action=query_plugins', '$(touch escaped)', '`touch escaped`']:
                result = subprocess.run(['bash', '-c', shell], env=dict({name: os.environ[name] for name in (
                                                                            'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                                                            'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                                                            'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                                                            'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                                                            'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                                                            'GITHUB_ACTIONS',
                                                                        ) if name in os.environ}, JSON_FIELDS=str(SCRIPT),
                                        PROBE_MARKER=str(marker), PROBE_SLUG=slug),
                                        cwd=work, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(marker.exists(), slug)
                self.assertFalse((Path(work) / 'escaped').exists())


class ModifyInstructionDataBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = SCRIPT.parent.parent / 'build-modify/SKILL.md'
        text = cls.document.read_text()
        cls.blocks = re.findall(r"(?m)^([^\n]*python3[^\n]*<<\s*'PYEOF')\n(.*?)\nPYEOF", text, re.S)

    def block(self, text):
        found = [(header, body) for header, body in self.blocks if text in body]
        self.assertEqual(len(found), 1, text)
        header, body = found[0]
        header = re.sub(r'^\s*[A-Z_]+=\$\(', '', header).strip()
        return header + '\n' + body + '\nPYEOF\n'

    def run_block(self, text, root, **values):
        return subprocess.run(['bash', '-c', self.block(text)], cwd=root,
                              env=dict({name: os.environ[name] for name in (
                                           'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                           'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                           'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                           'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                           'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                           'GITHUB_ACTIONS',
                                       ) if name in os.environ}, **values), text=True, capture_output=True, timeout=10)

    def test_every_python_heredoc_compiles(self):
        self.assertEqual(len(self.blocks), 7)
        for _, body in self.blocks:
            compile(body, str(self.document), 'exec')

    def test_build_paths_and_theme_names_are_data(self):
        with tempfile.TemporaryDirectory() as work:
            parent = Path(work)
            root = parent / 'client\'s "site"'
            themes = root / 'wp-content/themes'
            theme = 'theme\'s "name"'
            (themes / theme).mkdir(parents=True)
            (parent / 'json.py').write_text("raise RuntimeError('must not import project module')\n")
            result = self.run_block('themes_dir =', parent, BUILD_DIR=str(root))
            self.assertEqual((result.returncode, result.stdout), (0, theme + '\n'), result.stderr)
            result = self.run_block('build_id = os.path.basename', parent, BUILD_DIR=str(root), THEME_SLUG=theme)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((root / 'build.json').read_text())
            self.assertEqual(state['theme']['slug'], theme)
            result = self.run_block('build_json_path = sys.argv[1]', parent, BUILD_JSON_PATH=str(root / 'build.json'))
            self.assertEqual(json.loads(result.stdout), state, result.stderr)

    def test_theme_value_and_modification_metadata_do_not_become_code(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            path = root / 'theme\'s "name".json'
            path.write_text(json.dumps({'settings': {'color': {'palette': [{'slug': 'primary', 'color': '#000'}]}}}))
            payload = '\"; __import__(\'pathlib\').Path(\'escaped\').touch(); # $(touch escaped)'
            result = self.run_block('theme_json_path, target_slug', root, THEME_JSON_PATH=str(path), TARGET_SLUG='primary',
                                    NEW_VALUE=payload, TOKEN_PATH='color.palette')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(path.read_text())['settings']['color']['palette'][0]['color'], payload)
            state_path = root / 'build.json'
            state_path.write_text('{"build_id":"demo","modifications":[]}')
            before = {'quote': "it's data", 'code': payload}
            values = dict(BUILD_DIR=str(root), STEP_TYPE='theme-token', NL_REQUEST=payload, STEP_DESCRIPTION=payload,
                          STEP_FILES_CHANGED='theme.json, build.json', BEFORE_VALUE=json.dumps(before), AFTER_VALUE='{}')
            result = self.run_block('modification_entry =', root, **values)
            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = json.loads(state_path.read_text())['modifications'][0]
            self.assertEqual(recorded['request'], payload)
            self.assertEqual(recorded['before'], before)
            self.assertFalse((root / 'escaped').exists())
            prior = state_path.read_bytes()
            result = self.run_block('modification_entry =', root, **dict(values, BEFORE_VALUE='not json'))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(state_path.read_bytes(), prior)

    def test_version_scan_treats_basename_literally(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            basename = 'client\'s "site".test'
            for leaf in [basename + '-v1', basename + '-v2', basename.replace('.', 'X') + '-v99']:
                (root / leaf).mkdir()
            result = self.run_block('pattern = re.compile', root, PARENT_DIR=str(root), BASENAME=basename)
            self.assertEqual((result.returncode, result.stdout), (0, '3\n'), result.stderr)


if __name__ == "__main__":
    unittest.main()
