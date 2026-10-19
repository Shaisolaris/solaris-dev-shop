"""G41: release-candidate inventory and metadata reconciliation (release_candidate.py)."""
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "examples/capabilities/G41"
TOOL = ROOT / "employees/quality-security/assurance/release_candidate.py"
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


O = _load("g41_oracle_for_tests", X / "inventory_oracle.py")


def oracle(tool):
    p = subprocess.run([sys.executable, str(X / "inventory_oracle.py"), "--tool", str(tool)], capture_output=True,
                       text=True, env=ENV, timeout=600)
    return p.returncode, p.stdout


class OracleChecks(unittest.TestCase):
    def setUp(self):
        O.TOOL = TOOL

    def tearDown(self):
        O.cleanup()

    def _check(self, fn):
        ok, note = fn()
        self.assertTrue(ok, note)

    def test_o1(self): self._check(O.o1_clean_ready)
    def test_o2(self): self._check(O.o2_nothing_accepted)
    def test_o3(self): self._check(O.o3_acceptance_stale)
    def test_o4(self): self._check(O.o4_version_mismatch)
    def test_o5(self): self._check(O.o5_count_mismatch)
    def test_o6(self): self._check(O.o6_excluded_stays_out)
    def test_o7(self): self._check(O.o7_read_only_and_proposal)
    def test_o8(self): self._check(O.o8_gate_fields_unset)
    def test_o9(self): self._check(O.o9_conflict_and_invalid)
    def test_o10(self): self._check(O.o10_git_ancestry)


class Controls(unittest.TestCase):
    def test_naive_rejected(self):
        rc, out = oracle(X / "naive_inventory.py")
        self.assertEqual(rc, 1, out)
        self.assertIn("REJECTED 5/10", out)

    def test_noop_rejected(self):
        rc, out = oracle(X / "noop_inventory.py")
        self.assertEqual(rc, 1, out)
        self.assertIn("REJECTED 0/10", out)


class Direct(unittest.TestCase):
    def tearDown(self):
        O.cleanup()

    def test_external_pr_acceptance_counts_without_a_commit(self):
        t = O.prog({"P02": "accepted"}, {}, {}, gate_fields=True)
        (t / "acc.json").write_text(json.dumps({"entries": [{"id": "P02", "source_commit": None, "reply": "r"}]}))
        rc, rep, _ = O.inv(t)
        g = rep["goals"][0]
        self.assertEqual((rc, g["disposition"]), (0, "accepted"))
        self.assertIn("outside this repository", g["note"])

    def test_bad_external_commit_and_unknown_ids(self):
        t = O.prog({"G05": "accepted"}, {}, {"G05": O.sha("G05")}, gate_fields=True)
        (t / "acc.json").write_text(json.dumps({"entries": [{"id": "P01", "source_commit": "short"}]}))
        self.assertEqual(O.inv(t)[0], 2)
        (t / "acc.json").write_text(json.dumps({"entries": [{"id": "G99", "commit": O.sha(9)}]}))
        rc, rep, _ = O.inv(t)
        self.assertEqual(rep["unknown_ids"], ["G99"])

    def test_required_goal_outside_queue_is_invalid(self):
        t = O.prog({"G05": "accepted"}, {}, {}, gate_fields=True)
        q = json.loads((t / "queue.json").read_text())
        q["release_gate"]["required_final_goals"] = ["G41"]
        (t / "queue.json").write_text(json.dumps(q))
        self.assertEqual(O.inv(t)[0], 2)

    def test_text_output_and_out_file(self):
        t = O.prog({"G05": "accepted"}, {}, {"G05": O.sha("G05")})
        p = subprocess.run([sys.executable, str(TOOL), "inventory", str(t / "repo"), "--queue", str(t / "queue.json"),
                            "--acceptance", str(t / "acc.json"), "--candidates", str(t / "cand.json"), "--out",
                            str(t / "rep.json")], capture_output=True, text=True, env=ENV, timeout=60)
        self.assertEqual(p.returncode, 1)
        self.assertIn("release gate (computed): NOT_READY", p.stdout)
        self.assertIn("not applied", p.stdout)
        self.assertEqual(json.loads((t / "rep.json").read_text())["release_gate"]["state"], "NOT_READY")
        self.assertEqual([x.name for x in t.iterdir() if x.name.startswith(".rep.json")], [])
        p = subprocess.run([sys.executable, str(TOOL), "inventory", str(t / "repo"), "--queue", str(t / "queue.json"),
                            "--acceptance", str(t / "acc.json"), "--candidates", str(t / "cand.json"), "--out",
                            str(t / "no/dir/rep.json")], capture_output=True, text=True, env=ENV, timeout=60)
        self.assertEqual(p.returncode, 2)

    def test_proposal_none_for_unparseable_version(self):
        m = _load("g41_tool_for_tests", TOOL)
        self.assertEqual((m.propose("0.61"), m.propose("1.9.3"), m.propose("x")), ("0.62", "1.10", None))

    def test_this_checkout_metadata_agrees(self):
        m = _load("g41_tool_for_tests2", TOOL)
        self.assertEqual(m.metadata(ROOT)["problems"], [])


if __name__ == "__main__":
    unittest.main()
