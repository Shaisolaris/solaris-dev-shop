"""G30 day 5 daily integration: the evidence-matrix tool, its oracle and this stack's plan."""
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
CAP = os.path.join(ROOT, "examples", "capabilities", "G30")
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
        self.assertEqual(self.plan["goal"], "G30")
        self.assertEqual(self.plan["base"], "02ba9c571b10ad1dba792d2ac5534bcad3171e67")
        ids = [p["id"] for p in self.plan["prerequisites"]]
        self.assertEqual(ids, ["G13", "G14", "G17", "G20", "G21", "G22", "G23", "G25"])
        self.assertEqual([e["id"] for e in self.plan["external"]], [])
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G30/**", "tests/test_g30_capability.py"])
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
        findings = [l for l in out.splitlines() if l.startswith("FINDING ")]
        self.assertEqual(r.returncode, 1 if findings else 0, out)
        self.assertIn("x1 G22 books -> G14 net cash 32.69 -> G17 inflow 33.144028/month (agrees)", out)
        self.assertIn("x3 G23 evidence_scope and G25 claim_scope both state synthetic, offline evidence", out)
        # demonstrated defect (owned by G22, reported, not edited here): books with open exceptions reach a G17 decision
        self.assertEqual(len(findings), 1, out)
        self.assertIn("FINDING x2 G22 has open exceptions evt_007,evt_008 (unapplied refunds 40.00) but export-g14 exit 0", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("CROSS-CHECKS "), out)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g30_cross_checks", os.path.join(CAP, "cross_checks.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _stub(self, d, name, body):
        p = os.path.join(d, name)
        with open(p, "w") as fh:
            fh.write("import json, os, sys\n" + body)
        return p

    def test_x1_catches_a_figure_that_differs_from_g14(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G17 = self._stub(d, "g17.py", "print(json.dumps({'assumptions': {'inflow': {'value': 99}}, 'status': 'feasible'}))\n")
            f = []
            mod.x1(f, [])
            self.assertTrue(any("x1 G17 uses 99" in x for x in f), f)

    def test_x2_passes_when_the_export_refuses_open_exceptions(self):
        # the fix the finding asks for: export-g14 refusing while exceptions are open must clear x2
        mod = self._load()
        real = mod.G22
        with tempfile.TemporaryDirectory() as d:
            mod.G22 = self._stub(d, "g22.py", "import subprocess\nif sys.argv[1] == 'export-g14':\n"
                                 "    r = json.loads(subprocess.run([sys.executable, %r, 'report', '--db', sys.argv[sys.argv.index('--db') + 1], '--json'],"
                                 " stdout=subprocess.PIPE).stdout)\n"
                                 "    if r.get('open'): sys.exit(1)\n"
                                 "sys.exit(subprocess.run([sys.executable, %r] + sys.argv[1:]).returncode)\n" % (real, real))
            f, lines = [], []
            mod.x2(f, lines)
            self.assertEqual(f, [])
            self.assertTrue(any("kept out of a G17 decision" in x for x in lines), lines)

    def test_x3_catches_a_live_claim(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G23 = self._stub(d, "g23.py", "print(json.dumps({'evidence_scope': 'production site'}))\n")
            f = []
            mod.x3(f, [])
            self.assertTrue(any("x3 G23 report scope" in x for x in f), f)


if __name__ == "__main__":
    unittest.main()
