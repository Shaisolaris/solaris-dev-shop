# Backend testing strategy - integration-first, outcome-driven

Methodology absorbed 2026-06-13 from **goldbergyoni/nodejs-testing-best-practices**
(4.4k★, "April 2025" edition, last push 2026-02-10). License: NOASSERTION - this file
is a **paraphrase of the methodology**, not a copy of the source text or its example app;
no code is vendored. The patterns are Node-framed in the original but apply to any backend
stack (Laravel/FastAPI/Django/.NET/Rails) - translate the tooling, keep the strategy.

This deepens rules.md §W6 (which already has framework-detection, coverage bars, TDD,
and saga/queue failure injection). What's net-new: the *integration-first ordering*, the
*five backend exit doors* outcome model, and concrete checklists for message-queue and
external-integration tests.

## 1. Strategy: integration/component tests first, not unit-first
- **Start with component tests** - exercise the whole backend (route → service → real DB)
  in one process, mocking only out-of-process third parties. They catch the bugs that
  actually ship and double as living documentation of the API.
- Keep E2E (across deployed services + UI) **few and selective**; reach for pure unit
  tests for genuinely complex, branchy logic (algorithms, money math, parsers) - not for
  thin CRUD that a component test already covers.
- **Cover features, not functions:** a test maps to a user-visible behavior ("creating an
  order with an out-of-stock item returns 409"), not to a single method.
- Write tests **during** coding, not after. Test-after and partial-coverage theater are
  rejected (consistent with W6's TDD stance).

## 2. The five backend exit doors (assert on the OUTCOME, not internals)
For every flow, a test should assert on at least one of the five ways effect leaves the
backend - these are what a caller can observe, so they are what you test:
1. **HTTP response** - status + the whole body shape (assert the response object, not
   field-by-field), including auto-generated fields via schema assertion.
2. **State change** - re-read through the **public API**, not by peeking at the DB, to
   confirm the new state is really reachable by clients.
3. **External call(s) made** - assert the outgoing request fired with the right payload
   (via the HTTP interceptor, see §4), or correctly was NOT made.
4. **Message-queue message** - assert the expected message was published (or consumed).
5. **Observability** - for flows whose only product is a log/metric/trace, assert it.
A flow with no observable exit door is untestable by design - that itself is a finding.

## 3. Infrastructure & data setup
- **Real DB, not a fake/in-memory substitute.** Run the same engine as prod (Postgres ⇒
  Postgres) via docker-compose started by the test global-setup; tear down only in CI.
  Speed it up with a RAM-backed data dir and prod-like tuning, not by faking the engine.
- Build the schema with the **same migrations as production**, once per run.
- **Each test acts on its own records only** - create what you need inside the test; never
  depend on data another test made. Add randomness to unique fields to avoid collisions.
- Only **metadata/context** (lookup tables, feature flags) gets pre-seeded.
- **Clean-up strategy: after-all (recommended)** - let tests accumulate rows in their own
  namespaces and truncate once at the end; after-each only when isolation demands it.
- Assert the **response schema** too (not just values) wherever fields are auto-generated.

## 4. External integrations (third-party APIs)
- **Isolate from the network with an HTTP interceptor** (nock / MSW / WireMock / responses /
  Laravel Http::fake - pick the stack equivalent). The component stays in-process; the world
  is faked at the HTTP boundary.
- Define **happy-path default responses before every test**, then override per-test for
  corner cases (timeouts, 5xx, malformed bodies).
- **Deny all un-mocked outgoing requests by default** - an unexpected real network call
  should fail the test, not silently hit a live API.
- **Simulate network chaos:** latency, connection-reset, partial response - assert the
  resilience policy (timeout/retry/circuit-breaker from rules.md §W5) actually engages.
- **Validate the outgoing request shape** (schema) so you catch sending a malformed payload
  to the provider. Code against the provider's **published contract**; consider recording
  real responses periodically so the mock doesn't drift from reality.

## 5. Message-queue tests (deepens W4)
Use a fake/in-memory broker for the bulk; keep a couple of real-broker E2E tests. Cover:
- **Ack / nack** - message acknowledged on success, negatively-acked (and re-queued or DLQ'd)
  on failure.
- **Batch processing** - a batch of messages is handled correctly, including partial failure.
- **Poisoned message** - a malformed/un-processable message goes to the DLQ instead of
  wedging the consumer.
- **Idempotency** - the same message delivered twice produces one effect (ties to W4's
  idempotency rule and the webhook idempotency-store).
- **Connection failure** - broker drops and reconnects without leaving a zombie consumer.
- Promisify the test (await the processed signal); don't poll or nest callbacks.

## 6. Mocking discipline
- A **good mock** stands in for an out-of-process dependency at a stable boundary; a **bad
  mock** asserts internal call counts/order, freezing implementation details and breaking on
  every refactor. Prefer outcome assertions (§2) over "was this private method called once".
- Avoid hidden mocks set far from the test; **clean up all mocks before every test** to stop
  cross-test leakage. Be deliberate about partial mocks; type your mocks so they track the
  real signature.

## Stack tooling map (translate the strategy)
- **Laravel:** Pest feature tests, `RefreshDatabase`/transactions, `Http::fake()`, real
  Postgres/MySQL in docker, queue `Bus::fake()` / real Horizon for the few E2E.
- **FastAPI:** pytest + httpx AsyncClient (a real HTTP client, not the in-app test client
  shortcut where you can avoid it), dependency overrides, `respx`/`responses` interceptor,
  real Postgres via testcontainers.
- **Node (Fastify/Nest):** the source's home turf - axios against the in-process app, nock/MSW,
  testcontainers, a fake MQ.
- **.NET:** WebApplicationFactory, WireMock.Net, Respawn for DB reset, Testcontainers.
- **Rails:** request specs, WebMock/VCR, real Postgres, SolidQueue/Sidekiq test mode.

Coverage bars and TDD policy remain as W6 (floor 80%, stretch 85% Laravel / 90% FastAPI;
error-path coverage counts double). This file governs *how* the tests are shaped.
