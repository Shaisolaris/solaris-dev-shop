# QA Engineer - Top-5 Verified Source Candidates (2026-06-13)

Scope: QA tooling landscape - E2E, unit, API/contract, load, test-data, coverage. All facts verified against GitHub + project sites on 2026-06-13. Gate-0 = grep of ACTUAL employee content (SKILL.md / rules.md / learnings.md / plugin.json), not the description blurb.

Doctrine notes already-mastered and intentionally NOT re-absorbed:
- **Playwright (test framework)** - mastered (Playwright Pro v0.6.0 + 6 workflows + flaky catalog). Already deep; nothing to add.
- **microsoft/playwright-mcp** - already a thin CONNECT (live-browser exploratory lane). No change.
- **grafana/mcp-k6** - already a CONNECT; k6 PATTERNS owned by performance-engineer (AGPL). No change.

---

## Candidate table

| # | Tool | URL | Stars | License | Last commit | Maintainer | Gate-0 verdict | Tag |
|---|------|-----|-------|---------|-------------|------------|----------------|-----|
| 1 | Schemathesis | https://github.com/schemathesis/schemathesis | 3,318 | MIT | 2026-05-26 (pushed) | schemathesis org (used by Netflix, SAP, Red Hat, IBM, JetBrains) | ABSENT - 0 hits for schemathesis / property-based / fuzz. Pact + WireMock/MSW present but no schema-driven negative/property generation. NET-NEW. | ABSORB |
| 2 | Stryker-JS (mutation testing) | https://github.com/stryker-mutator/stryker-js | ~2,900 | Apache-2.0 | 2026-06-06 | stryker-mutator org | ABSENT - "mutation" only as Playwright DOM mutation, never mutation TESTING. Coverage named as a gate (>=80% line / >=70% branch) but its quality never validated. NET-NEW; fixes the existing "coverage as goal vs meaningful paths" red flag. | ABSORB |
| 3 | Testcontainers (node + cross-lang) | https://github.com/testcontainers/testcontainers-node | 2,500 (node); 4.8k Go, 4.3k .NET | MIT (node/Go/.NET); Apache-2.0 (py/rust) | v12.0.1 2026-05-27 | testcontainers org (AtomicJar/Docker) | ABSENT - integration tests only reference WireMock/Prism/MSW (mocking). No real-dependency container fixtures. NET-NEW. | ABSORB |
| 4 | Vitest | https://github.com/vitest-dev/vitest | ~16,600 | MIT | v5.0.0-beta (2026-05); v4.1.x stable | vitest-dev / VoidZero (Vite team) | THIN - only "Jest" named (sharding). No Vitest, no unit-runner selection methodology. Concept-present but tool/methodology gap. | METHODOLOGY |
| 5 | faker-js | https://github.com/faker-js/faker | 15,363 | MIT | 2026-06-11 | faker-js org | THIN - "Faker" named once in a factories list. Test-data tier exists but no deterministic-seeding / locale / factory discipline. | METHODOLOGY |

---

## Per-candidate detail

### 1. Schemathesis - ABSORB (methodology)
- **What it adds:** Property-based / fuzz API testing driven directly from an OpenAPI or GraphQL schema. Auto-generates valid + adversarial inputs via Hypothesis; checks response-schema conformance, server crashes (5xx), validation-bypass, and stateful multi-step workflows. CLI + pytest integration + CI.
- **Why net-new:** The employee owns consumer-driven CONTRACT testing (Pact) and example-based API tests (Postman/Bruno/Supertest) but has no NEGATIVE-space coverage - "what does the API do with inputs the developer never thought to test." Schemathesis is the fuzz/property layer that closes that gap, the canonical 2026 tool for it.
- **License:** MIT (clean - no flag). Bundled as METHODOLOGY (patterns + CLI invocation), no source vendored.
- **Gate-0:** grep schemathesis = 0; property-based = 0; fuzz = 0. Confirmed absent.

### 2. Stryker-JS - ABSORB (methodology)
- **What it adds:** Mutation testing - injects faults (mutants) into source and checks whether the test suite catches them. Mutation score is the real measure of test EFFECTIVENESS; line/branch coverage only proves code was executed, not asserted. Stryker-JS for JS/TS; sibling stryker-net (.NET); mutmut / cosmic-ray (Python) for parity.
- **Why net-new:** The MetaGPT gate sets coverage thresholds (>=80% line / >=70% branch) and the red-flags list explicitly warns about "coverage reported as goal vs meaningful paths covered" - but the employee has no instrument to prove coverage is meaningful. Mutation score is exactly that instrument.
- **License:** Apache-2.0 (permissive - no flag).
- **Gate-0:** grep stryker = 0; mutation-testing = 0 (only Playwright DOM "mutation"). Confirmed absent.

### 3. Testcontainers - ABSORB (methodology)
- **What it adds:** Ephemeral, real-dependency integration tests - spin up a throwaway Postgres / Redis / Kafka / Selenium / any-Docker-image per test run, then tear down. Cross-language (node/Go/.NET/py/rust/java). Default wait strategy now keys off the image healthcheck (v12).
- **Why net-new:** The employee's integration tier is mock-only (WireMock / Prism / MSW). Mocks drift from reality; Testcontainers tests the real boundary (real SQL dialect, real serialization, real network) without a shared staging DB. Standard 2026 integration-test substrate.
- **License:** MIT (node/Go/.NET) / Apache-2.0 (py/rust) - all permissive, no flag.
- **Gate-0:** grep testcontainers = 0. Integration row mentions WireMock/MSW only. Confirmed absent.

### 4. Vitest - METHODOLOGY note
- **What it adds:** Vite-native unit/component test runner; ESM-first, fast watch, Jest-compatible API, browser mode. The default unit runner for any Vite/Vue/Svelte/modern-React stack in 2026.
- **Why thin:** The unit tier already exists; this is a tool-selection rule (pick Vitest for Vite stacks, Jest for legacy/RN, pytest/Go-test/etc by language) plus the `--shard` parity already noted for Jest. Captured as a one-paragraph methodology note.
- **License:** MIT.

### 5. faker-js - METHODOLOGY note
- **What it adds:** Realistic synthetic test data (names, addresses, finance, locale-aware). Pairs with the existing factory/fixture rule.
- **Why thin:** "Faker" is already named. The net-new is the DISCIPLINE: seed the generator for deterministic CI runs (faker.seed(n)), use locale data for i18n tests, keep generated data in factories not inline. One methodology note.
- **License:** MIT.

---

## Disposition
- **Deep reference (new file references/api-fuzz-mutation-integration.md):** Schemathesis + Stryker + Testcontainers (the three net-new TESTING LAYERS). Methodology only - no source bundled.
- **Methodology notes folded into rules.md:** Vitest (unit-runner selection) + faker-js (test-data seeding discipline).
- **No new CONNECT/MCP** added: none of the five ships a verified maintained MCP server as of 2026-06-13, so they are tool/methodology absorptions invoked directly via CLI/library.
