"""G20: accessible asynchronous search (stale responses, keyboard model, states, layout).

The behaviour tests run the DOM-free core in a JavaScript shell (JavaScriptCore's jsc on macOS). Without one they are
skipped and say so. The Rendered tests start headless Chrome ONLY when G20_CHROME names a binary; by default they are
skipped and labelled, so the full suite never starts a browser. NarrowLayoutContract checks the 320 px overflow
contract from the demo source without a browser. Screen-reader output is not covered."""
import json
import os
import re
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
        self.assertEqual(len(res), 16, out)
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


CHROME = os.environ.get("G20_CHROME") or None  # opt-in only: never discovered, so a plain test run starts no browser
if CHROME and not Path(CHROME).is_file():
    CHROME = None
needs_chrome = unittest.skipUnless(CHROME, "G20_CHROME not set: rendered checks (320/360/1280 px) not run; no browser started")


def browser(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", G20_CHROME=CHROME or "")
    p = subprocess.run([sys.executable, str(G / "browser_checks.py"), "--json"] + [str(a) for a in args], capture_output=True, text=True, env=env, timeout=300)
    return p.returncode, json.loads(p.stdout.rsplit("BROWSER CHECKS", 1)[0])


@needs_chrome
class Rendered(unittest.TestCase):
    def test_rendered_layout_keyboard_focus_and_stale_responses(self):
        rc, rep = browser()
        bad = [r for r in rep["rows"] if not r["pass"]]
        self.assertEqual((rc, bad), (0, []))
        ids = {r["id"] for r in rep["rows"]}
        for w in (320, 360, 1280):
            for k in ("L01", "L02", "K01", "K02", "K03", "K04", "K05", "K06", "K07", "S01", "X01"):
                self.assertIn("%s-%d" % (k, w), ids)
        l01 = {r["id"]: r["detail"] for r in rep["rows"] if r["id"].startswith("L01")}
        for w in (320, 360, 1280):
            self.assertLessEqual(l01["L01-%d" % w]["docSW"], l01["L01-%d" % w]["docCW"])
            self.assertEqual(l01["L01-%d" % w]["docCW"], w)

    def test_controls_rejected(self):
        for stub in ("naive_core.js", "noop_core.js"):
            with self.subTest(stub=stub):
                rc, rep = browser("--core", G / stub)
                self.assertEqual(rc, 1)
                self.assertTrue(any(not r["pass"] for r in rep["rows"]))


def demo_css():
    html = (G / "demo/index.html").read_text(encoding="utf-8")
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def rules(css, base=False):
    if base:  # rules that apply at every width: drop @media blocks (the 320 px case is below the 40rem breakpoint)
        css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    out = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decl = {}
        for d in body.split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decl[k.strip().lower()] = v.strip().lower()
        out.append((" ".join(sel.split()), decl))
    return out


class NarrowLayoutContract(unittest.TestCase):
    """The 320 px overflow contract read from the demo source (no browser): long unbroken text must wrap, and nothing
    may demand more than 320 px of width. This is a static proxy; the rendered proof is browser_checks.py (opt-in)."""

    def test_long_unbroken_text_wraps(self):
        r = dict(rules(demo_css(), base=True))
        self.assertEqual(r.get("body", {}).get("overflow-wrap"), "anywhere")
        for sel, decl in rules(demo_css()):
            with self.subTest(sel=sel):
                self.assertNotIn(decl.get("overflow-wrap"), ("normal",), sel)
                self.assertNotIn(decl.get("word-wrap"), ("normal",), sel)
                self.assertNotIn(decl.get("white-space"), ("nowrap", "pre"), sel)
                self.assertNotIn(decl.get("word-break"), ("keep-all",), sel)

    def test_nothing_demands_more_than_320px(self):
        for sel, decl in rules(demo_css()):
            for k in ("width", "min-width", "flex-basis", "grid-template-columns"):
                v = decl.get(k, "")
                for num, unit in re.findall(r"(\d+(?:\.\d+)?)(px|rem|em|vw)", v):
                    px = float(num) * {"px": 1, "rem": 16, "em": 16, "vw": 3.2}[unit]
                    with self.subTest(sel=sel, prop=k):
                        self.assertLessEqual(px, 320, "%s { %s: %s }" % (sel, k, v))
        r = dict(rules(demo_css(), base=True))
        self.assertEqual(r["#q"]["width"], "100%")
        self.assertEqual(r["#results"]["grid-template-columns"], "1fr")
        self.assertEqual(r["*"]["box-sizing"], "border-box")

    def test_contract_rejects_the_unrepaired_page(self):
        # the 8d45038 body rule (no overflow-wrap) must fail the wrap test: the check has teeth without a browser
        old = demo_css().replace("overflow-wrap: anywhere;", "")
        self.assertIsNone(dict(rules(old, base=True))["body"].get("overflow-wrap"))

    def test_option_element_ids_come_from_option_dom_id(self):
        # a raw row id with a space or tab is not a valid IDREF for aria-activedescendant; the page must escape it
        html = (G / "demo/index.html").read_text(encoding="utf-8")
        ids = re.findall(r"li\.id\s*=\s*([^;]+);", html)
        self.assertEqual(ids, ['"opt-" + S.optionDomId(r.id)'])
        self.assertNotRegex(html, r"\.id\s*=\s*\"opt-\"\s*\+\s*r\.id")

    def test_no_browser_is_discovered_by_default(self):
        src = (G / "browser_checks.py").read_text(encoding="utf-8")
        self.assertNotIn("/Applications/Google Chrome.app", src)
        self.assertNotIn("shutil.which", src)
        me = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("shutil.which(\"google-chrome", me)
        p = subprocess.run([sys.executable, str(G / "browser_checks.py")], capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if k != "G20_CHROME"}, timeout=60)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn("no rendered check was run", p.stdout)


class StaticDemo(unittest.TestCase):
    def test_demo_is_offline_and_loads_the_checked_core(self):
        html = (G / "demo/index.html").read_text(encoding="utf-8")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn('src="../../../../employees/engineering/frontend-developer/async_search_core.js"', html)
        self.assertTrue((G / "demo" / "../../../../employees/engineering/frontend-developer/async_search_core.js").resolve().samefile(CORE))
        self.assertIn("screen-reader output and other browsers have not been run", html)
        self.assertIn("browser_checks.py", html)
        # the test transport is used only when a check installs it before load; the shipped page never sets it
        self.assertEqual(html.count("G20_TEST_FETCH"), 2)
        self.assertNotRegex(html, r"G20_TEST_FETCH\s*=[^=]")

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
