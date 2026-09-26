# Project Takeover Playbook

For inherited codebases: Kellbell, Turnpike, any agency handoff, rescue project, or existing-client scenario where Day 1 is about understanding, not building.

Runs a specific sequence of three skills. Don't skip stages.

---

## When to use

- New client with existing codebase (not greenfield)
- Rescue project - previous team underperformed or walked
- Post-acquisition due diligence on a repo
- "I inherited this mess, what do I do"
- Any project where the first working day is Day 1 of understanding, not Day 1 of shipping

## When NOT to use

- Greenfield build - different playbook entirely (use cto-advisor's scoping flow)
- Single-feature add-on to a codebase you already know - overkill
- Emergency production bug - use code-review's Debug Mode directly
- You just need a proposal - use upwork-proposals, not this

---

## The Sequence

Three stages, in order. Each stage produces a Mac artifact. The next stage reads that artifact.

### Stage 1: Onboarding (skill: `codebase-onboarding`)

**Goal:** Build a map. No criticism, no fixes - just understanding.

Outputs to Mac:
- `{Project}_Getting_Started.md` - readable "if someone joined tomorrow, what would they read"
- `{Project}_Architecture.md` - framework/stack/version inventory, main entry points, key modules with "what does this do"
- File structure overview with hotspots called out

**Don't start fixing bugs yet.** If code-review fires before onboarding completes, you'll review things you don't yet understand and produce noise - hallucinated criticism of patterns that are actually idiomatic for the stack.

**Time box:** 2-4 hours for a small project, 1-2 days for a medium one, up to a week for a monolith.

**Stage-1 done signal:** The owner could explain the codebase to a stranger in 10 minutes using only these two docs.

### Stage 2: Audit (skill: `code-review`)

**Goal:** Find every issue. Rank by severity. Propose fixes.

Run the full 7-phase code-review after onboarding is complete. Now you know the codebase well enough for the 20 angles to produce real findings, not noise.

Include **Dependency Audit Mode** in this pass - CVEs, outdated packages, license issues go in the same bug tracker. This is the highest-ROI finding category in most takeovers; don't treat it as an afterthought.

Outputs to Mac:
- `{Project}_Code_Bugs.md` - numbered, severity-tagged, ownership-assigned
- `{Project}_Dependency_Report.md` - CVE + upgrade plan
- `{Project}_Design_Spec.md` - colors, fonts, CSS architecture
- `{Project}_Sitemap.md` - every actual page
- Per-controller audit files

**Don't fix yet.** The audit output is the plan. Fix discipline comes later, in normal PR flow gated by code-review PR Review Mode.

**Stage-2 done signal:** every finding has a severity, an owner, and an effort estimate.

### Stage 3: Upgrade Plan (skill: `migration-architect`)

**Goal:** Handle major-version jumps and framework upgrades separately from the bug-fix backlog.

If Stage 2 surfaced any of:
- PHP major version bumps (7.x → 8.x)
- Laravel major version bumps (8 → 11)
- Node major version bumps (14 → 20)
- Framework swaps (AngularJS → Vue, jQuery → React, CodeIgniter → Laravel)
- Database engine migrations (MySQL 5.7 → 8.x, Postgres version bumps)

…those go through `migration-architect`, not `code-review`. Different risk profile, different rollback strategy, different testing discipline.

Outputs to Mac:
- `{Project}_Migration_Plan.md` - compatibility matrix, step-by-step plan with rollback checkpoints
- Effort estimate per stage
- Go/no-go recommendation for each major upgrade

**Stage-3 done signal:** for every major version bump, there's a plan that answers: what breaks, how we test, how we roll back, how long it takes, in what order.

---

## What this playbook deliberately does NOT do

- **Fix anything.** Stages 1-3 produce plans. Fixes happen afterwards in normal PR flow, gated by `code-review` in PR Review Mode.
- **Generate client proposals or quotes.** That's `upwork-proposals` or manual scoping.
- **Deploy anything.** That's `ftp-deploy`.
- **Set up QA.** That's `playwright-pro` after the codebase stabilizes post-fix.
- **Create ClickUp structure.** That comes after this playbook exits, in cto-advisor's normal project-setup flow.

---

## Trigger phrases

- "I'm taking over [project]"
- "inherited this codebase, where do I start"
- "rescue project, full handoff"
- "new client, existing code"
- "give me the takeover plan for [project]"
- "due diligence on this repo"
- "[project] onboarding" when it's clearly a takeover not a greenfield kick-off

---

## Anti-patterns that killed previous takeovers

- **Fixing before understanding.** Jumping to code-review without onboarding produces whack-a-mole bug reports that don't land in the real problem areas.
- **Auditing on Day 1 while scope is still fluid.** Audit output becomes stale by the time client scope is locked in. Onboard first, let scope settle, then audit.
- **Conflating bug fixes with major upgrades.** A PHP 7 → 8 migration isn't a "bug fix" - planning it in the same sprint as security fixes produces rollback hell.
- **Skipping the dep audit inside code-review.** CVEs are usually the highest-ROI finding in a takeover; don't treat them as an afterthought.
- **Doing all three stages in one the coding agent session.** Each stage is enough work for its own session with fresh context. Chain the handoff via Mac files.
- **Letting stage-1 drag.** Onboarding has a clear "done" signal (see above). If it runs past the time box without that signal, the codebase is bigger than expected - replan scope, don't just keep grinding.

---

## Session hand-off pattern

Each stage writes to Mac files that the next stage reads. Don't rely on the coding agent's context window to carry stage-1 output into stage-3.

```
Stage 1 session ends →
  writes {Project}_Getting_Started.md, {Project}_Architecture.md

Stage 2 session starts →
  reads Stage 1 outputs from Mac,
  writes {Project}_Code_Bugs.md, {Project}_Dependency_Report.md,
  {Project}_Design_Spec.md, {Project}_Sitemap.md

Stage 3 session starts →
  reads Stage 2 outputs from Mac,
  writes {Project}_Migration_Plan.md
```

Each new session begins with: list allowed dirs, read the handoff file for this project, read the prior stage's output, start work.

---

## Integration with cto-advisor's normal workflow

This playbook is the **prequel** to project execution. It runs once, at the start, to figure out what we're dealing with.

After Stage 3, the output plans flow back into cto-advisor's normal project setup:
- ClickUp structure created from the bug tracker + migration plan
- Milestones planned around fix batches and migration stages
- Team assignments based on effort estimates
- Client communication (white-label rule active) summarizing findings without exposing internal team structure

cto-advisor handles the sequel. This playbook just gets us to a starting line that's actually a starting line.
