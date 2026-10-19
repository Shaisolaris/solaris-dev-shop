#!/usr/bin/env python3
"""G25 oracle: black-box checks of a device-event protocol tool (simulator scope only).

Usage: protocol_oracle.py --tool "python3 path/to/device_protocol.py" [--seed N] [--scale-devices N] [--json]

The oracle writes its own synthetic command logs and event streams, runs the candidate's documented
CLI (ingest, simulate) and compares effect claims with what the streams allow. It never imports the
candidate. No hardware, serial port or network is used.
"""
from __future__ import annotations

import argparse
import json
import random
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HEAVY = "drop=0.2,dup=0.2,reorder=0.3,disconnect=0.05,reboot=0.02"


def run(tool, *args, timeout=600):
    p = subprocess.run(shlex.split(tool) + [str(x) for x in args], capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def ev(dev, boot, seq, kind, **kw):
    return dict(v=1, device=dev, boot=boot, seq=seq, kind=kind, **kw)


def ack(dev, boot, seq, cmd, state, result="done"):
    return ev(dev, boot, seq, "ack", cmd=cmd, result=result, state=state)


def write_lines(path, items):
    with open(path, "wb") as fh:
        for x in items:
            fh.write((x if isinstance(x, bytes) else json.dumps(x, sort_keys=True).encode()) + b"\n")


class World:
    """Two valves, four commands, each acknowledged once, in order."""
    CMDS = [{"cmd": "c-01", "device": "valve-a", "action": "open"}, {"cmd": "c-02", "device": "valve-b", "action": "open"},
            {"cmd": "c-03", "device": "valve-a", "action": "close"}, {"cmd": "c-04", "device": "valve-b", "action": "close"}]

    @staticmethod
    def stream():
        return [ev("valve-a", 1, 1, "hello"), ev("valve-b", 1, 1, "hello"),
                ev("valve-a", 1, 2, "state", state="closed"), ev("valve-b", 1, 2, "state", state="closed"),
                ack("valve-a", 1, 3, "c-01", "open"), ev("valve-a", 1, 4, "telemetry", flow_lpm=12.5),
                ack("valve-b", 1, 3, "c-02", "open"), ack("valve-a", 1, 5, "c-03", "closed"),
                ack("valve-b", 1, 4, "c-04", "closed"), ev("valve-b", 1, 5, "telemetry", flow_lpm=0)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True)
    ap.add_argument("--seed", type=int, default=2501)
    ap.add_argument("--scale-devices", type=int, default=200)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results, info = [], {}
    tmp = Path(tempfile.mkdtemp(prefix="g25-oracle-")).resolve()
    C = tmp / "commands.jsonl"
    write_lines(C, World.CMDS)

    def ingest(events, *extra, cmds=C):
        E = tmp / f"e{len(list(tmp.iterdir()))}.jsonl"
        write_lines(E, events)
        code, out, err = run(a.tool, "ingest", "--commands", cmds, "--events", E, "--json", *extra)
        try:
            rep = json.loads(out)
        except ValueError:
            rep = None
        return code, rep, err

    def claims(rep):
        return sorted(c.get("cmd") for c in (rep or {}).get("claims", []))

    def check(cid, title, fn):
        try:
            errs = fn()
        except Exception as exc:  # an oracle failure is a failed check, never a pass
            errs = [f"oracle error: {type(exc).__name__}: {exc}"]
        results.append({"id": cid, "title": title, "pass": not errs, "errors": errs[:6]})

    ALL = ["c-01", "c-02", "c-03", "c-04"]

    def o1():
        code, rep, err = ingest(World.stream())
        e = []
        if code != 0 or rep is None or rep.get("status") != "clean":
            e.append(f"clean stream: exit {code}, status {(rep or {}).get('status')}")
        if claims(rep) != ALL:
            e.append(f"clean stream: claims {claims(rep)}, expected {ALL}")
        if rep and any((rep.get("anomalies_found") or {}).values()):
            e.append(f"clean stream flagged anomalies {rep.get('anomalies_found')}")
        if rep and "not hardware" not in str(rep.get("claim_scope")):
            e.append("report does not state that claims are simulated, not hardware")
        if "Traceback" in err:
            e.append("traceback")
        return e
    check("o1", "clean control: in-order stream gives exactly the four claims, no anomalies, simulator scope stated", o1)

    def o2():
        rng = random.Random(a.seed)
        s = World.stream()
        noisy = [x for x in s for _ in range(3)]
        for i in range(len(noisy) - 1):  # local shuffles stay inside a small window
            if rng.random() < 0.5:
                noisy[i], noisy[i + 1] = noisy[i + 1], noisy[i]
        noisy += [ack("valve-a", 1, 6, "c-01", "open"), ack("valve-b", 1, 6, "c-02", "open")]  # retried commands re-acked
        code, rep, _ = ingest(noisy)
        e = []
        if claims(rep) != ALL:
            e.append(f"tripled, shuffled and re-acked stream: claims {claims(rep)}, expected each command once")
        if code != 0 or (rep or {}).get("status") != "clean":
            e.append(f"duplicates and local reordering are not anomalies: exit {code}, {(rep or {}).get('anomalies_found')}")
        return e
    check("o2", "duplicates, local reordering and re-acked retries never repeat a claim", o2)

    def o3():
        s = [ev("valve-a", 1, i, "telemetry", flow_lpm=1.0) for i in range(1, 60)]
        s[44] = ack("valve-a", 1, 45, "c-01", "open")
        del s[9]  # seq 10 never arrives
        code, rep, _ = ingest(s)
        e = []
        gaps = (rep or {}).get("anomalies_found", {}).get("gap", 0)
        if code != 1 or not gaps:
            e.append(f"a lost sequence number must be reported as a gap: exit {code}, gaps {gaps}")
        if claims(rep) != ["c-01"]:
            e.append(f"the ack after the gap must still be claimed once: {claims(rep)}")
        code, rep, _ = ingest([ev("valve-a", 1, 1, "hello"), ack("valve-a", 1, 3, "c-01", "open")])  # the hole is at the end
        if code != 1 or (rep or {}).get("anomalies_found", {}).get("gap") != 1 or claims(rep) != ["c-01"]:
            e.append(f"a hole before the last record: exit {code}, gaps {(rep or {}).get('anomalies_found', {}).get('gap')}, claims {claims(rep)}")
        for ahead, want in ((32, 0), (33, 1)):  # the documented window: seqs next+1 to next+32 wait for a hole
            s = [ev("valve-a", 1, i, "telemetry", flow_lpm=1.0) for i in range(2, 2 + ahead)] + [ev("valve-a", 1, 1, "hello")]
            code, rep, _ = ingest(s)
            got = (rep or {}).get("anomalies_found", {}).get("gap", 0)
            if got != want:
                e.append(f"{ahead} records ahead of a hole: {got} gaps, the documented 32-record window gives {want}")
        return e
    check("o3", "a missing sequence number, mid-stream or before the last record, is a reported gap; later events still apply once", o3)

    def o4():
        s = [ev("valve-a", 1, 1, "hello"), ev("valve-a", 2, 1, "hello"), ev("valve-a", 2, 2, "state", state="closed"),
             ack("valve-a", 1, 2, "c-01", "open"), ack("valve-a", 1, 3, "c-03", "closed")]
        code, rep, _ = ingest(s)
        e = []
        if claims(rep):
            e.append(f"acks from an earlier boot after a reboot were claimed: {claims(rep)}")
        if not (rep or {}).get("anomalies_found", {}).get("stale_boot_replay"):
            e.append("old-boot records not reported as replays")
        s2 = [ev("valve-a", 1, 1, "hello"), ack("valve-a", 1, 2, "c-01", "open"), ev("valve-a", 2, 1, "hello"),
              ack("valve-a", 2, 2, "c-01", "open")]  # the device re-sends an unconfirmed ack after rebooting
        code, rep, _ = ingest(s2)
        if claims(rep) != ["c-01"]:
            e.append(f"an ack re-sent after a reboot must count once: {claims(rep)}")
        return e
    check("o4", "records from an earlier boot are rejected replays; a re-sent ack after a reboot counts once", o4)

    def o5():
        s = [ev("valve-a", 1, 1, "hello"), ack("valve-a", 1, 2, "c-02", "open"),       # c-02 belongs to valve-b
             ack("valve-a", 1, 3, "c-99", "open"),                                     # never issued
             ack("valve-b", 1, 1, "c-02", "closed"),                                   # done but wrong state
             ack("valve-b", 1, 2, "c-04", "closed", result="rejected")]                # the device refused it
        code, rep, _ = ingest(s)
        e = []
        if claims(rep):
            e.append(f"misrouted, unknown, wrong-state or rejected acks were claimed: {claims(rep)}")
        f = (rep or {}).get("anomalies_found", {})
        if not f.get("unknown_command") or f.get("unknown_command", 0) < 2:
            e.append(f"misrouted and unknown commands not both reported: {f}")
        if not f.get("transition_mismatch"):
            e.append(f"done ack with the wrong resulting state not reported: {f}")
        if code != 1:
            e.append(f"exit {code}, expected 1")
        return e
    check("o5", "acks for another device, unknown or refused commands, or with the wrong resulting state make no claim", o5)

    def o6():
        good = World.stream()
        bad = [b"not json", b"{\"v\": 1", b"[" * 50000 + b"]" * 50000, b"x" * 100000, b"\xff\xfe{}",
               b'{"v":1,"device":"valve-a","boot":1,"seq":NaN,"kind":"hello"}',
               json.dumps(ev("valve-a", 1, True, "hello")).encode(), json.dumps(ev("valve-a", 1, 0, "hello")).encode(),
               json.dumps(ev("valve-a", -1, 7, "hello")).encode(), json.dumps(ev("Valve A", 1, 7, "hello")).encode(),
               json.dumps(ev("valve-a", 1, 7, "reboot_now")).encode(), json.dumps(dict(ev("valve-a", 1, 7, "hello"), extra=1)).encode(),
               b'{"v":1,"device":"valve-a","boot":1,"seq":7,"kind":"telemetry","flow_lpm":1e999}',
               b'{"v":1,"device":"valve-a","boot":1,"seq":7,"kind":"hello","seq":8}',
               json.dumps(ack("valve-a", 1, 7, "c-01; rm -rf /", "open")).encode(), b"[]", b"42"]
        mixed = []
        for i, g in enumerate(good):
            mixed.append(g)
            mixed.append(bad[i % len(bad)])
        mixed += bad
        code, rep, err = ingest(mixed)
        e = []
        if "Traceback" in err or rep is None:
            e.append(f"malformed lines crashed the tool: exit {code}")
            return e
        q = rep.get("anomalies_found", {}).get("quarantined", 0)
        if q != len(mixed) - len(good):
            e.append(f"quarantined {q} of {len(mixed) - len(good)} malformed lines")
        if claims(rep) != ALL:
            e.append(f"valid lines among malformed ones: claims {claims(rep)}")
        if code != 1:
            e.append(f"exit {code}, expected 1")
        if len(json.dumps(rep)) > 200000:
            e.append("report is not bounded (echoes malformed input)")
        return e
    def o6b():
        e = []
        code, rep, _ = ingest([ev("valve-a\n", 1, 1, "hello"), ev("valve-a", 1, 1, "hello")])
        if (rep or {}).get("anomalies_found", {}).get("quarantined", 0) < 1 and (rep or {}).get("anomalies_found", {}).get("bad_device", 0) < 1:
            e.append(f"a device id with a trailing newline was accepted: {(rep or {}).get('anomalies_found')}")
        C3 = tmp / "nl-commands.jsonl"
        write_lines(C3, [{"cmd": "c-01\n", "device": "valve-a", "action": "open"}])
        code, _, _ = ingest([ev("valve-a", 1, 1, "hello")], cmds=C3)
        if code != 2:
            e.append(f"a command id with a trailing newline in the log: exit {code}, expected 2")
        return e

    check("o6", "malformed, over-long, deeply nested and out-of-range lines are quarantined; valid lines still apply; report bounded; "
          "ids with a trailing newline are refused", lambda: o6() + o6b())

    def o7():
        s = [ev("valve-a", 1, 1, "hello"), ev("valve-a", 1, 2, "state", state="open"),  # opened with no command
             ev("valve-a", 1, 3, "state", state="fault"), ack("valve-a", 1, 4, "c-01", "fault")]
        code, rep, _ = ingest(s)
        e = []
        f = (rep or {}).get("anomalies_found", {})
        if not f.get("unexplained_transition"):
            e.append(f"a state change no command explains was not reported: {f}")
        if claims(rep):
            e.append(f"a state change or a fault ack produced a claim: {claims(rep)}")
        if ((rep or {}).get("devices") or {}).get("valve-a", {}).get("state") != "fault":
            e.append(f"device state should follow the device's report: {(rep or {}).get('devices')}")
        return e
    check("o7", "unexplained state changes are reported, never claimed; a fault ack is not a successful actuation", o7)

    def o8():
        e = []
        for seed in (a.seed, a.seed + 1, a.seed + 2):
            d = tmp / f"sim{seed}"
            d.mkdir()
            code, out, err = run(a.tool, "simulate", "--devices", 12, "--steps", 300, "--seed", seed, "--faults", HEAVY, "--record", d, "--json")
            try:
                rep = json.loads(out)
            except ValueError:
                e.append(f"seed {seed}: no JSON (exit {code})")
                continue
            sim = rep.get("simulation", {})
            if code != 0 or sim.get("claims_match_ground_truth") is not True or sim.get("ground_truth_double_actuations"):
                e.append(f"seed {seed}: exit {code}, {sim.get('verdict')}, doubles {sim.get('ground_truth_double_actuations')}")
            if rep.get("commands_unacknowledged"):
                e.append(f"seed {seed}: unacknowledged after settling: {len(rep['commands_unacknowledged'])}")
            lines = (d / "events.jsonl").read_bytes().splitlines() if (d / "events.jsonl").exists() else []
            keys = [(json.loads(l)["device"], json.loads(l)["boot"], json.loads(l)["seq"]) for l in lines]
            if len(keys) == len(set(keys)) or not rep.get("counts", {}).get("reboots"):
                e.append(f"seed {seed}: the recorded stream shows no duplicates or no reboots; faults were not applied")
            cmds = {json.loads(l)["cmd"]: json.loads(l) for l in (d / "commands.jsonl").read_bytes().splitlines()} if (d / "commands.jsonl").exists() else {}
            done = {}
            for l in lines:
                r = json.loads(l)
                if r["kind"] == "ack" and r["result"] == "done" and r["cmd"] in cmds and cmds[r["cmd"]]["device"] == r["device"]:
                    done[r["cmd"]] = True
            if claims(rep) != sorted(set(claims(rep))) or not set(claims(rep)) <= set(done):
                e.append(f"seed {seed}: a claim without a done ack from the right device, or a repeated claim")
            code2, out2, _ = run(a.tool, "ingest", "--commands", d / "commands.jsonl", "--events", d / "events.jsonl", "--json")
            try:
                if claims(json.loads(out2)) != claims(rep):
                    e.append(f"seed {seed}: replaying the recorded stream gives different claims")
            except ValueError:
                e.append(f"seed {seed}: ingest of the record gave no JSON (exit {code2})")
        return e
    check("o8", "simulated lossy link (drop, dup, reorder, disconnect, reboot): claims equal ground truth exactly once; replay agrees", o8)

    def o9():
        d = tmp / "crash"
        d.mkdir()
        run(a.tool, "simulate", "--devices", 6, "--steps", 300, "--seed", a.seed, "--faults", HEAVY, "--record", d, "--json")
        Cd, Ed = d / "commands.jsonl", d / "events.jsonl"
        code, out, _ = run(a.tool, "ingest", "--commands", Cd, "--events", Ed, "--json")
        ref = json.loads(out)
        e = []
        n = len(Ed.read_bytes().splitlines())
        for cut in (1, 49, 50, 51, n // 2, n - 1):
            S = d / f"state{cut}.json"
            code, out, err = run(a.tool, "ingest", "--commands", Cd, "--events", Ed, "--state", S, "--crash-after", cut)
            if code != 3 or "Traceback" in err:
                e.append(f"crash drill after {cut} lines: exit {code}")
                continue
            code, out, _ = run(a.tool, "ingest", "--commands", Cd, "--events", Ed, "--state", S, "--json")
            got = json.loads(out)
            if claims(got) != claims(ref) or got.get("counts") != ref.get("counts") or got.get("anomalies_found") != ref.get("anomalies_found"):
                e.append(f"resume after a crash at line {cut} differs from an unbroken run")
        S = d / "stateedit.json"
        run(a.tool, "ingest", "--commands", Cd, "--events", Ed, "--state", S, "--crash-after", n // 2)
        lines = Ed.read_bytes().splitlines()
        E2 = d / "edited.jsonl"
        E2.write_bytes(b"\n".join([lines[1], lines[0]] + lines[2:]) + b"\n")
        code, out, _ = run(a.tool, "ingest", "--commands", Cd, "--events", E2, "--state", S, "--json")
        if code != 2:
            e.append(f"resume onto an events file whose ingested part changed: exit {code}, expected 2")
        C2 = d / "other-commands.jsonl"
        C2.write_bytes(Cd.read_bytes() + b'{"action":"open","cmd":"c-ffffff","device":"valve-000"}\n')
        code, out, _ = run(a.tool, "ingest", "--commands", C2, "--events", Ed, "--state", S, "--json")
        if code != 2:
            e.append(f"resume with another command log: exit {code}, expected 2")
        body = json.loads(S.read_text())
        if body.get("claims"):
            S2 = d / "statedropped.json"
            S2.write_text(json.dumps(dict(body, claims=[])) + "\n")
            code, out, err = run(a.tool, "ingest", "--commands", Cd, "--events", Ed, "--state", S2, "--json")
            if code != 4 or "Traceback" in err:
                e.append(f"resume from a checkpoint with its claims deleted: exit {code}, expected 4 (damaged checkpoint)")
        else:
            e.append("the half-way checkpoint holds no claims, so the edit drill cannot run")
        # r3 (M25 r2): the line count is part of the checkpoint too, and JSON that is not an object is damaged
        for name, text in (("lines +1000", json.dumps(dict(body, lines=body.get("lines", 0) + 1000)) + "\n"), ("a JSON list", "[]\n")):
            S3 = d / "statecursor.json"
            S3.write_text(text)
            code, out, err = run(a.tool, "ingest", "--commands", Cd, "--events", Ed, "--state", S3, "--json")
            if code != 4 or "Traceback" in err or S3.read_text() != text:
                e.append(f"resume from a checkpoint with {name}: exit {code}, expected 4 with the file unchanged")
        return e
    check("o9", "crash drill at six points then resume equals an unbroken run; a changed input refuses to resume (2); "
          "an edited checkpoint (claims, line count) or a non-object one is refused (4)", o9)

    def o10():
        e = []
        bad_cmds = [[{"cmd": "c-01", "device": "valve-a", "action": "open"}, {"cmd": "c-01", "device": "valve-a", "action": "close"}],
                    [{"cmd": "c-01", "device": "valve-a", "action": "explode"}], [{"cmd": "c-01", "device": "valve-a"}]]
        for i, cs in enumerate(bad_cmds):
            p = tmp / f"badc{i}.jsonl"
            write_lines(p, cs)
            code, rep, err = ingest(World.stream(), cmds=p)
            if code != 2 or "Traceback" in err:
                e.append(f"bad command log {i}: exit {code}")
        E = tmp / "keep.jsonl"
        write_lines(E, World.stream())
        before = E.read_bytes()
        code, out, _ = run(a.tool, "ingest", "--commands", C, "--events", E, "--out", E)
        if code != 2 or E.read_bytes() != before:
            e.append(f"--out onto the events file: exit {code}, changed={E.read_bytes() != before}")
        code, out, _ = run(a.tool, "ingest", "--commands", C, "--events", tmp / "missing.jsonl")
        if code != 2:
            e.append(f"missing events file: exit {code}")
        for f in ("drop=2", "explode=0.1", "drop=x"):
            code, out, _ = run(a.tool, "simulate", "--faults", f)
            if code != 2:
                e.append(f"--faults {f}: exit {code}")
        return e
    check("o10", "invalid invocations (bad command log, output onto an input, missing file, bad faults) exit 2 and write nothing", o10)

    def o11():
        e = []
        t0 = time.time()
        outs = []
        for _ in range(2):
            code, out, _ = run(a.tool, "simulate", "--devices", a.scale_devices, "--steps", 300, "--seed", a.seed, "--faults", HEAVY, "--json")
            outs.append(out)
        dt = (time.time() - t0) / 2
        info["scale"] = {"devices": a.scale_devices, "steps": 300, "seconds_per_run": round(dt, 2)}
        try:
            rep = json.loads(outs[0])
            if rep.get("simulation", {}).get("claims_match_ground_truth") is not True:
                e.append("scale run: claims differ from ground truth")
            if len(rep.get("devices") or {}) != a.scale_devices or len(rep.get("claims") or []) < 50:
                e.append(f"scale run tracked {len(rep.get('devices') or {})} devices and {len(rep.get('claims') or [])} claims")
        except ValueError:
            e.append("scale run: no JSON")
        if outs[0] != outs[1]:
            e.append("the same seed gave different reports (not deterministic)")
        if dt > 120:
            e.append(f"scale run took {dt:.1f}s, budget 120s")
        return e
    check("o11", "scale: hundreds of devices under heavy faults, deterministic per seed, within budget", o11)

    def o12():
        e = []
        rng = random.Random(a.seed * 7 + 1)
        for trial in range(6):
            devs = [f"dev-{i}" for i in range(rng.randint(2, 6))]
            cmds, stream, want = [], [], set()
            boots = {d: rng.randint(0, 3) for d in devs}
            for d in devs:
                seq, state = 0, "closed"
                seq += 1
                stream.append(ev(d, boots[d], seq, "hello"))
                for _ in range(rng.randint(1, 8)):
                    c = f"c-{len(cmds) + 1:x}{trial}"
                    act = "open" if state == "closed" else "close"
                    cmds.append({"cmd": c, "device": d, "action": act})
                    state = "open" if act == "open" else "closed"
                    if rng.random() < 0.8:
                        seq += 1
                        stream.append(ack(d, boots[d], seq, c, state))
                        want.add(c)
                        if rng.random() < 0.3:
                            seq += 1
                            stream.append(ack(d, boots[d], seq, c, state))  # a retry re-acked
                    else:
                        state = "open" if state == "closed" else "closed"  # never executed
                        cmds[-1]["action"] = act
                        state = "closed" if act == "open" else "open"
            noisy = [x for x in stream for _ in range(rng.randint(1, 2))]
            for i in range(len(noisy) - 1):
                if rng.random() < 0.3:
                    noisy[i], noisy[i + 1] = noisy[i + 1], noisy[i]
            p = tmp / f"u{trial}.jsonl"
            write_lines(p, cmds)
            code, rep, _ = ingest(noisy, cmds=p)
            if claims(rep) != sorted(want):
                e.append(f"unseen trial {trial}: claims {len(claims(rep))}, expected {len(want)}")
        return e
    check("o12", "unseen generated streams (random devices, boots, retries, duplicates, local reordering) give exactly the expected claims", o12)

    passed = sum(r["pass"] for r in results)
    summary = {"tool": a.tool, "seed": a.seed, "passed": passed, "total": len(results), "checks": results, "info": info}
    if a.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for r in results:
            print(f"{'PASS' if r['pass'] else 'FAIL'} {r['id']} {r['title']}")
            for x in r["errors"]:
                print(f"     - {x}")
        for k, v in info.items():
            print(f"{k}: {v}")
        print(f"{passed}/{len(results)} checks passed")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
