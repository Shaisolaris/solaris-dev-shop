# API fuzz + mutation + real-dependency integration (three net-new testing layers)

Absorbed 2026-06-13 (qa-engineer v0.8.0). Methodology only - no source vendored. Three layers that were ABSENT from the employee (Gate-0 verified: zero hits for schemathesis / property-based / fuzz / stryker / mutation-testing / testcontainers). Each closes a specific gap the existing toolkit could not reach: the negative-input space (Schemathesis), test-suite EFFECTIVENESS vs mere coverage (Stryker), and the real-dependency boundary that mocks cannot honestly stand in for (Testcontainers).

Cross-cutting rule: these are ADDITIVE to the existing pyramid, not replacements. Pact still owns producer/consumer CONTRACTS; example-based API tests still own the documented happy/error cases; WireMock/MSW still own fast frontend mocking. The new layers run in CI as their own gated jobs.

---

## Layer 1 - Schemathesis (property-based / fuzz API testing) [MIT]

Source: github.com/schemathesis/schemathesis (MIT, 3,318 stars, pushed 2026-05-26, used by Netflix/SAP/Red Hat/IBM/JetBrains). Generates test cases directly from an OpenAPI or GraphQL schema using Hypothesis - both valid inputs and adversarial edge cases the author never thought to write.

### What it finds that example-based tests do not
- **Server crashes (5xx)** on inputs that satisfy the schema but break the handler.
- **Response-schema violations** - the API returns a shape its own spec forbids.
- **Validation bypass** - inputs the spec says are invalid that the server accepts anyway.
- **Stateful bugs** - multi-step workflows where step N corrupts state for step N+1 (Schemathesis can link operations via OpenAPI links).

### How to run
- CLI against a live API + its spec:
  - `schemathesis run http://localhost:8000/openapi.json --checks all`
  - key built-in checks: `not_a_server_error`, `status_code_conformance`, `content_type_conformance`, `response_schema_conformance`.
- pytest integration for first-class assertions + custom hooks:
  - `schema = schemathesis.openapi.from_url("http://localhost:8000/openapi.json")`
  - `@schema.parametrize()` over a test that calls `case.call_and_validate()`.
- Seed for deterministic CI: pass `--hypothesis-seed=<n>` so a CI failure reproduces locally.
- Auth/stateful: feed auth headers; enable `--experimental=stateful-only` style stateful runs when the spec declares links.

### Doctrine
- Run as a SEPARATE CI job against a running app (staging or an ephemeral instance - see Layer 3), not in the unit lane; it is slower and probabilistic.
- A property-test failure is a finding even if every example test passes - it found an input the developer's mental model missed. Triage by the existing P0..P3 taxonomy (a 500 on a schema-valid input is typically P1).
- Pin the Hypothesis seed in CI for reproducibility; record the minimal failing example (Schemathesis shrinks it) in the bug ticket.
- Schema quality gates this: a thin/wrong OpenAPI spec yields weak fuzzing. If the spec is poor, that itself is a finding handed to the API owner (Full-Stack Developer).
- License: MIT - clean, no copyleft. Methodology absorbed; tool invoked via CLI/lib, nothing vendored.

---

## Layer 2 - Stryker (mutation testing) [Apache-2.0]

Source: github.com/stryker-mutator/stryker-js (Apache-2.0, ~2,900 stars, updated 2026-06-06). Companion: stryker-net (.NET); mutmut / cosmic-ray (Python); PIT (JVM). Mutation testing injects small faults ("mutants") into the source - flip a `>` to `>=`, drop a `return`, negate a condition - then re-runs the suite. A mutant the suite still passes on ("survived") is a hole in your assertions.

### Why this is the real coverage metric
Line/branch coverage proves code was EXECUTED. It does not prove the test ASSERTED anything about the result. A test that calls a function and asserts nothing yields 100% line coverage and catches zero bugs. Mutation score (killed mutants / total mutants) measures whether the tests would actually catch a regression.

### How to run (JS/TS)
- `npx stryker init` then `npx stryker run`.
- Targets the existing runner (Vitest/Jest/Mocha) - it does not replace it, it re-runs it against mutants.
- Output: an HTML report listing survived mutants with file/line - each is a concrete "write an assertion here" task.

### Doctrine
- Mutation testing is EXPENSIVE (NxM: every mutant re-runs the suite). Do NOT run the full suite on every PR. Run it:
  - on changed files only in PR CI (Stryker incremental mode / `--since`), and
  - full-suite on a nightly/weekly schedule.
- Set a mutation-score threshold as a SECONDARY gate, layered on top of the existing MetaGPT coverage gate (>=80% line / >=70% branch). Start permissive (e.g. >=60% mutation score on critical modules) and ratchet up; an aggressive threshold on a legacy module just blocks everyone.
- Apply it where it pays: Tier-1 logic (payment, auth, money math, access control), not boilerplate/UI glue.
- This directly retires the standing red flag "coverage reported as goal vs meaningful paths covered" - mutation score is the meaningful-paths instrument.
- License: Apache-2.0 - permissive, no flag.

---

## Layer 3 - Testcontainers (real-dependency integration tests) [MIT / Apache-2.0]

Source: github.com/testcontainers/testcontainers-node (MIT, 2,500 stars, v12.0.1 2026-05-27) + cross-language: testcontainers-go (MIT, 4.8k), -dotnet (MIT, 4.3k), -python (Apache-2.0), -rust (Apache-2.0), -java. Spins up a throwaway Docker container (real Postgres / Redis / Kafka / MySQL / Elasticsearch / Selenium / any image) for the test run and tears it down after.

### Why this beats mock-only integration tests
The existing integration tier is WireMock / Prism / MSW - all mocks. Mocks encode the developer's BELIEF about the dependency and drift from reality: real SQL dialect quirks, real JSON/date serialization, real connection-pool behavior, real migration scripts. Testcontainers tests the actual boundary without a shared, polluted staging DB and without per-developer "works on my machine" databases.

### How to run (node example)
- `const pg = await new PostgreSqlContainer("postgres:16").start();`
- point the app at `pg.getConnectionUri()`, run migrations, run the test, `await pg.stop()`.
- v12 default wait strategy uses the image healthcheck when present, else `Wait.forListeningPorts()` - prefer images with a healthcheck so tests do not race startup.
- Use `@testcontainers/*` modules (postgresql, kafka, redis, etc.) for ready-made wrappers.

### Doctrine
- One container per test FILE or per worker, not per assertion - startup cost is real; reuse within a file, isolate across parallel workers (unique DB/schema per worker, per the existing parallel-isolation rule).
- Requires a Docker daemon in CI. The CI runner must have Docker (or a remote Docker host / `testcontainers cloud`). This is the main adoption cost - call it out in the test-strategy doc.
- Pin image tags to a digest or explicit version (e.g. `postgres:16.2`), never `latest` - matches the existing "pin versions / container isolation" environment-drift rule and the fleet SHA-pin doctrine.
- Pairs with Layer 1: run Schemathesis against an app wired to Testcontainers-backed real dependencies for the most honest fuzz run (the ephemeral instance Schemathesis doctrine refers to).
- License: MIT (node/Go/.NET) / Apache-2.0 (py/rust) - all permissive, no flag.

---

## Where these sit in the pyramid + CI

| Layer | Tier | CI job | Gate |
|---|---|---|---|
| Schemathesis | API (above integration) | separate "api-fuzz" job vs a running app | P0/P1 findings block; P2/P3 ticketed |
| Stryker | wraps unit | "mutation" job - incremental on PR, full nightly | mutation-score threshold on Tier-1 modules (secondary to line/branch gate) |
| Testcontainers | integration | runs inside the existing integration job (needs Docker) | same all-pass gate as integration |

Memory scope: log findings/insights from these layers under the `qa-engineer` memory scope key (flaky patterns, surviving-mutant hotspots, fuzz-found input classes) so they promote into rules.md per the self-learning protocol - do not cross-write into other employees' scopes.
