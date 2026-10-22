"""G40: fresh install and host portability (host_portability.py)."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "examples/capabilities/G40"
TOOL = ROOT / "employees/quality-security/qa-engineer/host_portability.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(*args, tool=TOOL, timeout=300, env=None):
    return subprocess.run([sys.executable, str(tool)] + [str(a) for a in args],
                          capture_output=True, text=True, env=env or ENV, timeout=timeout)


def _offline_env():
    env = {k: v for k, v in ENV.items() if not k.startswith("PIP_")}
    env["PIP_NO_INDEX"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _local_wheelhouse():
    """A folder with a setuptools>=61 wheel, found without network: $G40_WHEELHOUSE or this Python's ensurepip bundle."""
    import re
    cands = [os.environ.get("G40_WHEELHOUSE")]
    try:
        import ensurepip
        cands.append(os.path.join(os.path.dirname(ensurepip.__file__), "_bundled"))
    except ImportError:
        pass
    for c in cands:
        if c and os.path.isdir(c):
            for n in os.listdir(c):
                m = re.match(r"^setuptools-(\d+)", n)
                if m and n.endswith(".whl") and int(m.group(1)) >= 61:
                    return c
    return None


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

    def test_wheelhouse_that_is_not_a_folder_is_refused_and_nothing_written(self):
        d = Path(tempfile.mkdtemp(prefix="g40w-")); self.addCleanup(shutil.rmtree, d, True)
        out = d / "out"
        r = run("wheel-smoke", ROOT, "--outside", out, "--wheelhouse", d / "missing", "--json")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--wheelhouse", r.stderr); self.assertIn("Nothing was written", r.stderr)
        self.assertFalse(out.exists())

    def test_wheelhouse_without_setuptools_is_refused_before_anything_is_written(self):
        # M40 P3-2: an offline wheelhouse that cannot supply the backend fails up front, not as a cut pip tail
        d = Path(tempfile.mkdtemp(prefix="g40w-")); self.addCleanup(shutil.rmtree, d, True)
        wh = d / "wh"; wh.mkdir(); (wh / "setuptools-60.0.0-py3-none-any.whl").write_text("old\n")
        out = d / "out"
        for cmd in ("wheel-smoke", "report"):
            r = run(cmd, ROOT, "--outside", out, "--wheelhouse", wh, "--json")
            self.assertEqual(r.returncode, 2, cmd + r.stdout + r.stderr)
            self.assertIn("setuptools>=61", r.stderr); self.assertIn("Nothing was written", r.stderr)
            self.assertFalse(out.exists())

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_offline_without_wheelhouse_names_the_backend_and_the_remedy(self):
        d = Path(tempfile.mkdtemp(prefix="g40off-")); self.addCleanup(shutil.rmtree, d, True)
        work = d / "work"
        r = run("wheel-smoke", ROOT, "--outside", work, "--json", env=_offline_env(), timeout=600)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("build_backend_unavailable", r.stderr)
        self.assertIn("--wheelhouse", r.stderr)
        self.assertIn(str(work), r.stderr)

    @unittest.skipIf(sys.version_info < (3, 10), "wheel-smoke needs 3.10+")
    def test_offline_build_with_a_local_wheelhouse_passes(self):
        wh = _local_wheelhouse()
        if not wh:
            self.skipTest("no local setuptools>=61 wheel (set G40_WHEELHOUSE)")
        d = Path(tempfile.mkdtemp(prefix="g40off-")); self.addCleanup(shutil.rmtree, d, True)
        r = run("wheel-smoke", ROOT, "--outside", d / "work", "--wheelhouse", wh, "--json", env=_offline_env(), timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        j = json.loads(r.stdout)
        self.assertEqual(j["result"], "pass", j)
        self.assertTrue(j["build_backend_from"].startswith("wheelhouse "), j)
        self.assertFalse(j["employees_in_wheel"])

    def test_docs_state_offline_wheelhouse(self):
        for p in ("employees/quality-security/qa-engineer/host-portability.md", "examples/capabilities/G40/README.md", "docs/install.md"):
            self.assertIn("--wheelhouse", (ROOT / p).read_text(), p)

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

class SkillCopySafety(unittest.TestCase):
    def setUp(self):
        self.top = Path(tempfile.mkdtemp(prefix="g40-copy-safety-"))
        self.addCleanup(shutil.rmtree, self.top, True)
        self.repo = self.top / "repo"
        (self.repo / "control-plane").mkdir(parents=True)
        (self.repo / "control-plane/meta_control_plane.py").write_text("# local fixture\n")
        shutil.copy2(ROOT / "pyproject.toml", self.repo / "pyproject.toml")
        self.source = self.repo / "employees/quality-security/demo"
        self.source.mkdir(parents=True)
        (self.source / "capability.contract.json").write_text(json.dumps({"dependencies": {}}))
        (self.source / "SKILL.md").write_text("# Complete fixture skill\n")
        (self.source / "rules.md").write_text("Keep the fixture files together.\n")

    @staticmethod
    def snapshot(folder):
        return {p.relative_to(folder).as_posix(): p.read_bytes()
                for p in folder.rglob("*") if p.is_file()}

    def copy(self, destination):
        return run("skill-copy", self.repo, "quality-security/demo", "--dest", destination, "--json")

    def test_existing_skill_and_owner_files_survive_refusal(self):
        destination = self.top / "host"
        target = destination / "demo"
        (target / "nested").mkdir(parents=True)
        (target / "OWNER.txt").write_bytes(b"owner content\x00\xff")
        (target / "nested/.settings").write_text("local settings\n")
        before = self.snapshot(destination)
        result = self.copy(destination)
        self.assertEqual(self.snapshot(destination), before, "Existing user files were changed")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_existing_file_target_is_preserved(self):
        destination = self.top / "host"
        destination.mkdir()
        (destination / "demo").write_text("keep this file\n")
        result = self.copy(destination)
        self.assertEqual((destination / "demo").read_text(), "keep this file\n")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_broken_target_symlink_is_preserved(self):
        destination = self.top / "host"
        destination.mkdir()
        target = destination / "demo"
        try:
            target.symlink_to(self.top / "missing")
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable on this host")
        result = self.copy(destination)
        self.assertTrue(target.is_symlink())
        self.assertFalse((self.top / "missing").exists())
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_destination_under_checkout_is_refused_before_creating_it(self):
        destination = self.repo / "uncreated/copies"
        before = self.snapshot(self.repo)
        result = self.copy(destination)
        self.assertEqual(self.snapshot(self.repo), before)
        self.assertFalse((self.repo / "uncreated").exists())
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_fresh_copy_still_works_after_a_collision(self):
        first = self.top / "first"
        positive = self.copy(first)
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        self.assertEqual(self.snapshot(first / "demo"), self.snapshot(self.source))
        (first / "demo/OWNER.txt").write_text("keep\n")
        refused = self.copy(first)
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertEqual((first / "demo/OWNER.txt").read_text(), "keep\n")
        recovery = self.copy(self.top / "second")
        self.assertEqual(recovery.returncode, 0, recovery.stdout + recovery.stderr)
        self.assertEqual(self.snapshot(self.top / "second/demo"), self.snapshot(self.source))


class SkillCopyTemp(unittest.TestCase):
    def test_skill_copy_without_dest_leaves_no_temp_folder(self):
        """M40 P4-2: skill-copy without --dest left a g40-skill-* folder in TMPDIR on every run."""
        import tempfile as _tf, shutil as _sh, os as _os
        tmpdir = Path(_tf.mkdtemp(prefix="g40tmpdir-"))
        try:
            env = dict(_os.environ, TMPDIR=str(tmpdir), PYTHONDONTWRITEBYTECODE="1")
            p = subprocess.run([sys.executable, str(TOOL), "skill-copy", str(ROOT), "quality-security/qa-engineer", "--json"],
                               capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(p.returncode, 1, p.stderr)
            j = json.loads(p.stdout)
            self.assertEqual(j["status"], "broken")
            self.assertIsNone(j["dest"])
            self.assertIn("removed", j["temp_copy"])
            self.assertEqual(sorted(x.name for x in tmpdir.iterdir()), [])
            keep = tmpdir / "keep"
            p = subprocess.run([sys.executable, str(TOOL), "skill-copy", str(ROOT), "quality-security/qa-engineer", "--dest", str(keep), "--json"],
                               capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertTrue((keep / "qa-engineer" / "capability.contract.json").is_file())
            self.assertNotIn("temp_copy", json.loads(p.stdout))
        finally:
            _sh.rmtree(str(tmpdir), ignore_errors=True)


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
