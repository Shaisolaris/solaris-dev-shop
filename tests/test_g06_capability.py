"""G06 day 1 daily integration: the evidence-matrix tool, its oracle and this stack's plan."""
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
CAP = os.path.join(ROOT, "examples", "capabilities", "G06")
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
        self.assertEqual(self.plan["goal"], "G06")
        self.assertEqual(self.plan["base"], "02ba9c571b10ad1dba792d2ac5534bcad3171e67")
        ids = [p["id"] for p in self.plan["prerequisites"]]
        self.assertEqual(ids, ["G01", "G02", "G03"])
        self.assertEqual([e["id"] for e in self.plan["external"]], ["P01", "P02"])
        self.assertEqual(self.plan["external"][0]["source_commit"], "2577f3ed714650e62d022113a0ce23f5b6d7aa76")
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G06/**", "tests/test_g06_capability.py"])
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
        self.assertIn("EXTERNAL_UNVERIFIED", codes)  # no acceptance file given: P01/P02 has no binding here
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
        findings = [l for l in out.splitlines() if l.startswith("FINDING ")]
        self.assertEqual(r.returncode, 1 if findings else 0, out)
        self.assertIn("G03 verify/health/recover rc 0/0/0", out)
        self.assertIn("x2 G03 restore inside an activated project: 200 rows back, G02 resume rc 0, notes unchanged True", out)
        self.assertIn("x3 G01 audit over the integrated skills: scanned 61, gaps 0", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("CROSS-CHECKS "), out)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g06_cross_checks", os.path.join(CAP, "cross_checks.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _stub(self, d, name, body):
        p = os.path.join(d, name)
        with open(p, "w") as fh:
            fh.write("import json, os, sys\n" + body)
        return p

    def test_x1_catches_an_activation_that_touches_owner_data(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.ACT = self._stub(d, "act.py", "root = sys.argv[2]\nopen(os.path.join(root, 'Development', 'notes.txt'), 'a').write('x')\nprint('{}')\n")
            f, lines = [], []
            ctx = mod.x1(f, lines, d)
            self.assertTrue(any("changed owner files" in x and "notes.txt" in x for x in f), f)
            self.assertIsNotNone(ctx)

    def test_x1_x2_catch_a_broken_recovery_tool(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            real = mod.REC
            mod.REC = self._stub(d, "rec.py", "import subprocess\nif sys.argv[1] in ('verify', 'restore'):\n    sys.exit(1)\n"
                                 "sys.exit(subprocess.call([sys.executable, %r] + sys.argv[1:]))\n" % real)
            f, lines = [], []
            ctx = mod.x1(f, lines, d)
            self.assertTrue(any("G03 verify after activation exited 1" in x for x in f), f)
            mod.x2(f, lines, d, ctx)
            self.assertTrue(any("G03 restore into the activated project exited 1" in x for x in f), f)

    def test_x2_catches_a_resume_that_rewrites_its_notes(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            f, lines = [], []
            ctx = mod.x1(f, lines, d)
            self.assertEqual(f, [])
            real = mod.ACT
            mod.ACT = self._stub(d, "act.py", "import subprocess\nif sys.argv[1] == 'resume':\n"
                                 "    open(os.path.join(sys.argv[2], 'STATUS.md'), 'a').write('rewritten')\n"
                                 "sys.exit(subprocess.call([sys.executable, %r] + sys.argv[1:]))\n" % real)
            mod.x2(f, lines, d, ctx)
            self.assertTrue(any("resume rewrote its notes" in x and "STATUS.md" in x for x in f), f)

    def test_x3_reads_the_audit_counts(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.QOS = self._stub(d, "qos.py", "print(json.dumps({'counts': {'skills_scanned': 60, 'gaps': 1}, 'gaps': [{'skill': 'x'}]}))\n")
            f = []
            mod.x3(f, [], d)
            self.assertTrue(any("scanned 60, gaps 1" in x for x in f), f)


if __name__ == "__main__":
    unittest.main()
