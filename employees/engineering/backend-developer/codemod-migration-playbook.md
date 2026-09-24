# Codemod-Driven Migration + Strangler-Fig + Renovate (methodology, license-safe, no copy-paste)

Powers the **Codebase Migration Plan** gig from the backend side. This is the "migrate a large/legacy codebase without a big-bang rewrite" engine. full-stack-developer carries the same playbook for smaller all-in-one projects; THIS file is the backend/server-side authority (Java/Spring, Node/TS APIs, Python, .NET). It composes with the existing API Design Reviewer gate (rules.md W8) and backend-testing-strategy.md (integration-first verification of every migration step).

## 0. Gate-0 (already had vs net-new)
- ALREADY HAD: uv/Ruff/Hono/sqlc modern toolchain (python-toolchain-and-typed-api-stack.md), JVM + NestJS language packs, API Design Reviewer weighted gate, integration-first testing with five exit doors, postgres-performance.
- NET-NEW (this file): the migration METHOD itself - mechanical migration via codemods (jscodeshift / OpenRewrite), incremental architectural migration via strangler-fig, and continuous dependency-upgrade orchestration via Renovate. The existing files tell you the target stack; this file tells you how to GET a legacy codebase there safely.

## 1. The three-layer migration model
A real migration has three independent layers - run them as separate, composable workstreams, not one monolith of risk:
- **Mechanical (syntax/API) changes** -> codemods (deterministic, reviewable, repeatable).
- **Architectural changes** (monolith -> services, framework swap, ownership moves) -> strangler-fig (incremental, behind stable URLs).
- **Dependency currency** (keeping deps moving so the gap never reopens) -> Renovate (continuous, automated PRs).
Each layer is gated by tests (backend-testing-strategy.md) and, for new/changed API surface, the API Design Reviewer scorecard.

## 2. Mechanical migration with codemods
A codemod rewrites code by transforming its AST, not by regex. It makes a large mechanical change (API rename, import move, deprecation fix) deterministic and reviewable instead of hand-editing thousands of files.
- **jscodeshift** (MIT, Meta) - the canonical JS/TS codemod toolkit: write a transform against the AST, run it across the tree with a dry-run (`-d -p`) first, review the diff, then apply. Many libraries ship official jscodeshift codemods (Next.js `@next/codemod`, React, MUI) - prefer the vendor's codemod over a hand-rolled one.
- **OpenRewrite** (Apache-2.0 core) - the JVM-and-beyond equivalent: declarative "recipes" run via Maven/Gradle (`mvn rewrite:run` / `gradle rewriteRun`). Has large migration recipe catalogs (e.g. Java 8/Spring Boot 2 -> Java 21/Spring Boot 3, security/static-analysis remediation). It can also wrap jscodeshift codemods via `rewrite-codemods` so a JVM shop drives JS codemods from the same pipeline.
  - LICENSE FLAG: OpenRewrite's open-source core recipes are Apache-2.0, but some recipe modules (notably `rewrite-codemods` / Moderne-authored recipes) ship under the **Moderne Source Available License (MSAL)**, not OSI-approved - and the Moderne SaaS that runs recipes at scale across many repos is a commercial product. **Recommend-only**: flag the MSAL recipes + paid SaaS to the host before depending on them in a paid engagement; the Apache-2.0 OSS recipes + local CLI cover most needs free.
- **Discipline:** always dry-run -> review diff -> run the test suite -> commit the codemod result as its own reviewable change, separate from behavioral changes. A codemod that the tests cannot vouch for does not ship.

## 3. Architectural migration with strangler-fig
For monolith decomposition, framework swaps, or platform moves where a big-bang rewrite is the trap. The strangler-fig pattern grows the new system around the old one and gradually routes traffic over, so the legacy system stays live the whole time and there is never a single cutover moment.
- **Mechanics:** put a routing/facade layer (gateway, reverse proxy, CloudFront/edge, or an in-app router) in front. New endpoints/components are built alongside the legacy ones behind the SAME external URLs + data. Route traffic to the new implementation incrementally (one endpoint / one bounded context at a time), behind feature flags, with rollback tested in staging. Decommission each legacy slice only after its replacement is proven in production.
- **Why it wins:** zero-downtime (old system keeps serving), reversible at every step (flag flip back), and risk is sliced into many small cutovers instead of one catastrophic one. Users never see a transition.
- **Sequencing:** pick the highest-value / lowest-coupling bounded context first; establish the facade + a parity test (old vs new return the same result) before routing any real traffic; migrate data with dual-write or backfill + verification (DBA coordination); only then shift traffic.

## 4. Dependency-upgrade orchestration with Renovate
Migrations rot if dependencies fall behind again. Renovate keeps them current automatically.
- **What it is:** an automated dependency-update bot that opens PRs across 90+ package managers (npm, Maven, Gradle, pip/uv, NuGet, Docker, etc.), with grouping, scheduling, automerge for low-risk updates, and merge-confidence signals.
- **LICENSE FLAG:** Renovate (the self-hosted CLI/community edition) is **AGPL-3.0** - copyleft with the network clause; safe to RUN against a client repo, but flag the AGPL posture to the host before embedding/modifying-and-hosting it as part of a product. Mend's hosted Renovate GitHub App is free; the commercial tier (merge-confidence, SSO, audit) is paid. **Recommend-only**: default recommendation is the free hosted App or the AGPL CLI as-is (run, don't fork-and-host); escalate the license question to the host for anything beyond that.
- **Use in a migration:** turn Renovate on early so the codebase stops drifting during the migration; group framework upgrades; pair major-version bumps with the relevant codemod (section 2) so the bump and its mechanical fixes land together; gate automerge on the test suite.

## 5. The migration plan deliverable + execution path
- **Deliverable:** a phased plan - inventory + risk map -> Renovate on (stop the drift) -> codemod the mechanical debt (layer 1) -> strangler-fig the architectural moves (layer 2), context by context, each with a parity test + flag + rollback -> decommission. Every phase has explicit test gates and (for API surface) the Design Reviewer scorecard.
- WIRED when host grants repo access + github-mcp: run codemods/OpenRewrite locally with dry-run-first, open the migration PRs, wire Renovate config. PLAN-ONLY otherwise: deliver the phased plan + codemod list + strangler-fig routing design + Renovate config template; never claim a repo change not made.
- License posture summary: jscodeshift MIT (clean); OpenRewrite core Apache-2.0 (clean), but `rewrite-codemods`/Moderne recipes are MSAL + the scale SaaS is commercial (flag, recommend-only); Renovate CLI is AGPL-3.0 (flag, recommend run-not-fork). All methodology here is Solaris voice, no copy-paste.
