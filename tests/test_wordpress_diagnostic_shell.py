"""Execute the documented diagnostics against disposable files and a local SSH double.

No network, production WordPress instance, or real credentials are used. The SSH
double runs the supplied remote command in /bin/sh, preserving its second-shell
parsing boundary so quoting failures remain observable.
"""
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
WORKFLOW = ROOT / "employees/specialized/wordpress-master/diagnostics/diagnostic-config-security/SKILL.md"
WORKFLOW_DIR = WORKFLOW.parent.parent


@unittest.skipUnless(
    os.name == "posix" and shutil.which("bash") and shutil.which("jq") and shutil.which("git"),
    "POSIX Bash, jq and git required for documented SSH workflow",
)
class WordPressDiagnosticShellTests(unittest.TestCase):
    def run_workflow(self, root, wp_path, site_name="fixture", parent_config=False):
        config_dir = wp_path.parent if parent_config else wp_path
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "wp-config.php").write_text(
            "<?php\ndefine('WP_DEBUG', true);\n"
            "define('AUTH_KEY', 'put your unique phrase here');\n"
            "define('DISALLOW_FILE_EDIT', true);\n$table_prefix = 'wp_';\n"
        )
        env = {key: os.environ[key] for key in ("HOME", "PATH", "TMPDIR", "TEMP", "SYSTEMROOT") if key in os.environ}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(["git", "init", "-q", str(config_dir)], check=True, env=env)
        subprocess.run(["git", "-C", str(config_dir), "add", "wp-config.php"], check=True, env=env)
        (root / "sites.json").write_text(json.dumps({"sites": {
            site_name: {"host": "fixture-host", "user": "fixture-user", "wp_path": str(wp_path)}
        }}))
        bin_dir = root / "bin"
        bin_dir.mkdir()
        ssh = bin_dir / "ssh"
        ssh.write_text(
            "#!" + sys.executable + "\n"
            "import os,subprocess,sys\n"
            "a=sys.argv[1:]\n"
            "if len(a)<2 or a[-2]!='fixture-user@fixture-host': sys.exit(97)\n"
            "sys.exit(subprocess.call(['/bin/sh','-c',a[-1]],env=os.environ))\n"
        )
        ssh.chmod(0o700)
        blocks = re.findall(r"```bash\n(.*?)\n```", WORKFLOW.read_text(), flags=re.S)
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [shutil.which("bash"), "-c", "\n\n".join(blocks), "diagnostic", site_name],
            cwd=root, env=env, text=True, capture_output=True, timeout=20,
        )

    def test_remote_path_metacharacters_remain_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "unexpected-command"
            wp_path = Path(str(root / "wordpress") + "; : > " + str(marker) + "; #")
            result = self.run_workflow(root, wp_path)
            self.assertFalse(marker.exists(), "a remote shell interpreted profile path as code")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("define('WP_DEBUG', true)", result.stdout)
            self.assertIn("wp-config.php", result.stdout)

    def test_quotes_spaces_and_dollars_in_standard_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_workflow(root, root / "WordPress 'quoted' $literal space")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("put your unique phrase here", result.stdout)
            self.assertIn("$table_prefix = 'wp_';", result.stdout)
            self.assertIn("wp-config.php", result.stdout)

    def test_parent_config_path_remains_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wp_path = root / "site 'quoted'" / "public_html"
            wp_path.mkdir(parents=True)
            result = self.run_workflow(root, wp_path, parent_config=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("define('DISALLOW_FILE_EDIT', true)", result.stdout)
            self.assertIn("wp-config.php", result.stdout)

    def test_profile_name_is_a_literal_json_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_workflow(root, root / "wordpress", site_name='site"] | .sites["other')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("define('WP_DEBUG', true)", result.stdout)


@unittest.skipUnless(
    os.name == "posix" and shutil.which("bash") and shutil.which("jq"),
    "POSIX Bash and jq required for documented SSH workflow",
)
class WordPressRemoteDiagnosticVariants(unittest.TestCase):
    VARIANTS = (
        "site-scout", "diagnostic-user-audit", "diagnostic-file-permissions",
        "diagnostic-core-integrity", "diagnostic-code-quality", "diagnostic-version-audit",
    )

    def run_variant(self, name, root, wp_path, marker, site_name="fixture", error_log=None,
                    user_id="11", cli_available=True, simple_cli=False, missing_meta=False,
                    missing_config=False, debug_reply="true", debug_exit=0, expected_debug="enabled"):
        wp_path.mkdir(parents=True)
        content = wp_path / "wp-content"
        (content / "uploads").mkdir(parents=True)
        (content / "uploads").chmod(0o755)
        (content / "fixture.php").write_text("<?php // fixture\n")
        (content / "debug.log").write_text("fixture debug entry\n")
        config = wp_path / "wp-config.php"
        config.write_text("<?php\ndefine('WP_DEBUG', true);\n")
        config.chmod(0o600)
        (wp_path / ".htaccess").write_text("# fixture\n")
        (wp_path / ".htaccess").chmod(0o644)
        (wp_path / ".maintenance").touch()
        log = error_log or root / "php error 'log'"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("fixture PHP error\n")
        binary = root / "bin"
        binary.mkdir()
        wp = binary / ("wp" if simple_cli else "wp cli 'fixture'")
        calls = root / "wp-calls.jsonl"
        env = {key: os.environ[key] for key in ("HOME", "PATH", "TMPDIR", "TEMP", "SYSTEMROOT") if key in os.environ}
        env.update(PATH=str(binary) + os.pathsep + env.get("PATH", ""),
                   PYTHONDONTWRITEBYTECODE="1", SOLARIS_FIXTURE_WP_LOG=str(calls),
                   SOLARIS_FIXTURE_ERROR_LOG=str(log), SOLARIS_FIXTURE_CURL_LOG=str(root / "curl-calls.jsonl"),
                   SOLARIS_FIXTURE_DEBUG_REPLY=debug_reply, SOLARIS_FIXTURE_DEBUG_EXIT=str(debug_exit))

        def executable(path, body):
            path.write_text("#!" + sys.executable + "\n" + body)
            path.chmod(0o700)

        executable(binary / "ssh",
                   "import os,subprocess,sys\n"
                   "a=sys.argv[1:]\n"
                   "if len(a)<2 or a[-2]!='fixture-user@fixture-host':sys.exit(97)\n"
                   "sys.exit(subprocess.call(['/bin/sh','-c',a[-1]],env=os.environ))\n")
        executable(wp,
                   "import json,os,sys\n"
                   "a=sys.argv[1:]\n"
                   "with open(os.environ['SOLARIS_FIXTURE_WP_LOG'],'a') as f:f.write(json.dumps(a)+'\\n')\n"
                   "if a[:3]==['config','get','WP_DEBUG']:\n"
                   " print(os.environ['SOLARIS_FIXTURE_DEBUG_REPLY']);sys.exit(int(os.environ['SOLARIS_FIXTURE_DEBUG_EXIT']))\n"
                   "elif a[:2]==['option','get']:print('fixture-theme')\n"
                   "elif a[:2]==['user','meta']:print('2026-10-01')\n"
                   "elif '--format=count' in a:print('1')\n"
                   "elif '--field=ID' in a:print('[11]')\n"
                   "elif '--field=user_login' in a:print('[\"admin\"]')\n"
                   "elif a[:2]==['core','version']:print('6.7.1')\n"
                   "elif a[:2]==['db','version']:print('8.0')\n"
                   "else:print('[{\"name\":\"fixture-plugin\"}]')\n")
        executable(binary / "php",
                   "import json,os,sys\n"
                   "if '-v' in sys.argv:print('PHP 8.3 fixture')\n"
                   "elif 'json_encode' in ' '.join(sys.argv):print(json.dumps({'version':'8.3'}))\n"
                   "else:print(os.environ['SOLARIS_FIXTURE_ERROR_LOG'])\n")
        executable(binary / "curl",
                   "import json,os,sys\n"
                   "with open(os.environ['SOLARIS_FIXTURE_CURL_LOG'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')\n"
                   "print('200')\n")
        executable(binary / "stat",
                   "import pathlib,stat,sys\n"
                   "try:print(format(stat.S_IMODE(pathlib.Path(sys.argv[-1]).stat().st_mode),'o'))\n"
                   "except OSError:sys.exit(1)\n")
        executable(binary / "timeout",
                   "import os,sys\n"
                   "os.execvp(sys.argv[2],sys.argv[2:])\n")
        (root / "sites.json").write_text(json.dumps({"sites": {site_name: {
            "host": "fixture-host", "user": "fixture-user", "wp_path": str(wp_path),
            "wp_cli_path": str(wp), "wp_cli_prefix": str(wp), "source_type": "ssh",
            "wp_cli_available": cli_available, "site_url": "https://fixture.invalid/",
        }}}))
        blocks = re.findall(r"```bash\n(.*?)^\s*```", (WORKFLOW_DIR / name / "SKILL.md").read_text(), re.S | re.M)
        if name == "diagnostic-file-permissions":
            script = "\n".join(blocks[i] for i in (0, 1, 2, 3, 5, 7, 9))
            script += '\nprintf "PERMS:%s:%s:%s:%s\\n" "$CONFIG_PERMS" "$HTACCESS_PERMS" "$UPLOADS_PERMS" "$WP_DEBUG_STATUS"\n'
        elif name == "site-scout":
            script = "\n".join(blocks[i] for i in (*range(9), 10))
            script += '\nprintf "%s\\n" "$DEBUG_LOG" "$PHP_ERRORS" "$CONFIG_VALUES" "$ACTIVE_PLUGINS" "$HTTP_STATUS"\n'
        elif name == "diagnostic-user-audit":
            script = blocks[0] if missing_meta else "\n".join(blocks[:4])
            # A literal Bash array is fixture input, not generated shell source.
            import shlex
            script += "\nUSER_IDS=(" + shlex.quote(user_id) + ")\n" + blocks[4]
        elif name == "diagnostic-core-integrity":
            script = "\n".join(blocks[:2])
        else:
            script = "\n".join(b for b in blocks if "ssh " in b or "remote_wp " in b)
            # Legacy examples use placeholders; bind their documented profile
            # inputs for the original-source control, without adding quoting.
            for key, value in {"{user}": "fixture-user", "{host}": "fixture-host",
                               "{wp_path}": str(wp_path), "{wp_cli_path}": str(wp)}.items():
                script = script.replace(key, value)
        if missing_meta:
            shutil.rmtree(wp_path)
        if missing_config:
            config.unlink()
        result = subprocess.run([shutil.which("bash"), "-c", script, "diagnostic", site_name],
                                cwd=root, env=env, text=True, capture_output=True, timeout=20)
        self.assertFalse(marker.exists(), name + ": profile or log data executed as a remote command")
        if missing_meta:
            self.assertNotEqual(result.returncode, 0, "missing site must refuse before fallback queries")
            self.assertFalse(calls.exists(), "fallback queried a WP-CLI outside the intended site")
            return []
        self.assertEqual(result.returncode, 0, name + ": " + result.stdout + result.stderr)
        if name == "site-scout":
            self.assertIn("fixture PHP error", result.stdout)
            self.assertIn("fixture-plugin", result.stdout)
            self.assertIn("define('WP_DEBUG', true)", result.stdout)
        elif name == "diagnostic-file-permissions":
            expected_perms = "NOT_FOUND" if missing_config else "600"
            self.assertIn("PERMS:" + expected_perms + ":644:755:" + expected_debug, result.stdout)
        else:
            self.assertTrue(calls.exists(), "no intended WP-CLI call occurred")
        return [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []

    def test_quoted_profile_paths_preserve_intended_diagnostics(self):
        for name in self.VARIANTS:
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.run_variant(name, root, root / "WordPress 'quoted' $literal", root / "INJECTED")

    def test_metacharacters_remain_remote_path_data(self):
        for name in self.VARIANTS:
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                marker = root / "INJECTED"
                payload = str(root / "site") + "'; : > " + str(marker) + "; #"
                self.run_variant(name, root, Path(payload), marker)

    def test_literal_site_names_in_every_profile_lookup(self):
        for name in self.VARIANTS:
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.run_variant(name, root, root / "wordpress", root / "INJECTED",
                                 site_name='site"] | .sites["other')

    def test_php_reported_error_log_is_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "INJECTED"
            log = Path(str(root / "error") + "'; : > " + str(marker) + "; #")
            self.run_variant("site-scout", root, root / "wordpress", marker, error_log=log)

    def test_privileged_user_id_stays_one_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "INJECTED"
            user_id = "11; : > " + str(marker) + "; #"
            calls = self.run_variant("diagnostic-user-audit", root, root / "wordpress", marker, user_id=user_id)
            self.assertIn(["user", "meta", "get", user_id, "last_login"], calls)

    def test_permission_debug_fallback_without_wp_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_variant("diagnostic-file-permissions", root, root / "site 'quoted'",
                             root / "INJECTED", cli_available=False)

    def test_missing_site_refuses_metadata_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_variant("diagnostic-user-audit", root, root / "missing-site", root / "INJECTED",
                             simple_cli=True, missing_meta=True)

    def test_unreadable_debug_config_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_variant("diagnostic-file-permissions", root, root / "wordpress", root / "INJECTED",
                             cli_available=False, missing_config=True, expected_debug="unknown")

    def test_failed_or_unexpected_debug_cli_result_is_unknown(self):
        for reply, status in (("false", 1), ("unexpected", 0)):
            with self.subTest(reply=reply, status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.run_variant("diagnostic-file-permissions", root, root / "wordpress", root / "INJECTED",
                                 simple_cli=True, debug_reply=reply, debug_exit=status, expected_debug="unknown")

    def test_local_code_quality_target_is_data(self):
        source = (WORKFLOW_DIR / "diagnostic-code-quality/SKILL.md").read_text()
        blocks = re.findall(r"```bash\n(.*?)^\s*```", source, re.S | re.M)
        check = next(b for b in blocks if b.startswith("grep -rn "))
        for attack in (False, True):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                marker = root / "INJECTED"
                name = str(root / "code 'quoted' $literal")
                if attack:
                    name = str(root / "code") + "; : > " + str(marker) + "; #"
                target = Path(name)
                target.mkdir(parents=True)
                (target / "fixture.php").write_text("<?php mysql_query($query);\n")
                # Bind the legacy placeholder only in the original-source
                # control. New examples consume the quoted argument variable.
                script = 'TARGET_DIR="$1"\n' + check.replace("{target_dir}", str(target))
                result = subprocess.run([shutil.which("bash"), "-c", script, "diagnostic", str(target)],
                                        cwd=root, env={"PATH": os.environ["PATH"]},
                                        text=True, capture_output=True, timeout=10)
                self.assertFalse(marker.exists(), "local target directory executed as shell source")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("mysql_query", result.stdout)


if __name__ == "__main__":
    unittest.main()
