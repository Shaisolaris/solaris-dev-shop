"""G36 day 6 daily integration: the evidence-matrix tool, its oracle and this stack's plan."""
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
CAP = os.path.join(ROOT, "examples", "capabilities", "G36")
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
        self.assertEqual(self.plan["goal"], "G36")
        self.assertEqual(self.plan["base"], "02ba9c571b10ad1dba792d2ac5534bcad3171e67")
        ids = [p["id"] for p in self.plan["prerequisites"]]
        self.assertEqual(ids, ["G04", "G13", "G14", "G17", "G31", "G32", "G33", "G34", "G35"])
        self.assertEqual([e["id"] for e in self.plan["external"]], [])
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G36/**", "tests/test_g36_capability.py"])
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
        self.assertIn("x1 G31 date 2027-02-07 rests on the current G17 result; a changed G17 package blocks it", out)
        self.assertIn("x2 G35 recognized revenue equals G14 (EUR 45.00, USD 495.00), result reconciled", out)
        self.assertIn("x3 one csv_reconcile.py, loaded by G33 and G35; spend export status reconciled_with_gaps in both", out)
        self.assertIn("x4 G31 read_only, G35 nothing published or spent, all 7 G32 drafts unsent", out)
        self.assertEqual(out.rstrip().splitlines()[-1], "CROSS-CHECKS CLEAN (0 findings)", out)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g36_cross_checks", os.path.join(CAP, "cross_checks.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _stub(self, d, name, body):
        p = os.path.join(d, name)
        with open(p, "w") as fh:
            fh.write("import json, os, sys\n" + body)
        return p

    def test_x1_catches_a_g31_that_keeps_a_stale_g17_result(self):
        mod = self._load()
        real = mod.G31
        with tempfile.TemporaryDirectory() as d:
            # a G31 that ignores capacity changes: always answers like the real tool on the unchanged fixture
            frozen = run([real, "check", os.path.join(mod.FX31, "portal.json"), "--json"]).stdout.decode()
            mod.G31 = self._stub(d, "g31.py", "sys.stdout.write(%r)\n" % frozen)
            f = []
            mod.x1(f, [])
            self.assertTrue(any("x1 G31 still relies on a stored G17 result" in x for x in f), f)

    def test_x1_catches_a_stored_result_g17_no_longer_gives(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G17 = self._stub(d, "g17.py", "print(json.dumps({'status': 'feasible'}))\n")
            f = []
            mod.x1(f, [])
            self.assertTrue(any("x1 the G17 result G31 stores" in x for x in f), f)

    def test_x2_catches_a_revenue_figure_that_differs_from_g14(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G14 = self._stub(d, "g14.py", "print(json.dumps({'result': 'reconciled', 'currencies': {'EUR': {'recognized_revenue': '45.00'}, 'USD': {'recognized_revenue': '555.00'}}}))\n")
            f = []
            mod.x2(f, [])
            self.assertTrue(any("x2 G35 finance tie-out differs from G14: USD G35 495.00 G14 555.00" in x for x in f), f)

    def test_x2_catches_a_result_word_that_differs_from_g14(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G14 = self._stub(d, "g14.py", "print(json.dumps({'result': 'reconciled_with_findings', 'currencies': {'EUR': {'recognized_revenue': '45.00'}, 'USD': {'recognized_revenue': '495.00'}}}))\n")
            f = []
            mod.x2(f, [])
            self.assertTrue(any("result G35 reconciled G14 reconciled_with_findings" in x for x in f), f)

    def test_x3_catches_a_g13_status_that_differs(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            mod.G13 = self._stub(d, "g13.py", "print(json.dumps({'status': 'reconciled'}))\n")
            f = []
            mod.x3(f, [])
            self.assertTrue(any("x3 G35 reports G13 status reconciled_with_gaps" in x for x in f), f)

    def test_x4_catches_a_draft_marked_sent(self):
        mod = self._load()
        real = mod.G32
        with tempfile.TemporaryDirectory() as d:
            mod.G32 = self._stub(d, "g32.py", "import subprocess, glob\n"
                                 "rc = subprocess.run([sys.executable, %r] + sys.argv[1:], stdout=subprocess.DEVNULL).returncode\n"
                                 "for p in glob.glob(os.path.join(sys.argv[2], 'drafts', '*welcome.json')):\n"
                                 "    doc = json.load(open(p)); doc['send'] = 'performed'; json.dump(doc, open(p, 'w'))\n"
                                 "sys.exit(rc)\n" % real)
            f = []
            mod.x4(f, [])
            self.assertTrue(any("x4 G32 drafts without the no-send statement: 2 of 7" in x for x in f), f)


if __name__ == "__main__":
    unittest.main()
