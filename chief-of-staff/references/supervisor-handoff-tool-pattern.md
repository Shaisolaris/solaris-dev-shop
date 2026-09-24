# Supervisor Handoff-Tool Pattern

Methodology reference for the central-supervisor dispatch model, adapted from the
langgraph-supervisor pattern (langchain-ai/langgraph-supervisor-py, MIT). Patterns
only; no upstream code is vendored or run. This is the operating doctrine for HOW the
chief-of-staff hands a task to a worker employee, distinct from
cross-employee-integration-patterns.md, which documents the schema contracts BETWEEN
named employee pairs.

The upstream library now recommends the supervisor-via-tools approach over the wrapper
class. We adopt the tool-shaped mental model: a handoff is a tool call the supervisor
makes, not an ambient context bleed.

## Core model

A supervisor (chief-of-staff or alfred-dispatcher) controls all communication flow and
delegation. Workers never talk to each other directly; every transfer routes back
through the supervisor. Each worker is reachable through one named handoff tool. The
supervisor's job each turn is to pick the right handoff tool (or to finish), not to do
the work itself.

## Handoff tool anatomy

Each worker gets a dedicated handoff tool. A good handoff tool has:

- A specific name and description so the supervisor's intent-parse picks correctly
  (e.g. assign_to_backend_developer / delegate_to_security_auditor). Use one stable
  verb prefix across the fleet (assign_to_ or delegate_to_) so the tool surface reads
  consistently.
- An injected **task_description** argument the supervisor must populate: a detailed,
  self-contained statement of what the worker should do, carrying all relevant context.
  This is the key discipline. The worker should not have to reconstruct intent from raw
  history. The supervisor writes the brief.
- A defined data-passing contract: what state the worker receives on handoff (see
  history modes below).

Mapping to our fleet: each employee's rules.md is the worker; the task_description is
the typed handoff brief. This makes the existing "every handoff has a typed shape" rule
(rules.md) concrete: the supervisor authors the brief, the worker returns the typed
result or an explicit error.

## History modes (full vs last-message)

Control how much of a worker's output flows back into the shared conversation:

- **full_history** - all messages the worker generated are appended to the shared
  thread. Use when downstream employees or Shai need the worker's full reasoning trail
  (audits, multi-step chains where step N+1 depends on step N's intermediate work).
- **last_message** - only the worker's final response is appended. Use as the default
  for token economy and to keep the supervisor's context window clean; the worker's
  scratch work stays out of the shared thread.

Default to last_message; escalate to full_history only when a later step provably needs
the intermediate messages.

## Concise handoffs (suppress handoff bookkeeping)

The handoff tool-call/tool-result bookkeeping messages can be suppressed from the shared
state when a leaner history is wanted (upstream add_handoff_messages=False). Doctrine:
keep the dispatch decisions visible during debugging, suppress them for token-tight
production runs. The decision and its rationale should still be capturable to the
session log even when suppressed from the live thread.

## Message forwarding (skip re-summarization)

When the supervisor judges a worker's last message is already sufficient, it forwards
that message straight to the final output instead of paraphrasing it (upstream
create_forward_message_tool, which takes a from_agent argument). Two wins:

- Saves supervisor tokens (no re-summarization pass).
- Avoids misrepresenting the worker through paraphrase. The specialist's exact words
  reach Shai.

Rule: if a single worker fully answers the request and no synthesis across workers is
needed, forward rather than rewrite. Only synthesize when combining 2+ workers'
outputs or when the worker's raw output needs translation for the audience.

## Multi-level hierarchies (supervisor of supervisors)

A supervisor can manage other supervisors, each owning a sub-team. Build mid-level
supervisors per domain (e.g. an engineering-pod supervisor over backend/frontend/qa,
a go-to-market supervisor over sales-engineer/proposal-writer), then a top-level
supervisor routes to the domain supervisor rather than to 30+ leaf employees directly.

Use this when leaf-employee count makes a single flat routing table unwieldy, or when a
domain has its own internal handoff sequence (Pattern 2 in
cross-employee-integration-patterns.md) that should be encapsulated. Keep our flat
execution layer intact: this is a routing convenience for the supervisor, not new
within-department management.

## When to use which dispatch shape

- One worker fully owns it -> single handoff + message-forward the result.
- Ordered dependency -> sequential handoffs, supervisor briefs each next worker with a
  task_description that includes the prior worker's relevant output.
- Independent parallel work -> fan out handoffs, then synthesize (do not forward; merge).
- Many domains -> route to a mid-level domain supervisor (multi-level hierarchy).

## Anti-patterns

- Handing off without a task_description (forcing the worker to reverse-engineer intent
  from raw history) - this is the context-bleed anti-pattern already named in
  cross-employee-integration-patterns.md, now with a concrete fix.
- full_history everywhere - bloats the window; default to last_message.
- Paraphrasing a worker that already answered cleanly - forward it instead.
- Worker-to-worker handoff that bypasses the supervisor - breaks the single
  communication-flow invariant.

---
Source: langchain-ai/langgraph-supervisor-py (MIT, ~1.6k stars), README methodology read
2026-06-15. Methodology absorbed; the Python library is not adopted (Solaris employees
are markdown SOPs, not LangGraph graphs). No code vendored or run.
