# Embedded Testing + Connectivity Methodology

Methodology-only reference. No third-party code is bundled here. Absorbed 2026-06-13.
Sources: ThrowTheSwitch (Unity/CMock/Ceedling, MIT), espressif/esp-mqtt (Apache-2.0),
tensorflow/tflite-micro (Apache-2.0), mendersoftware/mender (open-core, FLAGGED below).

---

## 1. Host-based embedded C unit testing (Unity + CMock + Ceedling)

The core gap this fills: firmware logic should be tested **off-target on the host** (x86) in CI,
not only flashed and prodded by hand. Hardware-in-the-loop and bed-of-nails fixtures test the
*board*; this tests the *code*.

### The three layers (all MIT, ThrowTheSwitch)
- **Unity** - assertion + test-runner framework. Single C file + 2 headers, drops into any toolchain.
  `TEST_ASSERT_EQUAL_INT`, `TEST_ASSERT_EQUAL_HEX8`, `TEST_ASSERT_TRUE`, `TEST_ASSERT_EQUAL_MEMORY`.
- **CMock** - auto-generates mocks/stubs from a header. Point it at `hal_gpio.h` and it produces
  `mock_hal_gpio.c` with `hal_gpio_set_Expect(...)`, `hal_gpio_read_ExpectAndReturn(...)`,
  `..._StubWithCallback(...)`. This is what lets you test logic without real silicon.
- **Ceedling** - Ruby/Rake build+test orchestrator. Discovers tests, wires Unity + CMock,
  runs them, emits pass/fail + gcov coverage. `ceedling test:all`, `ceedling gcov:all`.

### The discipline that makes it work: depend on interfaces, not registers
Code is testable only if hardware access is behind a thin HAL the test can mock.
- Bad: business logic pokes `GPIO->ODR |= (1<<5)` directly -> untestable on host.
- Good: business logic calls `hal_gpio_set(LED_PIN, HIGH)`; CMock mocks `hal_gpio_*` in the test;
  the real driver implements it against registers and is the *only* thing needing on-target test.

### Test structure (Arrange-Act-Assert)
```c
#include "unity.h"
#include "mock_hal_gpio.h"   // CMock-generated from hal_gpio.h
#include "led_controller.h"  // unit under test

void test_led_on_drives_pin_high(void) {
    hal_gpio_set_Expect(LED_PIN, GPIO_HIGH);   // expectation (Arrange)
    led_on();                                  // Act
    // CMock verifies the expectation on teardown (Assert)
}
```

### What to unit-test vs not
- DO unit-test: protocol state machines, parsers/encoders, ring buffers, retry/backoff logic,
  CRC/checksum, configuration validation, unit conversions, scheduler/queue logic.
- DO NOT bother host-unit-testing: raw register pokes, vendor SDK internals, timing-exact ISRs
  (test those on-target or with HIL).

### CI gate
- `ceedling gcov:all` in CI on every PR; treat a coverage drop on core logic as a red flag.
- Tests must build and pass on the **host** (no board attached) - that is the whole point.

### Red flags
- "We test by flashing and watching the LED." -> no automated regression net.
- Business logic that includes vendor register headers directly -> not unit-testable.
- Mocks hand-written and drifting from the real header -> let CMock regenerate them.

---

## 2. MQTT client design (esp-mqtt, Apache-2.0 - methodology)

Name-dropping "MQTT" is not design. The decisions that matter on a constrained device:

- **QoS:** 0 = fire-and-forget (telemetry you can lose), 1 = at-least-once (dedupe on receiver),
  2 = exactly-once (expensive 4-way handshake; rarely justified on MCUs). Default telemetry = QoS 0/1,
  commands/config = QoS 1 with idempotent handlers.
- **Last Will and Testament (LWT):** register a retained "offline" message on connect so the broker
  publishes device-down status automatically when the keepalive lapses. Essential for fleet liveness.
- **Retained messages:** broker stores last value per topic; new subscribers get current state
  immediately. Use for device shadow/config, NOT for high-rate telemetry (it pins memory on the broker).
- **Keepalive + clean session:** size keepalive to power budget (longer = fewer wakeups, slower
  failure detection). `clean_session=false` to resume subscriptions after a sleep/reconnect.
- **Reconnect with backoff:** exponential backoff + jitter; never tight-loop reconnect (it DoSes the
  broker and drains battery). The state machine here is a prime unit-test target (see section 1).
- **Topic design:** hierarchical, device-id-scoped, e.g. `tenant/{id}/dev/{mac}/telemetry`.
  Subscribe with wildcards server-side, publish to fully-qualified topics device-side.
- **Security:** mTLS (per-device cert) over TLS 1.3; never username/password over plain TCP in the field.

### Red flags
- QoS 2 for routine telemetry. Retained on a 10Hz sensor topic. No LWT (silent dead devices).
  Tight reconnect loop. Shared device credentials instead of per-device certs.

---

## 3. TFLM deployment (tensorflow/tflite-micro, Apache-2.0 - methodology)

Cross-reference: the step-by-step quantize -> C-array -> tensor-arena -> op-resolver workflow now
lives in SKILL.md (Edge ML section). Key rule restated: INT8 post-training quantization with a
representative dataset, MicroMutableOpResolver (only the ops used), and empirically-sized arena via
`interpreter.arena_used_bytes()`.

---

## 4. Fleet OTA operations (Mender - methodology + self-host note)

LICENSE FLAG: Mender is open-core. The client is Apache-2.0, but GitHub's detector returns
"not identifiable" across the org and the server has tiered/commercial editions. Absorb the
**operational methodology only**; do not bundle code. Self-host note: the open-source Mender server
runs via Docker Compose / Helm; managed (Hosted Mender) and Enterprise tiers are commercial. RAUC and
SWUpdate are fully-GPL alternatives if a copyleft-clean stack is required.

### Operational pattern (applies to Mender/RAUC/SWUpdate alike)
- **Artifact, not raw image:** ship a signed artifact with metadata (device-type compatibility,
  version, checksum) so the wrong image cannot land on the wrong hardware.
- **A/B (dual-bank) at the device:** write to the inactive bank, switch on verified boot, auto-rollback
  if the new bank fails its health check within N boots. Never overwrite the running bank.
- **Delta updates:** ship only the binary diff to save bandwidth/airtime on cellular/LoRa fleets.
- **Phased / canary rollout:** 1% -> 10% -> 50% -> 100%, gated on success metrics from the prior wave.
  Halt-on-failure. This mirrors the staged-rollout rule already in SKILL.md, made operational.
- **Dynamic device grouping:** target by attribute (hw rev, firmware version, region) so you can
  hold back a known-bad hardware revision.
- **Rollback-on-failure is mandatory:** an OTA path without automatic rollback is a brick generator.

### Red flags
- Single-bank "update in place" on field hardware. OTA with no rollback. No artifact/compatibility
  check (image lands on incompatible board). Rollout to 100% in one shot with no canary.
