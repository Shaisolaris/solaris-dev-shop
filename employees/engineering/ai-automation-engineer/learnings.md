# AI Automation Engineer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#n8n], [#zapier], [#make], [#linkedin], [#webhook], [#security], [#tos], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - AI Automation Engineer rebuild**: Clear altitude split with LLM Agent Designer is critical. Designer does architecture; Automation Engineer does wiring. Codified in both employees' SKILLs.
  *Proposed rule: For employees with overlapping-but-distinct scopes, write the boundary into BOTH employees' SKILLs. Single-sided boundary = drift.*
  Tags: [#altitude-split], [#bidirectional-boundary]

- **2026-04-24 - AI Automation Engineer rebuild**: LinkedIn Mac setup has specific requirements (dedicated machine, humanized pacing, kill switch, ToS caution). Built dedicated playbook rather than treating as generic automation.
  *Proposed rule: High-risk, high-specific-requirement automations get dedicated playbooks. Generic automation advice fails them.*
  Tags: [#dedicated-playbooks], [#linkedin]

- **2026-04-24 - AI Automation Engineer rebuild**: Solaris's OWN infrastructure (weekly skill scan + Sunday knowledge sweep) ARE scheduled-task automations. Self-referential canonical examples.
  *Proposed rule: Solaris's meta-layer automations are the canonical examples this employee points to when teaching patterns. Use them first.*
  Tags: [#solaris-as-reference]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-06-14 - v0.9.0 ECC build-capability deepening (3 sellable capabilities)
- Created references/mcp-and-pipeline-building.md from affaan-m/ECC (MIT). BUILD craft, methodology only, no code bundled.
- Lifted: mcp-server-patterns (build MCP servers - Node/TS SDK + Zod; tools/resources/prompts primitives; stdio for local, Streamable HTTP for remote; verify registration signatures against current MCP docs/Context7 rather than copying from memory; schema-first + LLM-readable errors + idempotency + SDK pinning). recsys-pipeline-architect (six-stage Source->Hydrator->Filter->Scorer->Selector->SideEffect; 8-step workflow; 3 trade-offs to surface - single vs multi-action scoring, isolation vs joint, online vs offline; attribution to xAI For You algo, no trademark use; side effects always async). data-scraper-agent (COLLECT->ENRICH->STORE; free stack Python+free-LLM+GH-Actions+Notion/Sheets/Supabase; batch LLM calls + model fallback for cost; feedback-learning loop; robots.txt/ToS/dedup/secrets guardrails; quality checklist).
- Gate-0 vs n8n-mcp.md + orchestration-patterns.md: section 1 is BUILDING an MCP server (n8n-mcp.md is CONSUMING n8n via MCP - different altitude); sections 2-3 are net-new pipeline + scraper capabilities. No overlap.
- Fleet doctrine: the ECC scraper reference pinned GitHub Actions to mutable tags (checkout@v4, setup-python@v5); overrode with SHA-pin requirement for shipped client CI. No em-dashes in the new file.
  *Proposed rule: when building an MCP server, never copy SDK registration signatures from memory - the @modelcontextprotocol/sdk surface has changed across versions; verify against current docs/Context7 and pin the SDK.* Tags: [#mcp], [#promoted?]
  *Proposed rule: any "pick top K for a (user, context)" problem (feed, ranking, RAG-rerank, notification triage) uses the six-stage pipeline; filter before score; side effects never block.* Tags: [#pipeline]
  *Proposed rule: scraper stacks ship SHA-pinned GH Actions, batch LLM calls (~5/call) with a model fallback chain, dedup by URL before write, and respect robots.txt/ToS.* Tags: [#scraper], [#cost], [#compliance]
- No license flags (ECC MIT; recsys-pipeline-architect MIT; data-scraper-agent community-permissive).

## 2026-07-24 engineering-core upstream
- Fail closed when n8n-mcp or required automation toolchain is unavailable; one BLOCKED toolchain cause.
- Still no unattended external message send or purchase without human.
## Sources

- Upstream: Zie619/n8n-workflows (MIT (permissive - clean)); browser-use/workflow-use (AGPL-3.0  *** FLAGGED: copyleft. Methodology only; no code bundling. Self-host if ever); temporalio/temporal (MIT (permissive - clean)); activepieces/activepieces (NOASSERTION  *** FLAGGED: GitHub reports NOASSERTION; repo is MIT for the framework with); n8n-io/self-hosted-ai-starter-kit (Apache-2.0 (permissive - clean))
- What was used: methodology absorbed: Zie619/n8n-workflows; connected as external reference: Zie619/n8n-workflows, temporalio/temporal, activepieces/activepieces; methodology only: browser-use/workflow-use, temporalio/temporal, n8n-io/self-hosted-ai-starter-kit
- License notes: browser-use/workflow-use: AGPL-3.0  *** FLAGGED: copyleft. Methodology only; no code bundling. Self-host if ever; activepieces/activepieces: NOASSERTION  *** FLAGGED: GitHub reports NOASSERTION; repo is MIT for the framework with
