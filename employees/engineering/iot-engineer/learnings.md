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
## Sources

- Upstream: ThrowTheSwitch/Unity + CMock + Ceedling (MIT (all three)); espressif/esp-mqtt (Apache-2.0); espressif/esp-iot-solution (Apache-2.0); tensorflow/tflite-micro (Apache-2.0); mendersoftware/mender (Apache-2.0 core (GitHub reports "not identifiable" - open-core, server tiers vary) FLAG)
- What was used: methodology absorbed: ThrowTheSwitch/Unity + CMock + Ceedling; methodology only: espressif/esp-mqtt, tensorflow/tflite-micro, mendersoftware/mender; connected as external reference: espressif/esp-iot-solution
- License notes: mendersoftware/mender: Apache-2.0 core (GitHub reports "not identifiable" - open-core, server tiers vary) FLAG
