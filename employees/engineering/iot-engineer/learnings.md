# IoT / Embedded Engineer - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from msitarzewski embedded firmware engineer**: Static allocation + calculated stack + ISR-FromISR discipline are the consistent production-firmware professional rules.
- **2026-04-25 - OTA + signed firmware from Day 1** is the rule that separates field-deployable IoT from prototypes.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-06-13 - Depth pass v0.6.0
- Net-new capability: host-based embedded unit testing (Unity + CMock + Ceedling, MIT). Prior content had only hardware DfT/bed-of-nails; no software unit-test methodology. Now in references/embedded-testing.md. Key rule: hardware behind a thin HAL so CMock can mock it and logic is testable off-target in CI.
- Deepened thin areas: MQTT client design (QoS/LWT/retained/keepalive/backoff/topic design, esp-mqtt), TFLM quantize->C-array->arena->op-resolver workflow (tflite-micro), fleet OTA operations (artifact/A-B/delta/canary/rollback, Mender - methodology only, open-core FLAG).
- Perfection: removed deprecated Google Cloud IoT from the live cloud table + SKILL description (kept as an explicit deprecation note). Added esp-iot-solution production-components CONNECT block. Added prototype/pilot/production rigor lane to rules.md so small tasks are not over-engineered. Reconciled the undocumented v0.5.0 version bump.
## 2026-10-18 - G25 device event protocol (simulator)
- Dedupe by command id, not by (device, seq): a device that reboots re-sends an unconfirmed ack under a new boot and seq, so seq-only dedupe would claim the effect twice (oracle o4 and the faulted simulations exercise this).
- After a reboot the device must send its unconfirmed acks before its `state` record; the other order made the controller see a state change no ack explained (3 false `unexplained_transition` in a 131-claim faulted run).
- Hash an over-long line in the order it is read; the first draft hashed its tail before its head, which would make resume verification disagree with the file (caught in code review before any run).
- Reference: device-event-protocol.md, device_protocol.py.
## Sources

- Upstream: ThrowTheSwitch/Unity + CMock + Ceedling (MIT (all three)); espressif/esp-mqtt (Apache-2.0); espressif/esp-iot-solution (Apache-2.0); tensorflow/tflite-micro (Apache-2.0); mendersoftware/mender (Apache-2.0 core (GitHub reports "not identifiable" - open-core, server tiers vary) FLAG)
- What was used: methodology absorbed: ThrowTheSwitch/Unity + CMock + Ceedling; methodology only: espressif/esp-mqtt, tensorflow/tflite-micro, mendersoftware/mender; connected as external reference: espressif/esp-iot-solution
- License notes: mendersoftware/mender: Apache-2.0 core (GitHub reports "not identifiable" - open-core, server tiers vary) FLAG
- **2026-10-18 - G25 r2 (M25 self-validation)**: binding a checkpoint to its inputs is not binding its body: deleting claims from a valid checkpoint resumed with exit 0. Hash the body, check its structure against the command log, and give a damaged checkpoint its own exit code (4) so a caller can tell it from "anomalies listed". Python's `$` matches before a final newline; ids need `fullmatch`. A doc command is a test: run the Commands block verbatim in an empty folder.
- **2026-10-18 - G25 r3 (M25 r2 self-validation)**: a checksum over part of a checkpoint invites edits to the rest: `lines` sat outside `body_sha256`, so editing it shifted every reported line number and still exited 1. Hash every field but the hash itself, and recompute what can be recomputed from the inputs (the line count from the bytes already read), because a forger can recompute a hash but not the input. JSON that parses but is not an object is damage, not another tool's file.
