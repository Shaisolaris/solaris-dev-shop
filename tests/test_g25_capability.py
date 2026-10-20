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



def _ev(dev, seq, boot=1, **kw):
    return dict({"v": 1, "device": dev, "boot": boot, "seq": seq, "kind": "hello"}, **kw)


def _far_buffered(b):
    name, d = next((n, d) for n, d in b["devices"].items() if d["boot"] is not None)
    s = d["next"] + dp.WINDOW + 8
    d["buffer"] = {str(s): _ev(name, s, d["boot"])}


class M25Rework(unittest.TestCase):
    """G25 r2: regression tests for the M25 Grok self-validation findings S1 to S4 and its two survivors (on 822db7d)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g25r2-test-"))
        code, _, _ = cli("simulate", "--devices", 4, "--steps", 200, "--seed", 5, "--faults", HEAVY, "--record", self.tmp / "rec")
        self.assertEqual(code, 0)
        self.C, self.E = self.tmp / "rec" / "commands.jsonl", self.tmp / "rec" / "events.jsonl"

    def _state(self, cut=70):
        S = self.tmp / "s.json"
        if S.exists():
            S.unlink()
        self.assertEqual(cli("ingest", "--commands", self.C, "--events", self.E, "--state", S, "--crash-after", cut)[0], 3)
        return S, json.loads(S.read_text())

    def _resume(self, S, body):
        S.write_text(json.dumps(body, sort_keys=True) + "\n")
        return cli("ingest", "--commands", self.C, "--events", self.E, "--state", S, "--json")

    def test_s1_edited_or_damaged_checkpoint_exits_4(self):
        S, st = self._state()
        self.assertTrue(st["claims"], "the cut must fall after some claims")
        cases = {"claims removed": dict(st, claims=[]),
                 "one value edited": dict(st, counts=dict(st["counts"], applied=st["counts"]["applied"] + 1)),
                 "devices not records": dict(st, devices={"valve-000": 5})}
        for name, body in cases.items():
            with self.subTest(case=name):
                code, out, err = self._resume(S, body)
                self.assertEqual(code, 4, out)
                self.assertEqual(json.loads(out)["status"], "damaged_state")
                self.assertNotIn("Traceback", err)
        # a forger who recomputes the body hash still fails the structure checks
        for name, mutate in {"claim without an ack": lambda b: b["devices"][b["claims"][0]["device"]]["acked"].remove(b["claims"][0]["cmd"]),
                             "claim for an unlogged command": lambda b: b["claims"].append({"cmd": "c-fffff", "device": "valve-000", "action": "open"}),
                             "devices not records": lambda b: b.update(devices={"valve-000": 5}),
                             "claim with another action": lambda b: b["claims"][0].update(action="close" if b["claims"][0]["action"] == "open" else "open"),
                             "device record with an extra field": lambda b: next(iter(b["devices"].values())).update(owner="x"),
                             "buffered record beyond the window": _far_buffered}.items():
            with self.subTest(forged=name):
                b = json.loads(json.dumps(st))
                mutate(b)
                b["body_sha256"] = dp._body_sha(b)  # r3: the hash covers the whole checkpoint
                code, out, err = self._resume(S, b)
                self.assertEqual(code, 4, out)
                self.assertNotIn("Traceback", err)
        S.write_text("{not json")
        self.assertEqual(cli("ingest", "--commands", self.C, "--events", self.E, "--state", S)[0], 4)
        S, st = self._state()  # an untouched checkpoint still resumes to the unbroken report
        _, ref, _ = ingest(self.E, commands=self.C)
        code, got, _ = ingest(self.E, "--state", S, commands=self.C)
        self.assertEqual((claims(got), got["counts"]), (claims(ref), ref["counts"]))
        self.assertEqual(self._resume(S, dict(st, schema="solaris.device-protocol-state/1"))[0], 2)  # another tool version

    def test_s2_doc_commands_run_verbatim_in_a_fresh_folder(self):
        doc = (TOOL.parent / "device-event-protocol.md").read_text()
        block = doc.split("## Commands\n", 1)[1].split("\n\n", 1)[0]
        cmds = [c.split("#")[0].strip() for c in block.replace("\\\n", " ").splitlines() if c.strip()]
        fresh = self.tmp / "fresh"
        fresh.mkdir()
        (fresh / "device_protocol.py").write_bytes(TOOL.read_bytes())
        got = []
        for c in cmds:
            argv = c.split()
            self.assertEqual(argv[:2], ["python3", "device_protocol.py"])
            p = subprocess.run([sys.executable] + argv[1:], cwd=fresh, capture_output=True, text=True, timeout=300)
            got.append(p.returncode)
            self.assertNotIn("Traceback", p.stderr)
        self.assertEqual(got, [0, 1, 3, 1], cmds)
        self.assertEqual(cli("simulate", "--steps", 20, "--record", self.C)[0], 2)  # a file is not a folder

    def test_s3_window_holds_32_records_ahead_of_a_hole(self):
        for ahead, gaps in ((32, 0), (33, 1)):
            ctl = dp.Controller({})
            for sq in range(2, 2 + ahead):
                ctl.receive(json.dumps(_ev("d", sq)).encode(), sq)
            ctl.receive(json.dumps(_ev("d", 1)).encode(), 99)
            ctl.finish()
            with self.subTest(ahead=ahead):
                self.assertEqual(ctl.counts.get("gap", 0), gaps)
                self.assertEqual(ctl.devices["d"]["next"], 2 + ahead)

    def test_s4_trailing_newline_is_not_an_id(self):
        self.assertEqual(dp.check_event(_ev("v1\n", 1)), "bad_device")
        self.assertEqual(dp.check_event(_ev("v1", 1, kind="ack", cmd="c-1\n", result="done", state="open")), "bad_payload")
        C = self.tmp / "c.jsonl"
        C.write_text(json.dumps({"cmd": "c-1\n", "device": "v1", "action": "open"}) + "\n")
        E = self.tmp / "e.jsonl"
        E.write_text("")
        self.assertEqual(cli("ingest", "--commands", C, "--events", E)[0], 2)

    def test_rejected_then_done_ack_of_one_command_claims_nothing(self):
        cmds = {"c-1": {"cmd": "c-1", "device": "v1", "action": "open"}}
        ctl = dp.Controller(cmds)
        ctl.receive(json.dumps(_ev("v1", 1, kind="ack", cmd="c-1", result="rejected", state="closed")).encode(), 1)
        ctl.receive(json.dumps(_ev("v1", 2, kind="ack", cmd="c-1", result="done", state="open")).encode(), 2)
        self.assertEqual(ctl.claims, [])
        self.assertEqual(ctl.counts.get("duplicate_acks"), 1)



class M25R2Rework(unittest.TestCase):
    """G25 r3: regression tests for the M25 r2 Grok self-validation findings (on a902bc4): lines outside the hash (P3),
    non-object JSON (P4), --record under a file (P4) and the three guards no test reached (P4)."""
    setUp = M25Rework.setUp
    _state = M25Rework._state
    _resume = M25Rework._resume

    def _refused(self, S, body, want):
        before = json.dumps(body, sort_keys=True) + "\n"
        code, out, err = self._resume(S, body)
        self.assertEqual(code, 4, out)
        self.assertEqual(json.loads(out)["status"], "damaged_state")
        self.assertIn(want, json.loads(out)["error"])
        self.assertNotIn("Traceback", err)
        self.assertEqual(S.read_text(), before)  # nothing written

    def test_p3_cursor_edits_exit_4(self):
        S, st = self._state()
        for name, body in {"lines +1000": dict(st, lines=st["lines"] + 1000), "lines 0": dict(st, lines=0),
                           "offset +1": dict(st, offset=st["offset"] + 1),
                           "events_prefix_sha256": dict(st, events_prefix_sha256="0" * 64),
                           "tool_version": dict(st, tool_version="9.9.9")}.items():
            with self.subTest(edit=name):
                self._refused(S, body, "does not match body_sha256")
        # a forger who recomputes the hash still cannot move the line count away from the ingested bytes
        for n in (st["lines"] + 1000, 0, st["lines"] - 1):
            with self.subTest(forged_lines=n):
                b = dict(st, lines=n)
                b["body_sha256"] = dp._body_sha(b)
                self._refused(S, b, "lines does not match the events already ingested")
        S, st = self._state()  # untouched: resumes with the true line numbers
        code, got, _ = ingest(self.E, "--state", S, commands=self.C)
        _, ref, _ = ingest(self.E, commands=self.C)
        self.assertEqual((got["resumed_from_line"], got["inputs"]["event_lines"]), (st["lines"], ref["inputs"]["event_lines"]))
        self.assertEqual(got["anomalies"], ref["anomalies"])
        self.assertEqual(self._resume(S, dict(st, schema="solaris.device-protocol-state/2"))[0], 2)  # the r2 schema

    def test_p4_valid_json_that_is_not_an_object_exits_4(self):
        S, _ = self._state()
        for text in ("[]", "null", '"text"', "3", "true"):
            with self.subTest(text=text):
                S.write_text(text)
                code, out, err = cli("ingest", "--commands", self.C, "--events", self.E, "--state", S, "--json")
                self.assertEqual((code, json.loads(out)["status"]), (4, "damaged_state"), out)
                self.assertIn("not a checkpoint object", json.loads(out)["error"])
                self.assertNotIn("Traceback", err)
                self.assertEqual(S.read_text(), text)

    def test_p4_record_under_a_file_is_a_clean_error(self):
        afile = self.tmp / "afile"
        afile.write_text("x")
        for rec in (afile / "sub", afile / "sub" / "deeper"):
            with self.subTest(rec=rec.name):
                code, out, err = cli("simulate", "--steps", 20, "--record", rec)
                self.assertEqual(code, 2, out)
                self.assertIn("is not a folder", out)
                self.assertNotIn("Traceback", err)
        self.assertEqual(afile.read_text(), "x")
        real = self.tmp / "realdir"
        real.mkdir()
        link = self.tmp / "linkdir"
        link.symlink_to(real, target_is_directory=True)
        code, out, err = cli("simulate", "--steps", 20, "--record", link)  # a symlink, even to a folder, is refused
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", err)
        self.assertEqual(list(real.iterdir()), [])
        self.assertEqual(cli("simulate", "--steps", 20, "--record", self.tmp / "new" / "deep")[0], 0)  # a fresh path still works
        if not (hasattr(os, "geteuid") and os.geteuid() == 0):  # root can write a read-only folder
            ro = self.tmp / "ro"
            ro.mkdir()
            os.chmod(ro, 0o500)
            try:
                code, out, err = cli("simulate", "--steps", 20, "--record", ro / "sub")
            finally:
                os.chmod(ro, 0o700)
            self.assertEqual(code, 2, out)
            self.assertIn("cannot write", out)
            self.assertNotIn("Traceback", err)

    def test_p3_a_last_line_without_a_newline_still_resumes(self):
        E2 = self.tmp / "no-newline.jsonl"
        E2.write_bytes(self.E.read_bytes().rstrip(b"\n"))
        S = self.tmp / "eof.json"
        code1, first, _ = ingest(E2, "--state", S, commands=self.C)
        code2, again, err = ingest(E2, "--state", S, commands=self.C)  # resumes from the end-of-file checkpoint
        self.assertEqual((code2, again["resumed_from_line"]), (code1, first["inputs"]["event_lines"]), err)
        self.assertEqual(claims(again), claims(first))

    def test_p4_three_guards_behind_the_hash(self):
        S, st = self._state()
        self.assertTrue(st["claims"], "the cut must fall after some claims")
        other = next(c for c, v in json.loads(json.dumps({l["cmd"]: l for l in map(json.loads, self.C.read_text().splitlines())})).items()
                     if v["device"] != "valve-000")
        cases = {"fewer records applied than effects claimed": lambda b: b["counts"].update(applied=0),
                 "counts is not a map of non-negative integers": lambda b: b["counts"].update(applied=str(b["counts"]["applied"])),
                 "lists an ack that is not one of its commands": lambda b: b["devices"]["valve-000"]["acked"].append(other)}
        for want, mutate in cases.items():
            with self.subTest(guard=want):
                b = json.loads(json.dumps(st))
                mutate(b)
                b["body_sha256"] = dp._body_sha(b)
                self._refused(S, b, want)


if __name__ == "__main__":
    unittest.main()
