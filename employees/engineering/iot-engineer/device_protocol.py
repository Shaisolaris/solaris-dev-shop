#!/usr/bin/env python3
"""Offline synthetic device-event protocol: a controller that turns an unreliable event stream into
exactly-once effect claims (G25).

Scope: SIMULATOR ONLY. Devices, links and valves here are synthetic Python objects. Nothing talks to
hardware, a serial port, a radio or a network, and no "effect" in a report is a physical event; it is
a simulated valve actuation (`claim_scope` in every report says so).

Commands
  ingest    --commands C.jsonl --events E.jsonl [--state S.json] [--crash-after N] [--json] [--out R.json]
            Replay a recorded event stream through the controller. Duplicates, out-of-order records,
            replays from an old boot, acks for unknown commands and malformed lines never create or
            repeat an effect claim. With --state the run checkpoints and a rerun resumes.
  simulate  --devices N --steps S --seed K [--faults drop=0.1,dup=0.1,reorder=0.2,disconnect=0.02,reboot=0.01]
            [--record DIR] [--json]
            Run synthetic devices over a lossy link and compare the controller's claims with the
            simulator's ground truth. --record writes commands.jsonl and events.jsonl as received.

Exit codes: 0 clean, 1 anomalies found (each is listed), 2 invalid invocation or input file,
3 crash drill (--crash-after) stopped the run; the checkpoint is kept, rerun to resume,
4 the --state checkpoint is damaged or edited (its body hash or structure does not check out).
Python 3.9+; standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOL_VERSION = "1.2.0"
REPORT_SCHEMA = "solaris.device-protocol-report/1"
STATE_SCHEMA = "solaris.device-protocol-state/3"   # /2 added body_sha256 (M25 S1); /3 hashes the whole checkpoint (M25 r2)
CLAIM_SCOPE = "simulated valve actuations from a synthetic event stream; not hardware evidence"
MAX_LINE = 64 * 1024            # longer lines are quarantined, never parsed
MAX_DEVICES = 10000
MAX_SEQ = 2 ** 53
MAX_BOOT = 2 ** 31
WINDOW = 32                     # reorder buffer per device: next+1 .. next+32 may wait (M25 S3); beyond it a gap
MAX_LISTED = 200                # anomaly details listed in a report (all are counted)
CHECKPOINT_EVERY = 50
DEVICE_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")   # used with fullmatch: "$" would accept a trailing newline (M25 S4)
CMD_RE = re.compile(r"c-[0-9a-f]{1,32}")
KINDS = ("hello", "telemetry", "state", "ack")
STATES = ("closed", "open", "fault")
ACTIONS = {"open": "open", "close": "closed"}
RESULTS = ("done", "rejected")


class Invalid(Exception):
    pass


class Crash(Exception):
    pass


class Damaged(Exception):
    """The --state checkpoint does not check out (exit 4)."""


# -- parsing ------------------------------------------------------------------------------

def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key {k!r}")
        out[k] = v
    return out


def _no_const(name):
    raise ValueError(f"{name} is not a number")


def parse_line(raw: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(record, None) or (None, reason). Never raises."""
    if len(raw) > MAX_LINE:
        return None, "too_long"
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_no_const)
    except RecursionError:
        return None, "too_deep"
    except (UnicodeDecodeError, ValueError):
        return None, "not_json"
    if not isinstance(obj, dict):
        return None, "not_object"
    return obj, None


def _int(v: Any, lo: int, hi: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def check_event(e: Dict[str, Any]) -> Optional[str]:
    """Why an event is malformed, or None. Bounded: only known fields are read."""
    if e.get("v") != 1:
        return "bad_version"
    if not isinstance(e.get("device"), str) or not DEVICE_RE.fullmatch(e["device"]):
        return "bad_device"
    if not _int(e.get("boot"), 0, MAX_BOOT):
        return "bad_boot"
    if not _int(e.get("seq"), 1, MAX_SEQ):
        return "bad_seq"
    k = e.get("kind")
    if k not in KINDS:
        return "bad_kind"
    allowed = {"v", "device", "boot", "seq", "kind"} | {
        "hello": set(), "telemetry": {"flow_lpm"}, "state": {"state"}, "ack": {"cmd", "result", "state"}}[k]
    if set(e) - allowed:
        return "unknown_field"
    if k == "telemetry":
        f = e.get("flow_lpm")
        if isinstance(f, bool) or not isinstance(f, (int, float)) or not math.isfinite(f) or not 0 <= f <= 1000:
            return "bad_payload"
    if k == "state" and e.get("state") not in STATES:
        return "bad_payload"
    if k == "ack":
        if not isinstance(e.get("cmd"), str) or not CMD_RE.fullmatch(e["cmd"]):
            return "bad_payload"
        if e.get("result") not in RESULTS or e.get("state") not in STATES:
            return "bad_payload"
    return None


def load_commands(path: Path) -> Dict[str, Dict[str, Any]]:
    """The controller's own command log. Unlike device events, a bad record here is an invalid input."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Invalid(f"commands: cannot read {path.name}: {exc.strerror}") from None
    cmds: Dict[str, Dict[str, Any]] = {}
    for n, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        c, why = parse_line(line)
        if c is None:
            raise Invalid(f"commands line {n}: {why}")
        if set(c) != {"cmd", "device", "action"} or not isinstance(c["cmd"], str) or not CMD_RE.fullmatch(c["cmd"]) \
                or not isinstance(c["device"], str) or not DEVICE_RE.fullmatch(c["device"]) or c["action"] not in ACTIONS:
            raise Invalid(f"commands line {n}: needs exactly cmd (c-<hex>), device and action (open or close)")
        if c["cmd"] in cmds:
            raise Invalid(f"commands line {n}: command {c['cmd']} issued twice")
        cmds[c["cmd"]] = c
    return cmds


# -- controller ---------------------------------------------------------------------------

def _dev_new() -> Dict[str, Any]:
    return {"boot": None, "next": 1, "buffer": {}, "state": "closed", "acked": []}


class Controller:
    """Per device: one session per boot, sequence numbers applied strictly in order through a bounded
    reorder buffer, and an effect claim only for the first successful ack of a command issued to it."""

    def __init__(self, commands: Dict[str, Dict[str, Any]], st: Optional[Dict[str, Any]] = None):
        self.commands = commands
        st = st or {}
        self.devices: Dict[str, Dict[str, Any]] = st.get("devices", {})
        for d in self.devices.values():
            d["buffer"] = {int(k): v for k, v in d["buffer"].items()}
        self.claims: List[Dict[str, Any]] = st.get("claims", [])
        self.claimed = {c["cmd"] for c in self.claims}
        self.counts: Dict[str, int] = st.get("counts", {})
        self.anomalies: List[Dict[str, Any]] = st.get("anomalies", [])

    def _note(self, kind: str, **detail: Any) -> None:
        self.counts[kind] = self.counts.get(kind, 0) + 1
        if len(self.anomalies) < MAX_LISTED:
            self.anomalies.append(dict(kind=kind, **detail))

    def _count(self, kind: str) -> None:
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def receive(self, raw: bytes, line_no: int) -> None:
        e, why = parse_line(raw)
        if e is None or (why := check_event(e)) is not None:
            self._note("quarantined", line=line_no, reason=why)
            return
        name = e["device"]
        d = self.devices.get(name)
        if d is None:
            if len(self.devices) >= MAX_DEVICES:
                self._note("quarantined", line=line_no, reason="too_many_devices")
                return
            d = self.devices[name] = _dev_new()
        if d["boot"] is None or e["boot"] > d["boot"]:
            if d["boot"] is not None:
                self._flush(name, d, reason="reboot")  # the old session ends; its holes are lost
                self._count("reboots")
            d["boot"], d["next"], d["buffer"] = e["boot"], 1, {}
        elif e["boot"] < d["boot"]:
            self._note("stale_boot_replay", line=line_no, device=name, boot=e["boot"], current_boot=d["boot"])
            return
        s = e["seq"]
        if s < d["next"] or s in d["buffer"]:
            self._count("duplicates_dropped")
            return
        if s > d["next"]:
            if s - d["next"] <= WINDOW and len(d["buffer"]) < WINDOW:
                d["buffer"][s] = e
                self._count("reordered_buffered")
                return
            d["buffer"][s] = e
            self._flush(name, d, reason="window")
            return
        self._apply(name, d, e)
        self._drain(name, d)

    def _drain(self, name: str, d: Dict[str, Any]) -> None:
        while d["next"] in d["buffer"]:
            self._apply(name, d, d["buffer"].pop(d["next"]))

    def _flush(self, name: str, d: Dict[str, Any], reason: str) -> None:
        """Declare the missing sequence numbers lost, then apply what is buffered in order."""
        while d["buffer"]:
            first = min(d["buffer"])
            if first > d["next"]:
                self._note("gap", device=name, boot=d["boot"], missing_from=d["next"], missing_to=first - 1, reason=reason)
                d["next"] = first
            self._drain(name, d)

    def _apply(self, name: str, d: Dict[str, Any], e: Dict[str, Any]) -> None:
        d["next"] = e["seq"] + 1
        self._count("applied")
        k = e["kind"]
        if k == "state":
            if e["state"] != d["state"]:
                # the device is the truth for its own state; a change no command explains is reported, never claimed
                self._note("unexplained_transition", device=name, boot=e["boot"], seq=e["seq"], **{"from": d["state"], "to": e["state"]})
                d["state"] = e["state"]
        elif k == "ack":
            c = self.commands.get(e["cmd"])
            if c is None or c["device"] != name:
                self._note("unknown_command", device=name, boot=e["boot"], seq=e["seq"], cmd=e["cmd"])
                return
            if e["cmd"] in self.claimed or e["cmd"] in d["acked"]:
                self._count("duplicate_acks")
                return
            d["acked"].append(e["cmd"])
            if e["result"] != "done":
                self._count("commands_rejected_by_device")
                d["state"] = e["state"]
                return
            want = ACTIONS[c["action"]]
            if e["state"] != want:
                self._note("transition_mismatch", device=name, cmd=e["cmd"], action=c["action"], reported=e["state"])
                d["state"] = e["state"]
                return
            if d["state"] == "fault":
                self._note("transition_mismatch", device=name, cmd=e["cmd"], action=c["action"], reported=e["state"], note="device was in fault")
            d["state"] = want
            self.claimed.add(e["cmd"])
            self.claims.append({"cmd": e["cmd"], "device": name, "action": c["action"]})

    def finish(self) -> None:
        for name, d in sorted(self.devices.items()):
            self._flush(name, d, reason="end_of_input")

    def snapshot(self) -> Dict[str, Any]:
        devs = {n: dict(d, buffer={str(k): v for k, v in sorted(d["buffer"].items())}) for n, d in sorted(self.devices.items())}
        return {"devices": devs, "claims": self.claims, "counts": self.counts, "anomalies": self.anomalies}

    def report(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        issued = len(self.commands)
        unacked = sorted(c for c in self.commands if not any(c in d["acked"] for d in self.devices.values()))
        anomaly_kinds = ("quarantined", "stale_boot_replay", "gap", "unexplained_transition", "unknown_command", "transition_mismatch")
        found = {k: self.counts.get(k, 0) for k in anomaly_kinds}
        rep = {
            "schema": REPORT_SCHEMA, "tool_version": TOOL_VERSION, "claim_scope": CLAIM_SCOPE,
            "effects_claimed": len(self.claims), "claims": sorted(self.claims, key=lambda c: c["cmd"]),
            "commands_issued": issued, "commands_unacknowledged": unacked,
            "devices": {n: {"boot": d["boot"], "state": d["state"], "last_seq": d["next"] - 1}
                        for n, d in sorted(self.devices.items())},
            "counts": dict(sorted(self.counts.items())), "anomalies_found": found,
            "anomalies": self.anomalies, "anomalies_listed": len(self.anomalies),
        }
        rep.update(extra)
        rep["status"] = "anomalies" if any(found.values()) else "clean"
        return rep


# -- ingest -------------------------------------------------------------------------------

def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.parent / f".{path.name}.{secrets.token_hex(6)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _same(a: Path, b: Path) -> bool:
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


def _guard_output(out: Path, inputs: List[Path]) -> None:
    if out.is_symlink() or (out.exists() and not out.is_file()):
        raise Invalid(f"{out.name}: exists and is not a regular file")
    if not out.parent.is_dir():
        raise Invalid(f"{out.name}: its folder does not exist")
    fold = lambda p: os.path.normcase(os.path.realpath(p)).casefold()
    for p in inputs:
        if _same(out, p) or fold(out) == fold(p):
            raise Invalid(f"{out.name}: would overwrite an input")


def run_ingest(a) -> Tuple[int, Dict[str, Any]]:
    cpath, epath = Path(a.commands), Path(a.events)
    spath = Path(a.state) if a.state else None
    outs = [p for p in (spath, Path(a.out) if a.out else None) if p is not None]
    for p in outs:
        _guard_output(p, [cpath, epath])
    if spath and a.out and (_same(spath, Path(a.out)) or os.path.realpath(spath) == os.path.realpath(a.out)):
        raise Invalid("--state and --out name the same file")
    if a.crash_after is not None and (a.crash_after < 1 or not spath):
        raise Invalid("--crash-after needs --state and a line count of 1 or more")
    cmds = load_commands(cpath)
    csha = hashlib.sha256(cpath.read_bytes()).hexdigest()
    try:
        efh = open(epath, "rb")
    except OSError as exc:
        raise Invalid(f"events: cannot read {epath.name}: {exc.strerror}") from None
    with efh:
        st = None
        offset, lines, h = 0, 0, hashlib.sha256()
        if spath and spath.exists():
            try:
                st = json.loads(spath.read_text(encoding="utf-8"), object_pairs_hook=_no_dupes)
            except (OSError, ValueError, RecursionError):
                raise Damaged(f"state: {spath.name} is not a readable checkpoint; remove it to start over") from None
            if not isinstance(st, dict):  # valid JSON but not a checkpoint object: damaged, not another tool (M25 r2)
                raise Damaged(f"state: {spath.name} is not a checkpoint object; remove it to start over")
            if st.get("schema") != STATE_SCHEMA or st.get("commands_sha256") != csha:
                raise Invalid(f"state: {spath.name} belongs to another command log or tool; remove it to start over")
            why = None if _int(st.get("offset"), 0, 2 ** 62) and _int(st.get("lines"), 0, 2 ** 62) else "offset or lines is not a count"
            why = why or check_snapshot(st, cmds)
            if why:
                raise Damaged(f"state: {spath.name}: {why}; remove it to start over")
            prefix = efh.read(st["offset"])
            if len(prefix) != st["offset"] or hashlib.sha256(prefix).hexdigest() != st.get("events_prefix_sha256"):
                raise Invalid("state: the events file no longer starts with the part already ingested; remove the state to start over")
            # lines is re-derived from the bytes already ingested, so a forged count fails even with a recomputed
            # hash: every ingested line ends with a newline, except a last line at the end of the file (M25 r2)
            if st["lines"] != prefix.count(b"\n") + (1 if prefix and not prefix.endswith(b"\n") else 0):
                raise Damaged(f"state: {spath.name}: lines does not match the events already ingested; remove it to start over")
            h.update(prefix)
            offset, lines = st["offset"], st["lines"]
        ctl = Controller(cmds, st)
        resumed_from = lines if st else None

        def checkpoint() -> None:
            if spath:
                snap = ctl.snapshot()
                body = dict(schema=STATE_SCHEMA, tool_version=TOOL_VERSION, commands_sha256=csha, offset=offset, lines=lines,
                            events_prefix_sha256=h.hexdigest(), **snap)
                body["body_sha256"] = _body_sha(body)
                _write_atomic(spath, (json.dumps(body, sort_keys=True) + "\n").encode("utf-8"))

        if st is None:
            checkpoint()  # a fresh run is resumable from line 0 even if it stops before the first interval
        since = 0
        while True:
            raw = efh.readline(MAX_LINE + 2)
            if not raw:
                break
            h.update(raw)
            offset += len(raw)
            if len(raw) > MAX_LINE + 1 and not raw.endswith(b"\n"):
                chunk = raw
                while not chunk.endswith(b"\n"):  # skip the rest of an over-long line without holding it
                    chunk = efh.readline(MAX_LINE)
                    if not chunk:
                        break
                    h.update(chunk)
                    offset += len(chunk)
                body = b"x" * (MAX_LINE + 1)
            else:
                body = raw.rstrip(b"\r\n")
            lines += 1
            if body.strip():
                ctl.receive(body, lines)
            since += 1
            if a.crash_after is not None and resumed_from is None and lines >= a.crash_after:
                raise Crash(f"crash drill after line {lines}; checkpoint at line {st_lines(spath)}")
            if since >= CHECKPOINT_EVERY:
                checkpoint()
                since = 0
        ctl.finish()
        checkpoint()
    rep = ctl.report({"inputs": {"commands_sha256": csha, "events_sha256": h.hexdigest(), "event_lines": lines},
                      "resumed_from_line": resumed_from})
    return (0 if rep["status"] == "clean" else 1), rep


def _body_sha(body: Dict[str, Any]) -> str:
    """sha256 over every checkpoint field except body_sha256 itself: the cursor (offset, lines, prefix hash), the
    tool version and the controller state (M25 r2: lines sat outside the hash)."""
    rest = {k: v for k, v in body.items() if k != "body_sha256"}
    return hashlib.sha256(json.dumps(rest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def check_snapshot(st: Dict[str, Any], cmds: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Why a checkpoint's controller state is not one this tool could have written, or None (M25 S1)."""
    snap = {k: st.get(k) for k in ("devices", "claims", "counts", "anomalies")}
    if st.get("body_sha256") != _body_sha(st):
        return "its body does not match body_sha256 (edited or damaged)"
    devs, claims, counts, anomalies = snap["devices"], snap["claims"], snap["counts"], snap["anomalies"]
    if not isinstance(devs, dict) or len(devs) > MAX_DEVICES:
        return "devices is not a map of at most 10000 devices"
    for name, d in devs.items():
        if not DEVICE_RE.fullmatch(name) or not isinstance(d, dict) or set(d) != {"boot", "next", "buffer", "state", "acked"}:
            return f"device {name[:64]!r} is not a device record"
        if not (d["boot"] is None or _int(d["boot"], 0, MAX_BOOT)) or not _int(d["next"], 1, MAX_SEQ + 1) \
                or d["state"] not in STATES or not isinstance(d["acked"], list) or not isinstance(d["buffer"], dict) \
                or len(d["buffer"]) > WINDOW:
            return f"device {name!r} has a bad field"
        if any(not isinstance(c, str) or cmds.get(c, {}).get("device") != name for c in d["acked"]) or len(set(d["acked"])) != len(d["acked"]):
            return f"device {name!r} lists an ack that is not one of its commands"
        for k, e in d["buffer"].items():
            if not k.isdigit() or not isinstance(e, dict) or check_event(e) is not None or e["seq"] != int(k) \
                    or e["device"] != name or not d["next"] < e["seq"] <= d["next"] + WINDOW:
                return f"device {name!r} has a bad buffered record"
    if not isinstance(claims, list):
        return "claims is not a list"
    seen = set()
    for c in claims:
        if not isinstance(c, dict) or set(c) != {"cmd", "device", "action"} or c.get("cmd") in seen:
            return "a claim is malformed or repeated"
        seen.add(c["cmd"])
        if cmds.get(c["cmd"]) != c or c["cmd"] not in devs.get(c["device"], {}).get("acked", []):
            return f"claim {str(c.get('cmd'))[:40]!r} is not a logged command that its device acknowledged"
    if not isinstance(counts, dict) or any(not isinstance(k, str) or not _int(v, 0, 2 ** 62) for k, v in counts.items()):
        return "counts is not a map of non-negative integers"
    if not isinstance(anomalies, list) or len(anomalies) > MAX_LISTED or any(not isinstance(x, dict) or not isinstance(x.get("kind"), str) for x in anomalies):
        return "anomalies is not a list of at most 200 records"
    if counts.get("applied", 0) < len(claims):
        return "fewer records applied than effects claimed"
    return None


def st_lines(spath: Optional[Path]) -> int:
    try:
        return int(json.loads(spath.read_text())["lines"]) if spath and spath.exists() else 0
    except (OSError, ValueError, KeyError):
        return 0


# -- simulator ----------------------------------------------------------------------------

class SimDevice:
    """A synthetic valve. Executed command ids and unconfirmed acks live in 'flash' and survive reboots;
    the event outbox and sequence counter are RAM and do not."""

    def __init__(self, name: str):
        self.name, self.boot, self.seq, self.state = name, 0, 0, "closed"
        self.executed: List[str] = []          # ground truth: each entry is one simulated actuation
        self.flash_unconfirmed: Dict[str, Dict[str, Any]] = {}
        self.outbox: Dict[int, Dict[str, Any]] = {}

    def emit(self, kind: str, **body: Any) -> Dict[str, Any]:
        self.seq += 1
        e = dict(v=1, device=self.name, boot=self.boot, seq=self.seq, kind=kind, **body)
        self.outbox[self.seq] = e
        return e

    def on_command(self, c: Dict[str, Any]) -> None:
        if c["cmd"] in self.executed or c["cmd"] in self.flash_unconfirmed:
            ack = self.flash_unconfirmed.get(c["cmd"]) or {"cmd": c["cmd"], "result": "done", "state": self.state}
            self.emit("ack", **ack)  # a retried command is re-acknowledged, never re-executed
            return
        self.state = ACTIONS[c["action"]]
        self.executed.append(c["cmd"])
        ack = {"cmd": c["cmd"], "result": "done", "state": self.state}
        self.flash_unconfirmed[c["cmd"]] = ack
        self.emit("ack", **ack)

    def reboot(self) -> None:
        self.boot += 1
        self.seq = 0
        self.outbox = {}
        self.emit("hello")
        for ack in self.flash_unconfirmed.values():  # unconfirmed acks are re-sent first, in execution order
            self.emit("ack", **ack)
        self.emit("state", state=self.state)


def parse_faults(text: str) -> Dict[str, float]:
    f = {"drop": 0.0, "dup": 0.0, "reorder": 0.0, "disconnect": 0.0, "reboot": 0.0}
    if text:
        for part in text.split(","):
            k, _, v = part.partition("=")
            if k not in f:
                raise Invalid(f"--faults: unknown fault {k!r}")
            try:
                f[k] = float(v)
            except ValueError:
                raise Invalid(f"--faults: {k} needs a number") from None
            if not (0 <= f[k] <= 0.5):
                raise Invalid(f"--faults: {k} must be between 0 and 0.5")
    return f


def run_simulate(a) -> Tuple[int, Dict[str, Any]]:
    if not (1 <= a.devices <= 1000 and 1 <= a.steps <= 100000):
        raise Invalid("--devices must be 1..1000 and --steps 1..100000")
    faults = parse_faults(a.faults)
    rec = Path(a.record) if a.record else None
    if rec and (rec.is_symlink() or (rec.exists() and not rec.is_dir())):
        raise Invalid(f"--record: {rec} exists and is not a folder")
    # a file further up the path ("afile/sub") would make mkdir fail after the run (M25 r2 D04)
    for parent in (rec.parents if rec else ()):
        if parent.exists() or parent.is_symlink():
            if not parent.is_dir():
                raise Invalid(f"--record: {parent} is not a folder, so {rec} cannot be created")
            break
    rng = random.Random(a.seed)
    devs = [SimDevice(f"valve-{i:03d}") for i in range(a.devices)]
    for d in devs:
        d.reboot()
    cmds: Dict[str, Dict[str, Any]] = {}
    cmd_log: List[bytes] = []
    received: List[bytes] = []
    ctl = Controller(cmds)
    in_flight: List[Tuple[int, bytes]] = []     # (deliver_at_step, line) device -> controller
    online = {d.name: True for d in devs}
    seen_acks: Dict[str, int] = {}               # controller-side cumulative ack per device/boot
    counter = 0
    settle = 400                                 # fault-free tail so every retry can finish

    def deliver(line: bytes) -> None:
        received.append(line)
        ctl.receive(line, len(received))

    for step in range(a.steps + settle):
        noisy = step < a.steps
        # controller issues new commands while the noisy phase lasts
        if noisy and rng.random() < 0.3:
            d = rng.choice(devs)
            counter += 1
            c = {"cmd": f"c-{counter:06x}", "device": d.name, "action": "open" if d.state == "closed" else "close"}
            cmds[c["cmd"]] = c
            cmd_log.append(json.dumps(c, sort_keys=True).encode())
        # controller (re)sends every command it has no ack for; the link may lose it
        for c in cmds.values():
            dv = devs[int(c["device"].split("-")[1])]
            if c["cmd"] in ctl.claimed or any(c["cmd"] in x["acked"] for x in ctl.devices.values()):
                continue
            if online[dv.name] and not (noisy and rng.random() < faults["drop"]):
                dv.on_command(c)
        for d in devs:
            if noisy and rng.random() < faults["reboot"]:
                d.reboot()
            if noisy and rng.random() < faults["disconnect"]:
                online[d.name] = not online[d.name]
            elif not noisy:
                online[d.name] = True
            if noisy and rng.random() < 0.05:
                d.emit("telemetry", flow_lpm=round(rng.uniform(0, 40) if d.state == "open" else 0.0, 2))
            if not online[d.name]:
                continue
            for s, e in sorted(d.outbox.items()):    # resend everything not yet acknowledged by the controller
                line = json.dumps(e, sort_keys=True).encode()
                if noisy and rng.random() < faults["drop"]:
                    continue
                delay = rng.randint(1, 4) if noisy and rng.random() < faults["reorder"] else 0
                in_flight.append((step + delay, line))
                if noisy and rng.random() < faults["dup"]:
                    in_flight.append((step + rng.randint(0, 3), line))
        due = [x for x in in_flight if x[0] <= step]
        in_flight = [x for x in in_flight if x[0] > step]
        for _, line in due:
            deliver(line)
        # controller -> device: cumulative event ack and command confirmations (may be lost)
        for d in devs:
            cd = ctl.devices.get(d.name)
            if cd is None or cd["boot"] != d.boot or not online[d.name] or (noisy and rng.random() < faults["drop"]):
                continue
            upto = cd["next"] - 1
            d.outbox = {s: e for s, e in d.outbox.items() if s > upto}
            seen_acks[d.name] = upto
            for cmd in list(d.flash_unconfirmed):
                if cmd in cd["acked"]:
                    del d.flash_unconfirmed[cmd]
    ctl.finish()
    executed = [(d.name, c) for d in devs for c in d.executed]
    truth = sorted(c for _, c in executed)
    claimed = sorted(c["cmd"] for c in ctl.claims)
    double = sorted({c for c in truth if truth.count(c) > 1}) if len(truth) != len(set(truth)) else []
    sim = {"seed": a.seed, "devices": a.devices, "steps": a.steps, "faults": faults,
           "ground_truth_actuations": len(truth), "ground_truth_double_actuations": double,
           "claims_match_ground_truth": claimed == truth, "lines_received": len(received),
           "simulator": "synthetic devices and link in this process; no hardware"}
    if rec:
        try:
            rec.mkdir(parents=True, exist_ok=True)  # a fresh folder works as the doc shows (M25 S2)
            _write_atomic(rec / "commands.jsonl", b"".join(l + b"\n" for l in cmd_log))
            _write_atomic(rec / "events.jsonl", b"".join(l + b"\n" for l in received))
        except OSError as exc:
            raise Invalid(f"--record: cannot write {rec}: {exc.strerror}") from None
    rep = ctl.report({"simulation": sim})
    ok = claimed == truth and not double and not rep["commands_unacknowledged"]
    rep["simulation"]["verdict"] = "claims equal ground truth, exactly once" if ok else "MISMATCH"
    return (0 if ok else 1), rep


# -- cli ----------------------------------------------------------------------------------

def render(rep: Dict[str, Any]) -> str:
    lines = [f"status: {rep['status']}", f"effects claimed: {rep['effects_claimed']} of {rep['commands_issued']} commands "
             f"({rep['claim_scope']})"]
    if rep.get("commands_unacknowledged"):
        lines.append(f"unacknowledged commands: {len(rep['commands_unacknowledged'])}")
    for k, v in rep["anomalies_found"].items():
        if v:
            lines.append(f"anomaly {k}: {v}")
    for k in ("duplicates_dropped", "duplicate_acks", "reordered_buffered", "reboots"):
        if rep["counts"].get(k):
            lines.append(f"{k}: {rep['counts'][k]}")
    if "simulation" in rep:
        lines.append(f"simulation: {rep['simulation']['verdict']} (ground truth {rep['simulation']['ground_truth_actuations']})")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="device_protocol.py", description="Offline synthetic device-event protocol (simulator only).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest")
    i.add_argument("--commands", required=True)
    i.add_argument("--events", required=True)
    i.add_argument("--state")
    i.add_argument("--crash-after", type=int)
    i.add_argument("--json", action="store_true")
    i.add_argument("--out")
    s = sub.add_parser("simulate")
    s.add_argument("--devices", type=int, default=8)
    s.add_argument("--steps", type=int, default=500)
    s.add_argument("--seed", type=int, default=25)
    s.add_argument("--faults", default="")
    s.add_argument("--record")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        code, rep = run_ingest(a) if a.cmd == "ingest" else run_simulate(a)
    except Crash as exc:
        sys.stdout.write(f"crash drill: {exc}\nrerun the same command without --crash-after to resume\n")
        return 3
    except Damaged as exc:
        if getattr(a, "json", False):
            sys.stdout.write(json.dumps({"schema": REPORT_SCHEMA, "status": "damaged_state", "error": str(exc)}) + "\n")
        else:
            sys.stdout.write(f"damaged checkpoint: {exc}\nnothing written\n")
        return 4
    except Invalid as exc:
        if getattr(a, "json", False):
            sys.stdout.write(json.dumps({"schema": REPORT_SCHEMA, "status": "invalid", "error": str(exc)}) + "\n")
        else:
            sys.stdout.write(f"invalid: {exc}\nnothing written\n")
        return 2
    data = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if getattr(a, "out", None):
        _write_atomic(Path(a.out), data.encode("utf-8"))
    sys.stdout.write(data if a.json else render(rep))
    return code


if __name__ == "__main__":
    sys.exit(main())
