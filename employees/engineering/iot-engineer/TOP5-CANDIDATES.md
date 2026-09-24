# IoT / Embedded Engineer - TOP-5 Source Candidates (2026 scan)

Scan date: 2026-06-13. Bar: established/safe, 100+ stars (or 50+ with notable maintainer), permissive license preferred (GPL/AGPL/NOASSERTION flagged), commit within ~6mo. Gate-0 = grep of this employee's ACTUAL content; if the capability is already present in substance, mark content-duplicate.

## Verified metadata (shields.io stars + license, GitHub commits.atom for last-commit)

| # | Source | Stars | License | Last commit | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-------|---------|-------------|------------|--------------|----------------|-----|
| 1 | ThrowTheSwitch/Unity + CMock + Ceedling | 5.3k / 825 / 815 | MIT (all three) | 2026-05-29 / 2026-05-29 / 2026-06-13 | ThrowTheSwitch | Host-based embedded C unit testing: Unity asserts, CMock auto-mocks the HAL/driver layer, Ceedling orchestrates build+test+coverage. The professional way to test firmware logic off-target before flashing. | NOT present. Employee has only "test fixtures (bed-of-nails, JTAG)" = hardware DfT, no software unit-test methodology, no HAL-mocking, no host build. True gap. | ABSORB (methodology) |
| 2 | espressif/esp-mqtt | 727 | Apache-2.0 | 2026-05-29 | Espressif (official) | Production MQTT client design: QoS 0/1/2 trade-offs, Last Will and Testament, retained messages, keepalive/clean-session, TLS mutual auth, reconnect/backoff, topic-design discipline. | Partial/thin. Employee only lists "MQTT + HTTPS + WebSockets" as an AWS bullet. No QoS/LWT/retained/keepalive design rules. Net-new methodology. | METHODOLOGY |
| 3 | espressif/esp-iot-solution | 2.6k | Apache-2.0 | 2026-06-09 | Espressif (official) | Production-grade ESP component library: sensor/display/USB/power-management drivers, reference designs, Component-Registry packaging workflow (idf.py add-dependency, version pinning). | NOT present (no grep hit). Connects directly to existing ESP-IDF/PlatformIO stack. | CONNECT |
| 4 | tensorflow/tflite-micro | 3k | Apache-2.0 | 2026-06-06 | TensorFlow / Google | Canonical TFLM deployment workflow: train -> INT8 post-training quantization -> xxd to C array -> MicroInterpreter + tensor-arena sizing -> op resolver. The how, not just the name-drop. | Partial. Employee names "TensorFlow Lite Micro (TFLM) INT8" but gives no quantize/deploy/arena-sizing workflow. Net-new methodology. | METHODOLOGY |
| 5 | mendersoftware/mender | 1.2k | Apache-2.0 core (GitHub reports "not identifiable" - open-core, server tiers vary) FLAG | 2026-06-09 | Northern.tech / Mender | Fleet OTA operations: artifact format, delta updates, phased/canary deployments, dynamic device grouping, rollback-on-failure, dual-A/B at the fleet level. | Partial. Employee lists "Mender / RAUC / SWUpdate" in one OTA bullet; no fleet-rollout/grouping/artifact methodology. Net-new methodology. | METHODOLOGY |

## License flags for Shai
- Mender (#5): core client is Apache-2.0, but GitHub license detector returns "not identifiable" across the org (open-core; server has tiered/commercial components). Methodology-only absorption is safe; do NOT bundle code. Self-host note: the open-source Mender server is self-hostable via Docker/Helm; managed/Enterprise tiers are commercial.
- Considered but rejected on license/freshness grounds (kept out of the top 5):
  - cesanta/mongoose (13k) - dual GPLv2 / commercial. Strong networking lib but GPL is a hard flag for bundling; methodology-only at best. Not selected; esp-mqtt covers the MQTT need under Apache.
  - eclipse-paho/paho.mqtt.embedded-c (1.5k) - last commit 2024-01, stale (>6mo). Rejected on freshness.
  - eclipse-mosquitto/mosquitto (11k) - EPL/EDL dual; it is a broker, not device firmware. Out of scope for this employee.

## Disposition
- #1 Unity/CMock/Ceedling -> PART C deepen: new reference file references/embedded-testing.md (methodology; MIT so safe to describe build/mock patterns).
- #2 esp-mqtt + #5 Mender -> PART C: fold MQTT-client design + fleet-OTA operations methodology into the same reference file (no code bundled; Mender = methodology + self-host note).
- #3 esp-iot-solution -> CONNECT: note in SKILL as the production component source for the existing ESP stack.
- #4 tflite-micro -> METHODOLOGY: add the quantize->deploy->arena workflow to the edge-ML section.
