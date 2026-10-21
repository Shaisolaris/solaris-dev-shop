"""G12 day 2 daily integration: the evidence-matrix tool, its oracle and this stack's plan."""
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
CAP = os.path.join(ROOT, "examples", "capabilities", "G12")
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
        self.assertEqual(self.plan["goal"], "G12")
        self.assertEqual(self.plan["base"], "02ba9c571b10ad1dba792d2ac5534bcad3171e67")
        ids = [p["id"] for p in self.plan["prerequisites"]]
        self.assertEqual(ids, ["G04", "G05", "G07", "G08", "G09"])
        self.assertEqual([e["id"] for e in self.plan["external"]], [])
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G12/**", "tests/test_g12_capability.py"])
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


    def test_too_long_text_is_named_as_too_long(self):
        """M12 P4-1: a resolved_overlaps reason over 300 characters was refused as "expected a non-empty string"."""
        cases = [("resolved_overlaps", [{"path": "a.txt", "reason": "r" * 301}], "resolved_overlaps[0].reason: 301 characters is too long; at most 300"),
                 ("resolved_overlaps", [{"path": "a.txt", "reason": ""}], "resolved_overlaps[0].reason: expected a non-empty string"),
                 ("resolved_overlaps", [{"path": "a.txt", "reason": 7}], "resolved_overlaps[0].reason: expected a non-empty string")]
        for key, value, msg in cases:
            with self.subTest(msg=msg):
                bad = dict(self.plan)
                bad[key] = value
                with tempfile.TemporaryDirectory() as d:
                    p, out = os.path.join(d, "p.json"), os.path.join(d, "r.json")
                    with open(p, "w") as fh:
                        json.dump(bad, fh)
                    r = run([TOOL, "check", "--plan", p, "--repo", ROOT, "--out", out])
                    self.assertEqual(r.returncode, 2)
                    self.assertIn(msg.encode(), r.stderr)
                    self.assertFalse(os.path.exists(out))

class CrossChecks(unittest.TestCase):
    def test_cross_checks_compare_real_tools(self):
        r = run([os.path.join(CAP, "cross_checks.py")])
        out = r.stdout.decode()
        findings = [l for l in out.splitlines() if l.startswith("FINDING ")]
        self.assertEqual(r.returncode, 1 if findings else 0, out)
        self.assertIn("x1 G07 transfer ana->ben: stale ana order refused (exit 2), ben on delivered revision 1 refused (exit 2), ben revision 2 runs (exit 0), brief names ben", out)
        self.assertIn("x2 G05 receipt on the G04 brief: re-run current, revision reissued for the new owner stale", out)
        self.assertIn("x3 G05 receipt on artifact r2: current for G08 live r2, stale after rollback to r1", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("CROSS-CHECKS "), out)

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g12_cross_checks", os.path.join(CAP, "cross_checks.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _always(self, mod, state):
        real = mod.qos

        def fake():
            q = real()
            q.binding_state = lambda reviewed, subject: (state, {})
            return q
        mod.qos = fake

    def test_x1_catches_a_handoff_that_ignores_the_fleet_claim(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "handoff.py")
            with open(p, "w") as fh:
                fh.write("import sys\nsys.exit(0)\n")
            mod.HANDOFF = p
            f = []
            mod.x1(f, [])
            self.assertTrue(any("not refused" in x for x in f), f)

    def test_x2_catches_a_receipt_that_survives_the_owner_change(self):
        mod = self._load()
        self._always(mod, "current")
        f = []
        mod.x2(f, [])
        self.assertTrue(any("want stale" in x for x in f), f)

    def test_x3_catches_a_receipt_that_survives_a_rollback(self):
        mod = self._load()
        self._always(mod, "current")
        f = []
        mod.x3(f, [])
        self.assertTrue(any("after G08 rollback" in x for x in f), f)


    def _wrap_handoff(self, mod, d, after_ben):
        """Run the real G04 handoff, then apply after_ben (python source) when the worker is ben."""
        p = os.path.join(d, "handoff_wrap.py")
        with open(p, "w") as fh:
            fh.write("import os, subprocess, sys\n"
                     "rc = subprocess.call([sys.executable, %r] + sys.argv[1:])\n"
                     "if 'ben' in sys.argv:\n" % mod.HANDOFF
                     + "".join("    " + l + "\n" for l in after_ben.splitlines())
                     + "sys.exit(rc)\n")
        mod.HANDOFF = p

    def test_x1_catches_a_brief_that_keeps_the_old_owner(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            self._wrap_handoff(mod, d, "for r, _, fs in os.walk('.'):\n"
                                       "    for f in fs:\n"
                                       "        if f == 'HANDOFF-BRIEF.md':\n"
                                       "            q = os.path.join(r, f); t = open(q).read().replace('- Owner: ben', '- Owner: ana'); open(q, 'w').write(t)")
            f = []
            mod.x1(f, [])
            self.assertTrue(any("does not name ben only" in x for x in f), f)

    def test_x1_catches_a_failed_run_for_the_new_owner(self):
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            self._wrap_handoff(mod, d, "rc = 3")
            f = []
            mod.x1(f, [])
            self.assertTrue(any("x1 new owner ben" in x for x in f), f)

    def test_x1_catches_a_handoff_that_lets_the_new_owner_rerun_a_delivered_revision(self):
        # G04 r3: an owner change on a delivered revision is refused (exit 2); a G04 that runs it again would
        # deliver revision 1 a second time
        mod = self._load()
        with tempfile.TemporaryDirectory() as d:
            self._wrap_handoff(mod, d, "rc = 0")
            f = []
            mod.x1(f, [])
            self.assertTrue(any("on the delivered revision 1" in x and "want 2" in x for x in f), f)

    def test_x2_catches_a_receipt_stale_after_a_plain_rerun(self):
        mod = self._load()
        self._always(mod, "stale")
        f = []
        mod.x2(f, [])
        self.assertTrue(any("plain re-run" in x for x in f), f)

    def test_x3_catches_a_receipt_not_current_for_the_live_release(self):
        mod = self._load()
        self._always(mod, "stale")
        f = []
        mod.x3(f, [])
        self.assertTrue(any("after G08 deploy of r2" in x for x in f), f)

if __name__ == "__main__":
    unittest.main()
