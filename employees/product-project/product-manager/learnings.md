# Product Manager - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: "Outcomes over outputs" is the single most violated PM principle. Codified as hard rule.
- **2026-04-24 - Clean build**: Instrumentation-before-ship is the difference between a learning org and a feature factory. Required pre-launch.
- V5-ORDER-04: removed the coding agent-is provider lock-in; employee is provider-neutral.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-05-01 - M1 absorption: MetaGPT PRD schema (v0.4.0)
- **Pattern absorbed**: 9-section PRD canonical structure (Original Requirement, Goals, User Stories, Competitive Analysis, Requirement Analysis, Requirement Pool with P0/P1/P2, UI Draft, Open Questions)
- **Why this matters**: Battle-tested at MetaGPT scale - eliminates ambiguity in Architect handoff
- **Hard rule added**: No engineering work begins without a PRD passing this schema
- **Source**: github.com/FoundationAgents/MetaGPT
- **Verification plan**: Use this schema on next 3 client kickoffs, compare clarity vs prior unstructured briefs

## 2026-06-15 - DEEPEN: spec-driven + BMAD planning (v0.7.0)
- **Absorbed (methodology only, nothing bundled/run)**: github/spec-kit (MIT, 112,273 stars) constitution -> spec -> clarify -> plan -> tasks -> analyze -> checklist ladder; bmad-code-org/BMAD-METHOD (MIT per LICENSE text; GitHub auto-detect NOASSERTION = FLAG; 49,144 stars) greenfield persona pipeline analyst -> PM -> architect -> scrum master + plan-then-build.
- **Net-new (Gate-0 PASS)**: the constitution layer + the spec-as-PR-reviewable-source-of-truth ladder + BMAD plan-then-build sequencing - none existed; the PM had PRD/OST/RICE/roadmap/metrics but no explicit spec-driven artifact discipline.
- **Wired**: spec-driven-2026.md + Workflow 1.5 (spec-driven kickoff) + two When-rules. Boundary held: PM owns constitution(product half)/spec/clarify/checklist; cloud-architect owns the plan; project-manager/delivery-lead own tasks->implement.
