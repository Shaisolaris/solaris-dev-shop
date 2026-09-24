# MongoDB / NoSQL operational admin (MongoDB MCP)

Absorbed from mongodb-js/mongodb-mcp-server (Apache-2.0, official MongoDB, ~1k stars, commit main @ 2026-06-13). The DBA already had MongoDB MODELING concepts (denormalize-vs-reference, aggregation pipeline, replica sets, sharding). Net-new here is the OPERATIONAL admin workflow + Atlas control-plane the DBA lacked: how to inspect, index, diagnose, and provision MongoDB live, safely.

## Connect safely (defaults matter)
- Two auth modes: a connection string (`MDB_MCP_CONNECTION_STRING`, local or `mongodb+srv://...` Atlas) OR Atlas API service-account creds (`MDB_MCP_API_CLIENT_ID`/`_SECRET`, required for the Atlas control-plane tools).
- **Read-only by default.** Run with `--readOnly` / `MDB_MCP_READ_ONLY=true` for any investigation. Only drop read-only for an explicit, reviewed write/DDL operation - and never on prod without change control.
- Atlas service accounts: minimum required permissions only (least privilege). Atlas access-list (IP/CIDR) gates who can connect.

## Database-tier admin tools (the daily NoSQL admin loop)
- **Inspect:** `list-databases` → `list-collections` → `collection-schema` (infer the real shape, MongoDB is schemaless on disk) → `collection-indexes` → `collection-storage-size` / `db-stats` for sizing.
- **Diagnose a slow query:** `explain` returns the winning-plan execution stats - read it the way you'd read a Postgres EXPLAIN. COLLSCAN in the plan = missing index (matches the existing hard rule "MongoDB indexes are mandatory; collection scans kill performance").
- **Fix:** `create-index` (compound/order matters - ESR rule: Equality, Sort, Range), verify with `collection-indexes`, `drop-index` to remove the unused/duplicate ones that only slow writes.
- **Query/maintain:** `find` / `count` / `aggregate` / `aggregate-db` for reads; `insert-many` / `update-many` / `delete-many` for writes; `create-collection` / `rename-collection` / `drop-collection` / `drop-database` for DDL. Treat every `drop-*` and unfiltered `update-many`/`delete-many` as destructive - confirm filter + backup before running, read-only mode off only deliberately.

## Atlas control-plane (provisioning + tuning)
- **Provision:** `atlas-create-project` / `atlas-create-cluster` (M10–M80, replica set or shard, autoscaling default) / `atlas-create-free-cluster` / `atlas-upgrade-cluster` (M0→Flex/M10 tier bumps).
- **Access:** `atlas-create-db-user` / `atlas-list-db-users` / `atlas-create-access-list` / `atlas-inspect-access-list` (IP/CIDR allow-listing).
- **Operate + tune:** `atlas-inspect-cluster`, `atlas-list-clusters`, `atlas-list-alerts`, and crucially `atlas-get-performance-advisor` - Atlas's own slow-query + suggested-index recommendations; use it as the starting point before hand-rolling index changes.
- **Stream processing:** `atlas-streams-build/discover/manage/teardown` for Kafka-style pipelines (set up workspace, start/stop processors, debug a failing processor).
- **Local dev:** `atlas-local-*` for local Atlas deployments.

## Doctrine
- Index discipline mirrors the relational rules: index before scale, ESR for compound indexes, drop unused indexes (they tax every write), and let the Performance Advisor + `explain` drive decisions with data, not guesses.
- Read-only is the default posture; writes/DDL are deliberate, change-controlled, and backed up first. The DBA OWNS the data model and the destructive operations - never auto-fire a `drop` or unfiltered bulk write.

## CONNECT note (host installs)
Host installs `npx -y mongodb-mcp-server@latest --readOnly` (Node) pointed at the connection string or Atlas creds. Atlas tools need a service account; scope it minimally.
