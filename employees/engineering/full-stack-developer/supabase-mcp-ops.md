# Supabase MCP - operational layer (project ops, migrations, branching, diagnostics)

Absorbed from supabase-community/supabase-mcp (Apache 2.0, ~2.6k★, official Supabase community, verified 2026-06-13). The **coding** BaaS patterns (service_role vs anon key, @supabase/ssr cookie refresh, getUser() vs getSession(), Realtime cleanup, Edge Function Deno shape, Storage RLS + signed URLs) are in rules.md §BaaS and stay there. THIS file is the net-new slice: operating a Supabase project through the MCP - migrations, branching, diagnostics, codegen, and the safety modes around them. Server is host-installed (hosted HTTP `https://mcp.supabase.com/mcp`, or local CLI at `http://localhost:54321/mcp`); this is how full-stack uses it.

## Migrations: tracked DDL vs raw query (the rule that prevents schema drift)
- **`apply_migration` for any schema change (DDL).** It records the migration in the database so the change is versioned and reproducible. Never make a schema change via raw SQL - it won't be tracked and prod/dev will drift.
- **`execute_sql` only for non-DDL queries** (reads, data tweaks). If it changes the schema, it's the wrong tool.
- `list_migrations` / `list_tables` / `list_extensions` to know current state before changing it.

## Branching workflow (paid plan) - test schema changes before they touch prod
Treat the database like code with a dev branch:
1. `create_branch` → a dev branch seeded with production's migrations.
2. Develop + `apply_migration` on the branch; Edge Functions deploy to the branch too.
3. `merge_branch` to promote migrations + functions to production.
4. `rebase_branch` to pull production changes back onto the branch when prod moved (migration drift).
5. `reset_branch` to roll a branch back to a prior migration version.
This is the safe path the rules already call for ("test the migration on a data clone") - branching IS that clone, first-class.

## Diagnostics (use these instead of guessing why prod is broken)
- **`get_advisors`** - security + performance advisory notices (e.g. missing RLS, exposed tables, perf issues). Run it as a gate before shipping; the security findings are not optional.
- **`get_logs`** by service: `api`, `postgres`, `edge functions`, `auth`, `storage`, `realtime`. First stop when a specific surface misbehaves - pull that service's logs, don't speculate.

## Codegen + project wiring
- **`generate_typescript_types`** from the live schema → save to the repo and import. This is the canonical "DB → typed UI with no `any`" path the data-flow architecture demands. Regenerate after every schema migration.
- `get_project_url` + `get_publishable_keys` (prefer modern **publishable** keys over legacy anon) to wire the client. Never surface `service_role` here - server-only, per the BaaS rules.
- `search_docs` for version-correct Supabase docs before using an API you're unsure about.

## Safety modes (set these; don't run wide-open against prod)
- **`read_only=true`** by default when pointed at real data - executes queries as a read-only Postgres user and disables every mutating tool (apply_migration, deploy_edge_function, all branch ops, storage config, project create/pause/restore).
- **`project_ref=<ref>`** to scope the server to ONE project; without it the server can touch every project in the account.
- **`features=...`** to enable only the tool groups you need (e.g. `database,docs`) - smaller attack surface.
- **Don't connect to production; don't hand this MCP to end users** - it runs with developer permissions. Use a dev project with non-production data. Review every tool call before it executes (prompt-injection risk: a malicious row can instruct the LLM).

## When to reach for it
- Standing up / evolving a Supabase-backed feature → branch, apply_migration, generate types, get_advisors before merge.
- "Auth/storage/realtime is broken in prod" → get_logs for that service first.
- Security pass → get_advisors; fix RLS/exposure findings before deploy.
