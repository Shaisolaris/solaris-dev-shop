"""G25 device event protocol (simulator only): unit, CLI, oracle and stub checks."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "employees" / "engineering" / "iot-engineer" / "device_protocol.py"
G25 = ROOT / "examples" / "capabilities" / "G25"
FIX = G25 / "fixtures"
HEAVY = "drop=0.2,dup=0.2,reorder=0.3,disconnect=0.05,reboot=0.02"
sys.path.insert(0, str(TOOL.parent))
import device_protocol as dp  # noqa: E402


def cli(*args, tool=TOOL):
    p = subprocess.run([sys.executable, str(tool)] + [str(a) for a in args], capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout, p.stderr


def ingest(events, *extra, commands=FIX / "commands.jsonl"):
    code, out, err = cli("ingest", "--commands", commands, "--events", events, "--json", *extra)
    return code, (json.loads(out) if out.strip().startswith("{") else None), err


def claims(rep):
    return sorted(c["cmd"] for c in rep["claims"])


ALL = ["c-01", "c-02", "c-03", "c-04"]


class Parsing(unittest.TestCase):
    def test_parse_line_bounds(self):
        self.assertEqual(dp.parse_line(b"x" * (dp.MAX_LINE + 1)), (None, "too_long"))
        self.assertEqual(dp.parse_line(b"[" * 30000 + b"]" * 30000)[1], "too_deep")
        self.assertEqual(dp.parse_line(b'{"a":1,"a":2}')[1], "not_json")
        self.assertEqual(dp.parse_line(b'{"a":NaN}')[1], "not_json")
        self.assertEqual(dp.parse_line(b"\xff")[1], "not_json")
        self.assertEqual(dp.parse_line(b"[]")[1], "not_object")

    def test_check_event(self):
        good = {"v": 1, "device": "valve-a", "boot": 1, "seq": 1, "kind": "ack", "cmd": "c-1", "result": "done", "state": "open"}
        self.assertIsNone(dp.check_event(good))
        for change, why in [({"v": 2}, "bad_version"), ({"device": "Valve"}, "bad_device"), ({"boot": -1}, "bad_boot"),
                            ({"seq": True}, "bad_seq"), ({"seq": 0}, "bad_seq"), ({"seq": 2 ** 53 + 1}, "bad_seq"),
                            ({"kind": "reboot"}, "bad_kind"), ({"extra": 1}, "unknown_field"), ({"cmd": "c-1;x"}, "bad_payload"),
                            ({"result": "maybe"}, "bad_payload"), ({"state": "ajar"}, "bad_payload")]:
            self.assertEqual(dp.check_event(dict(good, **change)), why, change)
        tel = {"v": 1, "device": "d", "boot": 0, "seq": 1, "kind": "telemetry", "flow_lpm": float("inf")}
        self.assertEqual(dp.check_event(tel), "bad_payload")
        self.assertEqual(dp.check_event(dict(tel, flow_lpm=True)), "bad_payload")
        self.assertIsNone(dp.check_event(dict(tel, flow_lpm=3.5)))


class Bounds(unittest.TestCase):
    @staticmethod
    def line(dev, seq, boot=1):
        return json.dumps({"v": 1, "device": dev, "boot": boot, "seq": seq, "kind": "hello"}).encode()

    def test_reorder_buffer_is_bounded(self):
        ctl = dp.Controller({})
        for s in range(2, 500):  # seq 1 never arrives
            ctl.receive(self.line("d", s), s)
            self.assertLessEqual(len(ctl.devices["d"]["buffer"]), dp.WINDOW)
        self.assertGreaterEqual(ctl.counts.get("gap", 0), 1)
        ctl.finish()
        self.assertEqual(ctl.devices["d"]["next"], 500)

    def test_hole_at_end_of_input_is_a_gap(self):
        cmds = {"c-1": {"cmd": "c-1", "device": "d", "action": "open"}}
        ctl = dp.Controller(cmds)
        ack = {"v": 1, "device": "d", "boot": 1, "seq": 3, "kind": "ack", "cmd": "c-1", "result": "done", "state": "open"}
        for n, raw in enumerate([self.line("d", 1), json.dumps(ack).encode()], 1):
            ctl.receive(raw, n)
        self.assertEqual((ctl.claims, ctl.counts.get("gap", 0)), ([], 0))  # still waiting for seq 2
        ctl.finish()
        self.assertEqual(ctl.counts.get("gap"), 1)
        self.assertEqual([c["cmd"] for c in ctl.claims], ["c-1"])

    def test_device_resends_unconfirmed_acks_before_state(self):
        d = dp.SimDevice("d")
        d.reboot()
        d.on_command({"cmd": "c-1", "device": "d", "action": "open"})
        d.reboot()
        self.assertEqual([e["kind"] for _, e in sorted(d.outbox.items())], ["hello", "ack", "state"])
        d.on_command({"cmd": "c-1", "device": "d", "action": "open"})
        self.assertEqual(d.executed, ["c-1"])  # a retried command is re-acked, never re-executed

    def test_device_cap(self):
        old = dp.MAX_DEVICES
        dp.MAX_DEVICES = 3
        try:
            ctl = dp.Controller({})
            for i in range(6):
                ctl.receive(self.line(f"d{i}", 1), i + 1)
            self.assertEqual((len(ctl.devices), ctl.counts.get("quarantined")), (3, 3))
        finally:
            dp.MAX_DEVICES = old

    def test_anomaly_list_capped(self):
        ctl = dp.Controller({})
        for n in range(1, 1000):
            ctl.receive(b"junk", n)
        rep = ctl.report({})
        self.assertEqual((rep["anomalies_found"]["quarantined"], rep["anomalies_listed"]), (999, dp.MAX_LISTED))


class Fixtures(unittest.TestCase):
    def test_clean_control(self):
        code, rep, _ = ingest(FIX / "clean-events.jsonl")
        self.assertEqual((code, rep["status"], claims(rep)), (0, "clean", ALL))
        self.assertIn("not hardware evidence", rep["claim_scope"])

    def test_faulty_stream_claims_each_once(self):
        code, rep, _ = ingest(FIX / "faulty-events.jsonl")
        self.assertEqual((code, claims(rep)), (1, ALL))
        self.assertEqual(rep["anomalies_found"]["stale_boot_replay"], 1)
        self.assertEqual(rep["counts"]["duplicate_acks"], 2)
        self.assertEqual(rep["counts"]["reboots"], 1)

    def test_malformed_lines_quarantined(self):
        code, rep, _ = ingest(FIX / "malformed-events.jsonl")
        self.assertEqual((code, claims(rep), rep["anomalies_found"]["quarantined"]), (1, ALL, 9))
        self.assertNotIn("rm -rf", json.dumps(rep))
        self.assertLess(len(json.dumps(rep)), 20000)

    def test_unexplained_and_unknown(self):
        code, rep, _ = ingest(FIX / "unexplained-events.jsonl")
        self.assertEqual((code, claims(rep)), (1, []))
        f = rep["anomalies_found"]
        self.assertEqual((f["unexplained_transition"], f["unknown_command"]), (1, 2))
        self.assertEqual(len(rep["commands_unacknowledged"]), 4)


class Recovery(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g25-test-"))
        code, _, _ = cli("simulate", "--devices", 6, "--steps", 250, "--seed", 11, "--faults", HEAVY, "--record", self.tmp)
        self.assertEqual(code, 0)
        self.C, self.E = self.tmp / "commands.jsonl", self.tmp / "events.jsonl"

    def test_crash_and_resume_equal_unbroken(self):
        _, ref, _ = ingest(self.E, commands=self.C)
        for cut in (1, 50, 123):
            S = self.tmp / f"s{cut}.json"
            code, out, err = cli("ingest", "--commands", self.C, "--events", self.E, "--state", S, "--crash-after", cut)
            self.assertEqual(code, 3, err)
            self.assertTrue(S.exists())
            code, got, _ = ingest(self.E, "--state", S, commands=self.C)
            self.assertEqual((claims(got), got["counts"], got["anomalies_found"]), (claims(ref), ref["counts"], ref["anomalies_found"]))
            self.assertEqual(got["resumed_from_line"], ((cut - 1) // 50) * 50)  # the crash lands before that line's checkpoint

    def test_resume_refuses_changed_input(self):
        S = self.tmp / "s.json"
        cli("ingest", "--commands", self.C, "--events", self.E, "--state", S, "--crash-after", 120)
        lines = self.E.read_bytes().splitlines()
        E2 = self.tmp / "e2.jsonl"
        E2.write_bytes(b"\n".join([lines[1], lines[0]] + lines[2:]) + b"\n")
        self.assertEqual(cli("ingest", "--commands", self.C, "--events", E2, "--state", S)[0], 2)
        C2 = self.tmp / "c2.jsonl"
        C2.write_bytes(self.C.read_bytes() + b'{"action":"open","cmd":"c-fff","device":"valve-000"}\n')
        self.assertEqual(cli("ingest", "--commands", C2, "--events", self.E, "--state", S)[0], 2)

    def test_resume_after_long_line(self):
        E = self.tmp / "long.jsonl"
        E.write_bytes(b"x" * 200000 + b"\n" + (FIX / "clean-events.jsonl").read_bytes() * 10)
        S = self.tmp / "sl.json"
        self.assertEqual(cli("ingest", "--commands", FIX / "commands.jsonl", "--events", E, "--state", S, "--crash-after", 60)[0], 3)
        code, rep, err = ingest(E, "--state", S)
        self.assertEqual((code, claims(rep), rep["resumed_from_line"]), (1, ALL, 50), err)

    def test_simulation_matches_ground_truth(self):
        for seed in (1, 2):
            code, out, _ = cli("simulate", "--devices", 10, "--steps", 300, "--seed", seed, "--faults", HEAVY, "--json")
            rep = json.loads(out)
            self.assertEqual(code, 0)
            self.assertTrue(rep["simulation"]["claims_match_ground_truth"])
            self.assertGreater(rep["counts"]["reboots"], 0)
            self.assertGreater(rep["counts"]["duplicates_dropped"], 0)
        self.assertEqual(cli("simulate", "--seed", 3, "--json")[1], cli("simulate", "--seed", 3, "--json")[1])


class Invocation(unittest.TestCase):
    def test_invalid_exits_2_and_writes_nothing(self):
        tmp = Path(tempfile.mkdtemp(prefix="g25-inv-"))
        E = tmp / "e.jsonl"
        E.write_bytes((FIX / "clean-events.jsonl").read_bytes())
        before = E.read_bytes()
        self.assertEqual(cli("ingest", "--commands", FIX / "commands.jsonl", "--events", E, "--out", E)[0], 2)
        self.assertEqual(cli("ingest", "--commands", FIX / "commands.jsonl", "--events", E, "--state", E)[0], 2)
        self.assertEqual(E.read_bytes(), before)
        self.assertEqual(cli("ingest", "--commands", FIX / "commands.jsonl", "--events", tmp / "none")[0], 2)
        self.assertEqual(cli("ingest", "--commands", FIX / "commands.jsonl", "--events", E, "--crash-after", 5)[0], 2)
        bad = tmp / "c.jsonl"
        bad.write_text('{"cmd":"c-1","device":"a","action":"open"}\n{"cmd":"c-1","device":"a","action":"close"}\n')
        self.assertEqual(cli("ingest", "--commands", bad, "--events", E)[0], 2)
        for f in ("drop=2", "explode=0.1", "drop=x"):
            self.assertEqual(cli("simulate", "--faults", f)[0], 2)
        self.assertEqual(sorted(os.listdir(tmp)), ["c.jsonl", "e.jsonl"])

    def test_out_report_written(self):
        tmp = Path(tempfile.mkdtemp(prefix="g25-out-"))
        code, _, _ = cli("ingest", "--commands", FIX / "commands.jsonl", "--events", FIX / "clean-events.jsonl", "--out", tmp / "r.json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((tmp / "r.json").read_text())["schema"], dp.REPORT_SCHEMA)


class Oracle(unittest.TestCase):
    def score(self, tool):
        p = subprocess.run([sys.executable, str(G25 / "protocol_oracle.py"), "--tool", f"{sys.executable} {tool}", "--json"],
                           capture_output=True, text=True, timeout=600)
        r = json.loads(p.stdout)
        return p.returncode, r["passed"], r["total"]

    def test_tool_passes_all(self):
        self.assertEqual(self.score(TOOL), (0, 12, 12))

    def test_stubs_fail(self):
        self.assertEqual(self.score(G25 / "noop_stub.py"), (1, 0, 12))
        self.assertEqual(self.score(G25 / "naive_stub.py"), (1, 1, 12))


if __name__ == "__main__":
    unittest.main()
