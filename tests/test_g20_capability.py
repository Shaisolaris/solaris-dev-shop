"""G20: accessible asynchronous search (stale responses, keyboard model, states, layout).

The behaviour tests run the DOM-free core in a JavaScript shell (JavaScriptCore's jsc on macOS). Without one they are
skipped and say so; nothing here starts a browser, so rendering, focus and screen-reader output are not covered."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "examples/capabilities/G20"
CORE = ROOT / "employees/engineering/frontend-developer/async_search_core.js"
JSC_DEFAULT = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def find_jsc():
    for c in (os.environ.get("G20_JSC"), shutil.which("jsc"), JSC_DEFAULT):
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


JSC = find_jsc()
needs_jsc = unittest.skipUnless(JSC, "no JavaScript shell (jsc): G20 behaviour checks not run")


def oracle(*args, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(G / "ui_oracle.py")] + [str(a) for a in args],
                       capture_output=True, text=True, cwd=cwd or ROOT, env=env, timeout=300)
    return p.returncode, p.stdout


def core_tests(core):
    p = subprocess.run([JSC, str(core), str(G / "harness.js"), str(G / "core_tests.js")],
                       capture_output=True, text=True, timeout=120)
    res = {}
    for line in p.stdout.splitlines():
        if line.startswith("TEST "):
            parts = line.split(" ", 3)
            res[parts[1]] = parts[2]
    return res, p.stdout


class Behaviour(unittest.TestCase):
    @needs_jsc
    def test_oracle_accepts_the_core_and_rejects_both_stubs(self):
        code, out = oracle("--json")
        self.assertEqual(code, 0, out)
        rep = json.loads(out)
        self.assertEqual((rep["passed"], rep["total"]), (17, 17))
        self.assertTrue(rep["complete"])
        self.assertEqual(rep["scale"]["stale_shown"], 0)
        self.assertIn("not run: browser rendering", rep["unrun"])
        for stub in ("naive_core.js", "noop_core.js"):
            with self.subTest(stub=stub):
                code, out = oracle("--json", "--core", G / stub)
                self.assertEqual(code, 1, out)
                rep = json.loads(out)
                self.assertEqual(rep["passed"], 0, rep["checks"])
                self.assertEqual(rep["checks"].keys(), {f"o{i}" for i in range(1, 12)})  # static checks only for the real core

    @needs_jsc
    def test_core_unit_tests(self):
        res, out = core_tests(CORE)
        self.assertEqual(len(res), 14, out)
        bad = {k: v for k, v in res.items() if v not in ("PASS", "SKIP")}
        self.assertEqual(bad, {}, out)
        # jsc has no AbortController, so the abort test can only be skipped here; it is reported, not passed
        self.assertIn(res["superseded_request_is_aborted"], ("PASS", "SKIP"))
        for stub in ("naive_core.js", "noop_core.js"):
            with self.subTest(stub=stub):
                r, _ = core_tests(G / stub)
                self.assertGreaterEqual(sum(v == "FAIL" for v in r.values()), 10, r)

    @needs_jsc
    def test_unseen_seeds_and_scale(self):
        for seed in (1, 99, 2026):
            with self.subTest(seed=seed):
                code, out = oracle("--json", "--seed", seed, "--scale", 3)
                self.assertEqual(code, 0, out)
                rep = json.loads(out)
                self.assertEqual(rep["scale"]["worlds"], 450)
                self.assertEqual(rep["scale"]["stale_shown"], 0)
                self.assertEqual(rep["scale"]["options"], 30000)

    @needs_jsc
    def test_fresh_caller_from_another_folder(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = oracle(cwd=d)
        self.assertEqual(code, 0, out)
        self.assertIn("17/17 checks passed", out)
        self.assertIn("not run:", out)

    def test_invalid_arguments_exit_2(self):
        self.assertEqual(oracle("--scale", 0)[0], 2)
        self.assertEqual(oracle("--core", G / "missing.js")[0], 2)


class StaticDemo(unittest.TestCase):
    def test_demo_is_offline_and_loads_the_checked_core(self):
        html = (G / "demo/index.html").read_text(encoding="utf-8")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn('src="../../../../employees/engineering/frontend-developer/async_search_core.js"', html)
        self.assertTrue((G / "demo" / "../../../../employees/engineering/frontend-developer/async_search_core.js").resolve().samefile(CORE))
        self.assertIn("has NOT been run", html)

    def test_fixture_is_synthetic_and_reproducible(self):
        rows = json.loads((G / "fixtures/articles.json").read_text())
        self.assertEqual(len(rows), 240)
        self.assertEqual(len({r["id"] for r in rows}), 240)
        js = (G / "demo/fixture-data.js").read_text()
        self.assertIn("Synthetic fixture", js)
        self.assertEqual(json.loads(js.split("window.G20_FIXTURE = ", 1)[1].rstrip().rstrip(";")), rows)
        sys.path.insert(0, str(G))
        try:
            import make_fixtures
        finally:
            sys.path.pop(0)
        self.assertEqual(make_fixtures.articles(), rows)

    def test_breakpoint_matches_core(self):
        html = (G / "demo/index.html").read_text(encoding="utf-8")
        core = CORE.read_text(encoding="utf-8")
        self.assertIn("var NARROW_MAX_PX = 639;", core)
        self.assertIn("@media (min-width: 40rem)", html)


if __name__ == "__main__":
    unittest.main()
