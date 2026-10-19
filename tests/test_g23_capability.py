"""G23 WordPress trace and config diagnosis (synthetic fixtures only; no WordPress is run)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "employees" / "specialized" / "wordpress-master" / "wp_trace_diag.py"
G23 = ROOT / "examples" / "capabilities" / "G23"
FIX = G23 / "fixtures"
sys.path.insert(0, str(TOOL.parent))
import wp_trace_diag as wd  # noqa: E402


def cli(*args, tool=TOOL):
    p = subprocess.run([sys.executable, str(tool)] + [str(a) for a in args], capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout, p.stderr


def diag(path, *extra):
    code, out, err = cli("diagnose", path, "--json", *extra)
    return code, (json.loads(out) if out.strip().startswith("{") else None), err


def codes(rep):
    return sorted(f["code"] for f in rep["findings"])


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


class Units(unittest.TestCase):
    def test_fingerprint_folds_literals_and_in_lists(self):
        a = wd.fingerprint("SELECT * FROM wp_postmeta WHERE post_id IN (1, 2, 3) AND meta_key = '_price'")
        b = wd.fingerprint("select *  from wp_postmeta where post_id in (9) and meta_key = 'x' /* qm */")
        self.assertEqual(a, b)
        self.assertNotEqual(wd.fingerprint("SELECT * FROM wp_2_posts"), wd.fingerprint("SELECT * FROM wp_3_posts"))

    def test_path_component(self):
        self.assertEqual(wd.path_component("/s/wp-content/plugins/Acme-Seo/x.php"), "plugin:acme-seo")
        self.assertEqual(wd.path_component("/s/wp-content/mu-plugins/guard.php"), "mu-plugin:guard")
        self.assertEqual(wd.path_component("/s/wp-content/themes/plain/f.php"), "theme:plain")
        self.assertEqual(wd.path_component("/s/wp-includes/load.php"), "core")
        self.assertEqual(wd.path_component("/elsewhere/x.php"), "unknown")

    def test_bisect_explain(self):
        r = lambda ps, res: {"plugins": ps, "result": res}
        self.assertEqual(wd.bisect_explain([r(["a", "b", "c"], "fail"), r(["a"], "ok"), r(["b", "c"], "ok"), r(["a", "b"], "fail")])[:2], ("pair", [("a", "b")]))
        self.assertEqual(wd.bisect_explain([r(["a", "b"], "fail"), r(["a"], "ok")])[:2], ("single", [("b",)]))
        self.assertEqual(wd.bisect_explain([r(["a"], "ok")])[0], "none")
        self.assertEqual(wd.bisect_explain([r(["a", "b"], "fail"), r(["a"], "ok"), r(["b"], "ok"), r(["a", "b"], "ok")])[0], "none")

    def test_size(self):
        self.assertEqual(wd._size("256M"), 256 * 1024 ** 2)
        self.assertEqual(wd._size("1G"), 1024 ** 3)
        self.assertIsNone(wd._size("lots"))
        self.assertIsNone(wd._size(True))


class Fixtures(unittest.TestCase):
    def test_clean_control(self):
        code, rep, _ = diag(FIX / "01-clean-control.json")
        self.assertEqual((code, rep["verdict"], rep["findings"]), (0, "healthy", []))
        self.assertIn("no PHP, WordPress, WP-CLI or database was run", rep["evidence_scope"])
        self.assertIn("synthetic fixture", rep["evidence_scope"])

    def test_plugin_conflict_one_finding_both_sources(self):
        code, rep, _ = diag(FIX / "02-plugin-conflict.json")
        self.assertEqual((code, codes(rep)), (1, ["PLUGIN_CONFLICT"]))
        f = rep["findings"][0]
        self.assertEqual(f["components"], ["plugin:acme-forms", "plugin:acme-seo"])
        self.assertIn("bisect runs agree", f["detail"])

    def test_slow_and_repeated_query_localized(self):
        code, rep, _ = diag(FIX / "03-slow-and-repeated-query.json")
        self.assertEqual(codes(rep), ["REPEATED_QUERY", "SLOW_QUERY"])
        self.assertTrue(all(f["components"] == ["plugin:shop-filters"] for f in rep["findings"]))
        code, rep, _ = diag(FIX / "03-slow-and-repeated-query.json", "--slow-ms", "1000", "--repeat", "50")
        self.assertEqual((code, rep["findings"]), (0, []))

    def test_config_faults(self):
        code, rep, _ = diag(FIX / "04-config-faults.json")
        self.assertEqual(codes(rep), ["CONFIG_AUTOLOAD_BLOAT", "CONFIG_CACHE_DROPIN_MISSING", "CONFIG_CRON_NOT_RUNNING", "CONFIG_DEBUG_DISPLAY"])

    def test_bisect_ambiguous_is_reported_without_a_culprit(self):
        code, rep, _ = diag(FIX / "08-bisect-ambiguous.json")
        self.assertEqual((code, codes(rep)), (1, ["PLUGIN_FAILURE_UNLOCALIZED"]))
        self.assertIn("4 plugin pairs", rep["findings"][0]["detail"])

    def test_fixtures_are_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(G23 / "make_fixtures.py"), d], check=True, capture_output=True)
            for f in sorted(FIX.glob("*.json")):
                self.assertEqual((Path(d) / f.name).read_bytes(), f.read_bytes(), f.name)


class Rules(unittest.TestCase):
    def run_bundle(self, b, *extra):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.json"
            p.write_text(json.dumps(b))
            return diag(p, *extra)

    def test_each_config_fault_alone_and_controls(self):
        cases = {
            "CONFIG_SAVEQUERIES": lambda b: b["wp_config"].update(SAVEQUERIES=True),
            "CONFIG_CACHE_DISABLED": lambda b: b["wp_config"].update(WP_CACHE=False),
            "CONFIG_MEMORY_LIMIT": lambda b: b["wp_config"].update(WP_MEMORY_LIMIT="72M"),
            "CONFIG_DEBUG_DISPLAY": lambda b: b["wp_config"].update(WP_DEBUG=True, WP_DEBUG_DISPLAY=True),
        }
        for want, inject in cases.items():
            b = load("01-clean-control")
            inject(b)
            with self.subTest(want=want):
                self.assertEqual(codes(self.run_bundle(b)[1]), [want])
        b = load("01-clean-control")
        b["environment"] = "staging"
        b["wp_config"].update(WP_DEBUG=True, WP_DEBUG_DISPLAY=True, SAVEQUERIES=True)
        self.assertEqual(self.run_bundle(b)[1]["findings"], [])
        b = load("01-clean-control")
        b["system_cron"] = None
        rep = self.run_bundle(b)[1]
        self.assertEqual(rep["findings"], [])
        self.assertTrue(any("cron not judged" in n for n in rep["notes"]))

    def test_error_log_forms(self):
        b = load("01-clean-control")
        b["php_errors"] = [
            "PHP Fatal error:  Uncaught Error: Call to undefined function shop_core_price() in /w/wp-content/plugins/shop-filters/w.php:20",
            "PHP Fatal error:  Allowed memory size of 268435456 bytes exhausted (tried to allocate 20480 bytes) in /w/wp-content/plugins/acme-seo/s.php on line 9",
            "PHP Fatal error:  Cannot redeclare function x() (previously declared in /w/wp-content/plugins/acme-forms/a.php:2) in /w/wp-content/plugins/acme-forms/b.php on line 4"]
        rep = self.run_bundle(b)[1]
        self.assertEqual(codes(rep), ["CONFIG_MEMORY_LIMIT", "PLUGIN_FATAL", "PLUGIN_FATAL"])
        mem = next(f for f in rep["findings"] if f["code"] == "CONFIG_MEMORY_LIMIT")
        # G23 r2 (M23 S1): the limit is the fault (core configuration); the allocating plugin is only where it ran out
        self.assertEqual((mem["severity"], mem["components"]), ("high", ["core"]))
        self.assertIn("last allocation was in plugin:acme-seo", mem["detail"])

    def test_slow_hook(self):
        b = load("01-clean-control")
        b["requests"][0]["hooks"].append({"hook": "init", "callback": "Sync::remote", "component": "plugin:acme-forms", "ms": 300})
        rep = self.run_bundle(b)[1]
        self.assertEqual([(f["code"], f["components"]) for f in rep["findings"]], [("SLOW_HOOK_CALLBACK", ["plugin:acme-forms"])])

    def test_secret_values_are_neither_stored_nor_checked(self):
        b = load("01-clean-control")
        b["wp_config"].update(DB_USER="synthetic-user", DB_HOST="db.internal", AUTH_KEY="k" * 400)
        code, rep, _ = self.run_bundle(b)
        self.assertEqual((code, rep["findings"]), (0, []))
        out = json.dumps(rep)
        for v in ("synthetic-user", "db.internal", "k" * 400):
            self.assertNotIn(v, out)
        note = next(n for n in rep["notes"] if "secret-like" in n)
        self.assertTrue(note.startswith(f"{sum(1 for k in b['wp_config'] if wd.SECRET_RE.search(k))} secret-like"))
        self.assertTrue(wd.SECRET_RE.search("DB_NAME") and wd.SECRET_RE.search("DB_USER"))

    def test_same_pair_twice_in_log_is_one_finding(self):
        line = ("PHP Fatal error:  Cannot redeclare acme_x() (previously declared in /w/wp-content/plugins/acme-seo/a.php:4) "
                "in /w/wp-content/plugins/acme-forms/b.php on line {n}")
        b = load("01-clean-control")
        b["php_errors"] = [line.format(n=7), line.format(n=9)]
        rep = self.run_bundle(b)[1]
        self.assertEqual(codes(rep), ["PLUGIN_CONFLICT"])
        self.assertEqual(len(rep["findings"][0]["evidence"]), 2)

    def _loop(self, n, callers):
        b = load("01-clean-control")
        b["requests"][0]["queries"] = [
            {"sql": f"SELECT meta_value FROM wp_postmeta WHERE post_id = {i}", "ms": 0.3, "caller": callers[i % len(callers)], "component": "core"}
            for i in range(n)]
        return codes(self.run_bundle(b)[1])

    def test_repeat_threshold_is_per_caller_and_inclusive(self):
        self.assertEqual(self._loop(10, ["A->loop"]), ["REPEATED_QUERY"])
        self.assertEqual(self._loop(9, ["A->loop"]), [])
        self.assertEqual(self._loop(18, ["A->a", "B->b", "C->c"]), [])

    def test_secrets_never_echoed(self):
        b = load("04-config-faults")
        for args in ((), ("--json",)):
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / "b.json"
                p.write_text(json.dumps(b))
                out = cli("diagnose", p, *args)[1]
                self.assertNotIn("synthetic-not-a-secret", out)
                self.assertNotIn("synthetic-not-a-key", out)


class Compare(unittest.TestCase):
    def test_same_measurements_claim(self):
        code, out, _ = cli("compare", FIX / "05-before.json", FIX / "06-after-same-measurements.json", "--json")
        rep = json.loads(out)
        self.assertEqual((code, rep["comparable"], rep["speedup_claimed"]), (0, True, True))
        before, after = load("05-before"), load("06-after-same-measurements")
        import statistics
        for u in rep["urls"]:
            self.assertAlmostEqual(u["median_before_ms"], statistics.median(r["total_ms"] for r in before["requests"] if r["url"] == u["url"]), places=3)
            self.assertAlmostEqual(u["median_after_ms"], statistics.median(r["total_ms"] for r in after["requests"] if r["url"] == u["url"]), places=3)

    def test_different_measurements_no_claim(self):
        code, out, _ = cli("compare", FIX / "05-before.json", FIX / "07-after-different-measurements.json", "--json")
        rep = json.loads(out)
        self.assertEqual((code, rep["comparable"], rep["speedup_claimed"]), (3, False, False))
        self.assertTrue(any("measurement differs" in w for w in rep["not_comparable_because"]))
        self.assertTrue(any("7 samples before, 5 after" in w for w in rep["not_comparable_because"]))

    def test_overlap_is_inconclusive_and_same_file_refused(self):
        a = load("05-before")
        b = json.loads(json.dumps(a))
        for r in b["requests"]:
            r["total_ms"] = round(r["total_ms"] * 0.8, 2)
        b["requests"][0]["total_ms"] = 5000.0
        with tempfile.TemporaryDirectory() as d:
            pa, pb = Path(d) / "a.json", Path(d) / "b.json"
            pa.write_text(json.dumps(a)); pb.write_text(json.dumps(b))
            rep = json.loads(cli("compare", pa, pb, "--json")[1])
            self.assertFalse(rep["speedup_claimed"])
            self.assertTrue(any(u["result"].startswith("inconclusive") for u in rep["urls"]))
            self.assertEqual(cli("compare", pa, pa)[0], 2)


class Invocation(unittest.TestCase):
    def test_invalid_inputs_exit_2_and_keep_report(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "r.json"
            self.assertEqual(cli("diagnose", FIX / "01-clean-control.json", "--out", out)[0], 0)
            first = out.read_bytes()
            good = load("01-clean-control")
            bads = {"json": "{", "dup": '{"schema":"a","schema":"b"}', "deep": "[" * 40000 + "]" * 40000}
            for field, val in (("colour", "x"), ("schema", "wp/2"), ("environment", "prod")):
                bads[field] = json.dumps(dict(good, **{field: val}))
            b = json.loads(json.dumps(good)); b["requests"][0]["total_ms"] = True; bads["bool"] = json.dumps(b)
            bads["dup-valid"] = '{"schema": "solaris.wp-trace/1", ' + json.dumps(good)[1:]
            b = json.loads(json.dumps(good)); b["requests"][1]["id"] = b["requests"][0]["id"]; bads["dupid"] = json.dumps(b)
            b = json.loads(json.dumps(good)); b["requests"][0]["queries"][0]["component"] = "plugin:Bad Name"; bads["comp"] = json.dumps(b)
            for name, text in bads.items():
                p = d / f"{name}.json"
                p.write_text(text)
                with self.subTest(name=name):
                    code, _, err = cli("diagnose", p, "--out", out)
                    self.assertEqual(code, 2)
                    self.assertNotIn("Traceback", err)
                    self.assertEqual(out.read_bytes(), first)
            os.symlink(FIX / "01-clean-control.json", d / "link.json")
            self.assertEqual(cli("diagnose", d / "link.json")[0], 2)
            cp = d / "copy.json"
            cp.write_bytes((FIX / "01-clean-control.json").read_bytes())
            self.assertEqual(cli("diagnose", cp, "--out", cp)[0], 2)
            self.assertEqual(cp.read_bytes(), (FIX / "01-clean-control.json").read_bytes())
            self.assertEqual(cli("diagnose", cp, "--repeat", "1")[0], 2)
            self.assertEqual(sorted(x.name for x in d.iterdir() if not x.name.endswith(".json") or x.name in ("r.json",)), ["r.json"])


class Oracle(unittest.TestCase):
    def score(self, tool):
        p = subprocess.run([sys.executable, str(G23 / "wp_oracle.py"), "--tool", f"{sys.executable} {tool}", "--json"],
                           capture_output=True, text=True, timeout=600)
        r = json.loads(p.stdout)
        return p.returncode, r["passed"], r["total"]

    def test_tool_passes_all(self):
        self.assertEqual(self.score(TOOL), (0, 12, 12))

    def test_stubs_fail(self):
        self.assertEqual(self.score(G23 / "noop_stub.py"), (1, 2, 12))
        self.assertEqual(self.score(G23 / "naive_stub.py"), (1, 1, 12))



MEM = ("[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Allowed memory size of 33554432 bytes exhausted (tried to allocate 20480 bytes) "
       "in /var/www/site/wp-content/plugins/media-tools/r.php on line 3")


class M23Rework(unittest.TestCase):
    """G23 r2 (M23 r1 Grok self-validation of d6be00e): memory blame (S1), source file and line (S2), the nine
    documented rules pinned (S3), --json with --out (S4), and the behaviours nobody pinned (S5)."""
    run_bundle = Rules.run_bundle

    def mem(self, cfg):
        b = load("01-clean-control")
        b["wp_config"].pop("WP_MEMORY_LIMIT", None)
        b["wp_config"].update(cfg)
        b["php_errors"] = [MEM]
        rep = self.run_bundle(b)[1]
        return next(f for f in rep["findings"] if f["code"] == "CONFIG_MEMORY_LIMIT")

    def test_s1_memory_exhaustion_is_the_limit_not_the_allocating_plugin(self):
        f = self.mem({"WP_MEMORY_LIMIT": "32M"})
        self.assertEqual(f["components"], ["core"])
        self.assertIn("that is the configured WP_MEMORY_LIMIT 32M", f["detail"])
        self.assertIn("WP_MEMORY_LIMIT=32M", f["evidence"])
        self.assertIn("plugin:media-tools, which shows where memory ran out, not what used it", f["detail"])
        f = self.mem({"WP_MEMORY_LIMIT": "256M"})  # N22: configured above the size PHP died at
        self.assertIn("WP_MEMORY_LIMIT is 256M (256 MiB) but PHP stopped at 32 MiB", f["detail"])
        self.assertIn("raise PHP memory_limit", f["fix"])
        self.assertIn("above WP_MEMORY_LIMIT 16M", self.mem({"WP_MEMORY_LIMIT": "16M"})["detail"])
        self.assertIn("not in the bundle", self.mem({})["detail"])
        self.assertIn("is not a size", self.mem({"WP_MEMORY_LIMIT": "lots"})["detail"])

    def test_s2_slow_log_file_and_line_are_kept(self):
        b = load("01-clean-control")
        # the faster run is seen first, so the slowest run's source must be tracked, not just the first one
        b["requests"][0]["queries"].append({"sql": "SELECT * FROM wp_postmeta WHERE meta_key = 'y'", "ms": 900.0,
                                            "source_file": "mysql-slow.log", "source_line": 88})
        b["requests"][1]["queries"].append({"sql": "SELECT * FROM wp_postmeta WHERE meta_key = 'x'", "ms": 3912.0,
                                            "source_file": "mysql-slow.log", "source_line": 1204})
        code, rep, _ = self.run_bundle(b)
        f = next(f for f in rep["findings"] if f["code"] == "SLOW_QUERY")
        self.assertEqual(f["components"], ["unknown"])
        self.assertEqual([e for e in f["evidence"] if e.startswith("source ")], ["source mysql-slow.log:1204", "source mysql-slow.log:88"])
        self.assertEqual(f["sources"], ["mysql-slow.log:88", "mysql-slow.log:1204"])
        self.assertIn("not tied to a plugin", f["detail"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.json"; p.write_text(json.dumps(b))
            self.assertIn("sources: mysql-slow.log:88, mysql-slow.log:1204", cli("diagnose", p)[1])
        code, out, _ = cli("diagnose", FIX / "03-slow-and-repeated-query.json", "--json")
        self.assertTrue(all("sources" not in f for f in json.loads(out)["findings"]))  # no source given: nothing invented
        for bad in ({"source_line": 3}, {"source_file": "s.log", "source_line": 0}, {"source_file": "a\nb"},
                    {"source_file": "s.log", "source_line": True}):
            b = load("01-clean-control")
            b["requests"][0]["queries"][0].update(bad)
            with self.subTest(bad=bad):
                self.assertEqual(self.run_bundle(b)[0], 2)

    def test_s3_documented_thresholds_and_rules(self):
        q = lambda ms: {"sql": "SELECT * FROM wp_posts WHERE post_status = 'publish'", "ms": ms, "caller": "q()", "component": "plugin:acme-seo"}
        h = lambda ms: {"hook": "init", "callback": "slow_cb", "component": "plugin:acme-seo", "ms": ms}
        for ms, want in ((50.0, True), (49.99, False)):
            b = load("01-clean-control"); b["requests"][0]["queries"].append(q(ms))
            with self.subTest(slow_ms=ms):
                self.assertEqual("SLOW_QUERY" in codes(self.run_bundle(b)[1]), want)
        for ms, want in ((100.0, True), (99.99, False)):
            b = load("01-clean-control"); b["requests"][0]["hooks"].append(h(ms))
            with self.subTest(hook_ms=ms):
                self.assertEqual("SLOW_HOOK_CALLBACK" in codes(self.run_bundle(b)[1]), want)
        for peak, want in ((230.4, True), (230.3, False)):   # 90% of 256M is 230.4 MiB
            b = load("01-clean-control"); b["wp_config"]["WP_MEMORY_LIMIT"] = "256M"
            for r in b["requests"]:
                r["peak_memory_mb"] = 40.0
            b["requests"][0]["peak_memory_mb"] = peak
            with self.subTest(peak=peak):
                self.assertEqual("CONFIG_MEMORY_LIMIT" in codes(self.run_bundle(b)[1]), want)
        for wp_cache, want in ((True, False), (False, True), ("true", True), (1, True), (None, True)):
            b = load("01-clean-control")
            if "advanced-cache.php" not in b["dropins"]:
                b["dropins"].append("advanced-cache.php")
            if wp_cache is None:
                b["wp_config"].pop("WP_CACHE", None)
            else:
                b["wp_config"]["WP_CACHE"] = wp_cache
            with self.subTest(wp_cache=wp_cache):
                self.assertEqual("CONFIG_CACHE_DISABLED" in codes(self.run_bundle(b)[1]), want)
        for size, want in ((800001, True), (800000, False)):
            b = load("01-clean-control"); b["autoload_bytes"] = size
            with self.subTest(autoload=size):
                self.assertEqual("CONFIG_AUTOLOAD_BLOAT" in codes(self.run_bundle(b)[1]), want)

    def _cmp(self, before, after):
        with tempfile.TemporaryDirectory() as d:
            pa, pb = Path(d) / "a.json", Path(d) / "b.json"
            pa.write_text(json.dumps(before)); pb.write_text(json.dumps(after))
            code, out, _ = cli("compare", pa, pb, "--json")
            return code, json.loads(out)

    def test_s3_compare_rules(self):
        base = load("05-before")
        def faster(b, k=0.5):
            b = json.loads(json.dumps(b))
            for r in b["requests"]:
                r["total_ms"] = round(r["total_ms"] * k, 3)
            return b
        self.assertEqual(self._cmp(base, faster(base))[0], 0)
        other = faster(base); other["site"] = "another-site"
        code, rep = self._cmp(base, other)
        self.assertEqual((code, rep["speedup_claimed"]), (3, False))
        self.assertTrue(any(w.startswith("site differs") for w in rep["not_comparable_because"]))
        # five samples per URL are enough; four are not
        def keep(b, n):
            b = json.loads(json.dumps(b)); seen = {}
            b["requests"] = [r for r in b["requests"] if seen.setdefault(r["url"], []).append(1) or len(seen[r["url"]]) <= n]
            return b
        self.assertEqual(self._cmp(keep(base, 5), faster(keep(base, 5)))[0], 0)
        code, rep = self._cmp(keep(base, 4), faster(keep(base, 4)))
        self.assertEqual(code, 3)
        self.assertTrue(any("at least 5 needed" in w for w in rep["not_comparable_because"]))
        # a tie between the slowest after-sample and the fastest before-sample is not "faster"
        tie = faster(base)
        u = tie["requests"][0]["url"]
        fastest_before = min(r["total_ms"] for r in base["requests"] if r["url"] == u)
        slowest = max((r for r in tie["requests"] if r["url"] == u), key=lambda r: r["total_ms"])
        slowest["total_ms"] = fastest_before
        code, rep = self._cmp(base, tie)
        self.assertEqual(code, 0)
        self.assertFalse(rep["speedup_claimed"])
        self.assertTrue(next(x for x in rep["urls"] if x["url"] == u)["result"].startswith("inconclusive"))

    def test_s3_s5_out_rules(self):
        good = FIX / "01-clean-control.json"
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertEqual(cli("diagnose", good, "--out", d / "missing" / "r.json")[0], 2)
            target = d / "elsewhere.json"
            target.write_text("keep")
            os.symlink(target, d / "link.json")
            self.assertEqual(cli("diagnose", good, "--out", d / "link.json")[0], 2)  # S5: a symlink is refused
            self.assertEqual(target.read_text(), "keep")
            (d / "dir.json").mkdir()
            self.assertEqual(cli("diagnose", good, "--out", d / "dir.json")[0], 2)

    def test_s4_json_with_out_prints_json(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            code, stdout, _ = cli("diagnose", FIX / "04-config-faults.json", "--json", "--out", out)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout), json.loads(out.read_text()))
            code, stdout, _ = cli("diagnose", FIX / "04-config-faults.json", "--out", out)  # --out alone: text summary
            self.assertTrue(stdout.startswith("verdict: faults_found"))
            code, stdout, _ = cli("compare", FIX / "05-before.json", FIX / "06-after-same-measurements.json", "--json", "--out", out)
            self.assertEqual((code, json.loads(stdout)), (0, json.loads(out.read_text())))

    def test_s5_unknown_component_and_declarer_outside_wp_content(self):
        b = load("01-clean-control")
        b["requests"][0]["queries"].append({"sql": "SELECT SLEEP(1)", "ms": 1000.0, "caller": "", "component": "unknown"})
        code, rep, _ = self.run_bundle(b)
        self.assertEqual((code, codes(rep)), (1, ["SLOW_QUERY"]))
        b = load("01-clean-control")
        b["php_errors"] = ["PHP Fatal error:  Cannot redeclare lib_fmt() (previously declared in /opt/lib/fmt.php:12) "
                           "in /var/www/site/wp-content/plugins/acme-forms/lib.php on line 30"]
        rep = self.run_bundle(b)[1]
        self.assertEqual(codes(rep), ["PLUGIN_FATAL"])
        self.assertEqual(rep["findings"][0]["components"], ["plugin:acme-forms"])
        self.assertIn("outside wp-content", rep["findings"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
