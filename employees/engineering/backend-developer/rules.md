# Backend Developer - Rules (Active Methodology)

Last revised: 2026-06-09 (deep-absorption rebuild from real sources - see plugin.json absorbed_from)
Lineage: split from full-stack-developer 2026-05-18; inherits its stack-defaults, api-design, auth-patterns, minimal-change-mode.

Supported languages now include Java 17+ (Spring Boot 3.x, Quarkus 3.x LTS) + JPA/Hibernate and NestJS (TypeScript). For any Java/Quarkus/JPA or NestJS job, load jvm-and-nestjs-language-packs.md - it carries the language-specific idioms, security, TDD slices, verification loops, and the java-reviewer + java-build-resolver gates (the generic W1-W8 doctrine still applies on top). Detect the Java framework from pom.xml/build.gradle FIRST.

## Core principles
- **Data model precedes the API precedes the UI.** Schema design is the foundation; get it wrong and everything downstream is leveraged pain.
- **Every external call gets a timeout budget, a retry policy with backoff, and an idempotency requirement - defined up front, not after the first outage.** (msitarzewski backend-architect)
- **Contracts are machine-readable.** OpenAPI/AsyncAPI/protobuf for every public and service-to-service API; backwards compatibility via explicit versioning + deprecation windows + contract tests. (msitarzewski backend-architect)
- **Follow the design verbatim.** When implementing against a spec, never change the data structures/interfaces and never call members that don't exist in the design - push back on the spec instead. (MetaGPT WriteCode rules)
- **Smallest diff that solves the problem.** Every changed line must be justifiable by the task. Three similar lines beat a premature abstraction - extract at the 4th occurrence. (msitarzewski minimal-change-engineer)
- **Idempotency at the I/O boundary.** Every retryable POST gets an idempotency key. Every webhook handler runs twice eventually.
- **Types at the contract surface.** Zod / Pydantic v2 / FluentValidation / Laravel form requests on every request+response. "Make impossible states impossible." (lodetomasi typescript-sage)
- **Simplicity over architecture-astronautics.** Monolith / modular monolith / microservices / serverless chosen by team size, domain boundaries, operational maturity, and scaling need; microservices ONLY when independent deployment, ownership, or scaling justifies the operational complexity. Pick the simplest scaling model that satisfies current + near-term load, then document the path to horizontal. (msitarzewski backend-architect)
- **API structure must not mirror the database schema.** (wshobson api-design-principles)
- **Match the codebase.** Read 3 surrounding files before editing; inherited code runs in minimal-change mode.

## W1. API design workflow (wshobson api-design-principles + checklist; msitarzewski contract governance)
Run BEFORE implementation, in order:
1. **Model resources as plural nouns**, never verbs. Shallow nesting only - more than 2 levels means flatten (`/order-items/{id}/reviews`, not `/users/{id}/orders/{oid}/items/{iid}/reviews`).
2. **Map methods + status codes exactly:** GET (safe, idempotent) → 200; POST create → 201 + `Location` header; PUT full replace (idempotent) → 200; PATCH partial → 200; DELETE (idempotent) → 204, or 409 Conflict when blocked by references. 400 malformed / 401 missing auth / 403 insufficient perms / 404 / 422 validation / 429 rate-limited / 500.
3. **Paginate every collection endpoint.** Default page size 20, max enforced 100. Offset response `{items, page, page_size, total, pages}`; cursor-based `{items, next_cursor, has_more}` for large or fast-moving datasets.
4. **Standardize once, reference everywhere:** filtering `?status=active`, sorting `?sort=-created_at` (minus = desc, comma = multi), search `?q=`, sparse fieldsets `?fields=id,name`. Error envelope, enum values, pagination, idempotency keys, and correlation IDs are defined ONCE in the contract and reused across all endpoints. (msitarzewski)
5. **Version from day one.** URL versioning (`/api/v1/...`) is the Solaris default - explicit and easy to route; header versioning only when a client demands clean URLs. A breaking change forces a version bump.
6. **Rate limits on the contract:** `X-RateLimit-Limit/Remaining/Reset` headers, 429 + `Retry-After`. Mandatory on auth/signup/payment endpoints.
7. **Specify per endpoint:** auth requirement, timeout, retry semantics, rate limit, idempotency rules. (msitarzewski: "specify timeout, retry, rate limit, and authentication semantics for every API")
8. **Gate with the design-review pipeline** (lint → breaking-change detection → weighted scorecard - see §API Design Reviewer below) before dev handoff.
9. **GraphQL variant:** schema-first; DataLoader mandatory (N+1); Relay cursor connections; mutation payloads carry structured errors; `@deprecated` for migrations; query depth limiting + complexity analysis; introspection hardened off in prod; field-level authz. (wshobson graphql-architect)

## W2. Data modeling + migrations (msitarzewski backend-architect; VoltAgent backend-developer)
- Postgres conventions: UUID PKs (`gen_random_uuid()`), `TIMESTAMP WITH TIME ZONE` always, soft delete via `deleted_at`, CHECK constraints for invariants (`price >= 0`), partial indexes for the active subset (`WHERE deleted_at IS NULL`), GIN tsvector index for text search.
- **When** changing a critical data model → zero-downtime expand-and-contract: expand schema → dual write → backfill → switch reads (with fallback) → contract. Plan backfill, dual writes, read fallback, and rollback BEFORE the change; validate with reconciliation checks + audit logs. (msitarzewski)
- **When** new migration → forward + rollback both, version-controlled, language-standard framework only (Laravel migrations / Alembic / Prisma / EF Core). Test on staging with prod-shaped data.
- **When** query > 100ms or hits > 1K rows → EXPLAIN ANALYZE, add index deliberately, verify improvement, loop in DBA.
- Connection pooling configured explicitly; transactions with rollback paths; read replicas + backup/recovery are part of the design, not afterthoughts. (VoltAgent)
- N+1 is the default ORM mistake - more than 3 queries in a loop → eager-load or batch.

## W3. Authentication & authorization (wshobson backend-architect; VoltAgent specialists)
- **Never roll your own.** Auth0 / Clerk / Supabase / Laravel Sanctum-Passport-Breeze / OAuth2+JWT per stack.
- Laravel: **Sanctum** for first-party SPA + mobile tokens; **Passport** only when you genuinely need OAuth2 server flows. (VoltAgent laravel-specialist)
- FastAPI: OAuth2 + JWT with scopes via dependency injection; auth deps are yield/function dependencies so tests can override them. (VoltAgent fastapi-developer)
- JWT discipline: validate signature + claims + expiry; refresh-token rotation; never store secrets client-readable. API keys get rotation + quotas. (wshobson backend-architect)
- 401 = unauthenticated, 403 = unauthorized - never interchangeable. RBAC default; ABAC when policy complexity demands it.
- Service-to-service: mTLS or signed tokens; least privilege per service.
- Passwords: Argon2 or bcrypt only. (VoltAgent node-specialist)
- Audit-log sensitive operations.

## W4. Queues, background jobs, sagas (VoltAgent backend-developer + laravel-specialist; wshobson saga-orchestration)
- Stack defaults: Horizon (Laravel) / BullMQ (Node) / Celery+Redis (Python). Jobs are idempotent; retry with exponential backoff + jitter.
- Every queue integration ships with: producer/consumer pattern declared, DLQ handling, idempotency guarantee, replay capability, monitoring/alerting. (VoltAgent backend-developer)
- Laravel jobs: design for failed-job handling from the start; use batching + chaining for pipelines; Horizon for monitoring. (VoltAgent laravel-specialist)
- **When** a workflow spans multiple services without 2PC → saga. Rules (wshobson saga-orchestration):
  - Every step idempotent - commands replay on broker reconnect.
  - Compensations are the most critical code path; write them first, test them by injecting failure at each step index.
  - `saga_id` correlation ID flows through every event and log line; log every state transition (`saga_id`, `step`, `old → new`).
  - Per-step timeouts, never one global timeout. No synchronous calls inside saga steps.
  - A partially-executed step still needs compensation.
  - Compensation handlers ALWAYS publish completion - if the underlying op was already rolled back, treat as success (else sagas stick in COMPENSATING forever).
- Event sourcing (only when audit trail / temporal queries justify it): events are immutable facts - never delete or modify; version events from day one; idempotent event handlers; plan for projection rebuilds. (wshobson event-sourcing-architect)
- Webhooks: verify signature first → idempotency-store the event ID → queue for async processing. Events arrive out of order; design for it.

## W5. Error handling, resilience, observability (wshobson backend-architect; msitarzewski backend-architect)
- Error envelope: structured `{ error: { code, message, details } }` with STABLE error codes the frontend can branch on; field-level validation errors; timestamps. No bare throws - include what was attempted, the IDs involved, the upstream cause.
- Never 200 OK with `{"error": ...}` in the body.
- Resilience per external dependency: timeout + deadline propagation, retries with exponential backoff + jitter + a retry budget, circuit breaker on repeated failure, bulkhead isolation for pools, graceful degradation path (cached/fallback response). (wshobson backend-architect)
- Health checks: liveness + readiness endpoints minimum; deep health checks for dependencies.
- Logging: structured JSON, log levels, correlation/request IDs on every line, tenant/user context where appropriate, PII redacted. (msitarzewski: stable error codes in logs too)
- Metrics: RED (Rate, Errors, Duration) per endpoint; SLIs/SLOs for latency, availability, saturation, error rate. Default SLO: p95 < 200ms for client work (msitarzewski); 100ms p95 for performance-tier APIs (VoltAgent).
- Tracing: OpenTelemetry across gateway → services → queues → DB.
- **Alert on user-impacting symptoms, not infrastructure resource usage.** (msitarzewski)

## W6. Testing (wshobson test-automator + tdd-orchestrator; VoltAgent coverage bars)
- Order of operations: detect the project's existing framework + conventions → identify testable units + integration points → design cases covering happy path, edge cases, error handling, boundary conditions → write in project style → verify runnable with clear failure messages → report untested risk areas. (wshobson test-automator)
- Organization: unit tests per source file; integration tests per endpoint/service interaction; E2E per user journey.
- Coverage floor ≥ 80%; stretch 85% (Laravel), 90% (FastAPI) per VoltAgent specialist bars. Coverage of error paths counts double in review.
- TDD (red-green-refactor) by default on NEW business logic - outside-in for features, inside-out for libraries; anti-patterns to reject: test-after, partial coverage theater. (wshobson tdd-orchestrator) On inherited code: minimal-change mode wins; add characterization tests before touching.
- FastAPI: pytest + httpx AsyncClient + dependency overrides + factories. Laravel: Pest feature tests + database testing. (VoltAgent)
- Architecture testability: use-case tests run against in-memory adapters - if they require a running database, the boundaries are wrong. (wshobson architecture-patterns)
- Saga/queue tests: inject failure at every step index; assert compensation completes.
- **Integration-first + outcome-driven testing → `backend-testing-strategy.md`.** Component tests over a real DB in-process before unit tests; assert on the five backend exit doors (HTTP response, state-via-public-API, external call, MQ message, observable log/metric) not on internals; deny un-mocked outbound calls; MQ test checklist (ack/nack, batch, poisoned message, idempotency, reconnect). (goldbergyoni/nodejs-testing-best-practices, methodology-only)

## W7. Spec→code SOP (MetaGPT Engineer role - roles/engineer.py + actions/write_code.py)
When implementing against a delivered spec (delivery-lead handoff, architect design, client contract):
1. **Assemble the coding context per file:** the design doc (data structures + interfaces), the task description, existing legacy code, debug/test logs, bug feedback. Architect + PM artifacts outrank everything; pull other source files only if currently needed.
2. **Task decomposition test:** if you can't write a file without spelunking other files, the task definition is too vague - push back for a clearer interface definition rather than guessing.
3. **Write rules:** one file at a time; COMPLETE code - no TODOs left behind; always set defaults; strong types + explicit variables; never change the designed data structures/interfaces; never use members that don't exist in the design; import before use; verify no class/function required of this file is missing.
4. **Self-review (6 questions, per file):** (1) implemented per requirements? (2) logic fully correct? (3) follows the designed data structures + interfaces? (4) every function actually implemented? (5) all dependencies imported? (6) methods from other files reused correctly? Verdict LGTM/LBTM - LBTM means rewrite before handing off. (MetaGPT WriteCodeReview)
5. **Completion check:** summarize what was built vs. the task list; ask "does this log indicate anything left to do?" - if yes, loop with the explicit todo list; if no, mark done. Keep traceability: each file records which design/task docs it implements.
6. **Artifact discipline (wshobson feature-development):** each phase writes its output file before the next phase starts - requirements → design → code → tests; never rely on conversation memory; stop at phase checkpoints for approval; halt on failure, never silently continue.
- Requirements intake = one question at a time: problem statement, acceptance criteria, explicit OUT-of-scope, technical constraints, dependencies. (wshobson feature-development)

## W8. Review gates (wshobson security-auditor + performance-engineer; msitarzewski minimal-change)
- Security review findings format: Severity (Critical/High/Medium/Low) + OWASP category + file:line + issue with attack vector + concrete fix with code. End with counts by severity + top-3 priority fixes. Scope: **OWASP API Security Top 10 (2023)** - call out **BOLA / broken object-level authorization** by name (the #1 API risk: does every record-fetch check the caller owns/may-see that object, not just that they're logged in?), broken function-level authz, broken object-property-level authz / mass assignment, unrestricted resource consumption - plus the web OWASP Top 10, JWT validation, privilege escalation, SQLi/command injection/path traversal/SSRF/prototype pollution, secrets handling, rate limits, CORS/CSRF, dependency CVEs.
- Pre-release API checklist deltas (shieldfy API-Security-Checklist, MIT): **pin the JWT algorithm server-side** (reject `alg:none` and HS/RS confusion); don't expose sequential/auto-increment IDs in URLs (UUID/ULID); force request + response `Content-Type`; return **generic 5xx bodies** - never leak stack traces, framework banners, or SQL to the client. Authoritative deep-dives: OWASP Cheat Sheet Series (REST Security, Authn, Authz, JWT) - link and attribute, CC-BY-SA, do not copy in.
- Performance review impact bands: Critical >500ms, High 100-500ms, Medium 50-100ms, Low <50ms. Every finding states the TRADEOFF of the fix; end with recommended SLOs/budgets for the feature.
- Minimal-change PR discipline: a bug-fix PR contains only the bug fix; out-of-scope findings become listed follow-ups, never sneak edits; walk the diff line by line - "does the task require this exact line?"
- Prototype mode (msitarzewski rapid-prototyper) is explicitly NOT production mode: a validation prototype skips the production-readiness gate but must be labeled "prototype - not production" and never silently promoted. Promotion re-enters the standard lane (SKILL.md "Right-size the process"). Tiny one-line fixes likewise skip the heavy gates but never skip contract/auth/validation/secret safety.

## Production readiness checklist (VoltAgent backend-developer - run before any deploy handoff)
- OpenAPI documentation complete and matching implementation
- Database migrations verified (forward + rollback)
- Configuration externalized; environment validated on startup; secrets strategy documented
- Load tests executed against realistic profiles
- Security scan passed
- Metrics exposed + health endpoints live
- Operational runbook ready; rollback path documented (DevOps refuses the deploy without one)

## Stack-specific quick rules (VoltAgent specialists; lodetomasi maxims)
- **Laravel:** PHP 8.2+ type declarations everywhere; API Resources for all responses; action classes + service layer over fat controllers; custom casts for value objects; eager loading audited per endpoint; Octane + route/view caching for perf tiers.
- **Node:** graceful shutdown handlers mandatory; never block the event loop - streams over buffering; AsyncLocalStorage for request context; `for...of`/`Promise.all` not `forEach` for async; npm audit in CI.
- **TypeScript:** discriminated unions + type guards at boundaries; branded types for IDs; strict mode; eliminate `any` deliberately. (lodetomasi typescript-sage)
- **TS API frameworks + typed SQL (see `python-toolchain-and-typed-api-stack.md`):** Hono is a supported Web-Standards/edge API framework alongside Fastify/NestJS - pick it for Cloudflare Workers / Bun / Lambda / Deno and portable BFF layers (typed zod-validator routes, RPC types, boundary auth middleware). sqlc compiles hand-written SQL to typed Go/Kotlin/Python/TS code (schema-checked at build time; migrations stay in Alembic/Flyway/Atlas).
- **Python/FastAPI:** Pydantic v2 models for every request/response; yield-dependencies for DB sessions; SQLAlchemy 2.0 async + Alembic; type hints + mypy. (VoltAgent fastapi-developer, lodetomasi python-alchemist)
- **Python toolchain (see `python-toolchain-and-typed-api-stack.md`):** uv is the default project/dependency/env manager (one `uv.lock`, `uv sync --frozen` in CI/Docker, managed interpreter); Ruff is the single linter+formatter (replaces flake8/black/isort/pydocstyle/pyupgrade), gated in CI + pre-commit. Both pair with mypy, do not replace it.
- **Django:** ORM with select_related/prefetch_related discipline; DRF serializers typed; admin is not an API.
- **Rails:** Active Record scopes; Sidekiq/SolidQueue jobs with idempotency; Russian-doll caching tiers. (VoltAgent rails-expert)

## Red flags
- Card data hitting your server - PCI scope violation
- Webhook handler without idempotency - double-processed events
- Saga step making synchronous service calls, or compensation without test coverage
- New required field added to an existing API response/request - breaking change without version bump
- Raw SQL string concatenation; plaintext secrets in repo (rotate + git-history clean)
- Missing rate limit on auth/signup/payment endpoints
- 200 OK with error in body; error responses without stable codes
- N+1 in production; query > 100ms unexamined
- Migration without rollback; critical-model change without expand-and-contract plan
- "While I'm here" refactors inside bug-fix PRs (minimal-change violation)
- Alerts firing on CPU instead of user-impacting symptoms
- Framework decorators in domain entities; all logic living in controllers (wshobson architecture-patterns)
- Cron in a single process - no observability, single point of failure

## Standing gotchas
- Laravel `$wpdb` returns strings - cast types
- Prisma + MySQL UUIDs - `@default(uuid())` + `@id`; MySQL has no native UUID
- Async + forEach - `forEach` doesn't await; use `for...of` or `Promise.all(map)`
- Laravel + MySQL JSON columns - query with `->` accessor; cast to `'array'`
- Prisma on Railway - `migrate deploy`, never `migrate dev`, in production
- Bluehost opcache - doesn't auto-invalidate; post-deploy cache clear required
- Lambda + RDS = connection storm without RDS Proxy
- Always store UTC, convert at presentation
- Stripe webhooks arrive out of order - design for it
- Temporal/durable workflows: workflow code must be deterministic - `workflow.now()` not `time.time()`; I/O lives in activities (wshobson temporal-python-pro)

## Cross-references
- **frontend-developer** - API consumption side
- **database-administrator** - schema at scale, query tuning, RLS surface on Supabase; reviews new tables > 3 columns and any query > 1K rows
- **devops-engineer** - deployment + CI/CD; refuses deploys without rollback path
- **security-auditor** - review before any customer-facing endpoint (W8 format)
- **performance-engineer** - owns diagnosis order: queries → N+1 → caching → infrastructure
- **payments-specialist** - Stripe patterns; never accept card data
- **full-stack-developer** - generalist coordinator; owns client-side BaaS surface (auth flows, SSR, Realtime, Storage)

---

## BaaS / Supabase server-side patterns (added 2026-05-29, retained)

When the project uses Supabase as BaaS and has a separate Node / Python / PHP / .NET backend tier (not pure Edge-Function-only - that's full-stack-developer's lane), this employee owns the server-side SDK integration. Postgres + RLS surface = DBA; client-side auth flow = full-stack-developer.

- **When** elevated privileges needed (admin tasks, scheduled jobs, sync) → `service_role` key from a server-only secret store. Never in bundles, logs, or error responses.
- **When** acting AS a user → forward the user's JWT, build the client with `setSession({ access_token, refresh_token })`, let RLS enforce permissions. The secure default.
- **When** building an Edge Function → `Deno.serve()` shape, Zod-validated input, typed response, structured JSON logs; same rate-limit/idempotency/signature discipline as any HTTP handler.
- **When** DB-tight work (transactional multi-row writes, complex aggregations) → SQL function + `supabase.rpc()`. Composing it in TS causes consistency bugs on retries.
- **When** webhooks write to Supabase → service_role client + signature verification + idempotency-store the event ID.
- **When** new authz need surfaces → file an RLS policy change with DBA; no backend `if (user.role === 'admin')` bypasses.
- Red flags: service_role in any log/response; always-service_role backends (defeats RLS); multi-table writes composed in TS.

Source: supabase/agent-skills (MIT, verified 2026-05-29).

---

## API Design Reviewer pipeline (Shai laptop skill, absorbed 2026-06-04; operationalized 2026-06-13)

Run on any REST contract BEFORE dev handoff. Optional automation scripts (api_linter.py, breaking_change_detector.py, api_scorecard.py) live in the snapshot `solaris/archives/shai-laptop-skills-2026-06/api-design-reviewer/`; **this section is the self-contained procedure that works with or without them** - if the snapshot isn't mounted, run the same checks by hand against the OpenAPI doc.

**1. Lint** (each violation = a fix item): resources kebab-case (`/user-profiles`), fields camelCase; reject `/getUsers`, `/user_profiles`; method+status-code compliance (W1.2); URL shapes (collection / item / nested ≤2 / action-POST / query filters); consistent error envelope; every shape documented.

**2. Breaking-change detection** vs the previous contract - diff the two OpenAPI docs (script if available, else read both). A hit on ANY of these is breaking and forces a major version bump + deprecation window:
   - endpoint removed or path changed; method removed
   - response field removed / renamed / retyped; enum value removed
   - request: a new REQUIRED field, or a previously-optional field made required, or a type narrowed
   - success status code changed; error code semantics changed
   Additive-only changes (new optional field, new endpoint, new enum value the client tolerates) are non-breaking → minor bump.

**3. Weighted scorecard - explicit formula.** Score each axis 0-100 against its rubric, then:
   `total = 0.30*consistency + 0.20*documentation + 0.20*security + 0.15*usability + 0.15*performance` (result is 0-100).
   - **consistency** (start 100, −10 per lint category violated): naming, status codes, error envelope, pagination shape, filter/sort params all uniform.
   - **documentation**: OpenAPI present (+40), every endpoint has request+response examples (+30), every error response documented (+30).
   - **security**: auth specified per endpoint (+30), rate limits on auth/payment/signup (+25), input validation declared (+25), no secrets/PII in examples or error bodies (+20).
   - **usability**: predictable URLs (+30), pagination on all collections (+25), helpful stable error codes (+25), correlation-ID header (+20).
   - **performance**: pagination caps enforced (+30), cache headers where applicable (+25), no obvious N+1-inducing shape (+25), payload sized (no over-fetch) (+20).
   **PASS bar: total ≥ 80 AND security ≥ 16/20 (i.e. security axis ≥ 80).** Either below bar ⇒ fix before handoff, do not ship the contract.

**4. Versioning:** URL versioning (`/api/v1/`) is the default; header/media-type only when a client demands clean URLs.

Define enum values + error envelope ONCE, referenced everywhere. If there's a `/start`, there must be a `/submit` or `/complete`. Ties into delivery-lead's spec-lock + QA contract-testing gate.

**External authorities (cite, don't copy):** the rule taxonomy mirrors Zalando's RESTful API Guidelines (CC-BY-4.0) - MUST/SHOULD/MAY severity and RFC 9457 `application/problem+json` are their conventions; use RFC 9457 as the interop error format when a client needs a standard one rather than our custom envelope.

---

## Cross-employee integration patterns (retained)

(Org-wide catalog: `meta/chief-of-staff/references/cross-employee-integration-patterns.md`.)

- **↔ Frontend:** new endpoint handoff = Zod/Pydantic schema (req+res), verb, auth, rate limit, idempotency rules, example payload + curl, error shapes with stable codes. Incomplete if frontend has to ask follow-ups.
- **↔ DBA:** reviews any new table > 3 columns or new index BEFORE deploy; EXPLAIN ANALYZE on queries > 1K rows; language-standard migration frameworks only.
- **↔ Security auditor:** 9-dimension secure-code pass before customer-facing endpoints; PCI-scope check via security-auditor for payment endpoints.
- **↔ DevOps:** deployment recipe (env vars, migrations, observability hooks) + rollback path before deploy.
- **↔ Performance engineer:** bring slow query log + trace + load test report when p95 > target.

---

## Connected MCP servers (host-installed)

### Postgres MCP Pro - deterministic perf/index/health (ABSORB: crystaldba/postgres-mcp, MIT, ~2.4k★)
Full methodology in `postgres-performance.md`. The short version: when tuning Postgres, **use deterministic tools, not LLM guesses** - `pg_stat_statements` to find real slow queries, `hypopg` to simulate indexes before writing them, the Anytime greedy search with a storage cost-benefit bar (≈10x space for 100x speed), and the PgHero-derived health checks (index/buffer-cache/connection/**vacuum-wraparound**/replication/constraint/sequence). Run against real data in **restricted** (read-only, time-capped) mode; reserve **unrestricted** for throwaway dev DBs. Host installs `crystaldba/postgres-mcp` (Docker or pipx) with a `DATABASE_URI`; user must `CREATE EXTENSION pg_stat_statements; CREATE EXTENSION hypopg;`. DBA still reviews new indexes/tables per the existing handoff rule.

### Redis MCP - cache / queue / rate-limit / pubsub inspection (CONNECT: redis/mcp-redis, MIT, ~530★, official)
The official Redis MCP server lets this employee operate a live Redis from inside the workflow.
- **What it does:** strings/hashes/lists/sets/sorted-sets/streams CRUD, key inspection + TTL, pub/sub, and vector-set operations against a running Redis/Redis Stack instance.
- **When to call it:** debugging a cache (is the key there? what's its TTL? why is it stale?), inspecting a queue/stream backlog, verifying a rate-limiter counter, checking session/lock state, or sanity-checking pub/sub fan-out - i.e. the Redis side of the queue/cache patterns already in W4 and the perf workflow.
- **When NOT to:** as the app's data path. It's an operational/inspection tool for the developer, not a substitute for the application's own Redis client.
- Host installs `redis/mcp-redis` and supplies the Redis connection URL (and credentials for managed Redis). No code is vendored here.
