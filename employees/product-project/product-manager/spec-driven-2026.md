# Spec-driven product workflow + BMAD planning pipeline - depth reference

METHODOLOGY absorption (2026-06-15). Methodology only - no CLI, no agent bundles, no code is installed or run. Two complementary external methods folded into how the PM specifies and sequences product work:

- **github/spec-kit** (Spec-Driven Development; MIT; 112,273 stars; pushed 2026-06-11; not archived) - the constitution -> spec -> plan -> tasks sequence and the PR-reviewable, executable-spec discipline.
- **bmad-code-org/BMAD-METHOD** (Breakthrough Method for Agile AI-Driven Development; MIT per the LICENSE file text, GitHub auto-classifier shows NOASSERTION = FLAG; 49,144 stars; pushed 2026-06-14; not archived) - the greenfield planning persona pipeline (analyst -> PM -> architect -> scrum master) and the plan-then-build, web-bundle-upfront discipline.

## Gate-0 (why this is net-new, not a duplicate)
The PM already owns discovery (W2 OST/JTBD), positioning (W2.5), the PRD (W1, house skeleton + MetaGPT 9-section), prioritization (W3), roadmap (W4), and metrics (W5). What it did NOT have:
1. An explicit **spec-as-the-reviewable-artifact** discipline - the PRD was the doc, but the idea that the spec itself is version-controlled, PR-reviewed, and consistency-checked BEFORE any plan/tasks is new.
2. A named **constitution** layer - durable, project-level principles (quality bar, testing standard, UX consistency, performance budget) that every spec inherits and is checked against.
3. The clean **spec -> plan -> tasks** decomposition with a clarify gate and a cross-artifact consistency check, distinct from the prioritization/roadmap motions.
4. The **BMAD plan-then-build sequencing** framing for greenfield: do ALL the upfront planning (brief -> PRD -> architecture -> sharded stories) before implementation, and the persona-pipeline view of who produces each artifact.
This reference adds those without re-deriving the PRD skeleton, OST, or RICE that already exist. It plugs in BEFORE the engineering handoff (PM -> cloud-architect -> project-manager chain in rules.md).

## A. Spec-Driven Development (spec-kit) - the constitution -> spec -> plan -> tasks ladder
Core inversion: the specification is the source of truth, not scaffolding to discard once coding starts. The spec is meant to be precise enough that a plan and tasks fall out of it. Treat each artifact as a reviewable deliverable, not a throwaway brief.

The ladder (each step is its own artifact, reviewed before the next):
1. **Constitution** (project governing principles) - written ONCE per project, updated rarely. Captures the non-negotiables: code-quality bar, testing standard, UX consistency rules, performance requirements, security gates. Every later spec and plan is checked against it. This is the PM's product-principles layer made explicit and durable, distinct from a single feature's goals.
2. **Specify** (the spec) - describe WHAT to build and WHY. Requirements + user stories + acceptance criteria. Deliberately tech-stack-agnostic at this stage (no framework/library choices). This maps to the PM's existing PRD house skeleton - keep that skeleton; the new discipline is that the spec is version-controlled and PR-reviewable on its own.
3. **Clarify** (recommended gate before planning) - sequential, coverage-based questioning that surfaces underspecified areas and records the answers in a Clarifications section of the spec. This is the structured form of the PM's existing "every open question has an owner + deadline" rule - run it BEFORE the plan, not after dev starts.
4. **Plan** (the technical implementation plan) - NOW introduce the tech stack and architecture choices. Owned at the architecture layer (cloud-architect), informed by the spec. The PM hands a locked, clarified spec into this step.
5. **Tasks** (actionable task list) - decompose the plan into ordered, executable tasks. This is the handoff into delivery (project-manager / delivery-lead own execution mechanics).
6. **Analyze** (cross-artifact consistency + coverage) - run after tasks, before implementation: does every requirement in the spec trace to a task? Any contradictions between constitution, spec, plan, and tasks? Gaps? This is a coverage check the PM owns at the product level (spec -> tasks traceability) even though execution is downstream.
7. **Checklist** (quality checklists - "unit tests for English") - generate checklists that validate the spec's own completeness, clarity, and consistency. Useful as a PM gate on the spec before it leaves the product desk.

PM-owned slice: constitution, specify, clarify, the spec-side of analyze (requirement-to-task coverage), and checklist. Plan/tasks/implement are downstream (architecture + delivery), but the PM is responsible for the spec being clear enough that they succeed.

## B. BMAD planning pipeline - plan-then-build, persona by persona
BMAD's contribution for the PM is the **sequencing discipline for greenfield work**: do the full upfront planning before implementation, with a clear chain of who produces what.

The greenfield persona pipeline (the artifact chain, not the agents):
- **Analyst** -> brainstorming, market/industry research, the product brief. (PM's discovery W2 feeds this; analyst-style research routes to market-researcher.)
- **PM** -> the PRD (this employee's W1). BMAD's PRD sits on top of the brief.
- **Architect** -> the architecture document from the PRD. (cloud-architect owns this; it is the spec-kit "plan" step.)
- **Scrum master / dev** -> shard the PRD + architecture into epics and small, self-contained story files that an implementer can build one at a time. (Execution mechanics live with project-manager / delivery-lead; the PM provides the PRD that shards cleanly.)

Key BMAD disciplines worth carrying:
- **Plan fully, then build.** Finish brief -> PRD -> architecture -> sharded stories BEFORE implementation. Mid-build planning is where greenfield projects rot. (Reinforces the PM's "lock scope with written sign-off before dev" rule.)
- **Scale-adaptive depth.** Adjust planning depth to project complexity - a bug fix does not get the same ceremony as an enterprise system. Mirrors the PM's existing format selector (Standard PRD vs One-Page vs Feature Brief) and the small-task lane.
- **Upfront planning on flat-rate tooling.** BMAD's web-bundle approach (do brainstorming/brief/PRD/PRFAQ/UX in a web LLM, bring polished artifacts into the IDE for implementation) is an execution-cost note, not a PM methodology; recorded here as context, not adopted as a rule.
- **Self-contained story files.** Stories should carry enough context to be built without re-reading the whole PRD. The PM's job is a PRD whose stories (As-a/I-want/so-that + >=3 Given/When/Then) shard into exactly that.

## C. How this wires into the existing PM workflows
- Slots between **W2.5 (positioning)** and the engineering handoff. New optional **Workflow 1.5 (spec-driven kickoff)**: write/confirm the constitution -> turn the PRD into a reviewable spec -> run clarify -> hand the locked, clarified spec to cloud-architect for the plan. Use it when the engagement runs the spec-driven chain; the classic PRD path (W1) still stands for everything else.
- The **constitution** is a once-per-project artifact; the PM authors the product half (quality/UX/performance principles) and inherits the technical half from the CTO/architect.
- The **clarify gate** is the structured upgrade to the PM's open-questions rule - run it before plan, record answers in the spec.
- **analyze/checklist** give the PM a spec-quality gate before handoff: every requirement traces to a task; the spec passes its own completeness checklist.
- Boundary preserved: PM owns constitution(product half)/spec/clarify/spec-coverage/checklist. **cloud-architect** owns plan. **project-manager / delivery-lead** own tasks -> implement (execution mechanics, sharding, ClickUp). This is the existing PM -> cloud-architect -> project-manager -> engineering chain, now with named spec-driven artifacts on it.

## Sources (methodology only; nothing bundled or run)
- github/spec-kit - MIT - 112,273 stars - pushed 2026-06-11 - not archived. Constitution/specify/clarify/plan/tasks/analyze/checklist/implement ladder; executable-spec, spec-as-source-of-truth discipline. CLI (specify-cli), templates, and agent command files are NOT installed; self-host upstream if the tooling is wanted.
- bmad-code-org/BMAD-METHOD - MIT (LICENSE file is verbatim MIT; GitHub auto-detect = NOASSERTION = FLAG) - 49,144 stars - pushed 2026-06-14 - not archived. Greenfield planning persona pipeline (analyst -> PM -> architect -> scrum master), plan-then-build, scale-adaptive depth, sharded self-contained story files. Agent bundles, workflows, and web bundles are NOT installed.
