"""G40: fresh install and host portability (host_portability.py)."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "examples/capabilities/G40"
TOOL = ROOT / "employees/quality-security/qa-engineer/host_portability.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(*args, tool=TOOL, timeout=300):
    return subprocess.run([sys.executable, str(tool)] + [str(a) for a in args],
                          capture_output=True, text=True, env=ENV, timeout=timeout)


class G40Oracle(unittest.TestCase):
    def test_oracle_accepted(self):
        r = subprocess.run([sys.executable, str(X / "portability_oracle.py")], capture_output=True, text=True, env=ENV, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ACCEPTED 8/8", r.stdout)

    def test_naive_rejected(self):
        r = subprocess.run([sys.executable, str(X / "portability_oracle.py"), "--tool", str(X / "naive_portability.py"),
                            "--only", "o1,o7"], capture_output=True, text=True, env=ENV, timeout=300)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("REJECTED", r.stdout)

    def test_noop_rejected(self):
        r = subprocess.run([sys.executable, str(X / "portability_oracle.py"), "--tool", str(X / "noop_portability.py"),
                            "--only", "o1,o5"], capture_output=True, text=True, env=ENV, timeout=120)
        self.assertEqual(r.returncode, 1)
        self.assertIn("REJECTED", r.stdout)


class G40Direct(unittest.TestCase):
    def test_skill_copy_qa_engineer_broken(self):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        r = run("skill-copy", ROOT, "quality-security/qa-engineer", "--dest", d, "--json")
        self.assertEqual(r.returncode, 1, r.stderr)
        j = json.loads(r.stdout)
        self.assertEqual(j["status"], "broken")
        self.assertTrue(any("QUALITY-SECURITY-STANDARD" in m["ref"] for m in j["missing"]))

    def test_python_bounds(self):
        r = run("python-bounds", ROOT, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        j = json.loads(r.stdout)
        self.assertEqual(j["wheel_and_installer"], "3.10+")
        self.assertEqual(j["source_tools"], "3.9+")
        self.assertTrue(j["requires_python"].startswith(">="))

    def test_invalid_and_out(self):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        r = run("python-bounds", d)
        self.assertEqual(r.returncode, 2); self.assertIn("Nothing was written", r.stderr)
        missing = d / "no" / "x.json"
        r = run("python-bounds", ROOT, "--out", missing)
        self.assertEqual(r.returncode, 2); self.assertNotIn("Traceback", r.stderr)

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_wheel_smoke(self):
        d = Path(tempfile.mkdtemp(prefix="g40t-")); self.addCleanup(shutil.rmtree, d, True)
        r = run("wheel-smoke", ROOT, "--outside", d, "--json", timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        j = json.loads(r.stdout)
        self.assertEqual(j["result"], "pass")
        self.assertFalse(j["employees_in_wheel"])

    def test_outside_inside_the_checkout_is_refused(self):
        # M40 P3-1: --outside at or under REPO would put the venv and wheels in the checkout
        d = Path(tempfile.mkdtemp(prefix="g40o-")); self.addCleanup(shutil.rmtree, d, True)
        repo = d / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "dist", "*.egg-info"))
        for inside in (repo, repo / "work"):
            r = run("wheel-smoke", repo, "--outside", inside, "--json")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse((repo / "work").exists())

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_wheel_smoke_never_edits_repo_and_ignores_a_stale_build(self):
        # M40 P2-1: building in REPO wrote build/ and *.egg-info there, and a stale build/lib file was shipped
        d = Path(tempfile.mkdtemp(prefix="g40s-")); self.addCleanup(shutil.rmtree, d, True)
        repo = d / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "dist", "*.egg-info"))
        stale = repo / "build/lib/solaris_intake/stale_removed_module.py"
        stale.parent.mkdir(parents=True)
        stale.write_text("REMOVED = True\n")
        before = sorted(str(x.relative_to(repo)) for x in repo.rglob("*"))
        r = run("wheel-smoke", repo, "--outside", d / "work", "--json", timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(json.loads(r.stdout)["result"], "pass")
        after = sorted(str(x.relative_to(repo)) for x in repo.rglob("*"))
        self.assertEqual(after, before)
        wheels = list((d / "work" / "wheels").glob("*.whl"))
        self.assertEqual(len(wheels), 1)
        import zipfile
        self.assertNotIn("solaris_intake/stale_removed_module.py", zipfile.ZipFile(wheels[0]).namelist())

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_outside_that_exists_and_is_not_empty_is_refused_and_kept(self):
        # M40 r3 P2-1: an existing --outside lost its src/ folder and the tool said "Nothing was written"
        d = Path(tempfile.mkdtemp(prefix="g40k-")); self.addCleanup(shutil.rmtree, d, True)
        work = d / "work"
        (work / "src").mkdir(parents=True)
        (work / "src" / "keep.txt").write_text("user data\n")
        (work / "notes.txt").write_text("notes\n")
        before = sorted(str(x.relative_to(work)) for x in work.rglob("*"))
        for cmd in ("wheel-smoke", "report"):
            r = run(cmd, ROOT, "--outside", work, "--json", timeout=600)
            self.assertEqual(r.returncode, 2, cmd + r.stdout + r.stderr)
            self.assertIn("not empty", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertEqual(sorted(str(x.relative_to(work)) for x in work.rglob("*")), before)
        self.assertEqual((work / "src" / "keep.txt").read_text(), "user data\n")

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_outside_that_is_a_file_is_refused_and_kept(self):
        d = Path(tempfile.mkdtemp(prefix="g40f-")); self.addCleanup(shutil.rmtree, d, True)
        f = d / "afile"
        f.write_text("keep\n")
        r = run("wheel-smoke", ROOT, "--outside", f, "--json")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(f.read_text(), "keep\n")

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_failed_build_names_the_work_folder_instead_of_nothing_written(self):
        # M40 r3 P4-1: after a failed build the work folder holds the source copy, so "Nothing was written" was false
        d = Path(tempfile.mkdtemp(prefix="g40b-")); self.addCleanup(shutil.rmtree, d, True)
        repo = d / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "dist", "*.egg-info"))
        pp = repo / "pyproject.toml"
        text = pp.read_text()
        self.assertIn("build-backend", text)
        # valid TOML with requires-python, but a build backend that cannot be imported: the copy is made, then pip fails
        pp.write_text("\n".join('build-backend = "g40_no_such_backend"' if l.startswith("build-backend") else l
                                for l in text.splitlines()) + "\n")
        work = d / "work"
        r = run("wheel-smoke", repo, "--outside", work, "--json", timeout=600)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Nothing was written", r.stderr)
        self.assertIn(str(work), r.stderr)
        self.assertTrue((work / "src").is_dir())

    def test_docs_state_outside_rule(self):
        doc = (ROOT / "employees/quality-security/qa-engineer/host-portability.md").read_text()
        self.assertIn("new or empty", doc)
        self.assertIn("setuptools", doc)

    def test_docs_state_bounds(self):
        install = (ROOT / "docs/install.md").read_text()
        self.assertIn("3.10+", install); self.assertIn("3.9+", install)
        self.assertIn("host_portability.py", install)
        self.assertIn("3.9+", (ROOT / "docs/first-task.md").read_text())

    def test_role_declares_tool(self):
        c = json.loads((ROOT / "employees/quality-security/qa-engineer/capability.contract.json").read_text())
        self.assertIn("host_portability.py", c["dependencies"]["scripts"])
        self.assertTrue((ROOT / "employees/quality-security/qa-engineer/host-portability.md").is_file())


    def test_inspect_wheel_names(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("hp", str(TOOL))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        bad = m.inspect_wheel_names(["employees/x/SKILL.md", "foo.pyc"])
        codes = {f["code"] for f in bad}
        self.assertIn("wheel_ships_employees", codes)
        self.assertIn("wheel_contains_pyc", codes)
        self.assertIn("wheel_missing_control_plane", codes)
        good = m.inspect_wheel_names(["solaris_intake/control_plane/policy.json", "solaris_intake/__init__.py"])
        self.assertEqual(good, [])

    def test_role_rejects_parent_segments(self):
        # resolves to a real skill if .. were allowed; must still be refused
        role = "quality-security/qa-engineer/../../design/technical-writer"
        r = run("skill-copy", ROOT, role)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("Nothing was written", r.stderr)

class NoBytecode(unittest.TestCase):
    def test_python_bounds_writes_no_bytecode_into_the_checkout(self):
        import shutil as _sh, tempfile as _tf
        top = Path(_tf.mkdtemp(prefix="g40nb-"))
        try:
            dst = top / "repo"
            (dst / "employees/x/y").mkdir(parents=True)
            (dst / "employees/x/y/tool.py").write_text("print(1)\n")
            (dst / "control-plane").mkdir()
            (dst / "control-plane/meta_control_plane.py").write_text("")
            _sh.copy2(ROOT / "pyproject.toml", dst / "pyproject.toml")
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
            p = subprocess.run([sys.executable, str(TOOL),
                                "python-bounds", str(dst)], capture_output=True, text=True, env=env, timeout=120)
            self.assertIn(p.returncode, (0, 1), p.stderr)
            self.assertEqual([x for x in dst.rglob("__pycache__")], [])
        finally:
            _sh.rmtree(top, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
