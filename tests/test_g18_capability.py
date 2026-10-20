"""G18 day 3 daily integration: the evidence-matrix tool, its oracle and this stack's plan."""
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
CAP = os.path.join(ROOT, "examples", "capabilities", "G18")
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
        self.assertEqual(self.plan["goal"], "G18")
        self.assertEqual(self.plan["base"], "02ba9c571b10ad1dba792d2ac5534bcad3171e67")
        ids = [p["id"] for p in self.plan["prerequisites"]]
        self.assertEqual(ids, ["G03", "G10", "G11", "G13", "G14"])
        self.assertEqual([e["id"] for e in self.plan["external"]], ["P03"])
        self.assertEqual(self.plan["external"][0]["source_commit"], "bee80893c03beca8dcff9a7c77df15744ec9f370")
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G18/**", "tests/test_g18_capability.py"])
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
        self.assertIn("EXTERNAL_UNVERIFIED", codes)  # no acceptance file given: P03 has no binding here
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
        self.assertIn("x1 G10 -> G11 layer agreement: 12 fixtures compared", out)
        findings = [l for l in out.splitlines() if l.startswith("FINDING ")]
        self.assertEqual(r.returncode, 1 if findings else 0, out)
        self.assertFalse([f for f in findings if f.startswith(("FINDING x1", "FINDING x3"))], out)
        # r2 stacks G11 h1 94a0de4, which fixes the x2 finding r1 carried; a G11 that regresses brings it back
        self.assertEqual(findings, [], out)
        self.assertIn("x3 loaded exactly at as_of ('30.00'): G13 included, G14 included", out)
        self.assertIn("x3 sub-cent ('10.005'): G13 included, G14 left out (documented difference)", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("CROSS-CHECKS "), out)


    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g18_cross_checks", os.path.join(CAP, "cross_checks.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _stub(self, d, name, body):
        p = os.path.join(d, name)
        with open(p, "w") as fh:
            fh.write("import json, sys\n" + body)
        return p

    def test_x1_x2_catch_a_g11_that_ignores_network_evidence(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.IS = self._stub(d, "g11.py", "print(json.dumps({'decision': {'decision': 'rollback', 'trace': [{'check': 'burn', 'observed': 'x'}]}, 'diagnoses': []}))\n")
            f, lines = [], []
            mod.x1(f, lines)
            self.assertGreaterEqual(len([x for x in f if x.startswith("x1 ")]), 7, f)  # every non-application fixture
            f2 = []
            mod.x2(f2, [])
            self.assertEqual(len(f2), 2, f2)
            mod.IS = self._stub(d, "g11b.py", "print(json.dumps({'decision': {'decision': 'rollback', 'trace': [{'check': 'G10 network diagnosis during the impact', 'observed': 'unreadable'}]}, 'diagnoses': []}))\n")
            f3 = []
            mod.x2(f3, [])
            self.assertEqual(f3, [])

    def test_x3_catches_a_disagreeing_parser(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G14 = self._stub(d, "g14.py", "print(json.dumps({'exceptions': {'rejected': [{'id': 'P9', 'line': 4}], 'late': []}}))\n")
            f = []
            mod.x3(f, [])
            self.assertTrue(any("loaded exactly at as_of" in x for x in f), f)
            self.assertFalse(any("sub-cent" in x for x in f), f)


if __name__ == "__main__":
    unittest.main()
