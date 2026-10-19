"""G42 day 7 daily integration: the evidence-matrix tool, its oracle and this stack's plan."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "employees", "quality-security", "assurance")
TOOL = os.path.join(A, "daily_integration.py")
ORACLE = os.path.join(A, "daily_integration_oracle.py")
CAP = os.path.join(ROOT, "examples", "capabilities", "G42")
PLAN = os.path.join(CAP, "plan.json")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(argv, **kw):
    return subprocess.run([sys.executable] + argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=ENV, timeout=600, **kw)


def git_ok(*commits):
    if not os.path.isdir(os.path.join(ROOT, ".git")) and not os.path.isfile(os.path.join(ROOT, ".git")):
        return False
    for c in commits:
        r = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", c + "^{commit}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode:
            return False
    return True


class Oracle(unittest.TestCase):
    def test_tool_accepted(self):
        r = run([ORACLE, "--", sys.executable, TOOL])
        out = r.stdout.decode()
        self.assertEqual(r.returncode, 0, out[-2000:])
        self.assertIn("ACCEPTED 13/13", out)

    def test_controls_rejected(self):
        for c, most in (("noop.py", 0), ("naive.py", 1)):
            r = run([ORACLE, "--", sys.executable, os.path.join(A, "daily_integration_controls", c)])
            out = r.stdout.decode()
            self.assertEqual(r.returncode, 1, out[-1000:])
            m = re.search(r"REJECTED (\d+)/13", out)
            self.assertTrue(m, out[-500:])
            self.assertLessEqual(int(m.group(1)), most)

    def test_oracle_needs_a_candidate(self):
        self.assertEqual(run([ORACLE]).returncode, 2)


class Plan(unittest.TestCase):
    def setUp(self):
        with open(PLAN) as fh:
            self.plan = json.load(fh)

    def test_plan_matches_the_goal_contract(self):
        self.assertEqual(self.plan["goal"], "G42")
        self.assertEqual(self.plan["base"], "02ba9c571b10ad1dba792d2ac5534bcad3171e67")
        ids = [p["id"] for p in self.plan["prerequisites"]]
        self.assertEqual(ids, ["G02", "G03", "G04", "G05", "G13", "G19", "G37", "G38", "G39", "G40", "G41"])
        self.assertEqual([e["id"] for e in self.plan["external"]], [])
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G42/**", "tests/test_g42_capability.py"])
        for p in self.plan["prerequisites"]:
            for m in p["tests"]:
                self.assertTrue(os.path.isfile(os.path.join(ROOT, *m.split(".")) + ".py"), m)
            for c in p.get("commands", []):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, c[0])), c[0])

    def test_stack_binds_this_tree(self):
        commits = [self.plan["base"]] + [p["commit"] for p in self.plan["prerequisites"]]
        if not git_ok(*commits):
            self.skipTest("not a git checkout holding the candidate commits")
        r = run([TOOL, "check", "--plan", PLAN, "--repo", ROOT, "--json"])
        self.assertIn(r.returncode, (0, 1), r.stderr.decode()[-500:])
        doc = json.loads(r.stdout.decode())
        codes = {f["code"] for f in doc["findings"]}
        self.assertFalse(codes & {"DRIFT", "OVERLAP", "OUT_OF_SCOPE", "PREREQUISITE_NOT_INTEGRATED", "UNKNOWN_COMMIT",
                                  "BASE_NOT_ANCESTOR"}, doc["findings"])
        self.assertTrue(all(p["ancestor_of_head"] for p in doc["prerequisites"]))
        self.assertGreaterEqual(doc["integration_files"] or 0, 1)

    def test_invalid_plan_is_refused_without_writing(self):
        bad = dict(self.plan)
        bad["cross_checks"] = [["../outside.py"]]
        with tempfile.TemporaryDirectory() as d:
            p, out = os.path.join(d, "p.json"), os.path.join(d, "r.json")
            with open(p, "w") as fh:
                json.dump(bad, fh)
            r = run([TOOL, "check", "--plan", p, "--repo", ROOT, "--out", out])
            self.assertEqual(r.returncode, 2)
            self.assertIn(b"VERDICT INVALID_INPUT", r.stderr)
            self.assertNotIn(b"Traceback", r.stderr)
            self.assertFalse(os.path.exists(out))


class CrossChecks(unittest.TestCase):
    def test_cross_checks_compare_real_tools(self):
        r = run([os.path.join(CAP, "cross_checks.py")])
        out = r.stdout.decode()
        self.assertEqual(r.returncode, 0, out)
        self.assertIn("x1 G39 drill passes on G02 r3, G04 r2, G05 r2 and G19 h1 (14 steps ok)", out)
        self.assertIn("x2 G38 provenance on the integrated tree: consistent, 65 declarations all MIT", out)
        self.assertIn("x3 security-auditor lists provenance_check.py and boundary_probe.py, both present and compiling; "
                      "G40 skill-copy misses only 3 shared standards", out)
        self.assertIn("x4 legal-advisor names the G37 and G38 tests; G37 not legal advice, G38 not a legal opinion", out)
        self.assertEqual(out.rstrip().splitlines()[-1], "CROSS-CHECKS CLEAN (0 findings)", out)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g42_cross_checks", os.path.join(CAP, "cross_checks.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _stub(self, d, name, body):
        p = os.path.join(d, name)
        with open(p, "w") as fh:
            fh.write("import json, os, sys\n" + body)
        return p

    def test_x1_catches_a_failing_drill(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.DRILL = self._stub(d, "drill.py", "print('ok   work order started')\nprint('FAIL resume by ben: exit 2 (want 0)')\nprint('DRILL FAILED')\nsys.exit(1)\n")
            f = []
            mod.x1(f, [])
            self.assertTrue(any("x1 G39 drill does not pass" in x and "FAIL resume by ben" in x for x in f), f)

    def test_x2_catches_a_conflicting_declaration(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G38 = self._stub(d, "g38.py", "print(json.dumps({'result': 'inconsistent', 'findings': [{'code': 'declaration_mismatch'}], 'declarations': 66, 'declared_values': ['MIT', 'Apache-2.0']}))\nsys.exit(1)\n")
            f = []
            mod.x2(f, [])
            self.assertTrue(any("x2 G38 provenance" in x and "declaration_mismatch" in x for x in f), f)

    def test_x3_catches_a_listed_script_that_is_missing(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            import shutil
            sec = os.path.join(d, "security-auditor")
            shutil.copytree(mod.SEC, sec)
            os.remove(os.path.join(sec, "boundary_probe.py"))
            mod.SEC = sec
            f = []
            mod.x3(f, [])
            self.assertTrue(any("x3 security-auditor scripts" in x and "missing ['boundary_probe.py']" in x for x in f), f)

    def test_x3_catches_a_skill_copy_missing_more_than_shared_standards(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G40 = self._stub(d, "g40.py", "print(json.dumps({'status': 'broken', 'missing': [{'ref': 'provenance_check.py'}, {'ref': '../QUALITY-SECURITY-STANDARD.md'}]}))\nsys.exit(1)\n")
            f = []
            mod.x3(f, [])
            self.assertTrue(any("x3 G40 skill-copy of security-auditor misses more than the shared standards: ['provenance_check.py']" in x for x in f), f)

    def test_x4_catches_a_report_without_the_legal_boundary(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G37 = self._stub(d, "g37.py", "print(json.dumps({'status': 'complete', 'read_only': 'yes'}))\n")
            f = []
            mod.x4(f, [])
            self.assertTrue(any("x4 G37 report has no not_legal_advice statement" in x for x in f), f)


if __name__ == "__main__":
    unittest.main()
