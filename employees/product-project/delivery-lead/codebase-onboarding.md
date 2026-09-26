# Takeover Stage 1 - Codebase Onboarding (reference)

Delivery Lead ORCHESTRATES this stage; it does not perform it. The capability is the `codebase-onboarding` skill (full source: `solaris/archives/laptop-skills-2026-06/codebase-onboarding/`, incl. `scripts/codebase_analyzer.py`). In Solaris, the engineering employees (full-stack-developer / code-reviewer) execute it.

## Purpose
Auto-generate onboarding docs from an existing codebase: architecture + stack discovery from repo signals, key-file/config inventory, local-setup + common-task guidance, audience-aware framing, debugging/contribution checklist. Build a MAP - no criticism, no fixes.

## Outputs (to the client folder)
- `{Project}_Getting_Started.md` - "if someone joined tomorrow, what would they read".
- `{Project}_Architecture.md` - framework/stack/version inventory, entry points, key modules ("what does this do").
- File-structure overview with hotspots.

## Process
1. `python3 scripts/codebase_analyzer.py /path/to/repo [--json]` - gather facts.
2. Frame for the audience (new contributor / contractor / TL).
3. Stop at understanding. Do NOT review or fix yet - that produces hallucinated criticism of idiomatic patterns.

## Done signal
The owner could explain the codebase to a stranger in 10 minutes using only the two docs. Time box: 2-4h small / 1-2d medium / up to a week for a monolith - if it overruns without the done signal, the codebase is bigger than scoped: replan, don't grind.

→ Next: Stage 2 (code-reviewer, full 7-phase + dependency-audit). Then Stage 3 (migration-architect).
