# MCP Toolbox for Databases - multi-DB tool patterns

Absorbed from googleapis/mcp-toolbox (formerly genai-toolbox; Apache-2.0, ~15.6k stars, commit main @ 2026-06-13). Net-new for data-engineer: a vendor-neutral framework for exposing MANY databases to agents through governed, structured tools - the layer between "agent wants data" and "agent runs raw SQL on prod". Complements the existing dbt MCP (which is transformation-tier); this is the data-access-tier tool factory.

## Two modes
1. **Prebuilt tools (build-time, fast path):** `toolbox --prebuilt=<db>` instantly exposes generic tools like `list_tables` / `execute_sql` for exploration from any MCP client (a coding agent, Gemini CLI, Codex). Use for ad-hoc data exploration, not for production agents.
2. **Custom tools framework (run-time, the production pattern):** define purpose-built, parameterized, least-privilege tools in `tools.yaml`. This is what you ship for a real agent - never hand a production agent generic `execute_sql`.

## Supported sources (one config surface, many engines)
Google Cloud: AlloyDB, BigQuery, Cloud SQL (Postgres/MySQL/SQL Server), Spanner, Firestore, Dataplex/Knowledge Catalog. Other: PostgreSQL, MySQL, SQL Server, Oracle, MongoDB, Redis, Elasticsearch, CockroachDB, ClickHouse, Couchbase, Neo4j, Snowflake, Trino, and more. The value: ONE tool-definition grammar across the whole estate instead of N bespoke integrations.

## tools.yaml grammar (the durable pattern)
- **sources** - connection definitions (`kind: source`, `type: postgres|bigquery|...`, host/db/user/secret). Keep secrets in env/secret-manager, never inline in committed yaml.
- **tools** - the actions an agent may take (`kind: tool`, `type: postgres-sql`, bound to a `source`, with typed `parameters` and a parameterized `statement` using `$1`/named params). This is the safety mechanism: the agent calls a named tool with typed args - it does NOT author arbitrary SQL. Parameterization also kills SQL injection.
- **toolsets** - named groups of tools loaded together per agent/app (e.g. an analytics toolset vs an admin toolset), so each agent gets only the tools its role needs.
- **prompts** - reusable prompt templates colocated with the tools.

## Why this over raw DB MCPs (the doctrine to lift)
- **Restricted access:** expose a curated tool surface, not the whole database. The agent gets `search-hotels-by-name(name)`, never `DROP TABLE`.
- **Structured/parameterized queries:** predefined statements with typed params - no free-form SQL on prod, injection-safe by construction.
- **Built-in ops:** connection pooling, integrated IAM auth, end-to-end OpenTelemetry observability out of the box - the things you'd otherwise hand-roll per integration.
- **Per-agent least privilege:** toolsets let one Toolbox instance serve many agents, each scoped to its own toolset.

## When the data-engineer reaches for it
- A client/agent needs governed read (or tightly-scoped write) access to one or more operational databases or the warehouse, and you want a curated, auditable, injection-safe tool surface rather than dropping a generic SQL MCP on prod.
- Multi-source pipelines where defining sources + tools once in `tools.yaml` beats wiring per-DB MCPs.
- Pairs with the existing dbt MCP: Toolbox governs data ACCESS, dbt MCP governs TRANSFORMATION/lineage.

## CONNECT note (host installs)
Toolbox is a server the data-engineer DESIGNS configs for (the absorbed part is the tools.yaml pattern + restricted-access doctrine) and the host RUNS. Host installs the Toolbox binary / Docker image / `npx @toolbox-sdk/server`, points it at `tools.yaml` (`--tools-file`), and connects MCP clients. SDKs (Python `toolbox-core`, JS `@toolbox-sdk/core`, Go, Java) wire the same tools into ADK/LangChain/LlamaIndex agents in <10 lines. Note: Google Cloud also offers a managed-MCP variant for GCP databases.
