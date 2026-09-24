# TOP-5 Verified Sources (2026) - AI Automation Engineer

Scan date: 2026-06-13. All figures pulled live from the GitHub REST API on scan day.
Scope targeted: n8n + agent frameworks + workflow orchestration + browser/RPA automation + scheduling/durable execution.
Gate-0 method: case-insensitive grep across the employee's ACTUAL current content (SKILL.md, rules.md, n8n-mcp.md, learnings.md, plugin.json).

Legend: ABSORB = lift methodology into this employee. CONNECT = name + position the tool, point at it. METHODOLOGY = lift patterns only, no code/bundling.

---

## 1. Zie619/n8n-workflows  - ABSORB (methodology) + CONNECT
- URL: https://github.com/Zie619/n8n-workflows
- Stars: 55,125
- License: MIT (permissive - clean)
- Last commit (pushed_at): 2026-05-31
- Maintainer: Zie619 (active; large community traffic)
- What it adds: ~2,000 real, de-duplicated n8n workflow JSONs plus a fast searchable documentation/index over them. n8n is THIS employee's primary tool; this is the single largest battle-tested pattern library for it. Pairs directly with the already-absorbed n8n-mcp (build node-accurate) - n8n-mcp tells you the node schema, this gives you a proven workflow to start from instead of a blank canvas.
- Gate-0 verdict: ABSENT. No "n8n-workflows", "Zie619", "library of workflows" or "template" workflow-library concept in current content (only "export workflows as JSON" exists). Not a content-duplicate.
- Tag: METHODOLOGY (the "start from a proven template, adapt, validate" pattern) + CONNECT (point at the library).

## 2. browser-use/workflow-use  - METHODOLOGY (AGPL: methodology + self-host note)
- URL: https://github.com/browser-use/workflow-use
- Stars: 4,050
- License: AGPL-3.0  *** FLAGGED: copyleft. Methodology only; no code bundling. Self-host if ever run. ***
- Last commit: 2026-06-12
- Maintainer: browser-use org (YC-backed; the team behind browser-use, 78k★)
- What it adds: "RPA 2.0" - record a human doing a browser task once, get a deterministic, re-runnable, variable-parameterized workflow (self-healing, falls back to an agent when a step drifts). This is the missing deterministic-RPA layer between "agent does it live every time" (expensive/flaky) and "hand-coded Playwright" (brittle). Directly upgrades the LinkedIn-Mac and API-less-portal patterns.
- Gate-0 verdict: ABSENT. No "workflow-use", "RPA 2.0", or record-replay deterministic-RPA concept in current content (current content only has live Playwright + Browserbase/Apify). Not a content-duplicate.
- Tag: METHODOLOGY. AGPL → lift the record→deterministic-replay→agent-fallback pattern only; note self-host if Solaris ever runs the tool.

## 3. temporalio/temporal  - CONNECT + METHODOLOGY
- URL: https://github.com/temporalio/temporal
- Stars: 20,959
- License: MIT (permissive - clean)
- Last commit: 2026-06-13
- Maintainer: Temporal Technologies (mature, production-grade; Netflix/Stripe-class users)
- What it adds: durable execution - long-running workflows that survive process/host restarts, with automatic retry, state persistence, and exactly-once-effect semantics. Fills a real gap: the employee preaches idempotency + retries but has no answer for multi-hour/multi-day workflows that must not lose state. The decision rule "when does an automation outgrow n8n's execution model" currently has no landing spot.
- Gate-0 verdict: ABSENT. No "temporal" or "durable execution" anywhere in current content. Not a content-duplicate.
- Tag: CONNECT (name it as the escalation target above n8n for stateful long-runners) + METHODOLOGY (durable-execution / saga / compensation patterns).

## 4. activepieces/activepieces  - CONNECT
- URL: https://github.com/activepieces/activepieces
- Stars: 22,745
- License: NOASSERTION  *** FLAGGED: GitHub reports NOASSERTION; repo is MIT for the framework with a separate commercial/EE license on some pieces. Treat license as mixed - verify per-use; do not assume blanket MIT. ***
- Last commit: 2026-06-13
- Maintainer: Activepieces (active, well-funded OSS company)
- What it adds: an open-source, self-hostable Zapier/n8n alternative that is MCP-native (~400 MCP servers exposable to AI agents) with a TypeScript-first "pieces" model. Relevant as a CONNECT alternative when a client wants a more business-user-friendly self-hosted builder than n8n, or wants MCP servers surfaced into an automation natively.
- Gate-0 verdict: ABSENT. No "activepieces" in current content. Not a content-duplicate.
- Tag: CONNECT (alternative self-hosted platform; flag mixed license before adopting).

## 5. n8n-io/self-hosted-ai-starter-kit  - METHODOLOGY
- URL: https://github.com/n8n-io/self-hosted-ai-starter-kit
- Stars: 14,966
- License: Apache-2.0 (permissive - clean)
- Last commit: 2026-01-06 (within ~6 months; first-party n8n, low-churn by design)
- Maintainer: n8n-io (the n8n core team - canonical first-party)
- What it adds: the canonical docker-compose stack for self-hosted n8n + local AI (Ollama, Qdrant vector store, Postgres) wired together. This employee declares "n8n self-hosted is primary for Solaris" but has zero concrete self-host bring-up reference. This operationalizes that claim into a real starting stack.
- Gate-0 verdict: ABSENT. No "self-hosted-ai-starter" / concrete self-host stack reference in current content (only the abstract claim "self-hosted or n8n.cloud"). Not a content-duplicate.
- Tag: METHODOLOGY (self-host bring-up: compose stack, local LLM + vector store + Postgres, credentials per env).

---

## Runners-up (verified, not in top-5)
- **enescingoz/awesome-n8n-templates** - 22,971★, NOASSERTION (flagged), pushed 2026-06-01. 280+ categorized n8n templates. Strong, but overlaps Zie619/n8n-workflows (#1) which is larger + MIT-clean + searchable. Keep as a secondary template source for Scout.
- **crewAIInc/crewAI** - 53,463★, MIT, pushed 2026-06-13. Multi-agent role orchestration. Excellent but sits at LLM-Agent-Designer altitude (agent ARCHITECTURE), not this employee's no-code/low-code WIRING lane. Route to LLM Agent Designer.
- **Skyvern-AI/skyvern** - 21,896★, AGPL-3.0 (flagged), pushed 2026-06-13. LLM+vision browser RPA. Overlaps workflow-use (#2) and Browserbase (already connected); AGPL. Noted, not lifted.
