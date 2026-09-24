# Orchestration Patterns (Active Methodology)

Load when a workflow outgrows a simple linear n8n flow. Methodology only - no code bundled here; install/self-host the tools named below per their own licenses.

Absorbed 2026-06-13 from (scan-day GitHub figures):
- Zie619/n8n-workflows (MIT, 55.1k★) - n8n template-library practice
- browser-use/workflow-use (AGPL-3.0, 4.0k★) - deterministic RPA pattern *(AGPL: methodology lifted; self-host the tool if ever run, do not redistribute its code)*
- temporalio/temporal (MIT, 21.0k★) - durable execution
- activepieces/activepieces (NOASSERTION/mixed license, 22.7k★) - MCP-native self-hosted alternative *(verify per-piece license before adopting)*
- n8n-io/self-hosted-ai-starter-kit (Apache-2.0, 15.0k★) - self-host bring-up stack

---

## 1. Platform escalation ladder (where does this workflow belong?)

Pick the lightest tier that holds. Escalate only when a real requirement forces it.

1. **Linear, low-volume, business-user friendly** → Zapier / Make / Activepieces.
2. **Self-hosted, high-volume, visual + code** → n8n self-hosted (Solaris default). Build node-accurately via `n8n-mcp.md`.
3. **Bespoke glue, >5 conditional branches** → custom script (Python/Node), not a visual builder.
4. **Long-running / must survive process or host restarts / exactly-once effect over hours-to-days** → durable-execution engine (Temporal). n8n's execution model is not built for multi-day stateful workflows with crash recovery; do not force it.
5. **Bespoke interactive browser flow, at scale / stealth** → cloud browser (Browserbase, connected). One-off interactive → local Web Operator. Pre-built scraper exists → Apify Actor.

**Escalation trigger to write down explicitly:** if losing the workflow's mid-state would cause a duplicate side effect or an unrecoverable gap, it needs durable execution - not just retries.

## 2. Durable execution (Temporal pattern) - for long-runners

The employee already preaches idempotency + retries; durable execution is the answer for workflows too long-lived for those alone.

- **Workflow vs activity split:** the workflow function is deterministic orchestration (no I/O, no clocks, no randomness inline); all side-effecting work goes in *activities* that are retried independently. This is what lets the engine replay state after a crash.
- **Exactly-once effect, not exactly-once execution:** activities may run more than once on retry, so each must be idempotent (deterministic idempotency key from the event - never random). Same rule as webhooks, enforced harder.
- **Saga / compensation:** for multi-step workflows with irreversible steps, pair each forward step with a compensating action so a late failure can roll back cleanly. This is the durable-world version of "humans in the loop for irreversible actions."
- **Timers + waits are first-class:** "wait 3 days then check" is a durable timer that survives restarts - do NOT model long waits as a sleeping process or a fragile cron.
- **Self-host note:** Temporal is MIT and self-hostable. Default to self-host for Solaris (consistency with n8n self-host doctrine); flag Temporal Cloud cost if ever proposed.

## 3. Deterministic browser RPA (workflow-use pattern) - record once, replay reliably

The gap between "agent does the browser task live every run" (expensive, non-deterministic, flaky) and "hand-coded Playwright" (brittle to any UI change).

- **Record → deterministic replay:** capture a human doing the task once; produce a parameterized, re-runnable workflow (variables for the bits that change - search term, recipient, date).
- **Agent fallback on drift only:** run the deterministic path every time; invoke an LLM/agent step ONLY when a selector/step fails (the page changed). Cheap and stable in the common case, self-healing in the rare case.
- **Where this applies for Solaris:** the LinkedIn-Mac setup and any API-less portal. Prefer deterministic replay for the repetitive core (post, triage) and reserve live-agent runs for genuinely novel pages. Keep the humanized-pacing + volume-ceiling + kill-switch rules from `rules.md` on top.
- **AGPL self-host note:** workflow-use is AGPL-3.0. Lift the *pattern* freely; if Solaris runs the actual tool, self-host it and do not redistribute its code in a closed product. Browserbase/Apify (already connected) remain the managed-scale options.

## 4. Template-library-first (n8n-workflows pattern) - don't start from a blank canvas

- **Search before you build:** for a new n8n workflow, first check the template library (Zie619/n8n-workflows, ~2k MIT-licensed real workflows, searchable; awesome-n8n-templates as a secondary source) for a near-match.
- **Adapt, then validate:** import the closest template, swap credentials + parameters to the real case, then validate node config via `n8n-mcp.md` before activating. Templates close the "what nodes/shape do I even need" gap; n8n-mcp guarantees the params are real.
- **License hygiene:** Zie619/n8n-workflows is MIT (clean to reuse). awesome-n8n-templates is NOASSERTION - treat as reference, verify before shipping a template verbatim into a client deliverable.
- **Contribute back to Solaris:** a workflow that proves out becomes a Solaris-internal template + a `learnings.md` entry.

## 5. Self-host bring-up (self-hosted-ai-starter-kit pattern) - operationalizes "n8n self-hosted is primary"

Concrete starting stack for the abstract "self-hosted or n8n.cloud" claim:

- **Compose stack:** n8n + Postgres (persistence) + a local LLM runtime (Ollama) + a vector store (Qdrant), wired via docker-compose. Apache-2.0, first-party n8n - safe baseline to fork.
- **Credentials per environment:** dev / prod separation from day one; secrets via a real store (1Password Connect / Doppler / Vault), never in compose env files committed to git. Matches `rules.md` secret doctrine.
- **Backups are mandatory:** workflow definitions + credentials + execution history (see `rules.md` standing gotcha). A self-host with no backup is a single disk failure from total loss.
- **When to add local LLM:** use the local model for cheap/high-volume classification + drafting to cap AI cost; reserve hosted the coding agent/OpenAI for quality-critical steps. Feeds the cost-budget formula in `rules.md`.

## 6. Activepieces - CONNECT alternative (when n8n isn't the right fit)

- **When:** a client wants a more business-user-friendly self-hosted builder than n8n, or wants ~400 MCP servers surfaced natively into automations + AI agents.
- **License caution:** GitHub reports NOASSERTION (mixed - MIT framework with commercial/EE pieces). Verify the specific pieces' licenses before adopting in a client deliverable; do not assume blanket MIT.
- **Position:** a CONNECT alternative, not a replacement for the n8n default. Most Solaris work stays on n8n.

## 7. Agentic automation run discipline (autonomous-run guardrails + recipe pattern)

Sections 1-6 cover deterministic and durable orchestration. This section covers the case where an LLM agent, not a fixed workflow, drives the automation - the workflow decides its own next step. That power needs its own guardrails and its own packaging discipline. Methodology only; install/self-host the tools named below per their own licenses.

Absorbed 2026-06-15 (vetted: OSI-permissive, credible maintainer, >1k stars, active <6mo):
- All-Hands-AI/OpenHands (formerly OpenDevin) - MIT (core), ~65k stars, All Hands AI / Graham Neubig, active. Autonomous-run guardrails.
- block/goose (now under the Agentic AI Foundation at the Linux Foundation) - Apache-2.0, ~38k stars, active 2026. Recipe pattern.

### 7.1 Autonomous-run guardrails (OpenHands pattern)
When an agentic step runs many actions without a human between them, the idempotency + retries + kill-switch rules in `rules.md` are necessary but not sufficient. Add these four, declared explicitly before the automation goes live:

1. **Sandboxed execution.** Agent shell/file/browser actions run in an isolated sandbox (container or equivalent), never directly against the host or production. The sandbox boundary is a security control - treat it as one. For the LinkedIn-Mac and any portal automation, the headed browser session is the sandbox; keep agentic file/shell work off the host.
2. **Action confirmation mode.** Run in one stated mode: full-auto (sandbox-only, no confirmation), confirm-risky (pause for human approval before any irreversible or high-blast-radius action - send, post, delete, payment, external write), or read-only (no side effects). Default to confirm-risky for any automation touching real client systems. This is the agentic-altitude form of the existing "humans in the loop for irreversible actions" rule.
3. **Per-run resource budget.** Cap iterations, wall-clock time, and token/dollar spend per run; stop hard at the cap with a partial-result report rather than continuing silently. The cap is a number written into the automation, feeding the cost-budget formula in `rules.md`.
4. **Stuck-loop detection.** Detect repeated-identical-action or two-state oscillation with no progress and break out instead of burning the whole budget. Pairs with the durable-execution timers in section 2 - a stuck agentic step inside a long-runner must fail its activity, not hang the workflow.

**Escalation note:** an unattended agentic automation with no sandbox boundary and no confirmation mode is a release blocker for client work, not a feature. State all four guardrails before activating.

### 7.2 Recipe pattern (Goose) - portable, parameterized agent-task definition
Section 4 (template-library-first) covers reusing n8n workflow JSONs. A recipe is the agentic-run analogue: a declarative file that packages a repeatable agent task so it is shared, version-controlled, and re-run consistently instead of being re-prompted each time.

A recipe declares: parameters (the inputs that change per run, with types/defaults), the task instructions/prompt (written once, reused), the allowed tools/extensions (scopes the action space per task), optional sub-recipes (compose complex tasks from validated smaller ones), and validation against its schema before it runs (malformed task fails fast).

**Where this fits for Solaris:** when an agentic automation recurs across clients or runs (an enrichment sweep, a triage pass, a scheduled agentic report), capture it as a recipe rather than re-prompting from scratch. The recipe sits one level up from an n8n template: the template is a fixed node graph; the recipe is a reusable agent-task spec with named inputs and scoped capabilities, which the agent then executes (possibly by driving n8n). A proven recipe becomes a Solaris-internal template plus a `learnings.md` entry, same contribution loop as section 4. The agent-DESIGN altitude of recipes (signatures, critic loops, prompt optimization) lives with LLM Agent Designer (`agentic-build-patterns.md`); this employee wires the recipe into a running, guardrailed automation.
