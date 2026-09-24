# Agent Engineering Craft - Build-Side Methodology

> Load this when you are BUILDING or DEBUGGING an agent harness, not when you are scoring one. Scoring, eval metrics, per-metric thresholds, LLM-as-judge rubrics, and memory-scope keys live in `eval-methodology.md`. This file is the build craft: how to construct the harness, audit its architecture, debug it when it loops, and keep its token bill honest. No eval-metric tables are repeated here.

**Source canon:** [affaan-m/ECC](https://github.com/affaan-m/ECC) (Everything Claude Code), MIT. Methodology lifted from its `skills/` tree: `agent-harness-construction`, `agent-architecture-audit` (origin oh-my-agent-check), `agent-introspection-debugging`, `cost-aware-llm-pipeline`, `regex-vs-llm-structured-text`, plus the comparison mechanics from `agent-eval`. Methodology only; no source code copied verbatim, patterns restated in Solaris terms.

The owner flagged Solaris agent-building as weak. This file is the fix: the craft of making the harness itself good, separate from the eval gate that proves it.

---

## 1. The build-side mental model

An agent's output quality is bounded by four budgets. If the agent is bad, one of these is starved before the model is ever at fault:

1. **Action-space quality** - are the tools named, typed, and scoped well?
2. **Observation quality** - does each tool response tell the model what happened and what to do next?
3. **Recovery quality** - does every error path carry a root-cause hint, a safe retry, and a stop condition?
4. **Context-budget quality** - is the system prompt minimal and invariant, with heavy guidance loaded on demand?

Diagnose a weak agent by asking which of the four is starved first. Do not reach for a bigger model until all four are healthy. This is the build-side companion to the design-side "simplest that works" rule.

---

## 2. Agent harness construction

### Action space design
- Stable, explicit tool names. No renaming across versions; the name is a contract.
- Schema-first, narrow inputs. The schema is the spec; if a parameter is ambiguous in the schema, the model will misuse it.
- Deterministic output shapes. Same tool, same shape, every call.
- Avoid catch-all tools unless isolation is genuinely impossible. Overlapping semantics is the number-one harness defect.

### Tool granularity
- **Micro-tools** for high-risk, irreversible operations (deploy, DB migration, permission change, money movement). One action, one tool, gated.
- **Medium tools** for the common read / edit / search loop.
- **Macro-tools** only when per-call round-trip overhead is the dominant cost, never as a default.

### Observation design - the standard tool-response envelope
Every tool response should carry:
- `status`: success | warning | error
- `summary`: one-line human-readable result
- `next_actions`: concrete follow-ups the model can take
- `artifacts`: file paths / IDs the model may reference later

An error-only response with no `next_actions` is a harness bug, not a model failure.

### Error-recovery contract
For every error path the tool can emit, include: a root-cause hint, a safe retry instruction, and an explicit stop condition (so the model knows when NOT to retry). Missing stop conditions are how agents enter retry storms.

### Context budgeting
1. Keep the system prompt minimal and invariant across turns.
2. Move large guidance into skills/references loaded on demand, not inlined.
3. Prefer file references over pasting long documents into context.
4. Compact at phase boundaries, not at arbitrary token thresholds. Compacting mid-phase loses the active working set.

### Architecture pattern choice
- **ReAct** for exploratory tasks with an uncertain path.
- **Function-calling** for structured, deterministic flows.
- **Hybrid (default recommendation):** ReAct planning over typed-tool execution. Plan loosely, execute strictly.

### Harness benchmarking signals (build-time, not the eval gate)
Track during construction: completion rate, retries per task, pass@1 vs pass@3, and cost per *successful* task (not per call). Rising retries-per-task with flat completion is the early signal of a starved recovery budget. Full scoring methodology and thresholds: `eval-methodology.md`.

### Harness anti-patterns
- Many tools with overlapping semantics.
- Opaque tool output with no recovery hints.
- Error-only output with no next steps.
- Context overloaded with irrelevant references.

---

## 3. Agent architecture audit - the 12-layer stack

Use this when an agent is degrading, behaves inconsistently, works in the playground but breaks in the wrapper, or has been debugged for >15 minutes with no root cause. MANDATORY before shipping any agent or LLM feature to a client.

Every agent system has twelve layers; any one can corrupt the answer:

| # | Layer | What goes wrong |
|---|-------|-----------------|
| 1 | System prompt | Conflicting instructions, instruction bloat |
| 2 | Session history | Stale context from previous turns injected |
| 3 | Long-term memory | Cross-session pollution; old topics in new chats |
| 4 | Distillation | Compressed artifacts re-entering as pseudo-facts |
| 5 | Active recall | Redundant re-summary layers wasting context |
| 6 | Tool selection | Wrong routing; model skips a required tool |
| 7 | Tool execution | Hallucinated execution - claims a call it never made |
| 8 | Tool interpretation | Misread or ignored tool output |
| 9 | Answer shaping | Format corruption in the final response |
| 10 | Platform rendering | Transport layer (UI/API/CLI) mutates a valid answer |
| 11 | Hidden repair loops | A silent second LLM pass rewrites the answer |
| 12 | Persistence | Expired state / cached artifacts reused as live evidence |

### Five failure patterns to name explicitly
1. **Wrapper regression** - base model is correct, the wrapper makes it worse ("worked before the last update").
2. **Memory contamination** - old topics leak in; user corrections do not stick.
3. **Tool-discipline failure** - "must use tool X" lives only in prompt text, never code-enforced.
4. **Rendering / transport corruption** - logs show the right answer, the user sees garbage.
5. **Hidden agent layers** - silent repair / retry / summarize agents run with no contract.

### Audit workflow
1. **Scope** - target system, entrypoints, model stack, reported symptoms, time window, which layers apply.
2. **Evidence collection** - read the agent loop, tool router, memory-admission path, prompt assembly; pull logs and traces; grep for anti-patterns (tool requirements only in prose; LLM calls outside the main loop; memory admission without correction-priority; fallback/repair loops; silent output mutation).
3. **Failure mapping** - for each finding record symptom, mechanism, source layer, root cause, evidence (file:line), confidence 0.0-1.0.
4. **Fix strategy - code-first, not prompt-first**, in this order:
   1. Code-gate tool requirements (enforce in code, not prompt text).
   2. Remove or narrow hidden repair agents; make any fallback explicit with a contract.
   3. Reduce context duplication (same info via prompt + history + memory + distillation).
   4. Tighten memory admission so user corrections outrank agent assertions.
   5. Tighten distillation triggers; do not compress what should not be compressed.
   6. Reduce rendering mutation; pass through, do not transform.
   7. Convert internal flow to typed JSON envelopes, not freeform prose.

### Seven quick diagnostic questions
1. Can the model skip a required tool and still answer? → tool not code-gated.
2. Does old conversation content appear in new turns? → memory contamination.
3. Is the same info in system prompt AND memory AND history? → context duplication.
4. Does the platform run a second LLM pass before delivery? → hidden repair loop.
5. Does output differ between internal generation and user delivery? → rendering corruption.
6. Are "must use tool X" rules only in prompt text? → tool-discipline failure.
7. Can the agent's own monologue become persistent memory? → memory poisoning.

### Severity model
critical (can produce wrong operational behavior - fix before release) > high (frequently degrades correctness - this sprint) > medium (fragile or wasteful - next cycle) > low (cosmetic - backlog).

### Audit output order
Lead with severity-ranked findings (most critical first), then the architecture diagnosis (which layer corrupted what and why), then the ordered code-first fix plan. Do not open with compliments. If the system is broken, say so. Never blame the model before falsifying wrapper-layer regressions; never blame memory without showing the contamination path; never let a clean current state erase a dirty historical incident.

### Audit report schema
Produce a structured report: schema_version; executive_verdict (overall_health, primary_failure_mode, most_urgent_fix); scope (target_name, model_stack, layers_to_audit); findings[] (severity, title, mechanism, source_layer, root_cause, evidence_refs, confidence, recommended_fix); ordered_fix_plan[] (order, goal, why_now, expected_effect).

---

## 4. Agent introspection debugging - the four-phase self-debug loop

Use when a run loops on the same tools, burns tokens with no forward progress, drifts off-task, or hits a recoverable environment mismatch. This is a workflow, not a runtime: the agent debugs itself before escalating. Never claim auto-healing actions ("reset agent state", "update harness config") unless real tools are actually doing them.

### Phase 1 - Failure capture (before retrying blindly)
Record: session/task, goal in progress, error + trace, last successful step, last failed tool/command, the repeated pattern seen, environment assumptions to verify (cwd, branch, service state, expected files).

### Phase 2 - Root-cause diagnosis (match a known pattern first)
| Pattern | Likely cause | Check |
|---------|--------------|-------|
| Max tool calls / same command repeated | loop or no-exit path | inspect last N tool calls for repetition |
| Context overflow / degraded reasoning | unbounded notes, repeated plans | inspect recent context for duplication |
| ECONNREFUSED / timeout | service down or wrong port | verify service health, URL, port |
| 429 / quota | retry storm, no backoff | count repeats, inspect retry spacing |
| file missing after write / stale diff | race, wrong cwd, branch drift | re-check path, cwd, git status |
| tests still failing after "fix" | wrong hypothesis | isolate the exact failing test, re-derive |

Ask: is this logic, state, environment, or policy failure? Did the agent lose the real objective? Deterministic or transient? What is the smallest reversible action that validates the diagnosis?

### Phase 3 - Contained recovery
Take the smallest action that changes the diagnosis surface: stop retries and restate the hypothesis; trim low-signal context to goal+blockers+evidence; verify real filesystem/branch/process state instead of trusting memory; narrow to one failing command/file/test; switch from speculation to direct observation; escalate when high-risk or externally blocked.

### Phase 4 - Introspection report
Close with: failure, root cause, recovery action, result (success/partial/blocked), token/time burn risk, follow-up needed, preventive change to encode later.

### Recovery heuristic order
1. Restate the real objective in one sentence. 2. Verify world state. 3. Shrink the failing scope. 4. Run one discriminating check. 5. Only then retry. Bad pattern: retrying the same action three times with reworded prompts. Never end with "I fixed it" alone - always give the pattern, the root-cause hypothesis, the recovery action, and the evidence it is now better or still blocked.

---

## 5. Cost-aware LLM pipeline (build-time cost control)

Four composable techniques. This is the implementation craft; the cost *targets* and per-request budgets belong in the eval/monitoring layer.

1. **Model routing by complexity.** Default to the cheapest model (Haiku-class, ~1x). Route up to Sonnet (~4x) only when a complexity threshold is crossed (e.g. input length or item count over a tuned limit). Reserve Opus (~19x) for genuinely hard reasoning. Log every routing decision so thresholds can be tuned on real data.
2. **Immutable cost tracking.** Use a frozen tracker that returns a new instance on each `add`, never mutates. Carry an explicit `budget_limit` and fail early via an over-budget check before the call, not after the overspend.
3. **Narrow retry.** Retry only transient errors (connection, rate-limit, server). Fail fast and immediately on auth and bad-request errors - retrying those just burns budget. Exponential backoff between transient retries, capped at 3.
4. **Prompt caching.** Mark stable system prompts (>1024 tokens) as ephemeral-cached; keep the variable user input uncached. Saves both cost and latency on repeated context.

Compose them in one pipeline: route model → check budget → call with retry+caching → record cost immutably → return result and the new tracker. Pricing reference (2025-2026): Haiku 4.5 ~$0.80/$4.00 per 1M in/out (1x); Sonnet 4.6 ~$3/$15 (~4x); Opus 4.5 ~$15/$75 (~19x).

Anti-patterns: one expensive model for everything; retrying all errors; mutating cost state; hardcoding model names instead of constants/config; skipping caching on repetitive system prompts.

---

## 6. Regex vs LLM for structured text (deterministic-first parsing)

When parsing structured text (forms, invoices, quizzes, document structure), do NOT default to an LLM. Regex handles 95-98% of consistent, repeating formats cheaply and deterministically; reserve LLM calls for the flagged remainder.

### Decision
- Format consistent and repeating (>90% follows a pattern)? → start with regex. If regex clears 95%+, you are done, no LLM. If under 95%, add an LLM only for the edge cases.
- Free-form, highly variable text? → LLM directly.

### Hybrid pipeline
1. **Regex parse** into immutable typed items (handles the majority).
2. **Confidence scoring** - programmatically flag suspect extractions (too few choices, missing field, suspiciously short text), score 0.0-1.0.
3. **Route by confidence** - items at/above threshold (e.g. 0.95) go straight out; only items below threshold go to an LLM validator.
4. **LLM validator** uses the *cheapest* model (Haiku-class) to correct or confirm flagged items; never mutate the original, return corrected instances.

Real production reference (410-item quiz pipeline): 98% regex success, 2% flagged, ~5 LLM calls total, ~95% cost saving vs all-LLM, 93% test coverage. TDD fits parsers well: write tests for known patterns first, then edge cases.

Anti-patterns: sending all text to an LLM when regex handles 95%+; using regex on free-form text; skipping confidence scoring and hoping regex "just works"; mutating parsed objects during cleaning; not testing malformed/missing-field/encoding edge cases.

---

## 7. Agent comparison harness (mechanics only - scoring lives in eval-methodology.md)

When choosing between coding agents/models for a client or for Solaris itself, systematize the comparison instead of running on vibes:
- **Declarative task definitions** (YAML): prompt, target files, the commit pinned for reproducibility, and judge criteria.
- **Git-worktree isolation** per run - each agent run gets a fresh worktree from the pinned commit, no Docker needed, runs cannot corrupt each other or the base repo.
- **At least 3 trials per agent** to capture non-determinism; include at least one deterministic judge (tests or build) per task - LLM judges add noise.
- **Pin the commit** so results are reproducible across days. Treat task definitions as test fixtures: version them as code.

The metric definitions, thresholds, LLM-as-judge rubrics, and the CI eval gate are all in `eval-methodology.md` - do not duplicate them. This section only covers how to wire the comparison harness.

---

## Cross-references inside Solaris

- `eval-methodology.md` - all eval metrics, per-metric thresholds, LLM-as-judge rubrics, memory-scope keys, the CI eval gate. This file never repeats them.
- `superpowers-methodology.md` - load FIRST for design (brainstorm → plan → execute). This file is the build/debug layer beneath that design discipline.
- **AI Automation Engineer** - once the harness design is locked here, wiring it into n8n/Zapier/Make and shipping MCP tooling is that employee's altitude.
- **Security Auditor** - the 12-layer audit's memory-contamination and hidden-repair-loop findings are also data-exfil and prompt-injection surfaces; route cross-tenant memory leakage there.
- **QA Engineer** - the harness benchmarking signals feed the eval gate QA owns.
