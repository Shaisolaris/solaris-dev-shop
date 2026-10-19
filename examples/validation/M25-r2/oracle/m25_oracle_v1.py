#!/usr/bin/env python3
"""M25 oracle (Grok self-validation, not independent review). Written from device-event-protocol.md only,
before reading the builder's tests, oracle or fixtures. Each history carries a hand-derived expectation
(claims, final device state, anomaly classes, exit code). Core checks score; adversarial checks are findings.
Usage: PY m25_oracle.py ENGINE_PY [--python PY] [--json OUT] [--only IDS]"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

SCOPE = "simulated valve actuations from a synthetic event stream; not hardware evidence"
ap = argparse.ArgumentParser(); ap.add_argument("engine"); ap.add_argument("--python", default=sys.executable)
ap.add_argument("--json"); ap.add_argument("--only"); A = ap.parse_args()
ENG = str(Path(A.engine).resolve()); ONLY = set(A.only.split(",")) if A.only else None
TMP = Path(tempfile.mkdtemp(prefix="m25or-")).resolve()
RESULTS = []


def R(dev, boot, seq, kind, **kw):
    d = {"v": 1, "device": dev, "boot": boot, "seq": seq, "kind": kind}; d.update(kw); return json.dumps(d)


def ack(dev, boot, seq, cmd, state, result="done"):
    return R(dev, boot, seq, "ack", cmd=cmd, result=result, state=state)


def C(cmd, dev, action):
    return json.dumps({"cmd": cmd, "device": dev, "action": action})


def ingest(name, cmds, events, extra=(), raw_events=None, json_out=True):
    d = TMP / name; d.mkdir(parents=True, exist_ok=True)
    (d / "c.jsonl").write_text("".join(x + "\n" for x in cmds))
    if raw_events is not None:
        (d / "e.jsonl").write_bytes(raw_events)
    else:
        (d / "e.jsonl").write_text("".join(x + "\n" for x in events))
    args = [A.python, ENG, "ingest", "--commands", str(d / "c.jsonl"), "--events", str(d / "e.jsonl"), *extra]
    if json_out:
        args.append("--json")
    t = time.time()
    p = subprocess.run(args, capture_output=True, cwd=d, timeout=300,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(TMP), "PYTHONDONTWRITEBYTECODE": "1"})
    out = p.stdout.decode("utf-8", "replace"); err = p.stderr.decode("utf-8", "replace")
    try:
        rep = json.loads(out)
    except ValueError:
        rep = None
    return {"rc": p.returncode, "rep": rep, "out": out, "err": err, "dir": d, "secs": time.time() - t}


def claims(r):
    return sorted((c["cmd"], c["device"]) for c in (r["rep"] or {}).get("claims", []))


def af(r, k):
    return ((r["rep"] or {}).get("anomalies_found") or {}).get(k, 0)


def state(r, dev):
    return ((r["rep"] or {}).get("devices") or {}).get(dev, {}).get("state")


def check(cid, core, desc, fn):
    if ONLY and cid not in ONLY:
        return
    try:
        ok, obs = fn()
    except Exception as exc:  # harness or candidate failure: counts as not holding, reported
        ok, obs = False, f"oracle exception {type(exc).__name__}: {exc}"
    tb = False
    RESULTS.append({"id": cid, "core": core, "holds": bool(ok), "desc": desc, "observed": str(obs)[:400]})
    print(f"{cid} {'HOLDS' if ok else ('FAIL ' if core else 'GAP  ')} {desc}\n      observed: {str(obs)[:300]}")


V, W2 = "v1", "v2"
CL = [C("c-1", V, "open")]
BASE = [R(V, 1, 1, "hello"), R(V, 1, 2, "state", state="closed"), ack(V, 1, 3, "c-1", "open")]


def k01():
    r = ingest("k01", CL, BASE)
    return (r["rc"] == 0 and claims(r) == [("c-1", V)] and state(r, V) == "open"
            and r["rep"]["status"] == "clean" and r["rep"]["claim_scope"] == SCOPE), (r["rc"], claims(r), state(r, V))


def k02():  # reorder inside the buffer: same result as in order
    ev = [BASE[0], BASE[2], BASE[1], R(V, 1, 4, "telemetry", flow_lpm=1.5)]
    r = ingest("k02", CL, ev)
    return (r["rc"] == 0 and claims(r) == [("c-1", V)] and state(r, V) == "open" and af(r, "gap") == 0), (r["rc"], claims(r), state(r, V), r["rep"]["anomalies_found"])


def k03():  # exact duplicate record (same session+seq) is dropped, not an anomaly, never a second claim
    ev = BASE + [BASE[2], BASE[2], BASE[1]]
    r = ingest("k03", CL, ev)
    return (r["rc"] == 0 and claims(r) == [("c-1", V)] and r["rep"]["effects_claimed"] == 1), (r["rc"], claims(r), r["rep"]["counts"])


def k04():  # device re-acks the same command at a new seq: one claim only
    ev = BASE + [ack(V, 1, 4, "c-1", "open"), ack(V, 1, 5, "c-1", "open")]
    r = ingest("k04", CL, ev)
    return (claims(r) == [("c-1", V)] and r["rep"]["effects_claimed"] == 1 and r["rc"] in (0, 1)), (r["rc"], claims(r), r["rep"]["counts"])


def k05():  # reboot: hello, unconfirmed acks re-sent, then state; no second claim across sessions
    ev = BASE + [R(V, 2, 1, "hello"), ack(V, 2, 2, "c-1", "open"), R(V, 2, 3, "state", state="open")]
    r = ingest("k05", CL, ev)
    dv = r["rep"]["devices"][V]
    return (claims(r) == [("c-1", V)] and dv["boot"] == 2 and dv["state"] == "open" and af(r, "stale_boot_replay") == 0
            and af(r, "unexplained_transition") == 0), (r["rc"], claims(r), dv, r["rep"]["anomalies_found"])


def k06():  # lower-boot record after a new boot is a stale replay, never applied (its ack claims nothing)
    cl = CL + [C("c-2", V, "close")]
    ev = BASE + [R(V, 2, 1, "hello"), R(V, 2, 2, "state", state="open"), ack(V, 1, 4, "c-2", "closed"), R(V, 1, 5, "state", state="closed")]
    r = ingest("k06", cl, ev)
    return (r["rc"] == 1 and claims(r) == [("c-1", V)] and af(r, "stale_boot_replay") >= 1 and state(r, V) == "open"
            and "c-2" in json.dumps(r["rep"]["commands_unacknowledged"])), (r["rc"], claims(r), state(r, V), r["rep"]["anomalies_found"], r["rep"]["commands_unacknowledged"])


def k07():  # a hole at end of stream is a gap; claim before the hole stands
    ev = BASE + [R(V, 1, 5, "telemetry", flow_lpm=2.0)]
    r = ingest("k07", CL, ev)
    return (r["rc"] == 1 and af(r, "gap") >= 1 and claims(r) == [("c-1", V)]), (r["rc"], claims(r), r["rep"]["anomalies_found"])


def buf(n_ahead):
    ev = [R(V, 1, 1, "hello")] + [R(V, 1, s, "telemetry", flow_lpm=1.0) for s in range(3, 3 + n_ahead)] + [R(V, 1, 2, "state", state="closed")]
    return ev


def k08():  # 31 records ahead of a hole fit the 32 buffer under any reading: late seq 2 closes the hole, no gap
    # (v1 used 32 ahead; that boundary is ambiguous in the doc and moved to A13 after the first run, disclosed)
    r = ingest("k08", [], buf(31))
    return (r["rc"] == 0 and af(r, "gap") == 0 and r["rep"]["devices"][V]["last_seq"] == 33), (r["rc"], r["rep"]["anomalies_found"], r["rep"]["devices"])


def k09():  # 33 ahead overflows the 32 buffer: a gap is declared and the controller moves on
    r = ingest("k09", [], buf(33))
    return (r["rc"] == 1 and af(r, "gap") >= 1), (r["rc"], r["rep"]["anomalies_found"], r["rep"]["devices"])


def k10():  # ack for a command not in the log: unknown_command, no claim
    r = ingest("k10", CL, BASE[:2] + [ack(V, 1, 3, "c-9", "open")])
    return (r["rc"] == 1 and claims(r) == [] and af(r, "unknown_command") >= 1), (r["rc"], claims(r), r["rep"]["anomalies_found"])


def k11():  # ack from another device for v1's command: unknown_command, no claim for v2; v1's own ack claims
    ev = [R(W2, 1, 1, "hello"), ack(W2, 1, 2, "c-1", "open")] + BASE
    r = ingest("k11", CL, ev)
    return (r["rc"] == 1 and claims(r) == [("c-1", V)] and af(r, "unknown_command") >= 1), (r["rc"], claims(r), r["rep"]["anomalies_found"])


def k12():  # done ack with the wrong state: transition_mismatch, no claim
    r = ingest("k12", CL, BASE[:2] + [ack(V, 1, 3, "c-1", "closed")])
    return (r["rc"] == 1 and claims(r) == [] and af(r, "transition_mismatch") >= 1), (r["rc"], claims(r), r["rep"]["anomalies_found"])


def k13():  # rejected ack: counted, no claim
    r = ingest("k13", CL, BASE[:2] + [ack(V, 1, 3, "c-1", "closed", result="rejected")])
    return (claims(r) == [] and r["rep"]["effects_claimed"] == 0), (r["rc"], claims(r), r["rep"]["counts"], r["rep"]["anomalies_found"])


def k14():  # a state change no ack explains: unexplained_transition; state follows the device
    r = ingest("k14", [], [R(V, 1, 1, "hello"), R(V, 1, 2, "state", state="closed"), R(V, 1, 3, "state", state="open")])
    return (r["rc"] == 1 and af(r, "unexplained_transition") >= 1 and state(r, V) == "open"), (r["rc"], state(r, V), r["rep"]["anomalies_found"])


MARK = "ZZ-M25-SECRET-MARKER"


def bad_lines():
    deep = "{\"a\":" * 5000 + "1" + "}" * 5000
    return [b"not json " + MARK.encode(),
            json.dumps({"v": 1, "device": V, "boot": 1, "seq": 4, "kind": "hello", "note": MARK}).encode(),
            b'{"v":1,"device":"v1","boot":1,"seq":true,"kind":"hello"}',
            b'{"v":1,"device":"v1","boot":1,"seq":4,"kind":"telemetry","flow_lpm":NaN}',
            b'{"v":2,"device":"v1","boot":1,"seq":4,"kind":"hello"}',
            b'{"v":1,"device":"V1-' + MARK.encode() + b'","boot":1,"seq":4,"kind":"hello"}',
            b'{"v":1,"device":"v1","boot":1,"seq":0,"kind":"hello"}',
            b'{"v":1,"device":"v1","boot":2147483649,"seq":1,"kind":"hello"}',
            b'{"v":1,"device":"v1","device":"v2","boot":1,"seq":4,"kind":"hello"}',
            b'{"v":1,"device":"v1","boot":1,"seq":4,"kind":"hello","pad":"' + (MARK.encode() * 4000) + b'"}',
            deep.encode(),
            b'{"v":1,"device":"v1","boot":1,"seq":4,"kind":"hello","x":"\xff\xfe' + MARK.encode() + b'"}']


def k15():  # 12 malformed lines are quarantined, never echoed, and valid records around them still work
    raw = b"\n".join([BASE[0].encode(), BASE[1].encode()] + bad_lines() + [BASE[2].encode()]) + b"\n"
    r = ingest("k15", CL, None, raw_events=raw)
    return (r["rc"] == 1 and af(r, "quarantined") == 12 and claims(r) == [("c-1", V)] and MARK not in r["out"] + r["err"]
            and "Traceback" not in r["err"]), (r["rc"], af(r, "quarantined"), claims(r), MARK in r["out"] + r["err"], r["err"][-200:])


def k16():  # invalid command logs exit 2
    out = []
    for nm, cl in (("dup", [C("c-1", V, "open"), C("c-1", V, "close")]),
                   ("field", [json.dumps({"cmd": "c-1", "device": V, "action": "open", "x": 1})]),
                   ("action", [C("c-1", V, "toggle")])):
        out.append((nm, ingest("k16" + nm, cl, BASE)["rc"]))
    return all(rc == 2 for _, rc in out), out


def history(n_dev=4, rounds=40):
    """Interleaved multi-device history with reboots and re-acks; returns cmds, events, expected claims, final states."""
    cmds, ev, exp, st = [], [], set(), {}
    k = 0
    for d in range(n_dev):
        dev = f"valve-{d:03d}"; seq = 0; boot = 1; s = "closed"
        def emit(kind, **kw):
            nonlocal seq
            seq += 1; ev.append(R(dev, boot, seq, kind, **kw))
        emit("hello"); emit("state", state=s)
        for i in range(rounds):
            k += 1; cid = f"c-{k:x}"; tgt = "open" if s == "closed" else "closed"
            cmds.append(C(cid, dev, "open" if tgt == "open" else "close"))
            emit("telemetry", flow_lpm=float(i)); emit("ack", cmd=cid, result="done", state=tgt); s = tgt; exp.add((cid, dev))
            if i % 13 == 12:  # reboot and re-ack the last command
                boot += 1; seq = 0; emit("hello"); emit("ack", cmd=cid, result="done", state=tgt); emit("state", state=s)
        st[dev] = s
    return cmds, ev, sorted(exp), st


def interleave(ev):
    by = {}
    for line in ev:
        by.setdefault(json.loads(line)["device"], []).append(line)
    out, i = [], 0
    while any(by.values()):
        for d in sorted(by):
            if by[d]:
                out.append(by[d].pop(0))
    return out


def k17():  # interleaved multi-device history with reboots: exact claims and states
    cmds, ev, exp, st = history()
    r = ingest("k17", cmds, interleave(ev))
    got_st = {d: v["state"] for d, v in r["rep"]["devices"].items()}
    return (r["rc"] == 0 and claims(r) == exp and got_st == st), (r["rc"], len(claims(r)), len(exp), got_st == st, r["rep"]["anomalies_found"])


def k18():  # the same history with every record duplicated and adjacent pairs swapped: same claims and states
    cmds, ev, exp, st = history()
    ev = interleave(ev); mess = []
    for i in range(0, len(ev) - 1, 2):
        mess += [ev[i + 1], ev[i], ev[i]]
    if len(ev) % 2:
        mess.append(ev[-1])
    r = ingest("k18", cmds, mess)
    got_st = {d: v["state"] for d, v in r["rep"]["devices"].items()}
    return (claims(r) == exp and got_st == st and r["rep"]["effects_claimed"] == len(exp) and af(r, "gap") == 0), (r["rc"], len(claims(r)), len(exp), got_st == st, r["rep"]["anomalies_found"])


def strip(rep):
    rep = dict(rep); rep.pop("resumed_from_line", None); return rep


def k19():  # crash drill and resume give the same report as an unbroken run
    cmds, ev, exp, st = history(n_dev=3, rounds=30)
    ev = interleave(ev)
    full = ingest("k19full", cmds, ev)
    d = TMP / "k19"; stf = str(d / "st.json")
    a = ingest("k19", cmds, ev, extra=["--state", stf, "--crash-after", "120"])
    b = ingest("k19", cmds, ev, extra=["--state", stf])
    return (a["rc"] == 3 and b["rc"] == full["rc"] and b["rep"] and strip(b["rep"]) == strip(full["rep"])
            and b["rep"].get("resumed_from_line")), (a["rc"], b["rc"], full["rc"], b["rep"] and b["rep"].get("resumed_from_line"),
                                                     b["rep"] and strip(b["rep"]) == strip(full["rep"]))


def k20():  # resume onto a changed events prefix or changed command log is refused (exit 2)
    cmds, ev, exp, st = history(n_dev=2, rounds=30)
    ev = interleave(ev); d = TMP / "k20"
    stf = str(d / "st.json")
    a = ingest("k20", cmds, ev, extra=["--state", stf, "--crash-after", "70"])
    ev2 = list(ev); ev2[3] = ev2[3].replace('"flow_lpm": 1.0', '"flow_lpm": 9.0') if '"flow_lpm": 1.0' in ev2[3] else ev2[3]
    ev2[5] = R("valve-000", 1, 999, "hello")  # alter a line inside the read prefix
    b = ingest("k20", cmds, ev2, extra=["--state", stf])
    a2 = ingest("k20c", cmds, ev, extra=["--state", str(TMP / "k20c" / "st.json"), "--crash-after", "70"])
    c = ingest("k20c", cmds + [C("c-ffff", "valve-000", "open")], ev, extra=["--state", str(TMP / "k20c" / "st.json")])
    return (a["rc"] == 3 and b["rc"] == 2 and a2["rc"] == 3 and c["rc"] == 2), (a["rc"], b["rc"], a2["rc"], c["rc"])


def k21():  # an ack lost forever leaves the command unacknowledged, not claimed
    cl = CL + [C("c-2", V, "close")]
    r = ingest("k21", cl, BASE)
    return (claims(r) == [("c-1", V)] and "c-2" in json.dumps(r["rep"]["commands_unacknowledged"])), (r["rc"], claims(r), r["rep"]["commands_unacknowledged"])


def k22():  # simulate with faults matches ground truth; scope stated
    outs = []
    for seed in (1, 7, 42):
        d = TMP / f"k22-{seed}"; (d / "out").mkdir(parents=True)  # --record needs an existing folder (v1 omitted this)
        p = subprocess.run([A.python, ENG, "simulate", "--devices", "6", "--steps", "200", "--seed", str(seed), "--faults",
                            "drop=0.3,dup=0.3,reorder=0.4,disconnect=0.1,reboot=0.05", "--record", str(d / "out")],
                           capture_output=True, text=True, cwd=d, timeout=300, env={"PATH": "/usr/bin:/bin", "HOME": str(TMP)})
        outs.append((seed, p.returncode, SCOPE in p.stdout))
    return all(rc == 0 and sc for _, rc, sc in outs), outs


def k23():  # text output also states the simulator scope
    r = ingest("k23", CL, BASE, json_out=False)
    return (SCOPE in r["out"]), r["out"][:200]


CORE = [("K01", "clean control: one claim, state open, status clean, scope stated", k01),
        ("K02", "reorder inside the buffer gives the in-order result", k02),
        ("K03", "duplicate records are dropped, no second claim", k03),
        ("K04", "re-acks of one command at new seqs give one claim", k04),
        ("K05", "reboot and re-ack: one claim, new session, no anomaly", k05),
        ("K06", "lower-boot record is a stale replay and claims nothing", k06),
        ("K07", "hole at end of stream is a gap; earlier claim stands", k07),
        ("K08", "31 records ahead of a hole fit the buffer; no gap", k08),
        ("K09", "33 ahead overflow the buffer; gap declared", k09),
        ("K10", "ack for a command not in the log: unknown_command, no claim", k10),
        ("K11", "ack from another device: unknown_command; addressed device claims", k11),
        ("K12", "done ack with the wrong state: transition_mismatch, no claim", k12),
        ("K13", "rejected ack makes no claim", k13),
        ("K14", "unexplained state change flagged; state follows device", k14),
        ("K15", "12 malformed lines quarantined, never echoed, valid records still apply", k15),
        ("K16", "invalid command log exits 2 (dup id, unknown field, bad action)", k16),
        ("K17", "interleaved 4-device history with reboots: exact claims and states", k17),
        ("K18", "same history duplicated and swapped: exact claims and states, no gap", k18),
        ("K19", "crash drill exit 3, resume equals the unbroken report", k19),
        ("K20", "resume onto changed events or commands is refused (exit 2)", k20),
        ("K21", "lost ack: command unacknowledged, not claimed", k21),
        ("K22", "simulate with heavy faults matches ground truth (3 seeds)", k22),
        ("K23", "text report states the simulator scope", k23)]


# ---------------- adversarial (findings only) ----------------
def a01():  # seq as integral float
    r = ingest("a01", CL, [BASE[0], R(V, 1, 2.0, "state", state="closed"), BASE[2]])
    return (af(r, "quarantined") == 1), (r["rc"], af(r, "quarantined"), claims(r))


def a02():  # boundaries: boot 2^31 and seq 2^53 valid, 2^53+1 quarantined
    ev = [R(V, 2 ** 31, 2 ** 53, "hello"), R(W2, 1, 2 ** 53 + 1, "hello")]
    r = ingest("a02", [], ev)
    return (af(r, "quarantined") == 1 and (r["rep"]["devices"].get(V) or {}).get("boot") == 2 ** 31), (r["rc"], af(r, "quarantined"), r["rep"]["devices"])


def a03():  # 10001 distinct devices: the 10001st is quarantined, run bounded
    ev = [R(f"d{i}", 1, 1, "hello") for i in range(10001)]
    r = ingest("a03", [], ev)
    return (af(r, "quarantined") == 1 and len(r["rep"]["devices"]) == 10000 and r["secs"] < 60), (r["rc"], af(r, "quarantined"), len((r["rep"] or {}).get("devices", {})), round(r["secs"], 1))


def a04():  # an ack lost, then a reboot re-ack whose state is right: claimed once after the reboot
    ev = BASE[:2] + [R(V, 2, 1, "hello"), ack(V, 2, 2, "c-1", "open"), R(V, 2, 3, "state", state="open")]
    r = ingest("a04", CL, ev)
    return (claims(r) == [("c-1", V)] and af(r, "unexplained_transition") == 0), (r["rc"], claims(r), r["rep"]["anomalies_found"])


def a05():  # same seq reused within one boot with different content (device bug): no claim from the second copy
    cl = CL + [C("c-2", V, "close")]
    ev = BASE + [ack(V, 1, 3, "c-2", "closed")]
    r = ingest("a05", cl, ev)
    return (claims(r) == [("c-1", V)]), (r["rc"], claims(r), r["rep"]["counts"])


def a06():  # a tampered checkpoint (valid JSON, edited claims) is refused, not trusted
    cmds, ev, exp, st = history(n_dev=2, rounds=30); ev = interleave(ev)
    stf = TMP / "a06" / "st.json"
    ingest("a06", cmds, ev, extra=["--state", str(stf), "--crash-after", "70"])
    try:
        s = json.loads(stf.read_text())
    except Exception as exc:
        return False, f"no readable checkpoint: {exc}"
    txt = json.dumps(s)
    # add a fake claimed command id if the checkpoint keeps a claimed set; else flip a device state
    edited = txt.replace('"open"', '"fault"', 1) if '"open"' in txt else txt.replace('"closed"', '"fault"', 1)
    stf.write_text(edited)
    b = ingest("a06", cmds, ev, extra=["--state", str(stf)])
    full = ingest("a06full", cmds, ev)
    same = b["rep"] is not None and strip(b["rep"]) == strip(full["rep"])
    return (b["rc"] == 2 or same), (b["rc"], "same-as-unbroken" if same else "DIFFERENT report accepted", edited != txt)


def a13():  # "a buffer of 32": 32 records waiting ahead of a hole
    r = ingest("a13", [], buf(32))
    return (af(r, "gap") == 0), (r["rc"], af(r, "gap"), r["rep"]["devices"])


def a06b():  # checkpoint edited to drop its claims: resume must not silently report a different result
    cmds, ev, exp, st = history(n_dev=2, rounds=30); ev = interleave(ev)
    stf = TMP / "a06b" / "st.json"
    ingest("a06b", cmds, ev, extra=["--state", str(stf), "--crash-after", "70"])
    s = json.loads(stf.read_text()); n = len(s.get("claims", [])); s["claims"] = []
    stf.write_text(json.dumps(s, sort_keys=True))
    b = ingest("a06b", cmds, ev, extra=["--state", str(stf)])
    full = ingest("a06bfull", cmds, ev)
    same = b["rep"] is not None and strip(b["rep"]) == strip(full["rep"])
    return (b["rc"] == 2 or same), (b["rc"], f"claims removed {n}", "same" if same else f"DIFFERENT: claimed {b['rep'] and b['rep']['effects_claimed']} vs {full['rep']['effects_claimed']}")


def a14():  # structurally wrong checkpoint (valid JSON): refused with exit 2, no traceback
    cmds, ev, exp, st = history(n_dev=2, rounds=30); ev = interleave(ev)
    stf = TMP / "a14" / "st.json"
    ingest("a14", cmds, ev, extra=["--state", str(stf), "--crash-after", "70"])
    s = json.loads(stf.read_text()); s["devices"] = {"valve-000": 5}
    stf.write_text(json.dumps(s, sort_keys=True))
    b = ingest("a14", cmds, ev, extra=["--state", str(stf)])
    return (b["rc"] == 2 and "Traceback" not in b["err"]), (b["rc"], b["err"].strip().splitlines()[-1:] if b["err"] else "")


def a15():  # device "v1\n" breaks the documented ^...$ device pattern (Python $ also matches before a final newline)
    r = ingest("a15", [], [R(V, 1, 1, "hello"), R("v1\n", 1, 1, "hello")])
    return (af(r, "quarantined") == 1 and len(r["rep"]["devices"]) == 1), (r["rc"], af(r, "quarantined"), list(r["rep"]["devices"]))


def a16():  # command id "c-1\n" in the command log is invalid per the documented pattern (exit 2)
    r = ingest("a16", [C("c-1\n", V, "open")], BASE[:2])
    return (r["rc"] == 2), (r["rc"], r["err"].strip()[-120:])


def a07():  # 200k-line stream completes in bounded time
    cmds, ev, exp, st = history(n_dev=50, rounds=400)
    ev = interleave(ev)
    r = ingest("a07", cmds, ev)
    return (r["rc"] == 0 and claims(r) == exp and r["secs"] < 120), (len(ev), r["rc"], round(r["secs"], 1), claims(r) == exp)


def a08():  # done ack for another device's command, from that other device first, then a lower-boot replay of the right ack
    ev = [R(V, 2, 1, "hello"), R(V, 2, 2, "state", state="closed"), ack(V, 1, 3, "c-1", "open")]
    r = ingest("a08", CL, ev)
    return (claims(r) == [] and af(r, "stale_boot_replay") >= 1), (r["rc"], claims(r), r["rep"]["anomalies_found"])


def a09():  # anomaly list cap: 500 unknown-command acks, listed capped at 200, counts exact
    ev = [R(V, 1, 1, "hello")] + [ack(V, 1, s, f"c-{s:x}", "open") for s in range(2, 502)]
    r = ingest("a09", [], ev)
    return (af(r, "unknown_command") == 500 and len(r["rep"]["anomalies"]) <= 200), (r["rc"], af(r, "unknown_command"), len(r["rep"]["anomalies"]), r["rep"].get("anomalies_listed"))


def a10():  # an ack for the command is replayed after a later opposite command completed: no reclaim, state right
    cl = [C("c-1", V, "open"), C("c-2", V, "close")]
    ev = BASE + [ack(V, 1, 4, "c-2", "closed"), ack(V, 1, 5, "c-1", "open")]
    r = ingest("a10", cl, ev)
    return (claims(r) == [("c-1", V), ("c-2", V)] and r["rep"]["effects_claimed"] == 2), (r["rc"], claims(r), state(r, V), r["rep"]["anomalies_found"])


def a11():  # CRLF line endings and a blank line: valid records still parse
    raw = ("\r\n".join(BASE) + "\r\n\r\n").encode()
    r = ingest("a11", CL, None, raw_events=raw)
    return (claims(r) == [("c-1", V)]), (r["rc"], claims(r), af(r, "quarantined"))


def a12():  # flow_lpm as a huge exponent (inf) is quarantined
    r = ingest("a12", [], [R(V, 1, 1, "hello"), '{"v":1,"device":"v1","boot":1,"seq":2,"kind":"telemetry","flow_lpm":1e400}'])
    return (af(r, "quarantined") == 1), (r["rc"], af(r, "quarantined"))


ADV = [("A01", "seq 2.0 (integral float) is quarantined, not taken as an integer", a01),
       ("A02", "boot 2^31 and seq 2^53 accepted, seq 2^53+1 quarantined", a02),
       ("A03", "10001st distinct device quarantined, run under 60 s", a03),
       ("A04", "lost ack then reboot re-ack: one claim, no false unexplained transition", a04),
       ("A05", "reused seq with different content in one boot claims nothing new", a05),
       ("A06", "tampered checkpoint is refused or ignored, never trusted", a06),
       ("A07", "~200k-line stream: exact claims under 120 s", a07),
       ("A08", "stale-boot done ack after a newer boot claims nothing", a08),
       ("A09", "500 anomalies: count exact, list capped at 200", a09),
       ("A10", "late re-ack of an earlier command after a newer one completed: no reclaim", a10),
       ("A11", "CRLF and blank line tolerated", a11),
       ("A12", "flow_lpm 1e400 (infinite) is quarantined", a12),
       ("A13", "32 records ahead of a hole fit 'a buffer of 32' (boundary)", a13),
       ("A06b", "checkpoint with claims removed is refused or gives the unbroken report", a06b),
       ("A14", "structurally wrong checkpoint refused with exit 2, no traceback", a14),
       ("A15", "device id with a trailing newline is quarantined (documented pattern)", a15),
       ("A16", "command id with a trailing newline makes the command log invalid", a16)]

for cid, desc, fn in CORE:
    check(cid, True, desc, fn)
for cid, desc, fn in ADV:
    check(cid, False, desc, fn)
core = [r for r in RESULTS if r["core"]]; adv = [r for r in RESULTS if not r["core"]]
print(f"core: {sum(r['holds'] for r in core)} / {len(core)}  adversarial holding: {sum(r['holds'] for r in adv)} / {len(adv)}")
if A.json:
    Path(A.json).write_text(json.dumps({"engine": ENG, "python": A.python, "results": RESULTS}, indent=1))
shutil.rmtree(TMP, ignore_errors=True)
