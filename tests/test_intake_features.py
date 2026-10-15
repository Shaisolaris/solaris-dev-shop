"""Public CLI behavior, privacy boundaries, and adversarial fixture checks."""
import contextlib
import copy
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "control-plane"))
import meta_control_plane as mcp


class IntakeFeatures(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "control-plane/meta_control_plane.py"),
                               *map(str, args)], capture_output=True, text=True)

    def test_explain_matches_actual_assignment(self):
        result = self.cli("intake", "--explain", "review this code")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        trace = packet["explanation"]
        self.assertEqual(trace["capabilities"][0], packet["assignment"]["primary_capability"])
        self.assertIn("review this code", trace["matched_keywords"])
        self.assertTrue(trace["override_hits"])
        self.assertIn("not a probability", trace["confidence_meaning"])

    def test_confidence_runner_up_and_ties(self):
        policy = copy.deepcopy(mcp.load_policy())
        policy["route_overrides"] = []
        policy["capability_keywords"] = {"solaris.backend-developer": ["same"],
                                         "solaris.code-reviewer": ["same"]}
        d = mcp.intake("build the same thing please", policy=policy)
        self.assertEqual(d.assignment.confidence, 0.5)
        self.assertEqual(d.assignment.runner_up, "solaris.code-reviewer")

    def test_every_probe_has_bounded_confidence(self):
        import test_router
        for _, text, _ in test_router.load_probes():
            d = mcp.intake(text)
            if d.assignment:
                self.assertGreaterEqual(d.assignment.confidence, 0)
                self.assertLessEqual(d.assignment.confidence, 1)
                self.assertNotEqual(d.assignment.primary_capability, d.assignment.runner_up)

    def test_spanish_and_french_review(self):
        for request in ["revisa este código", "revisa este codigo", "révise ce code",
                        "re\u0301vise ce code"]:
            with self.subTest(request=request):
                d = mcp.intake(request)
                self.assertEqual(d.decision, "assign")
                self.assertEqual(d.assignment.primary_capability, "solaris.code-reviewer")

    def test_localized_authority_and_risk_are_not_bypassed(self):
        for request, reason in [("revisa este código y despliega en producción", "high_risk"),
                                ("révise ce code et mon bilan sanguin", "out_of_authority")]:
            d = mcp.intake(request)
            self.assertEqual(d.decision, "escalate")
            self.assertEqual(d.escalation.reason, reason)
            self.assertIsNone(d.assignment)

    def test_unicode_keyword_boundaries(self):
        self.assertFalse(mcp._word_boundary_hit("code", "decode"))
        self.assertFalse(mcp._word_boundary_hit("code", "codeé"))
        self.assertTrue(mcp._word_boundary_hit("código", "(CÓDIGO)!"))

    def test_context_is_opt_in_minimal_and_clearable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "routing.json"
            first = self.cli("intake", "--context", path, "Design a logo for the sample coffee brand")
            self.assertEqual(first.returncode, 0, first.stderr)
            context = json.loads(path.read_text())
            self.assertEqual(set(context), {"kind", "version", "primary_capability", "domains"})
            self.assertNotIn("coffee", path.read_text())
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o077, 0)
            follow = self.cli("intake", "--context", path, "--explain", "and make it red")
            d = json.loads(follow.stdout)
            self.assertEqual(d["assignment"]["primary_capability"], "solaris.image-generator")
            self.assertEqual(d["explanation"]["source"], "explicit_context")
            self.assertEqual(json.loads(self.cli("intake", "and make it red").stdout)["decision"], "clarify")
            self.assertEqual(self.cli("context", "clear", path).returncode, 0)
            self.assertFalse(path.exists())

    def test_context_cannot_override_safety_or_explicit_new_domain(self):
        context = {"primary_capability": "solaris.image-generator", "domains": ["design"]}
        for request in ["and change it then deploy to production", "and update this with my blood test results"]:
            d = mcp.intake(request, context=context)
            self.assertEqual(d.decision, "escalate")
            self.assertIsNone(d.assignment)
        d = mcp.intake("Write a test plan for the login regression", context=context)
        self.assertEqual(d.assignment.primary_capability, "solaris.qa-engineer")

    def test_context_clear_refuses_unrelated_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "unrelated.json"
            p.write_text('{"keep":"me"}')
            r = self.cli("context", "clear", p)
            self.assertEqual(r.returncode, 2)
            self.assertTrue(p.exists())
            self.assertNotIn("Traceback", r.stderr)

    def test_invalid_fixture_is_a_user_error(self):
        for value in [[], {"request": []}, {"request": "review this code", "expectations": []}]:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "invalid.json"
                p.write_text(json.dumps(value))
                r = self.cli("intake", "--fixture", p)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)

    def test_self_test_checks_the_actual_fixture_directory(self):
        self.assertEqual(mcp.FIXTURE_ROOT, ROOT / "fixtures/control-plane")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "bad-expectation.json").write_text(json.dumps({
                "request": "review this code", "expectations": {"decision": "block"}}))
            original = mcp.FIXTURE_ROOT
            try:
                mcp.FIXTURE_ROOT = p
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(mcp.self_test(), 1)
            finally:
                mcp.FIXTURE_ROOT = original

    def test_all_saved_fixtures_enforce_their_expectations(self):
        paths = list((ROOT / "fixtures/control-plane").glob("*.json"))
        self.assertGreaterEqual(len(paths), 10)
        for path in paths:
            with self.subTest(path=path.name):
                decision, fixture = mcp.run_fixture(path)
                self.assertEqual(mcp.check_fixture_expectations(decision, fixture), [])

    def test_html_report_is_complete_and_escapes_input(self):
        sys.path.insert(0, str(ROOT / "employees/quality-security/assurance"))
        quality = importlib.import_module("quality_os")
        report = quality.audit_existing_capabilities(ROOT / "employees")
        report["gaps"].append('<script>alert("unsafe")</script>')
        text = quality.render_audit_html(report)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("Skills scanned: 61", text)
        self.assertEqual(text.count("<tr>"), 62)

    @unittest.skipUnless(os.name == "posix", "Bash installer; Windows has a documented Python path")
    def test_uninstall_preserves_unrecognized_commands_and_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            shim = folder / "solaris-intake"
            shim.write_text("user-owned command\n")
            r = subprocess.run(["bash", str(ROOT / "install.sh"), "--uninstall", "--bin-dir", tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(shim.read_text(), "user-owned command\n")
            install = subprocess.run(["bash", str(ROOT / "install.sh"), "--bin-dir", tmp],
                                     cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(install.returncode, 1)
            self.assertEqual(shim.read_text(), "user-owned command\n")
            shim.write_text("#!/bin/bash\n# Solaris Dev Shop managed command\n")
            r = subprocess.run(["bash", str(ROOT / "install.sh"), "--uninstall", "--bin-dir", tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(shim.exists())
            self.assertTrue((ROOT / "README.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
