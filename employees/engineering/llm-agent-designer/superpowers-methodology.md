# Superpowers Methodology - Design Before Build

> ⚠️ ALWAYS load this file FIRST when designing a new agent / LLM application / a skill file / multi-step workflow. Without it, the coding agent jumps to code and ships the wrong thing fast.

**Source canon:** [obra/superpowers](https://github.com/obra/superpowers) - 169,582 stars (most-starred a coding agent project on GitHub), MIT, last commit 2026-04-24. By Jesse Vincent + Prime Radiant team. Companion repos: `obra/superpowers-skills` (community skills), `obra/superpowers-marketplace` (curated plugin marketplace), `obra/superpowers-lab` (experimental).

**What it is:** a complete software-development *methodology* for coding agents - a set of composable skills + initial instructions that ensure the agent uses them. Built around three command-driven phases: `/brainstorm` → `/write-plan` → `/execute-plan`. TDD-first. With a `skills-search` tool for skill discovery.

**Why it matters for LLM Agent Designer:** the base skill cites Solaris's own 59 plugins as the canonical reference. Self-referential is fine but doesn't capture the *industry-default* "design before code" methodology that's now consolidating around superpowers as the dominant pattern. This file fills that gap.

---

## The 3-step methodology (the load-bearing insight)

### `/brainstorm` - what are we actually trying to do?
Before any code, the agent steps back and elicits a spec from the conversation:
- What's the *user-visible* outcome? (Not the technical solution - the actual change in the world.)
- What's the simplest version that delivers that outcome?
- What are we explicitly *not* doing? (Non-goals - bigger value than goals; clears scope creep.)
- What's the failure mode if we ship the simplest version and stop?

Output: a 3-10 line spec that the human can read in 30 seconds and confirm.

### `/write-plan` - how exactly are we going to build it?
Once the spec is signed off, the agent writes a plan:
- Numbered steps, each small enough to execute in one focused chunk
- Each step has: what's being changed, why, and how we'll verify it works
- Dependencies between steps explicit
- Test approach declared upfront (TDD-first - write the test before the implementation when possible)
- Rollback strategy if a step goes sideways

Output: a plan a junior engineer with "no taste, no judgement, no project context, and an aversion to testing" could follow. (Per superpowers' own framing.) That bar is deliberate - if a plan needs interpretation, it isn't a plan, it's a wishlist.

### `/execute-plan` - do the work, one step at a time
Now the agent executes:
- One step at a time, in order
- After each step: run the test (or smoke check), confirm green, commit
- If a step blocks, back to `/write-plan` for that segment, not full restart
- Surface deviations from plan as they happen - don't silently re-plan

This is the discipline the methodology enforces.

---

## Why this methodology works for agent design

The most common failure mode in agent-built work isn't bad code. It's **building the wrong thing fast**. Agents have low cost-per-token and high speed; they outpace humans into bad scope. The 3-step methodology slows down the *first kilometer* (brainstorm + plan) so the *next 100* are in the right direction.

For Solaris specifically:
- **Client work** - the brainstorm step is where ambiguity gets resolved with the client BEFORE engineering hours. Same purpose as a discovery doc; different tool.
- **Plugin / employee design** - the brainstorm step is where the employee's role + altitude + dispatch is locked before SKILL.md drafting. Without it, employees drift into accumulation.
- **Skill creation** - `skill-creator` already in installed skills; superpowers methodology is the *workflow* on top.
- **MCP server design** - the plan step is where tool schemas + auth + error responses get specified before code. Without it, MCP servers ship with LLM-hostile errors.

---

## Decision rules - when to use the methodology

### Always use the 3-step
- Building a new agent / LLM app / multi-step workflow
- Designing a new Solaris employee
- Designing a a skill file or MCP server
- Inheriting a client codebase + planning the next change
- Any change that touches >3 files or >50 lines

### Skip the 3-step (just do it)
- Trivial fixes (typo, single-line bug)
- Mechanical refactors with deterministic outcome
- Documentation-only changes
- Following an existing plan that's already approved

### Modify the 3-step
- For small changes, collapse brainstorm + plan into a single 5-line spec
- For big changes, expand brainstorm into multiple iterations before locking
- For client work, the brainstorm should produce a doc the client can sign off on

---

## TDD-first discipline (superpowers default)

The methodology assumes test-first development whenever feasible:
1. **Write the test that fails** - describe the desired behavior in test form
2. **Run it** - confirm it fails for the right reason (not setup error)
3. **Make it pass** - minimum implementation to flip the test green
4. **Refactor** - clean up while green
5. **Repeat** - next failing test

Why this matters at agent altitude:
- Agents tend to write code that "looks right" without verification - TDD forces the verification step
- Tests act as a contract: "the work is done when these pass" - no scope drift
- For prompt engineering specifically: an eval test is the TDD equivalent. Write the eval before iterating on the prompt.

When to skip TDD:
- Exploration / spike code that will be thrown away
- UI-pixel work where automated tests are pricier than manual review
- Throwaway prototypes for a brainstorm session

---

## `skills-search` - the discovery layer

The superpowers ecosystem ships a `skills-search` tool that lets the agent (or human) search across installed skills semantically. The pattern:
1. Before writing a new skill, search if one already exists ("is there a skill for X?")
2. Before answering a methodology question, search if a skill encodes the answer
3. After completing work, observe whether a skill *should* exist and propose creating one

For Solaris this maps directly onto the **skill self-improvement loop** (search what's available before duplicating). Cross-reference with the skill scanner's `quality-filter.md`.

---

## Composable skills protocol

Superpowers' design treats skills as **composable units**:
- Each skill does ONE thing well
- Skills can call other skills
- Skills declare their inputs + outputs as schemas
- Skills are discoverable via metadata (description + tags)

This matches Solaris's own design but adds explicit *composition* primitives. For the LLM Agent Designer, this means:
- When designing a new Solaris employee, ask: "Does this employee compose other skills, or does it duplicate them?"
- If composing, declare the dependency in plugin.json
- If duplicating, that's an anti-pattern - refactor the shared logic into a reusable skill or reference file

---

## Anti-patterns the methodology prevents

- ❌ **Jumping to code** - answer "what are we doing?" before "how?"
- ❌ **Plans that aren't executable** - if the plan requires interpretation, it isn't a plan
- ❌ **Silent re-planning** - if a step blocks, surface it; don't re-plan in your head
- ❌ **Skipping the test step** - "I'll add tests after" never happens
- ❌ **Scope drift inside `/execute-plan`** - new requirements go back to `/brainstorm`, not into the current plan
- ❌ **Treating skills as monolithic** - small composable skills > one giant skill
- ❌ **Reinventing existing skills** - skills-search first

---

## Cross-references inside Solaris

- **Skill scanner** - `skills-search` pattern aligns with the scanner's own discovery + dedup logic; cross-reference in Scout's quality-filter
- **CTO** - project-takeover protocol Phase 2 (Audit) maps onto `/brainstorm`; Phase 3 (Upgrade Plan) maps onto `/write-plan`
- **Project Manager** - sprint-planning workflow uses the 3-step at sprint altitude (brainstorm = sprint goal, plan = sprint backlog, execute = standup-driven work)
- **Code Reviewer** - PR-review mode benefits from "did this PR follow the plan?" - when the diff doesn't match the plan, that's a flag
- **QA Engineer** - TDD-first methodology is the QA-Engineer-friendly version of how dev work should arrive
- **Solaris's own employee design** - every new employee absorption goes through Phase 1-6, which is the Solaris-flavored 3-step (Discovery → Extraction → Outline = brainstorm + plan; Draft → Self-QA → Commit = execute)

---

## When NOT to use superpowers methodology (be honest)

- Single-shot LLM apps where there's no agent loop (just prompt + response)
- Workflows that are inherently exploratory and the deliverable IS the exploration
- Live debugging where speed beats discipline
- Throwaway prototypes whose purpose is to be thrown away

For everything else: brainstorm → plan → execute. The discipline is the value.

---

## Companion install (optional)

```bash
# The superpowers framework as a a coding agent plugin
the coding agent /plugin install obra/superpowers

# Brings: /brainstorm, /write-plan, /execute-plan slash commands
# Plus: skills-search tool, TDD scaffolding, composable-skills protocol
```

Whether to install on the owner's machine is their call - the methodology stands on its own as documented here regardless. Install only if the owner wants the slash commands present in their sessions.
