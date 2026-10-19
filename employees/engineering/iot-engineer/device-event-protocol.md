# Device event protocol: exactly-once effect claims from an unreliable stream

Runnable reference: `device_protocol.py` (Python 3.9+, standard library only). Scope: **simulator only.**
Devices, links and valves are synthetic Python objects. Nothing here talks to hardware, a serial port,
a radio or a network. An "effect" in a report is a simulated valve actuation, and every report carries
`claim_scope: "simulated valve actuations from a synthetic event stream; not hardware evidence"`.
A claim about a physical device needs that device on a bench, and is out of scope for this tool.

## When to use it
- Designing or reviewing the controller side of any fleet that acts on device acknowledgements
  (valves, relays, locks, dosing pumps): anything where acting twice on a duplicate is harmful.
- Replaying a captured or synthetic event log to find gaps, replays and unexplained state changes.
- Proving a retry or reconnect design before firmware exists.

## The wire record
One flat JSON object per line, at most 64 KiB (longer lines are skipped without being held in memory):

    {"v":1, "device":"valve-007", "boot":3, "seq":41, "kind":"ack", "cmd":"c-00002a", "result":"done", "state":"open"}

| field | rule |
|---|---|
| `v` | must be 1 |
| `device` | `^[a-z0-9][a-z0-9-]{0,63}$` (whole string; a trailing newline is not allowed) |
| `boot` | integer 0..2^31, increments on every device restart (kept in flash) |
| `seq` | integer 1..2^53, restarts at 1 in each boot, +1 per record the device emits |
| `kind` | `hello`, `telemetry` (`flow_lpm` finite number), `state` (`closed`, `open`, `fault`), `ack` |
| `ack` | `cmd` `^c-[0-9a-f]{1,32}$` (whole string; a trailing newline is not allowed), `result` `done` or `rejected`, `state` after execution |

Unknown fields, duplicate keys, booleans as integers, NaN or infinite numbers, out-of-range values,
invalid UTF-8, over-long lines, pathologically nested lines and records from more than 10000
distinct devices are **quarantined**: counted, listed with line number and reason (capped
at 200 listed), never parsed further and never echoed back.

The command log is one JSON object per line with exactly `cmd`, `device`, `action` (`open` or `close`);
a duplicate command id, unknown field or bad action makes the whole run invalid (exit 2).

## Controller rules
1. **Sessions** are `(device, boot)`. A record from a lower boot than the device's current one is a
   `stale_boot_replay`: reported, never applied. A higher boot starts a new session.
2. **Ordering** inside a session is strict by `seq`. Records ahead of the next expected number wait in
   a buffer of 32 (seqs next+1 to next+32); a record further ahead, or the end of the stream with a hole,
   declares a `gap` and moves on.
   Duplicates (same session and seq, or seq already applied) are dropped and counted, not anomalies.
3. **Effects** are claimed only by an `ack` with `result: done`, for a command in the log, addressed to
   that same device, whose `state` equals the command's target. Each command id is claimed at most once
   across every session; repeats count as `duplicate_acks`. An ack for an unknown or another device's
   command is `unknown_command`; a done ack with the wrong state is `transition_mismatch`; a rejected
   ack is counted and makes no claim.
4. **State** follows the device's own reports. A change no ack explains is `unexplained_transition`.
5. **Recovery**: with `--state S.json` the controller checkpoints atomically (write temp, fsync,
   rename) every 50 lines and at the end. The checkpoint binds the sha256 of the events prefix already
   read and of the command log; a resume onto changed input is refused (exit 2). It also carries
   `body_sha256` over its controller state, and on load that state is checked for structure (device
   records, buffered records inside the window, every claim a logged command its device acknowledged);
   an edited, truncated or damaged checkpoint exits 4 and nothing is written. Limit: the hash is not a
   signature; someone who rewrites the body and recomputes it passes the hash, and only the structure
   checks stand between them and a resumed run. A checkpoint from tool 1.0.0
   (state schema /1) is refused with exit 2. `--crash-after N`
   drills a crash after N lines (exit 3); rerunning resumes and gives the same report as an unbroken run.

## Device side (what the simulator models, and what firmware must do)
- Execute a command id at most once: keep executed ids in flash; a repeated command re-acks.
- Keep unconfirmed acks in flash; after a reboot send `hello`, then the unconfirmed acks in execution
  order, then the current `state`.
- Increment `boot` in flash before the first record of a session.

## Commands
    python3 device_protocol.py simulate --devices 12 --steps 300 --seed 7 \
        --faults drop=0.2,dup=0.2,reorder=0.3,disconnect=0.05,reboot=0.02 --record out/
    python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --json
    python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --state out/st.json --crash-after 500   # exit 3
    python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --state out/st.json   # resumes, exit 1

These run as written in an empty folder: `--record` creates its folder (an existing file there is exit 2).
The faulted simulation exits 0 (claims equal ground truth) and its stream has anomalies, so `ingest` exits 1.

Exit codes: 0 clean, 1 anomalies listed, 2 invalid invocation or input, 3 crash drill, 4 damaged or edited checkpoint.
`simulate` exits 0 when claims equal the simulator's ground truth exactly once (anomalies from the
faults are still listed), 1 otherwise.

## Limits (stated, not hidden)
- No hardware, transport, radio timing, power loss mid-write on a real flash part, or clock skew.
- The controller trusts the device to report its state honestly; there is no authentication of
  records. Signed records and per-device keys belong to security-auditor and are not modelled.
- Effects whose ack is lost forever stay in `commands_unacknowledged`: the controller cannot know
  whether they happened, and says so instead of guessing.
- Simulator command choice reads the simulated device's true state; a real controller only has its
  last report.

Evidence: `examples/capabilities/G25/` (oracle, stubs, fixtures) and `tests/test_g25_capability.py`.
