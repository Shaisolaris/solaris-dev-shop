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

    def test_no_order_claim_can_go_and_bad_order_path_refused(self):
        self.rec()
        rc, out = self.claims({"schema": "solaris.delivery-claims/1", "contributions": [
            {"role": "data/data-engineer", "outputs": ["a.txt"]}]})
        self.assertEqual(rc, 0, out)
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


if __name__ == "__main__":
    unittest.main()
