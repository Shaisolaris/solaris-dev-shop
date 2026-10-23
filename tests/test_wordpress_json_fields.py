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
                result = subprocess.run(['bash', '-c', shell], env=dict(os.environ, JSON_FIELDS=str(SCRIPT), PROBE_JSON=data),
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        result = subprocess.run(['bash', '-c', shell], env=dict(os.environ, JSON_FIELDS=str(SCRIPT),
                                PROBE_JSON='{"slug":"woocommerce"}', PROBE_CURL_EXIT='22'),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1, 'A failed HTTP response is not a verified plugin')


if __name__ == "__main__":
    unittest.main()
