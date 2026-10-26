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


if __name__ == "__main__":
    unittest.main()
