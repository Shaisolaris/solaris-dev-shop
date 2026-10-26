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


class AncestryWork(unittest.TestCase):
    def test_ancestry_queries_are_deduplicated_per_check_and_refreshed_next_check(self):
        import collections
        import importlib.util
        import types
        from unittest import mock
        with open(PLAN) as fh:
            plan = json.load(fh)
        if not git_ok(plan["base"], *[p["commit"] for p in plan["prerequisites"]]):
            self.skipTest("not a checkout holding the exact candidate commits")
        spec = importlib.util.spec_from_file_location("integration_cache_test", TOOL)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        original = module.is_anc
        calls = collections.Counter()
        def observed(repo, old, new):
            calls[(repo, old, new)] += 1
            return original(repo, old, new)
        args = types.SimpleNamespace(repo=ROOT, plan=PLAN, skip_gate=[], reply=[], manifest=[],
                                     acceptance=None, python=None, run="none", timeout=120)
        with mock.patch.object(module, "is_anc", side_effect=observed):
            first = module.check(args)
            self.assertTrue(calls)
            self.assertTrue(all(n == 1 for n in calls.values()), calls.most_common(3))
            second = module.check(args)
        self.assertTrue(all(n == 2 for n in calls.values()), calls.most_common(3))
        self.assertEqual(first["prerequisites"], second["prerequisites"])
        self.assertTrue(all(p["ancestor_of_head"] for p in second["prerequisites"]))


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
        # r3 (owner request, 2026-10-19): the final integration stacks every build goal's newest head; r4 (2026-10-20)
        # moves G09, G11, G15, G32, G34, G39 and G41 to their newer heads, and r5 moves G39 and G40, same ids. The six
        # daily integrations (G06, G12, G18, G24, G30, G36) are not stacked: each one's own plan test binds its
        # exact tree, so their evidence folders cannot share this tree; every build they integrate is here.
        self.assertEqual(ids, ["G01", "G02", "G03", "G04", "G05", "G07", "G08", "G09", "G10", "G11", "G13", "G14", "G15",
                               "G16", "G17", "G19", "G20", "G21", "G22", "G23", "G25", "G31", "G32", "G33", "G34", "G35",
                               "G37", "G38", "G39", "G40", "G41", "H66", "H67", "H68"])
        amendment = next(p for p in self.plan["prerequisites"] if p["id"] == "H66")
        self.assertEqual(amendment["commit"], "66dadbe966a9b7eb66d20d92614302014875475e")
        self.assertIn("tests.test_explicit_runtime_setup", amendment["tests"])
        for daily in ("G06", "G12", "G18", "G24", "G30", "G36"):
            self.assertNotIn(daily, ids)
        self.assertEqual([e["id"] for e in self.plan["external"]], [])
        self.assertEqual(self.plan["writable"], ["employees/quality-security/assurance/**", "employees/quality-security/qa-engineer/**",
                                                 "examples/capabilities/G42/**", "tests/test_g42_capability.py", ".github/workflows/ci.yml", "pyproject.toml", "CHANGELOG.md", "README.md", "docs/capabilities.md",
                                                 "chief-of-staff/references/routing-patterns.md",
                                                 "employees/infrastructure/network-engineer/homelab-and-network-ops.md",
                                                 "employees/infrastructure/network-engineer/rules.md",
                                                 "employees/specialized/wordpress-master/diagnostics/build-git/SKILL.md",
                                                 "employees/specialized/wordpress-master/diagnostics/diagnostic-config-security/SKILL.md",
                                                 "tests/test_wordpress_instruction_examples.py",
                                                 "employees/engineering/devops-engineer/headless-fleet-runbook.md",
                                                 "employees/engineering/unreal-developer/SKILL.md",
                                                 "employees/specialized/wordpress-master/diagnostics/build-content/SKILL.md",
                                                 "employees/specialized/wordpress-master/diagnostics/build-modify/SKILL.md",
                                                 "employees/specialized/wordpress-master/diagnostics/build-scrape/SKILL.md",
                                                 "employees/specialized/wordpress-master/diagnostics/shared/json_fields.py",
                                                 "tests/test_wordpress_json_fields.py"])
        for p in self.plan["prerequisites"]:
            for m in p["tests"]:
                self.assertTrue(os.path.isfile(os.path.join(ROOT, *m.split(".")) + ".py"), m)
            for c in p.get("commands", []):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, c[0])), c[0])

    def test_security_component_preserves_every_source_blob_except_owned_plan_artifacts(self):
        subject = "8631e1bfcb45288194296b84e662def1c1da0bcf"
        component = next(p["commit"] for p in self.plan["prerequisites"] if p["id"] == "H66")
        if not git_ok(subject, component):
            self.skipTest("not a checkout holding the exact security component")
        def inventory(revision):
            raw = subprocess.check_output(["git", "-C", ROOT, "ls-tree", "-rz", revision])
            return {row.split(b"\t", 1)[1].decode(): row.split(b"\t", 1)[0]
                    for row in raw.split(b"\0") if row}
        excluded = {"examples/capabilities/G42/plan.json", "tests/test_g42_capability.py"}
        original = inventory(subject)
        expected = {path: value for path, value in original.items() if path not in excluded}
        self.assertEqual(inventory(component), expected)
        self.assertFalse(excluded & inventory(self.plan["base"]).keys())

    def test_h67_preserves_the_reviewed_wordpress_source_blobs_and_modes(self):
        subject = "7b55e5fb7e31c3d48733d13af73658c77f2bae81"
        amendment = next(p for p in self.plan["prerequisites"] if p["id"] == "H67")
        self.assertEqual(amendment["commit"], "b480fbf1e6660b8fc29cb9f520a5081e1076e583")
        self.assertEqual(amendment["tests"], ["tests.test_wordpress_diagnostic_shell",
                                             "tests.test_wordpress_instruction_examples",
                                             "tests.test_wordpress_json_fields"])
        component = amendment["commit"]
        if not git_ok(subject, component):
            self.skipTest("not a checkout holding the exact reviewed WordPress component")
        def inventory(revision):
            raw = subprocess.check_output(["git", "-C", ROOT, "ls-tree", "-rz", revision])
            return {row.split(b"\t", 1)[1].decode(): row.split(b"\t", 1)[0]
                    for row in raw.split(b"\0") if row}
        excluded = {"examples/capabilities/G42/plan.json", "tests/test_g42_capability.py"}
        expected = {path: value for path, value in inventory(subject).items() if path not in excluded}
        self.assertEqual(inventory(component), expected)
        self.assertFalse(excluded & inventory(self.plan["base"]).keys())

    def test_h68_binds_every_current_source_blob_and_mode(self):
        subject = "7e45f7b8dfa3a1bb860e8eab3e404225387d5f3b"
        amendment = next(p for p in self.plan["prerequisites"] if p["id"] == "H68")
        self.assertEqual(amendment["commit"], "830ebbd93f5dd846519ba33060acf91a09986fdf")
        component = amendment["commit"]
        if not git_ok(subject, component):
            self.skipTest("not a checkout holding the consolidated security component")
        def inventory(revision):
            raw = subprocess.check_output(["git", "-C", ROOT, "ls-tree", "-rz", revision])
            return {row.split(b"\t", 1)[1].decode(): row.split(b"\t", 1)[0]
                    for row in raw.split(b"\0") if row}
        excluded = {"examples/capabilities/G42/plan.json", "tests/test_g42_capability.py"}
        expected = {path: value for path, value in inventory(subject).items() if path not in excluded}
        self.assertEqual(inventory(component), expected)
        self.assertFalse(excluded & inventory(self.plan["base"]).keys())
        self.assertEqual({path: value for path, value in inventory("HEAD").items()
                          if path not in excluded}, expected)

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
        self.assertIn("x1 G39 drill passes on G02 r4, G04 r3, G05 r3 and G19 h1 (14 steps ok)", out)
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


class Interfaces(unittest.TestCase):
    """r3 interface reconciliation: G05 r3 closure fixtures carry subject_revision and verified_revision, and the
    G01 fixture runner accepts only each fixture kind's own top-level keys. On the r3 stack the G05 oracle (o13)
    failed until the closure kind listed both fields."""

    def closure(self, tmp, **extra):
        sys.path.insert(0, A)
        try:
            import quality_os as q
        finally:
            sys.path.pop(0)
        f = q.create_finding(defect_kind="security", severity="S1", title="Password compare is not constant time",
                             evidence=["review of src/auth.py"], reporter_role="qa-engineer", finding_id="fnd-g42-1")
        fd = dict(f.to_dict())
        del fd["created_at"]
        fx = dict({"fixture_kind": "closure", "finding": fd, "closer_role": "code-reviewer",
                   "independent_evidence": ["verified fix"]}, **extra)
        p = os.path.join(tmp, "closure.json")
        with open(p, "w") as fh:
            json.dump(fx, fh)
        return run([os.path.join(A, "quality_os.py"), "run", p])

    def test_closure_fixture_takes_the_g05_revision_fields(self):
        r1, r2 = "a" * 40, "b" * 40
        with tempfile.TemporaryDirectory() as tmp:
            stale = self.closure(tmp, subject_revision=r2, verified_revision=r1, expect_blocked=False,
                                 expectations={"outcome": "fail_gate", "gate_codes": ["STALE_CLOSURE_EVIDENCE"]})
            self.assertEqual(stale.returncode, 0, stale.stdout.decode()[-400:])
            self.assertIn("STALE_CLOSURE_EVIDENCE", stale.stdout.decode())
            current = self.closure(tmp, subject_revision=r2, verified_revision=r2, expect_blocked=False)
            self.assertEqual(current.returncode, 0, current.stdout.decode()[-400:])

    def test_a_misspelled_revision_field_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.closure(tmp, subject_revision="b" * 40, verified_revison="b" * 40, expect_blocked=False)
            self.assertEqual(r.returncode, 1, r.stdout.decode()[-400:])
            self.assertIn("INVALID_PACKET", r.stdout.decode())
