# Takeover Stage 3 - Migration Architect (reference)

Delivery Lead ORCHESTRATES this stage; it does not perform it. The capability is Shai's `migration-architect` skill (full source: `solaris/archives/shai-laptop-skills-2026-06/migration-architect/`). In Solaris, engineering (full-stack-developer / backend-developer) executes it.

## When it fires
ONLY for major-version jumps / framework swaps / engine migrations surfaced in Stage 2 - NOT for the bug-fix backlog (different risk profile, different rollback, different testing). Examples: PHP 7.x→8.x, Laravel 8→11, Node 14→20, AngularJS→Vue, jQuery→React, CodeIgniter→Laravel, MySQL 5.7→8, Postgres bumps.

## Core capabilities
- **Strategy planning** + **compatibility analysis** + **rollback strategy generation**.
- **Patterns:** Strangler Fig · Parallel Run · Canary; schema evolution + data-migration strategies; cloud-to-cloud + on-prem-to-cloud; feature flags for progressive rollout; circuit breaker.
- **Validation/reconciliation** between old and new during cutover.
- **Rollback** at DB / service / infrastructure layers.
- **Risk framework** (categories + mitigation) + **runbooks** (pre / during / post-migration checklists) + comms templates (exec summary + technical update).

## Output (to the client folder)
- `{Project}_Migration_Plan.md` - compatibility matrix, step-by-step plan with rollback checkpoints, effort estimate per stage, go/no-go per major upgrade.

## Done signal
For every major version bump: what breaks, how we test, how we roll back, how long it takes, in what order.

→ After Stage 3, output flows into normal project setup (ClickUp from bug tracker + migration plan; milestones around fix batches + migration stages; white-label client summary).
