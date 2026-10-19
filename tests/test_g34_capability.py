"""G34: content, metadata, link, accessibility and conversion-path diagnostics on saved HTML snapshots.

Everything runs offline on synthetic fixtures; live pages, rendering, Core Web Vitals and indexing are not covered."""
import filecmp
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "examples/capabilities/G34"
TOOL = ROOT / "employees/marketing/seo-aso-specialist/page_diagnostics.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("g34_page_diagnostics", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pd = load_tool()


def run(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True, env=env,
                       timeout=600)
    return p.returncode, p.stdout, p.stderr


def oracle(*extra):
    code, out, err = run(G / "diag_oracle.py", "--json", "--scale", "300", *extra)
    return code, json.loads(out)


def call(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = pd.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class Oracle(unittest.TestCase):
    def test_oracle_accepts_the_tool(self):
        code, rep = oracle()
        self.assertEqual(code, 0, [c for c in rep["checks"] if not c["ok"]])
        self.assertEqual((rep["passed"], rep["total"]), (14, 14))
        self.assertIn("not run:", rep["unrun"])

    def test_oracle_rejects_both_controls_for_the_right_reasons(self):
        for stub, failing in (("noop_diagnostics.py", {"o1", "o2", "o3", "o4", "o5", "o8", "o9", "o10", "o11",
                                                       "o12", "o13"}),
                              ("naive_diagnostics.py", {"o2", "o3", "o4", "o8", "o9"})):
            with self.subTest(stub=stub):
                code, rep = oracle("--tool", G / stub)
                self.assertEqual(code, 1)
                self.assertEqual({c["id"] for c in rep["checks"] if not c["ok"]}, failing)

    def test_fixtures_regenerate_byte_identical(self):
        with tempfile.TemporaryDirectory() as t:
            code, _, err = run(G / "make_fixtures.py", t)
            self.assertEqual(code, 0, err)
            cmp = filecmp.dircmp(t, str(G / "fixtures"))
            stack, diffs = [cmp], []
            while stack:
                c = stack.pop()
                diffs += c.left_only + c.right_only + c.diff_files + c.funny_files
                stack += c.subdirs.values()
            self.assertEqual(diffs, [])
            for a, _, files in os.walk(t):
                for f in files:
                    rel = os.path.relpath(os.path.join(a, f), t)
                    self.assertTrue(filecmp.cmp(os.path.join(t, rel), str(G / "fixtures" / rel), shallow=False), rel)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="g34-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for n in ("clean", "before"):
            shutil.copytree(str(G / "fixtures" / n), os.path.join(self.tmp, n))

    def site(self, n):
        return os.path.join(self.tmp, n, "site"), os.path.join(self.tmp, n, "config.json")

    def test_failed_replace_keeps_old_report_and_removes_temp(self):
        site, cfg = self.site("clean")
        out = os.path.join(self.tmp, "r.json")
        with open(out, "w") as f:
            f.write("previous report\n")
        with mock.patch.object(pd.os, "replace", side_effect=OSError("disk full")):
            code, _, err = call(site, "--config", cfg, "--out", out)
        self.assertEqual(code, 2)
        self.assertIn("could not write --out", err)
        with open(out) as f:
            self.assertEqual(f.read(), "previous report\n")
        self.assertEqual(sorted(os.listdir(self.tmp)), ["before", "clean", "r.json"])

    def test_incomplete_outranks_findings(self):
        site, cfg = self.site("before")
        os.symlink(os.path.join(self.tmp, "clean", "config.json"), os.path.join(site, "x.html"))
        os.symlink("/", os.path.join(site, "rootlink.html"))
        code, out, _ = call(site, "--config", cfg, "--json")
        rep = json.loads(out)
        self.assertEqual(code, 3)
        self.assertGreater(rep["summary"]["by_severity"]["high"], 0)
        self.assertEqual(sorted(s["path"] for s in rep["skipped"]), ["/rootlink.html", "/x.html"])

    def test_text_report_names_evidence_fix_and_unrun(self):
        site, cfg = self.site("before")
        code, out, _ = call(site, "--config", cfg)
        self.assertEqual(code, 1)
        self.assertIn("high | broken_link | /index.html | link /blog/decison-logs.html | fix: ", out)
        self.assertIn("not run: No network", out)
        rep = json.loads(call(site, "--config", cfg, "--json")[1])
        order = [(-pd.SEV[f["severity"]], f["page"], f["check"], f["detail"]) for f in rep["findings"]]
        self.assertEqual(order, sorted(order))
        self.assertEqual(rep["findings"][0]["severity"], "high")

    def test_config_and_baseline_validation(self):
        site, cfg = self.site("clean")
        bad = [{"base_url": "ftp://x.example"}, {"base_url": "https://"}, {"base_url": "https://x.example",
               "redirects": {"old": "/new"}}, {"base_url": "https://x.example", "conversion": {"/p.html": "/g"}},
               {"base_url": "https://x.example", "entry_pages": "/index.html"}, ["https://x.example"]]
        for i, c in enumerate(bad):
            with self.subTest(config=c):
                p = os.path.join(self.tmp, "c%d.json" % i)
                with open(p, "w") as f:
                    json.dump(c, f)
                self.assertEqual(call(site, "--config", p)[0], 2)
        b = os.path.join(self.tmp, "b.json")
        for content in ('{"schema": "g34/0", "findings": []}', '{"schema": "g34/1", "findings": [{}]}', "\xff"):
            with self.subTest(baseline=content):
                with open(b, "w", encoding="latin-1") as f:
                    f.write(content)
                self.assertEqual(call(site, "--config", cfg, "--baseline", b)[0], 2)

    def test_checks_the_fixtures_do_not_reach_each_fire(self):
        site = os.path.join(self.tmp, "extra")
        os.makedirs(site)
        head = '<html lang="en"><head><meta name="viewport" content="x">'
        pages = {"index.html": head + '<title></title><meta name="description" content="short one"></head>'
                               '<body><h1>I</h1><a href="/a.html">A page</a></body></html>',
                 "a.html": head + '<title>One</title><title>Two</title><meta name="description" content="short one">'
                           '<link rel="canonical" href="https://t.example/old.html"></head><body><h1>A</h1>'
                           '<a href="/">Home page</a></body></html>'}
        for n, h in pages.items():
            with open(os.path.join(site, n), "w") as f:
                f.write(h)
        cfg = os.path.join(self.tmp, "extra.json")
        with open(cfg, "w") as f:
            json.dump({"base_url": "https://t.example", "redirects": {"/old.html": "/a.html"},
                       "conversion": {"/a.html": {"goal": "/gone.html"}}}, f)
        rep = json.loads(call(site, "--config", cfg, "--json", "--fail-on", "none")[1])
        got = {f["key"] for f in rep["findings"]}
        want = {"title_missing|/index.html|no non-empty <title>", "canonical_missing|/index.html|no canonical link",
                "description_length|/index.html|9 characters", "title_multiple|/a.html|2 titles",
                "canonical_target_missing|/a.html|canonical https://t.example/old.html",
                "description_duplicate|/a.html|shared with /index.html",
                "description_duplicate|/index.html|shared with /a.html",
                "conversion_goal_missing|/a.html|goal /gone.html", "sitemap_missing|/sitemap.xml|no sitemap.xml at "
                "the snapshot root"}
        self.assertEqual(want - got, set())
        with open(os.path.join(site, "sitemap.xml"), "w") as f:
            f.write("<urlset><url><loc>https://t.example/</loc></url>")
        rep2 = json.loads(call(site, "--config", cfg, "--json", "--fail-on", "none")[1])
        self.assertIn("sitemap_invalid|/sitemap.xml|sitemap.xml does not parse", {f["key"] for f in rep2["findings"]})
        covered = {k.split("|")[0] for k in want} | {"sitemap_invalid"}
        for n in ("before", "unseen"):
            with open(str(G / "fixtures" / n / "expected.json")) as f:
                covered |= {k.split("|")[0] for k in json.load(f)}
        self.assertEqual(set(pd.CHECKS) - covered, set())


class Resolution(unittest.TestCase):
    def test_internal_path_rules(self):
        cfg = {"host": "lantern.example", "redirects": {}}
        s = pd.Site(cfg, {"/index.html", "/docs/index.html", "/blog/a.html"})
        cases = {("/blog/a.html", "b.html"): "/blog/b.html", ("/blog/a.html", "../../../x.html"): "/x.html",
                 ("/blog/a.html", "//lantern.example/docs/"): "/docs/", ("/blog/a.html", "//other.example/"): None,
                 ("/blog/a.html", "https://LANTERN.example"): "/", ("/blog/a.html", "mailto:a@b.example"): None,
                 ("/blog/a.html", "#x"): "/blog/a.html", ("/blog/a.html", ""): None,
                 ("/blog/a.html", "/caf%C3%A9.html?x=1#y"): "/caf\u00e9.html"}
        for (page, href), want in cases.items():
            with self.subTest(href=href):
                self.assertEqual(s.internal_path(page, href), want)
        self.assertEqual(s.to_key("/"), "/index.html")
        self.assertEqual(s.to_key("/docs"), "/docs/index.html")
        self.assertIsNone(s.to_key("/Docs/"))

    def test_redirect_follow(self):
        s = pd.Site({"host": "h", "redirects": {"/a": "/b", "/b": "/c", "/x": "/y", "/y": "/x"}}, set())
        self.assertEqual(s.follow("/a"), ("/c", 2, False))
        self.assertTrue(s.follow("/x")[2])
        self.assertEqual(s.follow("/z"), ("/z", 0, False))


if __name__ == "__main__":
    unittest.main()
