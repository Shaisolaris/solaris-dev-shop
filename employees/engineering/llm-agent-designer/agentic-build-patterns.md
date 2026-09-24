# Agentic Build Patterns - Named Techniques from Production Coding Agents

> Load this when you are CHOOSING a concrete build technique for an agent: how to feed a repo to the model, how to format edits, how to guardrail an autonomous run, how to package a reusable agent task, how to add a critic, how to optimize a prompt programmatically, or how to guarantee structured output. This is the technique layer that sits below `agent-engineering-craft.md` (which is the harness-construction / architecture-audit / debug craft) and points to `eval-methodology.md` for all scoring. No eval metrics, no harness anti-pattern tables, and no superpowers-methodology design steps are repeated here.

**Why this file exists:** `agent-engineering-craft.md` teaches how to construct, audit, and debug a harness in the abstract. This file lifts the SPECIFIC, battle-tested techniques that the most-used open coding agents actually ship, so a Solaris agent design can cite a proven pattern instead of inventing one. Methodology only. No source code is bundled or run; patterns are restated in Solaris terms.

**Sources (all vetted 2026-06-15: OSI-permissive, credible maintainer, >1k stars, active within 6 months):**
- Aider (Aider-AI/aider) - Apache-2.0, ~46k stars, active 2026. Repo-map and small-diff edit discipline.
- OpenHands (All-Hands-AI/OpenHands, formerly OpenDevin) - MIT (core), ~65k stars, maintained by All Hands AI / Graham Neubig, active. Autonomous-run guardrails.
- Goose (block/goose, now under the Agentic AI Foundation at the Linux Foundation) - Apache-2.0, ~38k stars, active 2026. Recipe pattern.
- AutoGen (microsoft/autogen) - Apache-2.0, ~57k stars, Microsoft, active. Critic-actor / reviewer-loop multi-agent.
- DSPy (stanfordnlp/dspy) - Apache-2.0, Stanford NLP, active. Programmatic prompt optimization.
- Instructor (567-labs/instructor, Jason Liu) - MIT, ~11k stars, active. Validation-and-retry structured output.
- Outlines (dottxt-ai/outlines) - Apache-2.0, ~14k stars, active. Constrained decoding / grammar-level structured output.

---

## 1. Repo-map + small-diff edit discipline (Aider pattern)

The two techniques that make a coding agent reliable on a real codebase, independent of model.

### Repo map (token-budgeted context selection)
Do NOT paste a whole repo into context, and do NOT rely on the model to guess which files exist. Build a compact, ranked map of the codebase and inject only that:
- Parse the repo into a symbol graph (functions, classes, signatures, their file locations) using a structural parser, not a regex. Aider uses tree-sitter; the principle is structural, not textual.
- Rank symbols by relevance to the current task (graph centrality plus mention in the active conversation), then emit a map that fits a fixed token budget. When the budget is tight, show signatures and drop bodies.
- The map is a navigation aid, not the working set. The model asks for the specific files it needs; the map tells it which ones exist and what they contain.

For Solaris: any agent that edits a codebase larger than a handful of files needs a repo-map step before the edit loop. Without it, the agent hallucinates file paths and edits the wrong file. This is the concrete fix for the context-budget-quality budget named in `agent-engineering-craft.md` section 1.

### Small-diff edit format (search/replace discipline)
Make the model emit edits as precise, reviewable diffs, never as "here is the whole new file":
- Use a strict edit format: an exact existing snippet to find plus the replacement. If the find-snippet does not match the file verbatim, the edit fails loudly rather than silently corrupting the file.
- One logical change per edit. A failed edit rolls back just that change, not the session.
- After every applied edit, run the linter and the relevant test. Feed any failure straight back to the model as the next observation (this is the observation-quality budget in action).
- Auto-commit each successful change to version control so every edit is a restore point and the diff history is the audit trail.

For Solaris: the strict-match edit format is the single biggest reliability lever for code-editing agents. Adopt the find-must-match-verbatim-or-fail rule as a hard contract, and the lint-and-test-after-each-edit loop as the default. Pair with the comparison-harness git-worktree isolation in `agent-engineering-craft.md` section 7.

---

## 2. Autonomous-run guardrails (OpenHands pattern)

When an agent runs many steps without a human between them, four guardrails keep it from doing damage or burning the budget. These are stricter than the loop-limit / cost-ceiling guidance already in the design protocol; they are the autonomous-execution-specific set.

1. **Sandboxed execution.** All shell, file, and browser actions run inside an isolated sandbox (container or equivalent), never directly against the host or production. The agent gets a workspace it cannot escape. Treat the sandbox boundary as a security control, not a convenience.
2. **Action confirmation modes.** Run in one of three explicit modes, chosen up front and stated: full-auto (no confirmation, sandbox only), confirm-risky (the agent pauses for human approval before any irreversible or high-blast-radius action - deploy, delete, money movement, external send), or read-only (no side effects at all). Default to confirm-risky for any run touching real systems.
3. **Per-run resource budget.** Cap iterations, wall-clock time, and token/dollar spend per run, and stop hard at the cap with a partial-result report rather than silently continuing. The cap is a number declared before the run, not a vibe.
4. **Stuck-loop detection.** Detect when the agent repeats the same action or oscillates between two states with no state change, and break out automatically into the introspection loop (see `agent-engineering-craft.md` section 4) instead of consuming the whole budget on a loop. Repeated-identical-action is the canonical trigger.

For Solaris: any agent shipped to run unattended (overnight builds, scheduled agentic jobs, client autonomous workers) must declare its confirmation mode, its per-run budget, and its sandbox boundary before it runs. An unattended agent with no sandbox and no confirmation mode is a release blocker, not a feature.

---

## 3. Recipe pattern (Goose) - a reusable, parameterized agent task

A recipe packages a repeatable agent task as a declarative file so it can be shared, version-controlled, and re-run consistently instead of being re-prompted from scratch each time.

A recipe declares:
- **Parameters** - the inputs that change per run (the target, the search term, the recipient), with types and defaults, so one recipe serves many concrete runs.
- **Instructions / prompt** - the task the agent performs, written once and reused.
- **Allowed tools / extensions** - which capabilities this task is permitted to use (scopes the action space per task, not globally).
- **Optional sub-recipes** - a recipe can call another recipe, so complex tasks compose from validated smaller ones.
- **Validation** - the recipe is validated against its schema before it runs, so a malformed task fails fast.

For Solaris: when the same agentic task recurs across clients or sessions (a code-review pass, a release-notes generation, a data-enrichment sweep), capture it as a recipe rather than re-prompting. The recipe is the agent-altitude analogue of a function definition: named inputs, scoped capabilities, composable, versioned. This complements the composable-skills protocol in `superpowers-methodology.md` (skills are the building blocks; a recipe is a concrete reusable invocation of them). The no-code workflow-template equivalent lives with AI Automation Engineer; this is the agent-run equivalent.

---

## 4. Critic-actor / reviewer loop (AutoGen pattern)

MetaGPT role-decomposition (PM to Architect to Engineer, spec then code) is already an absorbed SOP in `rules.md`. AutoGen adds the orthogonal pattern: a critic that reviews the actor's output before it is accepted.

- **Actor + critic, not just actor.** One agent (the actor) produces the work; a second agent (the critic / reviewer) evaluates it against explicit criteria and either approves or returns concrete revision requests. The actor revises; the loop repeats until the critic approves or a max-round cap is hit.
- **The critic needs its own rubric.** A critic with no criteria just rephrases. Give it the same kind of rubric you would give an LLM-as-judge eval (see `eval-methodology.md`) - what good looks like, what to reject. The difference: the eval scores after the fact; the critic gates inline before acceptance.
- **Cap the rounds.** Actor-critic loops can ping-pong forever. Set a max revision count; on reaching it, escalate to a human or ship the best-so-far with the critic's outstanding objections attached.
- **When to reach for it.** High-stakes single outputs where a second perspective measurably improves quality (a generated migration, a client-facing document, a security-sensitive change). Do NOT add a critic to every task - it doubles cost and latency. Prove the actor alone is insufficient first (same "simplest that works" discipline as never-start-multi-agent).

For Solaris: the critic-actor loop is the inline, generative form of the Code Reviewer and QA Engineer roles. Use it when the cost of a wrong single output exceeds the doubled token cost of reviewing it. Pair the critic's rubric with the eval rubric so inline gating and after-the-fact scoring stay consistent.

---

## 5. Programmatic prompt optimization (DSPy pattern)

The eval gate in `eval-methodology.md` tells you whether a prompt passes. DSPy adds the missing step: how to improve a prompt against that metric programmatically instead of by hand-tuning wording.

- **Program, do not prompt.** Express the task as a signature (typed input fields to typed output fields, e.g. question to answer) plus a module (predict, chain-of-thought, react), not as a hand-crafted prompt string. The wording becomes a compilation target, not a hand-written artifact.
- **Optimize against a metric.** Given a small training/dev set and a metric (the same kind of eval metric from `eval-methodology.md`), an optimizer searches over prompt instructions and few-shot demonstrations to maximize the metric. Bootstrap-few-shot generates and selects effective examples automatically; instruction-optimizers rewrite the instruction text.
- **Few-shot examples become a search result, not a guess.** Instead of hand-picking demonstrations, let the optimizer select the demonstrations that actually raise the metric on the dev set.
- **The eval set is the optimization target.** This closes the loop with the TDD-first discipline: the eval set you build before iterating (per `superpowers-methodology.md`) becomes the objective the optimizer compiles against.

For Solaris: when a prompt has a real eval set and a clear metric but is still being hand-tuned, that is the signal to reach for programmatic optimization. Do NOT optimize prompts that have no eval set - you would be optimizing against a vibe. Optimization is downstream of the eval gate, never a substitute for it. Heavy fine-tuning of model weights stays with AI/ML Engineer; this is prompt-and-demonstration optimization, which is this employee's altitude.

---

## 6. Structured + constrained output (Instructor and Outlines patterns)

The SKILL.md mentions JSON schema and output validation generically. These are the two distinct, complementary mechanisms - know which one a job needs.

### Tier 1 - validate and retry on the API output (Instructor pattern)
Wrap the model call so the response is parsed into a typed schema (Pydantic model or equivalent) and validated:
- Declare the desired output as a typed schema; the library coerces the model's response into it.
- On a validation failure, automatically re-ask the model with the validation error fed back as context (the reask loop), up to a retry cap.
- This works with any API model and needs no access to the decoder. It is the default for production apps calling a hosted API (Claude, OpenAI).
- Tradeoff: a malformed response still costs a round-trip before the retry; the guarantee is eventual-valid-or-fail, not first-token-valid.

### Tier 2 - constrain the generation itself (Outlines pattern)
Restrict what tokens the model is even allowed to emit, so the output is structurally valid by construction:
- Provide a schema, a regex, or a grammar; the decoder is masked so only tokens that keep the output valid against that constraint can be sampled. The result is guaranteed to parse - there is no malformed branch to retry.
- This requires control of the decoding step, so it applies to open / self-hosted models (vLLM, Ollama, transformers) and to providers that expose constrained decoding, not to a plain hosted chat endpoint.
- Use it when invalid output is unacceptable or expensive to retry (high-volume extraction, strict schemas, latency-sensitive parsing), and you control or can choose the serving stack.

### Decision rule
- Hosted API model (Claude / OpenAI), need typed output with graceful recovery -> Tier 1 (validate-and-retry). Default for most Solaris client apps.
- Self-hosted or constrained-decoding-capable model, invalid output is unacceptable or retries are too costly -> Tier 2 (constrained decoding).
- Both compose: constrain generation at the decoder AND validate the parsed object, when the stack allows.

For Solaris: this replaces "just ask for JSON and hope" with a named two-tier discipline. Choose the tier from the serving stack and the cost of an invalid output, and state which one the design uses. Cross-reference the deterministic-first parsing rule in `agent-engineering-craft.md` section 6 - prefer regex over an LLM where the format is consistent; reach for these patterns only when an LLM is genuinely required.

---

## Cross-references inside Solaris

- `agent-engineering-craft.md` - the harness-construction / 12-layer audit / introspection-debug / cost-pipeline / regex-vs-LLM craft this file's techniques plug into. Section 1 here (repo-map, small-diff) serves its context-budget and observation-quality budgets; section 2 (autonomous guardrails) feeds its introspection loop on stuck-detection.
- `eval-methodology.md` - all scoring, metric thresholds, and judge rubrics. Section 4's critic rubric and section 5's optimization metric both reference these; this file never restates a metric.
- `superpowers-methodology.md` - design-before-code 3-step. Recipes (section 3) complement the composable-skills protocol; the eval set built there is the optimization target in section 5.
- **AI Automation Engineer** - the no-code/workflow-template equivalent of recipes, and the autonomous-run guardrails as they apply to agentic automations, live there (orchestration-patterns.md). This file is the agent-design altitude; that is the wiring altitude.
- **AI/ML Engineer** - model-weight fine-tuning and the serving stack that enables Tier-2 constrained decoding.
- **Security Auditor** - the sandbox boundary and confirmation modes in section 2 are security controls; route any autonomous agent with host or production access there before ship.
- **Code Reviewer / QA Engineer** - the critic-actor loop (section 4) is the inline generative form of their roles; keep the critic rubric consistent with the QA eval rubric.
