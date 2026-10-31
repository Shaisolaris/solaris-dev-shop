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
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")


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

    def test_release_checks_and_review_bind_same_candidate(self):
        for field in ("candidate_commit", "checks_revision", "reviewed_revision"):
            for value in ("short", 7, "f" * 40):
                t = O.prog({"G05": "accepted"}, {"G05": O.sha("G05")}, {"G05": O.sha("G05")}, gate_fields=True)
                q = json.loads((t / "queue.json").read_text())
                q["release_gate"][field] = value
                (t / "queue.json").write_text(json.dumps(q))
                rc, rep, _ = O.inv(t)
                self.assertEqual((rc, O.state(rep)), (1, "NOT_READY"), (field, value, rep))
                self.assertTrue(any("revision" in r for r in rep["release_gate"]["reasons"]))
        # Same exact 40-hex root assertions remain a useful positive control.
        t = O.prog({"G05": "accepted"}, {"G05": O.sha("G05")}, {"G05": O.sha("G05")}, gate_fields=True)
        rc, rep, _ = O.inv(t)
        self.assertEqual((rc, O.state(rep)), (0, "READY"))

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


class Selection(unittest.TestCase):
    """M41 P3-1: a goal the queue does not select for the week does not block the gate."""
    def tearDown(self):
        O.cleanup()

    def _queue(self, t, sel):
        q = json.loads((t / "queue.json").read_text())
        for g in q["goals"]:
            if g["id"] in sel:
                g["selected_for_week"] = sel[g["id"]]
        (t / "queue.json").write_text(json.dumps(q))

    def test_unselected_goal_does_not_block_but_a_required_one_does(self):
        acc = {g: O.sha(g) for g in O.ALL}
        goals = dict(O.ALL, G26="held_environment_unverified")
        t = O.prog(goals, acc, dict(acc), gate_fields=True)
        rc, rep, _ = O.inv(t)
        self.assertEqual((rc, O.disp(rep, "G26")), (1, "missing"))  # selected by default: it blocks
        self._queue(t, {"G26": False})
        rc, rep, _ = O.inv(t)
        self.assertEqual((rc, O.state(rep), O.disp(rep, "G26"), rep["not_selected"]), (0, "READY", "not_selected", ["G26"]))
        self.assertNotIn("G26", rep["included_if_released"])
        self._queue(t, {"G26": False, "G41": False})  # a required final goal counts even when not selected
        acc.pop("G41")
        (t / "acc.json").write_text(json.dumps({"entries": [{"id": g, "commit": c} for g, c in acc.items()]}))
        rc, rep, _ = O.inv(t)
        self.assertEqual(rc, 1)
        self.assertIn("required final goal G41 is not accepted", rep["release_gate"]["reasons"])
        self._queue(t, {"G26": "no"})
        self.assertEqual(O.inv(t)[0], 2)


class RemoteHeads(unittest.TestCase):
    """M41 P3-2: a remote review branch that moved past the index makes the inventory say so."""
    def tearDown(self):
        O.cleanup()

    def _repo(self):
        import tempfile
        g = Path(tempfile.mkdtemp(prefix="g41t-git-"))
        O.MADE.append(g)
        run = lambda *a: subprocess.run(["git", "-C", str(g)] + list(a), capture_output=True, text=True, env=O.ENV,
                                        timeout=60).stdout.strip()
        run("init", "-q")
        c = {}
        for n in ("a", "b"):
            run("-c", "user.name=t", "-c", "user.email=t", "commit", "-q", "--allow-empty", "-m", n)
            c[n] = run("rev-parse", "HEAD")
        run("checkout", "-q", "--orphan", "other")
        run("-c", "user.name=t", "-c", "user.email=t", "commit", "-q", "--allow-empty", "-m", "z")
        c["z"] = run("rev-parse", "HEAD")
        return g, c

    def _prog(self, g, acc, cand):
        import shutil
        t = O.prog({g_: "accepted" for g_ in acc}, acc, cand, gate_fields=True)
        for f in ("pyproject.toml", "CHANGELOG.md", "control-plane", "employees"):
            shutil.move(str(t / "repo" / f), str(g / f))
        shutil.rmtree(t / "repo")
        os.symlink(str(g), str(t / "repo"))
        return t

    def test_newer_remote_head_makes_acceptance_stale(self):
        g, c = self._repo()
        t = self._prog(g, {"G19": c["a"], "G06": c["a"]}, {"G19": c["a"], "G06": c["a"]})
        rc, rep, _ = O.inv(t, "--git")
        self.assertEqual((rc, O.state(rep)), (0, "READY"))  # the index alone says everything is accepted
        (t / "heads.txt").write_text("%s\trefs/heads/review/grok-g19-api\n%s\trefs/heads/review/grok-g06-day1\n"
                                     "%s\trefs/heads/review/grok-m19-validation\n%s\tHEAD\n" % (c["b"], c["a"], c["z"], c["z"]))
        rc, rep, _ = O.inv(t, "--git", "--remote-heads", str(t / "heads.txt"))
        rows = {r["id"]: r for r in rep["goals"]}
        self.assertEqual((rc, O.state(rep)), (1, "NOT_READY"))
        self.assertEqual((rows["G19"]["disposition"], rows["G19"]["candidate_sha"]), ("acceptance_stale", c["b"]))
        self.assertEqual(rows["G19"]["newer_remote_heads"], [{"branch": "review/grok-g19-api", "sha": c["b"]}])
        self.assertEqual(rows["G06"]["disposition"], "accepted")  # head equals the accepted commit
        self.assertIn("G19 candidate index is stale: review/grok-g19-api is at %s" % c["b"][:12], rep["release_gate"]["reasons"])
        self.assertNotIn("G19", rep["included_if_released"])
        # an unrelated head (another history) is ignored; a head this clone does not hold blocks, named
        (t / "heads.txt").write_text("%s\trefs/heads/review/grok-g19-api\n%s\trefs/heads/review/grok-g06-x\n" % (c["z"], O.sha("gone")))
        rc, rep, _ = O.inv(t, "--git", "--remote-heads", str(t / "heads.txt"))
        rows = {r["id"]: r for r in rep["goals"]}
        self.assertEqual((rows["G19"]["disposition"], rows["G06"]["disposition"]), ("accepted", "accepted"))
        self.assertEqual(rc, 1)
        self.assertTrue(any(r.startswith("G06 remote head(s) not in this clone") for r in rep["release_gate"]["reasons"]))
        # --remote-heads needs --git; a malformed listing is refused
        self.assertEqual(O.inv(t, "--remote-heads", str(t / "heads.txt"))[0], 2)
        (t / "heads.txt").write_text("not a listing\n")
        self.assertEqual(O.inv(t, "--git", "--remote-heads", str(t / "heads.txt"))[0], 2)

if __name__ == "__main__":
    unittest.main()
