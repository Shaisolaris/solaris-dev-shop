"""G20: accessible asynchronous search (stale responses, keyboard model, states, layout).

The behaviour tests run the DOM-free core in a JavaScript shell (JavaScriptCore's jsc on macOS). Without one they are
skipped and say so. RecordedRendered reads the report of the one recorded browser run (rendered/report.json) and starts
nothing; LaunchGuard checks, without a browser, that browser_checks.py can start Chrome at most once per run. The single
Rendered test starts headless Chrome once, ONLY when G20_CHROME names a binary; by default it is skipped, so the full
suite never starts a browser. NarrowLayoutContract checks the 320 px overflow
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
from unittest import mock

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
    env = dict({name: os.environ[name] for name in (
                   'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                   'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                   'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                   'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                   'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                   'GITHUB_ACTIONS',
               ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
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


REPORT = G / "rendered" / "report.json"  # written by the one recorded browser_checks.py run (see rendered/README.md)


def load_bc():
    import importlib.util
    spec = importlib.util.spec_from_file_location("g20_browser_checks", G / "browser_checks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RecordedRendered(unittest.TestCase):
    """Reads the report of the single recorded run (one Chrome launch for all widths and both controls); starts nothing."""

    def setUp(self):
        self.rep = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_one_launch_covered_every_width_and_check(self):
        self.assertEqual(self.rep["launches"], 1)
        bad = [r["id"] for r in self.rep["rows"] if not r["pass"]]
        self.assertEqual(bad, [])
        ids = {r["id"] for r in self.rep["rows"]}
        for w in (320, 360, 1280):
            for k in ("L01", "L02", "K01", "K02", "K03", "K04", "K05", "K06", "K07", "S01", "X01"):
                self.assertIn("%s-%d" % (k, w), ids)
        l01 = {r["id"]: r["detail"] for r in self.rep["rows"] if r["id"].startswith("L01")}
        for w in (320, 360, 1280):
            self.assertLessEqual(l01["L01-%d" % w]["docSW"], l01["L01-%d" % w]["docCW"])
            self.assertEqual(l01["L01-%d" % w]["docCW"], w)

    def test_controls_were_rejected_in_the_same_session(self):
        self.assertEqual(sorted(self.rep["controls"]), ["naive_core.js", "noop_core.js"])
        for k, v in self.rep["controls"].items():
            self.assertTrue(v["rejected"] and v["passed"] < v["total"], (k, v))

    def test_screenshots_exist_for_every_width(self):
        for w in ("320", "360", "1280"):
            p = REPORT.parent / self.rep["screenshots"][w]
            self.assertTrue(p.is_file(), p)
            self.assertEqual(p.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


class LaunchGuard(unittest.TestCase):
    """No browser: the guard that keeps browser_checks.py to one Chrome launch per run."""

    def test_second_launch_is_refused_before_popen(self):
        mod = load_bc()
        calls = []
        mod.LAUNCHES.append(4242)
        with mock.patch.object(mod.subprocess, "Popen", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("Popen reached"))):
            with self.assertRaises(mod.LaunchRefused):
                mod.Browser("/nonexistent/chrome")
        self.assertEqual(calls, [])

    def test_failed_start_is_closed_and_not_retried(self):
        mod = load_bc()
        started = []

        class Dead:
            pid, returncode = 999999, 1
            def poll(self):
                return 1
            def terminate(self):
                raise AssertionError("not running, nothing to terminate")
            def kill(self):
                pass
            def wait(self, t=None):
                return 1
        with mock.patch.object(mod.subprocess, "Popen", lambda *a, **k: started.append(a) or Dead()):
            rows, shots, ctl, version = mod.run("/nonexistent/chrome", str(mod.CORE), None, controls=["x.js"])
        self.assertEqual(len(started), 1)
        self.assertEqual(mod.LAUNCHES, [999999])
        self.assertEqual([r["id"] for r in rows], ["E-run"])
        self.assertIn("not retried", rows[0]["detail"])
        with self.assertRaises(mod.LaunchRefused):
            mod.Browser("/nonexistent/chrome")

    def test_source_has_one_launch_site_outside_any_loop(self):
        src = (G / "browser_checks.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("subprocess.Popen("), 1)
        self.assertEqual(src.count("subprocess.run("), 0)  # the binary is never run again (no --version call)
        self.assertEqual(len(re.findall(r"\bBrowser\(chrome", src)), 1)
        run_src = src[src.index("def run("):src.index("def one_width(")]
        self.assertLess(run_src.index("b = Browser("), run_src.index("for label, c in"))
        self.assertIn("finally:", run_src)
        self.assertIn("b.close()", run_src[run_src.index("finally:"):])
        self.assertIn("self.proc.kill()", src[src.index("def _watchdog"):src.index("def cmd(")])


@needs_chrome
class Rendered(unittest.TestCase):
    """Opt-in (G20_CHROME): ONE run of browser_checks.py, one Chrome launch, all widths and both controls."""

    def test_one_live_run(self):
        env = dict({name: os.environ[name] for name in (
                       'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                       'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                       'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                       'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                       'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                       'GITHUB_ACTIONS',
                   ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1", G20_CHROME=CHROME or "")
        p = subprocess.run([sys.executable, str(G / "browser_checks.py"), "--json", "--controls"], capture_output=True, text=True, env=env, timeout=300)
        rep = json.loads(p.stdout.rsplit("BROWSER CHECKS", 1)[0])
        self.assertEqual((p.returncode, rep["launches"], [r["id"] for r in rep["rows"] if not r["pass"]]), (0, 1, []))


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
    may demand more than 320 px of width. This is a static proxy beside the rendered proof (rendered/report.json)."""

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
                           env={name: os.environ[name] for name in (
                                   'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                   'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                   'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                   'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                   'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                   'GITHUB_ACTIONS',
                               ) if name in os.environ}, timeout=60)
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
