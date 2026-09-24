# Modern backend toolchain - uv + Ruff (Python), Hono (TS edge API), sqlc (typed SQL)

Depth pass 2026-06-14. Net-new TOOLCHAIN methodology only. NO upstream code bundled; every tool below is host-installed by the developer or pinned in the project. Covers four current best-practice tools the employee named a stack for but had no toolchain doctrine on: the Python dependency+lint+format chain (uv, Ruff), a Web-Standards TS API framework (Hono), and compile-SQL-to-typed-code generation (sqlc).

Citation keys (this file): [uv] astral-sh/uv MIT (dual MIT/Apache-2.0) ~86k* released 2026-06 · [ruff] astral-sh/ruff MIT ~40k* 900+ rules · [hono] honojs/hono MIT ~30k* (Yusuke Wada) · [sqlc] sqlc-dev/sqlc MIT ~17.8k* rel v1.31.x 2026-04. All OSI-permissive.

Gate-0 against prior content: rules.md named the Python/FastAPI stack but specified only Pydantic v2 / SQLAlchemy 2.0 / Alembic / mypy - ZERO dependency-manager or linter/formatter doctrine; pip/poetry/black/flake8/isort never appeared. TypeScript rules named Fastify + NestJS as stacks but had no Web-Standards/edge framework and no SQL-codegen tool anywhere in engineering. All net-new.

---

## 1. Python project + dependency management with uv [uv] - ABSORB (MIT)

uv is the default Python project, dependency, and environment manager. It is one Rust binary that replaces pip + pip-tools + virtualenv + pipx + (most of) Poetry/pyenv. Reach for it on every new Python service and when taking over a requirements.txt / Poetry project.

- **One tool, one lockfile.** pyproject.toml declares dependencies; `uv lock` produces a cross-platform `uv.lock` (committed); `uv sync` makes the environment match the lock exactly. The lockfile is the source of truth - never hand-edit it, never `pip install` into a uv-managed env.
- **Reproducible installs as the contract.** `uv sync --frozen` in CI and in the Docker build: it fails if the lock is stale instead of silently resolving, so the image matches what was tested. Application images use `--no-dev` to drop test/lint deps.
- **Python version is managed too.** `uv python install 3.12` and a requires-python / .python-version pin remove the "works on my machine" interpreter drift; no separate pyenv needed.
- **Run without activating.** `uv run <cmd>` executes inside the project env (auto-syncing first), so scripts, tests, and CI steps never depend on a sourced venv. `uv tool install` / `uvx` replaces pipx for standalone CLI tools (ruff, pre-commit).
- **Speed is the adoption lever but not the rule.** It is the lockfile + frozen-CI discipline that matters; the 10-100x resolve speed is why the team will actually keep the lock fresh.
- **Migration path.** From pip: `uv pip compile` / `uv pip sync` are drop-in for a pip-tools workflow before a full move to `uv sync`. From Poetry: port [tool.poetry.dependencies] into PEP 621 [project].dependencies, then `uv lock`.
- **Docker pattern.** Copy pyproject.toml + uv.lock first, `uv sync --frozen --no-dev` to populate a cached layer, THEN copy source - so a code change does not bust the dependency layer. Use the official uv binary copied into a slim base, or uv's distroless image.
- **Red flags:** `pip install` inside a uv project; an uncommitted or stale uv.lock; CI resolving instead of `--frozen`; mixing Poetry and uv lock state in one repo.

## 2. Lint + format with Ruff [ruff] - ABSORB (MIT)

Ruff is the default Python linter AND formatter. One Rust binary replaces flake8 (plus its plugin zoo), black, isort, pydocstyle, pyupgrade, and autoflake - 900+ rules, native Black-compatible formatting.

- **Two commands cover the chain.** `ruff check` lints (and `--fix` auto-fixes the safe ones); `ruff format` formats (Black-compatible output, so adopting it does not churn an existing Black codebase). Drop black + isort + flake8 from the project once Ruff is in.
- **Config lives in pyproject.toml.** [tool.ruff] for line length / target version; [tool.ruff.lint] select/ignore to choose rule families (start with E,F,I = pycodestyle errors, pyflakes, import-sorting; add B bugbear, UP pyupgrade, S bandit-security as the bar rises). extend-select to layer on without losing defaults.
- **Make it enforcing, not advisory.** `ruff check` is a CI gate (non-zero exit fails the build); `ruff format --check` fails on unformatted code. Wire both into pre-commit (ruff-pre-commit hooks) so violations are caught before review, not in it.
- **Security overlap is a bonus, not the security gate.** Ruff's S (flake8-bandit) rules catch common issues (hardcoded-secret patterns, assert in prod paths, weak crypto calls) early - useful, but it does NOT replace the W8 OWASP review or dependency-CVE scanning.
- **Pairs with mypy, does not replace it.** Ruff is fast lint+format+import-hygiene; mypy (or ty/pyright) still owns type checking. Keep both in CI.
- **Red flags:** black/isort/flake8 still installed alongside Ruff (pick one - Ruff); `ruff check` run but never gated; formatting drift because `ruff format --check` is not in CI.

## 3. Web-Standards / edge TS APIs with Hono [hono] - ABSORB (MIT)

Hono is a small, fast, Web-Standards (Fetch API) TypeScript framework that runs the SAME code on Cloudflare Workers, Deno, Bun, AWS Lambda, and Node. It joins Fastify and NestJS as a supported Node/TS API stack; pick it for edge/serverless and Workers/Bun deployments.

- **When Hono vs Fastify vs NestJS:**
  - **Hono** - edge/serverless targets (Cloudflare Workers, Lambda, Bun, Deno), small-to-mid APIs, BFF/proxy layers, anywhere portability across runtimes matters. Built on Web Request/Response, so it is also the natural fit when the rest of the stack is Web-Standards.
  - **Fastify** - high-throughput long-running Node servers on traditional hosts; rich plugin ecosystem; schema-first JSON performance.
  - **NestJS** - large teams wanting opinionated DI/modules/decorators on top of Node.
- **Type-safe routing + validation.** Define routes with a validator (@hono/zod-validator or the typebox validator) so the handler's `c.req.valid('json')` is fully typed - the W1 "validate at the boundary" rule, expressed in the framework. Compose with `app.route()` for modular mounting.
- **RPC mode for end-to-end types.** Hono can export an AppType the client consumes via `hc<AppType>()`, giving compile-time-checked client calls without a separate OpenAPI codegen step. Use @hono/zod-openapi when you ALSO need a published OpenAPI doc (still required for external consumers per the production-readiness checklist).
- **Middleware discipline.** Built-in middleware for CORS, JWT auth, logger, secure-headers, rate-limit-friendly hooks; apply auth/security middleware at the router boundary, not per-handler, so no endpoint is accidentally unguarded (ties to W8 BOLA review - object-level authz still lives in the handler, middleware only proves authentication).
- **Runtime caveats.** Edge runtimes are NOT full Node: no raw TCP, limited Node built-ins, CPU/time budgets per request. Long-running jobs, heavy crypto, or persistent connections belong on a Node/Fastify tier or a queue - do not force them into a Worker. Keep secrets in the platform's binding/secret store, never in code.
- **Graceful shutdown / event-loop rules from the Node section still apply** when Hono runs on the Node adapter.
- **Red flags:** porting a CPU-heavy or long-lived workload into an edge Worker; per-handler auth instead of boundary middleware; shipping RPC types as the only contract for a third-party consumer (publish OpenAPI too).

## 4. Compile SQL to typed code with sqlc [sqlc] - ABSORB (MIT)

sqlc generates fully typed data-access code from hand-written SQL plus the schema. You write real SQL in .sql files; sqlc parses them against the schema and emits typed functions/models in Go, Kotlin, Python, or TypeScript. It is the typed-SQL alternative to a runtime ORM (and complements the existing SQLAlchemy/Active Record/Prisma stacks rather than replacing the team's chosen ORM wholesale).

- **The workflow.** Three inputs: schema DDL, queries in .sql with `-- name: GetUser :one` annotations, and sqlc.yaml config. `sqlc generate` emits typed code; `sqlc vet` runs lint rules (and can run queries against a real engine to catch invalid SQL at build time). Regenerate on every schema/query change; commit the generated code OR generate in CI - decide once and gate it.
- **Why it earns its place.** The SQL is checked against the actual schema at generate time, so a column rename or type change breaks the build, not production. No N+1-by-accident from lazy ORM relations - you see exactly the query that runs. Result rows and params are typed end to end.
- **Query annotations are the contract:** :one (single row), :many (slice), :exec (no rows), :execrows (affected count), :batchexec (batched). Name queries by intent; one file per aggregate/table keeps it reviewable.
- **Migrations stay separate.** sqlc reads the schema; it does NOT manage migrations - keep Alembic/Flyway/Atlas/golang-migrate as the migration tool, and point sqlc at the same DDL so generated code and live schema cannot drift.
- **Fits the engines we use.** First-class Postgres (pgx / database-sql) and MySQL; SQLite supported. Plugin codegen targets cover Go/Kotlin/Python/TypeScript.
- **When NOT to reach for it.** Highly dynamic query shapes (filters assembled at runtime), heavy use of an ORM's identity-map/change-tracking, or a team standardized on Prisma/SQLAlchemy - sqlc shines for explicit, static, performance-sensitive queries; mixing it in selectively (hot paths) is a valid pattern.
- **Red flags:** generated code edited by hand (it is overwritten next generate); schema fed to sqlc drifting from the migration tool's DDL; `sqlc generate` not run/checked in CI so stale types ship; using sqlc AND an ORM for the same queries without a clear boundary.

---

## Boundary notes
- DBA still owns schema-at-scale, index strategy, and pg_stat_statements / hypopg tuning (see postgres-performance.md); sqlc consumes the DDL the DBA blesses.
- DevOps owns the CI runner and image registry; this file owns what the Python/TS build STEP does (uv sync --frozen, ruff gates, sqlc generate check).
- No code from any source repo is vendored here; tools are installed by the developer/host and pinned per project.
