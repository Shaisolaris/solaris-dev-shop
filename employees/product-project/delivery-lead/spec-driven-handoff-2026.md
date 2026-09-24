# Spec -> plan -> tasks handoff discipline (PR-reviewable specs as a client deliverable)

METHODOLOGY absorption (2026-06-15). Source: github/spec-kit (Spec-Driven Development; MIT; 112,273 stars; pushed 2026-06-11; not archived). Methodology only - the Specify CLI, templates, and agent command files are NOT installed or run; self-host upstream if the tooling is wanted. This file is how Delivery Lead uses the spec-driven discipline as a CLIENT-DELIVERY artifact.

## Why it exists here (the gap it closes)
Delivery Lead already owns **spec-lock**: every interaction mechanic (what commits an answer, what advances, what Back does, timer-at-zero, reload-mid-flow) locked in writing, signed off next to its screen, before code. That is a SIGN-OFF discipline - it stops unspec'd guesses turning client clarifications into free feedback. What it did NOT have is the **artifact-shape discipline**: structuring the locked spec as a versioned, PR-reviewable document that decomposes cleanly into a plan and an ordered task list, with a constitution layer and a consistency gate. Spec-kit supplies that shape. Delivery Lead carries it as the way a locked spec is written, reviewed, and handed to the dev - and, where the engagement wants it, as a CLIENT-FACING deliverable in its own right.

## The artifact ladder (each is a reviewable deliverable)
1. **Constitution** - the project's governing rules, written once: code-quality bar, testing standard, deployment/rollback policy, security gates, the white-label and information-wall constraints that apply to every milestone. The dev's API Contract + Schema + Design Spec sit under it. Update rarely. (This is the durable layer above the per-milestone spec.)
2. **Spec** - WHAT and WHY: the locked mechanics (existing spec-lock content) written as a version-controlled document with requirements + acceptance criteria, not buried in a chat or a comment. The spec is the source of truth; the milestone is built from it.
3. **Clarify gate** - before any plan/build, run coverage-based questioning and record answers in a Clarifications section of the spec. This IS the existing "draft clarification questions for Shai, cross-reference existing docs, do not self-answer" rule, given a fixed home in the artifact. Parse inbound docs (Docling) first, then clarify only the gaps in one batched round.
4. **Plan** - the technical implementation plan (stack/architecture). Owned by the dev/TL under the architect's defaults; Delivery Lead consumes it, does not author the architecture.
5. **Tasks** - the ordered, executable task list. This maps directly to the existing ClickUp authoring: milestone = section; deliverable-level parent tasks; implementation subtasks; per-milestone `X.1/X.2/X.CR/X.QA/X.TL`; actual task numbers in dependencies; gate as a checklist on the review task.
6. **Analyze (consistency + coverage)** - before build, confirm every requirement in the spec traces to a task and nothing contradicts the constitution. This is a coverage gate on the ClickUp doc against the spec - it catches the historical failure modes in learnings.md (missing /submit endpoint, mirror-not-mirrored, gate placed on the wrong milestone) by forcing requirement-to-task traceability up front.
7. **Checklist ("unit tests for English")** - run a completeness/clarity/consistency checklist on the spec itself before it leaves the desk. A spec that fails its own checklist is not ready to build.

## How Delivery Lead uses it (the wire into the existing pipeline)
- **Spec-lock keeps its primacy.** The mechanic-lock sign-off rule is unchanged; spec-kit only changes how the locked spec is SHAPED (versioned, reviewable, decomposable) - it does not relax "signed off next to the screen before code."
- **Tasks = the ClickUp doc.** The spec-kit "tasks" step is the existing ClickUp Setup Guide. No new tool: a VA still copies the doc into ClickUp on a fixed-price micro-task; milestone = section; gate = checklist on the review task; dependencies use real task numbers.
- **Analyze before the three-layer review.** Run requirement-to-task coverage BEFORE the build, so the three-layer review (PO code review -> QA browser -> conditional TL) is verifying against a spec that is known-complete, not discovering scope gaps in QA.
- **Constitution carries the constraints.** The white-label rule, the information wall, GitHub-is-truth, verify-before-claim, and QA-mandatory live in the project constitution so every milestone spec inherits them.
- **PR-reviewable spec as a client deliverable (optional, engagement-dependent).** Where a client wants visibility, the spec/plan/tasks become a reviewable deliverable the client signs off on - white-label voice ("I", never "we"), information-wall clean (no contractor names, rates, "from client" attribution), verify-before-claim on every figure. A signed-off spec is a billable baseline; anything later that contradicts it is a change request, not feedback. This is the existing spec-lock economics expressed as a reviewable artifact.

## Boundaries (no duplication)
- This does NOT replace spec-lock, the three-layer review, the ClickUp authoring rules, the billing-model rule, or the doc-generation bundle/registry. It is the artifact SHAPE that the locked spec takes and the order it flows in.
- **Product-manager owns spec AUTHORING** for product work (constitution product-half, spec, clarify, checklist) - see the PM's spec-driven-2026.md. Delivery Lead owns the spec as a CLIENT-DELIVERY artifact and the handoff-to-dev discipline. Same ladder, different consumer: PM produces the product spec; Delivery Lead turns a locked engagement spec into reviewable client deliverables + the ClickUp task breakdown. Coordinate; do not double-author.
- **cloud-architect** owns the plan (architecture); Delivery Lead consumes it.
- No CLI, no agent bundles, no code installed. If a client or dev wants the actual spec-kit tooling, the host self-hosts it upstream.

## Honesty / limits
- Spec-kit is a methodology and a CLI; only the methodology is adopted here. Do not claim a spec was "generated" by a tool that is not installed.
- A spec passing its own checklist is necessary, not sufficient - the three-layer review and QA gate still decide "done"; never close a milestone on a clean spec or code review alone (Layer 2 browser QA is mandatory).

## Source (methodology only; nothing bundled or run)
- github/spec-kit - MIT - 112,273 stars - pushed 2026-06-11 - not archived. Constitution/specify/clarify/plan/tasks/analyze/checklist/implement ladder; spec-as-source-of-truth, PR-reviewable executable spec discipline. Specify CLI, templates, and agent command files NOT installed.
