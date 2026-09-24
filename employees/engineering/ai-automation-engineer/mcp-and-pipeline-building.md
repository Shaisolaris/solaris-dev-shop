# MCP and Pipeline Building - Shippable Capabilities

> Load this when you are SHIPPING one of three sellable capabilities: an MCP server for a client, a recommendation/ranking/feed/RAG-rerank pipeline, or a scheduled data-scraper stack. This is build craft, not workflow-wiring. The n8n-via-MCP construction layer is `n8n-mcp.md`; durable-execution / RPA / template-library orchestration is `orchestration-patterns.md`. This file does not repeat either.

**Source canon:** [affaan-m/ECC](https://github.com/affaan-m/ECC) (Everything a coding agent), MIT. Methodology lifted from `mcp-server-patterns` (ECC), `recsys-pipeline-architect` (community, MIT; pattern popularized by xAI's open-sourced For You algorithm, Apache 2.0), and `data-scraper-agent` (community). Methodology only; no source code copied verbatim. Where ECC examples pin GitHub Actions to mutable tags, this file applies Solaris fleet doctrine and SHA-pins instead.

---

## 1. Building MCP servers (Node / TypeScript SDK)

Use when shipping an MCP server for a client so their tools/resources are callable from a desktop agent app, Cursor, or a cloud client. (For *consuming* n8n through MCP, see `n8n-mcp.md`; that is a different altitude.)

### The three primitives
- **Tools** - actions the model can invoke (search, run a command, mutate state). Use for side effects.
- **Resources** - read-only data the model can fetch (file contents, API responses). Handlers receive a `uri`. Use for context.
- **Prompts** - reusable parameterized templates the client can surface (e.g. in a desktop agent app). Optional.

### SDK and validation
- Install `@modelcontextprotocol/sdk` and `zod`. Create the server with a name + version.
- The SDK registration surface has changed across versions: some expose `server.tool(name, description, schema, handler)` (positional), others `server.tool({ name, description, inputSchema }, handler)` or `registerTool()` / `registerResource()` / `registerPrompt()`. Do NOT copy-paste a signature from memory. Verify against the current MCP docs (modelcontextprotocol.io) or Context7 query "MCP" before writing registration code. Pin the SDK version in package.json and read release notes on upgrade.
- Use **Zod** (or the SDK's preferred schema format) for input validation on every tool.

### Transport choice
- **stdio** for local clients (a desktop agent app). Server reads/writes over stdin/stdout.
- **Streamable HTTP** for remote clients (Cursor, cloud). Single MCP HTTP endpoint per current spec; preferred for remote.
- **Legacy HTTP/SSE** only when backward compatibility is required.
- Keep server logic (tools + resources) independent of transport so the entrypoint can plug in stdio or HTTP without touching tool code.

### Best practices
- **Schema first.** Define an input schema for every tool; document each parameter and the return shape.
- **LLM-readable errors.** Return structured errors or messages the model can interpret and recover from. Never leak raw stack traces.
- **Idempotency.** Prefer idempotent tools so client retries are safe (mirrors the automation idempotency rule).
- **Rate and cost.** For tools that call external APIs, respect rate limits and document cost in the tool description.
- **Versioning.** Pin the SDK in package.json; check release notes on every upgrade.

This is the build counterpart to LLM Agent Designer's MCP *design* protocol. Designer specs the tool boundary and auth; this employee ships the server.

---

## 2. Recommendation / ranking / feed / RAG-rerank pipelines

Use whenever the system has to pick "the top K items for a (user, context)": social feeds, content CMS ordering, RAG rerankers, task prioritizers, notification triage, search reranking, ad ranking. This is plumbing *around* a scoring function, not the model itself (model architecture and training belong to AI/ML Engineer; prompt/RAG design to LLM Agent Designer).

### The six-stage framework
Source -> Hydrator -> Filter -> Scorer -> Selector -> SideEffect

| # | Stage | Job | Parallelism |
|---|-------|-----|-------------|
| 1 | Source | Fetch candidates from one or more origins | multiple sources in parallel |
| 2 | Hydrator | Enrich each candidate with metadata needed downstream | independent hydrators in parallel |
| 3 | Filter | Drop candidates that should never show (blocked, expired, duplicate, ineligible) | sequential, each filter sees fewer items |
| 4 | Scorer | Assign one or more scores | sequential, later scorers see earlier scores |
| 5 | Selector | Sort by final score, return top K | single op |
| 6 | SideEffect | Cache served IDs, log impressions, emit events, update counters | async, must never block the response |

### Why this exact order
- Sources before hydration: know what exists before paying to enrich it.
- Hydration before filtering: many filters need metadata the source did not provide.
- Filtering before scoring: scoring is the expensive stage; drop the ineligible first.
- Scorer chain (not a single scorer): real systems compose ML scoring + diversity reranking + business rules.
- Selector after scoring: keeps scoring deterministic and cacheable.
- SideEffects last and async: side effects must never block the user response.

### Eight-step workflow when invoked
1. Clarify use case in one round of three questions: items being ranked? input context? language/runtime?
2. Identify candidate sources: usually in-network (followed/owned/subscribed) + out-of-network (ML retrieval / trending / similar-to-liked).
3. List required hydrations: for each filter and scorer, what data is missing from the source?
4. List filters: duplicate, self, age, block/mute, previously-served, eligibility. Cheap before expensive; universal before user-specific.
5. Design the scorer chain: primary (ML) -> combiner (multi-action with weights) -> diversity -> business rules.
6. Selector: sort descending by final score, take top K (or a stratified in-network/out-of-network mix).
7. SideEffects: cache served IDs, emit impression events, update counters, log analytics, all fire-and-forget.
8. Generate a runnable scaffold in the user's stack (TS / Go / Python). No pseudocode passing as code.

### Three trade-offs to surface explicitly (never default silently)
1. **Single score vs multi-action.** Single score: one model predicts relevance, change behavior by retraining. Multi-action: predict P(action) for many actions (read, like, share, skip, report) and combine with serving-time weights, change behavior by changing weights, no retraining. Recommend multi-action when the user expects to tune frequently. (xAI's For You uses multi-action with positive and negative weights.)
2. **Candidate isolation vs joint scoring.** Isolated: each candidate scored independently, deterministic and cacheable (default). Joint: candidates attend to each other, more expressive but non-deterministic across batches, use only with a specific reason.
3. **Online vs offline vs hybrid.** Request-time online (100-300ms budget, default); pre-computed offline batch (lower latency, lower freshness); hybrid (retrieval offline, ranking online).

### Hard rules
- Do not invent benchmark numbers. "How much faster?" -> "depends on workload, run it yourself."
- Attribution discipline: cite the pattern as "popularized by xAI's open-sourced For You algorithm" / github.com/xai-org/x-algorithm (Apache 2.0).
- No trademark use: do not name a client artifact "X-like" or use "For You" branding. Suggested names: candidate pipeline, feed pipeline, ranking pipeline, recsys pipeline.
- The generated scaffold must run; filter order matters; side effects never block.

### Anti-patterns
Scoring before filtering; synchronous side effects; a single "relevance" score when the product needs to tune multiple objectives (engagement vs safety vs diversity vs ads); joint scoring as a default; pseudocode "for illustration".

---

## 3. Scheduled data-scraper stack (sellable capability)

Use when a client wants to monitor, collect, or track any public data automatically: job boards, prices, news, GitHub, sports, listings. Three layers: COLLECT -> ENRICH -> STORE. The reference stack runs effectively free (Python + a free-tier LLM such as Gemini Flash + GitHub Actions cron + Notion/Sheets/Supabase), which makes it cheap to ship and easy to demo to clients.

### Architecture (three layers)
- **Collect** - scraper runs on a schedule. `requests` + `BeautifulSoup` covers ~80% of public sites; `playwright` only for JS-rendered pages; RSS/REST where available. Each source file returns a normalized schema (at minimum name, url, date_found).
- **Enrich** - a free-tier LLM scores / summarizes / classifies each item against user context.
- **Store** - Notion (best review UI), Google Sheets, Supabase, or a local file.

### Suggested layout
config.yaml (all user-facing settings) + profile/context.md (user context for matching) + scraper/ (main orchestrator, rule-based pre-filter, one file per source) + ai/ (LLM client with model fallback, batch pipeline, optional content fetcher, feedback memory) + storage/ (one sync module per provider) + data/feedback.json (decision history) + setup.py (one-time schema) + enrich_existing.py (backfill) + .env.example + .github/workflows/scraper.yml.

### Cost discipline (the two rules that keep it free)
1. **Batch LLM calls, never one per item.** Batch ~5 items per call; 33 items become ~7 calls instead of 33. One-call-per-item hits the free-tier rate limit instantly.
2. **Model fallback chain.** Auto-fall back across models on 429/quota (e.g. flash-lite -> flash -> larger-flash -> latest). Carry a per-call rate-limit sleep so calls space out under the RPM ceiling.

### Learning loop
Persist a feedback.json of the user's positive/negative decisions; convert the recent history into a preference-bias section prepended to the enrichment prompt so the agent improves over time. The history is committed back to the repo by the scheduled job, so it persists with zero extra infra.

### Scheduling and CI (Solaris fleet doctrine applied)
Run on a GitHub Actions cron with `workflow_dispatch` for manual triggers, a `timeout-minutes` cap, and `permissions: contents: write` only if committing feedback history. Secrets go in GitHub Secrets, never in code.

**Fleet doctrine override:** the ECC reference pins actions to mutable tags (`actions/checkout@v4`, `actions/setup-python@v5`). Solaris CI requires SHA-pinning. Pin every action to a full commit SHA with the version in a trailing comment, for example `uses: actions/checkout@<full-sha>  # v4`. Re-pin deliberately on upgrade. Mutable tags are a supply-chain risk and are not acceptable in shipped client CI.

### Hard guardrails (compliance, mirrors the automation ToS line)
- Respect robots.txt and platform ToS; prefer public APIs over scraping where one exists.
- Rate-limit requests (sleep between calls) to avoid IP bans.
- Deduplicate by URL before every storage write.
- Secrets in .env + GitHub Secrets only; .env in .gitignore; ship a .env.example.
- Set LLM maxOutputTokens high enough (2048+) for batch responses so JSON does not truncate and fail to parse.

### Quality checklist before "done"
config.yaml controls all settings (no hardcoded values); profile/context.md holds matching context; dedup by URL before each push; model fallback chain present; batch size <= 5; maxOutputTokens >= 2048; .env gitignored with a .env.example; setup.py creates schema on first run; enrich_existing.py backfills; the scheduled job commits feedback.json; README covers setup in under 5 minutes, required secrets, and customization.

### Anti-patterns
One LLM call per item; hardcoded keywords in code; scraping with no rate limit; secrets in code; no deduplication; ignoring robots.txt; using `requests` on JS-rendered sites; maxOutputTokens too low.

---

## Cross-references inside Solaris

- `n8n-mcp.md` - building n8n workflows accurately via the n8n MCP (consuming MCP, not building a server). Distinct from section 1 here.
- `orchestration-patterns.md` - durable execution (Temporal), deterministic RPA, template-library-first, self-host bring-up. The scraper schedule here is the lightweight end; long-running stateful flows escalate to Temporal there.
- **LLM Agent Designer** - specs the MCP tool boundary, auth, and error contracts, plus prompt/RAG/agent design. This employee ships the server and wires the pipeline. Route enrichment-prompt design there before wiring section 3.
- **AI/ML Engineer** - owns the scoring model/training behind a section-2 pipeline; this employee owns the plumbing around it.
- **Security Auditor** - review scraper credential handling, ToS exposure, and MCP server auth before any client ship.
