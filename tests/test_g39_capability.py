"""G39: cross-employee delivery evidence and recovery drill (delivery_evidence.py)."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "examples/capabilities/G39"
TOOL = ROOT / "employees/product-project/delivery-lead/delivery_evidence.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(m)
    finally:
        sys.dont_write_bytecode = keep
    return m


O = _load("g39_oracle_for_tests", X / "drill_oracle.py")


def oracle(tool, only=None):
    args = [sys.executable, str(X / "drill_oracle.py"), "--tool", str(tool)] + (["--only", only] if only else [])
    p = subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=900)
    return p.returncode, p.stdout


class OracleChecks(unittest.TestCase):
    def setUp(self):
        O.TOOL = TOOL

    def tearDown(self):
        O.cleanup()

    def _check(self, fn):
        ok, note = fn()
        self.assertTrue(ok, note)

    def test_o1_clean(self): self._check(O.o1_clean)
    def test_o2_exit_truth(self): self._check(O.o2_exit_truth)
    def test_o3_unevidenced(self): self._check(O.o3_unevidenced)
    def test_o4_real_data_gaps(self): self._check(O.o4_real_data_gaps)
    def test_o5_stale_output(self): self._check(O.o5_stale_output)
    def test_o6_stale_tool(self): self._check(O.o6_stale_tool)
    def test_o7_tamper(self): self._check(O.o7_tamper)
    def test_o8_torn_tail(self): self._check(O.o8_torn_tail)
    def test_o9_killed_recorder(self): self._check(O.o9_killed_recorder)
    def test_o10_concurrent(self): self._check(O.o10_concurrent)
    def test_o11_invalid(self): self._check(O.o11_invalid)
    def test_o12_handoff_incomplete(self): self._check(O.o12_handoff_incomplete)
    def test_o13_symlink_output(self): self._check(O.o13_symlink_output)
    def test_o14_drill(self): self._check(O.o14_drill)
    def test_o15_upstream_inputs(self): self._check(O.o15_upstream_inputs)
    def test_o16_removed_output(self): self._check(O.o16_removed_output)
    def test_o17_unconfirmed_and_log(self): self._check(O.o17_unconfirmed_and_log)
    def test_o18_order_intake_ledger(self): self._check(O.o18_order_intake_ledger)


class Controls(unittest.TestCase):
    def test_naive_rejected_on_the_shortcuts(self):
        rc, out = oracle(X / "naive_evidence.py", "o5,o7,o8,o12")
        self.assertEqual(rc, 1, out)
        self.assertIn("REJECTED 0/4", out)

    def test_noop_rejected(self):
        rc, out = oracle(X / "noop_evidence.py", "o1,o2,o11")
        self.assertEqual(rc, 1, out)
        self.assertIn("REJECTED 0/3", out)


class Direct(unittest.TestCase):
    def setUp(self):
        self.parent = Path(tempfile.mkdtemp(prefix="g39t-"))
        self.root = self.parent / "delivery"
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def run_tool(self, *args):
        p = subprocess.run([sys.executable, str(TOOL)] + list(args), cwd=str(self.root), capture_output=True,
                           text=True, env=ENV, timeout=120)
        return p.returncode, p.stdout + p.stderr

    def rec(self, *extra, outputs=("a.txt",), cmd=None):
        cmd = cmd or [sys.executable, "-c", "open('a.txt','w').write('x')"]
        return self.run_tool("record", ".", "--role", "data/data-engineer", *extra, "--outputs", *outputs, "--", *cmd)

    def claims(self, body):
        (self.root / "c.json").write_text(json.dumps(body))
        return self.run_tool("verify", ".", "--claims", "c.json", "--json")

    def test_parseable_last_line_without_newline_is_refused(self):
        self.assertEqual(self.rec()[0], 0)
        p = self.root / ".delivery/contributions.jsonl"
        p.write_bytes(p.read_bytes().rstrip(b"\n"))
        self.assertEqual(self.rec()[0], 3)

    def test_parseable_last_line_without_newline_refused_even_with_head_on_previous(self):
        self.assertEqual(self.rec()[0], 0)
        h = self.root / ".delivery/head.json"
        first = h.read_text()
        self.assertEqual(self.rec()[0], 0)
        p = self.root / ".delivery/contributions.jsonl"
        p.write_bytes(p.read_bytes().rstrip(b"\n"))
        h.write_text(first)  # the head confirms record 0, so only the parseable-tail rule can refuse
        self.assertEqual(self.rec()[0], 3)

    def test_well_chained_record_with_wrong_seq_is_refused(self):
        self.assertEqual(self.rec()[0], 0)
        p = self.root / ".delivery/contributions.jsonl"
        r = json.loads(p.read_text())
        r["seq"] = 5
        line = json.dumps(r, sort_keys=True, separators=(",", ":"))
        p.write_text(line + "\n")
        # head rewritten to match, so only the sequence check can catch it
        (self.root / ".delivery/head.json").write_text(json.dumps(
            {"seq": 0, "sha256": hashlib.sha256(line.encode()).hexdigest()}, sort_keys=True))
        self.assertEqual(self.rec()[0], 3)

    def test_broken_ledger_refuses_before_running_the_command(self):
        self.rec()
        p = self.root / ".delivery/contributions.jsonl"
        p.write_text(p.read_text().replace('"exit":0', '"exit":9'))
        rc, _ = self.rec(cmd=[sys.executable, "-c", "open('ran.txt','w')"])
        self.assertEqual(rc, 3)
        self.assertFalse((self.root / "ran.txt").exists())
        (self.root / "c.json").write_text(json.dumps({"schema": "solaris.delivery-claims/1", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]}))
        rc, out = self.run_tool("verify", ".", "--claims", "c.json", "--json")
        c = json.loads(out)["contributions"][0]
        self.assertEqual((rc, c["state"]), (1, "unevidenced"))
        self.assertIn("ledger does not verify", c["action"])

    def test_two_deliveries_for_one_revision_is_no_go(self):
        for f in ("intake.json", "order.json"):
            shutil.copy2(X / "fixtures" / f, self.root / f)
        h = X.parents[2] / "employees/infrastructure/fleet-dispatcher/handoff.py"
        subprocess.run([sys.executable, str(h), "run", "order.json", "--worker", "ana"], cwd=str(self.root), env=ENV,
                       capture_output=True, timeout=120)
        led = self.root / "outbox/ledger.jsonl"
        line = led.read_text().splitlines()[0]
        with open(led, "a") as f:
            f.write(line + "\n")
        self.rec()
        rc, out = self.claims({"schema": "solaris.delivery-claims/1", "order": "order.json", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]})
        rep = json.loads(out)
        self.assertEqual((rc, rep["handoff"]["state"]), (1, "delivery_count_wrong"), out)

    def test_head_lagging_one_record_is_tolerated_but_not_two(self):
        self.rec()
        h = self.root / ".delivery/head.json"
        first = h.read_text()
        self.rec()
        h.write_text(first)  # as if the second append stopped before its head write
        self.assertEqual(self.rec()[0], 0)
        h.write_text(first)  # now two records behind
        self.assertEqual(self.rec()[0], 3)
        h.unlink()
        self.assertEqual(self.rec()[0], 3)

    def test_non_canonical_role_spelling_refused(self):
        for role in ("data/../data/data-engineer", "Data/data-engineer", "data/data-engineer/"):
            rc, _ = self.run_tool("record", ".", "--role", role, "--outputs", "a.txt", "--", sys.executable, "-c", "pass")
            self.assertEqual(rc, 2, role)

    def test_timeout_bounds_and_timeout_recorded(self):
        self.assertEqual(self.rec("--timeout", "0")[0], 2)
        self.assertEqual(self.rec("--timeout", "4000")[0], 2)
        rc, _ = self.rec("--timeout", "1", cmd=[sys.executable, "-c", "import time;open('a.txt','w');time.sleep(5)"])
        self.assertEqual(rc, 1)
        r = json.loads((self.root / ".delivery/contributions.jsonl").read_text().splitlines()[-1])
        self.assertIsNone(r["exit"])
        self.assertIn("timeout", r["reason"])

    def test_missing_command_and_bad_ok_exit(self):
        self.assertEqual(self.run_tool("record", ".", "--role", "data/data-engineer", "--outputs", "a.txt")[0], 2)
        self.assertEqual(self.rec("--ok-exit", "zero")[0], 2)
        self.assertFalse((self.root / ".delivery/contributions.jsonl").exists())

    def test_not_covered_when_claim_names_an_unrecorded_output(self):
        self.rec()
        (self.root / "b.txt").write_text("y")
        rc, out = self.claims({"schema": "solaris.delivery-claims/1", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt", "b.txt"]}]})
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(out)["contributions"][0]["state"], "not_covered")

    def test_no_order_claim_is_never_go_and_bad_order_path_refused(self):
        self.rec()
        rc, out = self.claims({"schema": "solaris.delivery-claims/1", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]})
        self.assertEqual((rc, json.loads(out)["verdict"]), (0, "EVIDENCED_NO_ORDER"), out)
        rc, out = self.run_tool("verify", ".", "--claims", "c.json")
        self.assertIn("not a delivery GO", out)
        shutil.copy2(X / "fixtures/order.json", self.parent / "order.json")
        rc, _ = self.claims({"schema": "solaris.delivery-claims/1", "order": "../order.json", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]})
        self.assertEqual(rc, 2)
        rc, _ = self.claims({"schema": "other", "contributions": []})
        self.assertEqual(rc, 2)

    def test_deleted_output_and_deleted_tool_are_stale(self):
        (self.root / "t.py").write_text("open('a.txt','w').write('x')\n")
        self.rec(cmd=[sys.executable, "t.py"])
        body = {"schema": "solaris.delivery-claims/1", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]}
        self.assertEqual(self.claims(body)[0], 0)
        (self.root / "t.py").unlink()
        rc, out = self.claims(body)
        self.assertEqual(json.loads(out)["contributions"][0]["state"], "stale")
        (self.root / "a.txt").unlink()
        rc, out = self.claims(body)
        self.assertEqual((rc, json.loads(out)["contributions"][0]["state"]), (1, "stale"))

    def test_lock_held_no_wait_exits_4(self):
        import fcntl
        self.rec()
        fd = os.open(str(self.root / ".delivery/ledger.lock"), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            self.assertEqual(self.rec("--no-wait")[0], 4)
        finally:
            os.close(fd)
        self.assertEqual(len((self.root / ".delivery/contributions.jsonl").read_text().splitlines()), 1)

    def test_verify_out_is_atomic_and_matches_stdout(self):
        self.rec()
        (self.root / "c.json").write_text(json.dumps({"schema": "solaris.delivery-claims/1", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]}))
        rc, out = self.run_tool("verify", ".", "--claims", "c.json", "--json", "--out", "v.json")
        self.assertEqual(json.loads(out), json.loads((self.root / "v.json").read_text()))
        self.assertEqual(sorted(p.name for p in self.root.iterdir() if "v.json" in p.name), ["v.json"])

    def test_engine_load_leaves_no_bytecode(self):
        prefix = self.root / "pycache-prefix"
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        env["PYTHONPYCACHEPREFIX"] = str(prefix)
        p = subprocess.run([sys.executable, str(TOOL), "record", ".", "--role", "data/data-engineer", "--outputs",
                            "a.txt", "--", sys.executable, "-c", "open('a.txt','w').write('x')"],
                           cwd=str(self.root), capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual([x.name for x in prefix.rglob("quality_os*.pyc")] if prefix.exists() else [], [])

    # ---- r2 (M39 P2-1, P2-2, P3-1, P3-2, P3-3, P4-2)
    def _body(self, **kw):
        return {"schema": "solaris.delivery-claims/1", "contributions": [dict({"role": "data/data-engineer",
                                                                              "outputs": ["a.txt"]}, **kw)]}

    def test_input_named_in_command_is_bound_without_flag(self):
        (self.root / "src.txt").write_text("v1")
        cmd = [sys.executable, "-c", "import sys;open('a.txt','w').write(open(sys.argv[1]).read())", "src.txt"]
        self.assertEqual(self.rec(cmd=cmd)[0], 0)
        r = json.loads((self.root / ".delivery/contributions.jsonl").read_text().splitlines()[-1])
        self.assertEqual(r["claimed_inputs"], ["src.txt"])
        self.assertEqual(self.claims(self._body())[0], 0)
        (self.root / "src.txt").write_text("v2")
        rc, out = self.claims(self._body())
        c = json.loads(out)["contributions"][0]
        self.assertEqual((rc, c["state"], c["inputs_changed"]), (1, "stale", ["src.txt"]))

    def test_bad_inputs_refused_before_running(self):
        self.assertEqual(self.rec()[0], 0)  # so .delivery/head.json exists and only the path rule refuses it
        for bad in ("../x", "/etc/hosts", ".delivery/head.json", "missing.txt"):
            rc, _ = self.rec("--inputs", bad, cmd=[sys.executable, "-c", "open('ran.txt','w')"])
            self.assertEqual(rc, 2, bad)
        self.assertFalse((self.root / "ran.txt").exists())

    def test_input_rewritten_by_the_run_is_noted_and_bound_after(self):
        (self.root / "state.txt").write_text("old")
        cmd = [sys.executable, "-c", "open('state.txt','w').write('new');open('a.txt','w').write('x')"]
        self.assertEqual(self.rec("--inputs", "state.txt", cmd=cmd)[0], 0)
        r = json.loads((self.root / ".delivery/contributions.jsonl").read_text().splitlines()[-1])
        self.assertEqual(r["inputs_changed_during_run"], ["state.txt"])
        # r5 (older M39 r2 P3-2): bound to the after-run bytes only, so it is a gap, never a clean contribution
        rc, out = self.claims(self._body())
        c = json.loads(out)["contributions"][0]
        self.assertEqual((rc, c["state"], c["gap_kinds"], c["inputs_rewritten_by_run"]),
                         (1, "evidenced_with_gaps", ["input_rewritten_by_run"], ["state.txt"]), out)
        self.assertIn("state.txt", c["action"])

    def test_ok_exit_only_0_or_0_1(self):
        for bad in ("0,2", "1", "0,1,2", "-1,0"):
            self.assertEqual(self.rec("--ok-exit", bad)[0], 2, bad)
        self.assertFalse((self.root / ".delivery/contributions.jsonl").exists())

    def test_exit_1_is_evidenced_with_gaps_and_needs_the_claim(self):
        cmd = [sys.executable, "-c", "import sys;open('a.txt','w').write('x');sys.exit(1)"]
        self.assertEqual(self.rec("--ok-exit", "0,1", cmd=cmd)[0], 0)
        rc, out = self.claims(self._body())
        rep = json.loads(out)
        self.assertEqual((rc, rep["verdict"], rep["contributions"][0]["state"]), (1, "NO_GO", "evidenced_with_gaps"))
        rc, out = self.claims(self._body(accept_gaps=True))
        self.assertEqual((rc, json.loads(out)["gaps"]), (0, ["data/data-engineer"]))
        rc, _ = self.claims(self._body(accept_gaps="yes"))
        self.assertEqual(rc, 2)

    def test_log_changed_or_removed_is_log_mismatch(self):
        self.rec()
        r = json.loads((self.root / ".delivery/contributions.jsonl").read_text())
        with open(self.root / r["log"], "a") as f:
            f.write("edited")
        rc, out = self.claims(self._body())
        self.assertEqual((rc, json.loads(out)["contributions"][0]["state"]), (1, "log_mismatch"))
        (self.root / r["log"]).unlink()
        rc, out = self.claims(self._body())
        self.assertEqual(json.loads(out)["contributions"][0]["state"], "log_mismatch")

    def test_emptied_or_deleted_ledger_with_head_is_broken(self):
        self.rec()
        p = self.root / ".delivery/contributions.jsonl"
        p.write_bytes(b"")
        self.assertEqual(self.rec()[0], 3)
        p.unlink()
        self.assertEqual(self.rec()[0], 3)
        rc, out = self.claims(self._body())
        self.assertEqual((rc, json.loads(out)["ledger"]["chain"]), (1, "broken"))


    # ---- r3 (M39 r2 P2-1 explicit inputs in four spellings, P3-1 exit 2 never counts whatever the record says)
    def _bound_then_stale(self, arg, change):
        cmd = [sys.executable, "-c", "open('a.txt','w').write('x')", arg]
        self.assertEqual(self.rec(cmd=cmd)[0], 0, arg)
        r = json.loads((self.root / ".delivery/contributions.jsonl").read_text().splitlines()[-1])
        self.assertEqual(self.claims(self._body())[0], 0, arg)
        change()
        rc, out = self.claims(self._body())
        c = json.loads(out)["contributions"][0]
        self.assertEqual((rc, c["state"]), (1, "stale"), (arg, r.get("claimed_inputs")))
        return r["claimed_inputs"]

    def test_flag_equals_value_input_is_bound(self):
        (self.root / "inp").mkdir()
        (self.root / "inp/a.csv").write_text("v1")
        got = self._bound_then_stale("--src=inp/a.csv", lambda: (self.root / "inp/a.csv").write_text("v2"))
        self.assertEqual(got, ["inp/a.csv"])

    def test_folder_named_in_command_is_bound(self):
        (self.root / "db").mkdir()
        (self.root / "db/t1.csv").write_text("v1")
        got = self._bound_then_stale("db", lambda: (self.root / "db/t1.csv").write_text("v2"))
        self.assertEqual(got, ["db"])

    def test_absolute_path_inside_root_is_bound_relative(self):
        (self.root / "b.csv").write_text("v1")
        got = self._bound_then_stale(str((self.root / "b.csv").resolve()), lambda: (self.root / "b.csv").write_text("v2"))
        self.assertEqual(got, ["b.csv"])

    def test_dotdot_spellings_inside_root_are_bound(self):
        # M39 r3 P3-1: inp/../inp/a.csv and ../delivery/inp/a.csv point inside ROOT and were silently unbound
        (self.root / "inp").mkdir()
        for k, arg in enumerate(("inp/../inp/a.csv", "../delivery/inp/a.csv")):
            (self.root / "inp/a.csv").write_text("v%d" % k)
            got = self._bound_then_stale(arg, lambda: (self.root / "inp/a.csv").write_text("changed%d" % k))
            self.assertEqual(got, ["inp/a.csv"], arg)
        (self.root / "real.csv").write_text("v1")
        os.symlink("real.csv", str(self.root / "inp/link.csv"))
        cmd = [sys.executable, "-c", "open('ran.txt','w')", "inp/../inp/link.csv"]
        self.assertEqual(self.rec(cmd=cmd)[0], 2)
        self.assertFalse((self.root / "ran.txt").exists())

    def test_input_outside_root_is_listed_unbound(self):
        # M39 r3 P3-2: an existing path outside ROOT was skipped without a note
        (self.parent / "outside.csv").write_text("v1")
        absout = str((self.parent / "outside.csv").resolve())
        cmd = [sys.executable, "-c", "open('a.txt','w').write('x')", absout, "../outside.csv", "../nothing-here.csv"]
        self.assertEqual(self.rec(cmd=cmd)[0], 0)
        r = json.loads((self.root / ".delivery/contributions.jsonl").read_text().splitlines()[-1])
        self.assertEqual((r["claimed_inputs"], r["unbound_inputs"]), ([], sorted([absout, "../outside.csv"])))
        rc, out = self.claims(self._body())
        c = json.loads(out)["contributions"][0]
        self.assertEqual((rc, c["unbound_inputs"]), (0, sorted([absout, "../outside.csv"])))
        self.assertIn("never re-checked", c["unbound_note"])

    def test_symlink_named_in_command_is_refused_before_running(self):
        (self.root / "real.csv").write_text("v1")
        os.symlink("real.csv", str(self.root / "link.csv"))
        cmd = [sys.executable, "-c", "open('ran.txt','w')", "link.csv"]
        self.assertEqual(self.rec(cmd=cmd)[0], 2)
        self.assertFalse((self.root / "ran.txt").exists())

    def test_rewritten_record_with_exit_2_is_never_go(self):
        self.assertEqual(self.rec()[0], 0)
        led = self.root / ".delivery/contributions.jsonl"
        recs = [json.loads(l) for l in led.read_text().splitlines()]
        recs[-1].update(exit=2, ok_exit=[0, 1, 2], ok=True)
        prev, out = "0" * 64, []
        for r in recs:  # a consistent full rewrite: re-chain every record and move the head with it
            line = json.dumps(dict(r, prev=prev), sort_keys=True, separators=(",", ":")).encode()
            out.append(line)
            prev = hashlib.sha256(line).hexdigest()
        led.write_bytes(b"\n".join(out) + b"\n")
        (self.root / ".delivery/head.json").write_text(json.dumps({"seq": len(out) - 1, "sha256": prev}))
        rc, txt = self.claims(self._body())
        rep = json.loads(txt)
        self.assertEqual(rep["ledger"]["chain"], "intact", txt)
        self.assertEqual((rc, rep["verdict"], rep["contributions"][0]["state"]), (1, "NO_GO", "failed"))


    # ---- r5 (older M39 r2 P3-2 and P3-3)
    def _delivered_order(self):
        for f in ("intake.json", "order.json"):
            shutil.copy2(X / "fixtures" / f, self.root / f)
        h = X.parents[2] / "employees/infrastructure/fleet-dispatcher/handoff.py"
        p = subprocess.run([sys.executable, str(h), "run", "order.json", "--worker", "ana"], cwd=str(self.root),
                           env=ENV, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_rewritten_input_with_order_is_go_with_gaps_never_go(self):
        self._delivered_order()
        (self.root / "state.txt").write_text("old")
        cmd = [sys.executable, "-c", "open('state.txt','w').write('new');open('a.txt','w').write('x')", "state.txt"]
        self.assertEqual(self.rec(cmd=cmd)[0], 0)
        body = dict(self._body(), order="order.json")
        rc, out = self.claims(body)
        rep = json.loads(out)
        self.assertEqual((rc, rep["verdict"], rep["clean_go"]), (1, "NO_GO", False), out)
        body = dict(self._body(accept_gaps=True), order="order.json")
        rc, out = self.claims(body)
        rep = json.loads(out)
        self.assertEqual((rc, rep["verdict"], rep["clean_go"], rep["gaps"], rep["gap_details"]),
                         (0, "GO_WITH_GAPS", False, ["data/data-engineer"],
                          {"data/data-engineer": ["input_rewritten_by_run"]}), out)
        rc, txt = self.run_tool("verify", ".", "--claims", "c.json")
        self.assertIn("GO_WITH_GAPS", txt)
        self.assertIn("rewrote its input state.txt", txt)
        # control: the same run without the rewrite is a clean GO
        cmd = [sys.executable, "-c", "open('a.txt','w').write(open('state.txt').read())", "state.txt"]
        self.assertEqual(self.rec(cmd=cmd)[0], 0)
        rc, out = self.claims(dict(self._body(), order="order.json"))
        rep = json.loads(out)
        self.assertEqual((rc, rep["verdict"], rep["clean_go"], rep["gaps"]), (0, "GO", True, []), out)

    def test_which_run_changes_are_rewrites(self):
        # a file read then changed or removed is a rewrite; a new file or a SQLite -shm index is not; -wal is
        (self.root / "db").mkdir()
        for f, t in (("t.db", "d"), ("t.db-shm", "i"), ("t.db-wal", "w"), ("gone.csv", "g")):
            (self.root / "db" / f).write_text(t)
        cases = (("open('db/t.db-shm','w').write('i2');open('db/new.csv','w').write('n')", []),
                 ("open('db/t.db-wal','w').write('w2')", ["db/t.db-wal"]),
                 ("import os;os.remove('db/gone.csv')", ["db/gone.csv"]))
        for code, want in cases:
            cmd = [sys.executable, "-c", code + ";open('a.txt','w').write('x')", "db"]
            self.assertEqual(self.rec(cmd=cmd)[0], 0, code)
            r = json.loads((self.root / ".delivery/contributions.jsonl").read_text().splitlines()[-1])
            self.assertEqual(r["inputs_rewritten_during_run"], want, (code, r["inputs_changed_during_run"]))
            rc, out = self.claims(self._body())
            c = json.loads(out)["contributions"][0]
            self.assertEqual((rc, c["state"]), (0, "evidenced") if not want else (1, "evidenced_with_gaps"), code)
        # a record written before r5 has no inputs_rewritten_during_run: every listed change counts
        led = self.root / ".delivery/contributions.jsonl"
        lines = led.read_text().splitlines()
        r = json.loads(lines[-1])
        del r["inputs_rewritten_during_run"]
        r["inputs_changed_during_run"] = ["db/new.csv"]
        line = json.dumps(r, sort_keys=True, separators=(",", ":"))
        led.write_text("\n".join(lines[:-1] + [line]) + "\n")
        (self.root / ".delivery/head.json").write_text(json.dumps(
            {"seq": r["seq"], "sha256": hashlib.sha256(line.encode()).hexdigest()}))
        rc, out = self.claims(self._body())
        c = json.loads(out)["contributions"][0]
        self.assertEqual((rc, c["state"], c["inputs_rewritten_by_run"]), (1, "evidenced_with_gaps", ["db/new.csv"]), out)

    def test_strict_exit_codes_tell_go_from_non_clean_verdicts(self):
        self._delivered_order()
        def strict():
            return self.run_tool("verify", ".", "--claims", "c.json", "--json", "--strict")
        self.assertEqual(self.rec()[0], 0)
        self.claims(dict(self._body(), order="order.json"))
        rc, out = strict()
        self.assertEqual((rc, json.loads(out)["verdict"], json.loads(out)["exit_policy"]), (0, "GO", "strict"), out)
        self.claims(self._body())
        rc, out = strict()
        self.assertEqual((rc, json.loads(out)["verdict"]), (4, "EVIDENCED_NO_ORDER"), out)
        self.assertEqual(self.claims(self._body())[0], 0)  # the default mapping is unchanged
        cmd = [sys.executable, "-c", "import sys;open('a.txt','w').write('x');sys.exit(1)"]
        self.assertEqual(self.rec("--ok-exit", "0,1", cmd=cmd)[0], 0)
        self.claims(dict(self._body(accept_gaps=True), order="order.json"))
        rc, out = strict()
        rep = json.loads(out)
        self.assertEqual((rc, rep["verdict"], rep["gap_details"]), (3, "GO_WITH_GAPS", {"data/data-engineer": ["exit_1"]}))
        self.assertEqual(self.claims(dict(self._body(accept_gaps=True), order="order.json"))[0], 0)
        self.claims(dict(self._body(), order="order.json"))
        self.assertEqual(strict()[0], 1)
        self.assertEqual(self.run_tool("verify", ".", "--claims", "missing.json", "--strict")[0], 2)


if __name__ == "__main__":
    unittest.main()
