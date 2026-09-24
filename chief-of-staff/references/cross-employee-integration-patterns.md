# Cross-Employee Integration Patterns

Documented handoff protocols between Solaris (and Alfred) employees. Without these, every cross-employee task reinvents the handshake.

## Pattern 1 - frontend ↔ backend
**Trigger:** frontend-developer needs an API endpoint OR backend-developer ships a new endpoint that frontend needs to consume.

**Handoff includes:**
- URL + HTTP verb
- Request shape (Zod or Pydantic schema, copy-pasteable)
- Response shape (success + each error variant)
- Auth requirement (none / session / JWT / API key)
- Rate limit (req/sec per user, headers exposed)
- Idempotency (whether Idempotency-Key header is required)
- Realistic example payload + curl command

**Acceptance criteria:** frontend can hit the endpoint locally without back-and-forth questions.

## Pattern 2 - product-manager → cloud-architect → engineering pod
**Trigger:** new feature spec accepted; needs to be built.

**Handoff sequence (per MetaGPT spec→code SOP):**
1. **PM** writes the PRD (9-section schema: problem, objectives, segments, value-prop, solution, constraints, success metrics, release plan, open questions)
2. **Cloud-architect** writes the Architecture (5 sections: data structures, interfaces, file list, Mermaid diagrams, deployment topology)
3. **Project-manager** writes the Task Decomposition (Logic Analysis 1:1 with file list, DAG of dependencies, Shared Knowledge files identified first)
4. **frontend / backend / fullstack** implements per the 8-step Engineer SOP (read task, read interface defs, read shared knowledge, implement matching schema verbatim, run tests, self-review, hand back)
5. **qa-engineer** runs the 7 quality gates + 3-case minimum (happy path + edge cases + adversarial)

Skipping any step = scope drift, schema drift, or untested code shipped.

## Pattern 3 - sales-engineer ↔ proposal-writer
**Trigger:** prospect reply turns into an opportunity.

**Handoff:**
- sales-engineer briefs proposal-writer with: stated success criteria, buying committee, competitor situation, decision timeline, budget signal
- proposal-writer drafts; sales-engineer reviews technical accuracy
- Joint review before send; both sign off

## Pattern 4 - security-auditor + cto + devops-engineer (new customer endpoint)
**Trigger:** new customer-facing endpoint about to ship.

**Sequence:**
1. backend-developer writes the endpoint
2. cto reviews architecture decision (ADR if new pattern)
3. security-auditor runs the 9-dimension review pass + runs `uvx snyk-agent-scan@latest` on the agent stack
4. devops-engineer wires CI/CD + observability + rollback path
5. After all pass → deploy

## Pattern 5 - chief-of-staff dispatches multi-employee work
**Trigger:** a request that needs 2+ employees in parallel or sequence.

**Decision (per chief-of-staff rules.md):**
- Single-employee → route directly
- Sequential multi-employee → MetaGPT chain (Pattern 2)
- Parallel multi-employee → spawn workers in mesh / hierarchical / ring / star topology
- Iterative refinement → handoff loop with explicit exit condition

**Conflict resolution (if 2+ employees return contradicting outputs):**
- Both defensible → Gossip protocol (present both to Shai)
- Multiple agree → Raft-style majority
- Hard-rule violation flagged → BFT-style veto (single veto blocks)
- Conflicting partial state → CRDT-style merge

## Pattern 6 - talent-scout ↔ knowledge-synthesizer
**Trigger:** weekly scout sweep produces candidates; or learnings.md hits promotion threshold.

**Direction:**
- Scout → KS: when a candidate is approved + absorbed, KS gets notified to update the affected employee's `learnings.md` with the absorption event
- KS → Scout: when a learning surfaces a capability gap, KS writes to `gaps-to-scout.md` for next sweep

## Pattern 7 - Solaris ↔ Alfred federation
**Trigger:** a cross-namespace need (e.g. "book a flight to a client meeting" → touches both work and personal).

**Hard rule:** namespace isolation by default. Cross-namespace requires explicit federation invocation + Shai approval logged in `meta/shared/federation/approvals.md`.

**Protocol:**
1. chief-of-staff (or alfred-dispatcher) identifies the cross-namespace need
2. Surfaces to Shai with explicit "this crosses Solaris/Alfred - approve?"
3. Approval logged + federation entry written
4. Both sides execute in coordinated handoff with sanitized context (Solaris doesn't see Alfred PII, Alfred doesn't see client confidential data)

## Anti-patterns to refuse
- Skipping handoff documentation ("just figured it out") - reinvented next time
- Cross-employee context bleeding without dispatcher orchestration - context manager exists for a reason
- One employee silently writing into another's rules.md - knowledge-synthesizer owns that promotion
- Sequential when parallel works - wastes time
- Parallel when sequential is required by dependencies - produces broken work

---

## Discipline canon + escalation (added 2026-05-18)

Full canon ownership table + escalation map: `meta/shared/hierarchy.md`.

**Short version:**
- Strategy layer (CEO/CFO/CTO/CMO/COO) owns canon for their discipline + has veto on ambiguity
- Meta layer (chief-of-staff/talent-scout/etc.) routes work + remembers + scouts
- Execution layer is FLAT - no within-department TLs (anti-pattern for AI fleet)
- Conflicts that resolve via protocols (Pattern 5) stay there; conflicts that don't escalate per the hierarchy.md map
- When all else fails → Shai. He is the only "above."
