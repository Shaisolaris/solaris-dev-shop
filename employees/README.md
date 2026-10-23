# Employees

61 work employees in 12 departments. The chief of staff is not in that count. It lives in `chief-of-staff/`. Alfred is not in this public edition.

## The two self-learning loops

**Internal (learning proposals)** - record useful observations in the owner's
project notes. Installed workflow files are read-only during ordinary use.
Repeated observations may justify a proposed source change, but neither a
repetition count nor a budget authorizes rewriting `learnings.md`, `rules.md`,
`SKILL.md`, catalogs or manifests. Make an authorized source change on a branch,
review it and validate its affected behavior before distributing an update.

**External (market watch)** - looks outward to the world.
- GitHub + web research for new skills, tools and techniques only when requested; no weekly schedule is installed by this product
- Receives gap-requests from the learnings sweep when "we keep lacking X"
- Reports back with external solutions to absorb per employee

Improvement is reviewed work, not an automatic background loop or self-updater.

## Structure

See `hierarchy.md` for the full org chart. Every employee folder contains:

```
<employee>/
├── SKILL.md          - identity, triggers, quick rules (always loaded on activation)
├── rules.md          - the methodology (how this employee works)
├── learnings.md      - bundled observations; proposed changes require source review
├── plugin.json       - skill plugin manifest
└── references/       - deep-dive files, loaded on demand
```

## Installation

Copy one employee folder into the place your coding agent loads project skills. Start with `SKILL.md`. If that file says to load `rules.md`, copy that too.

The public count is 61. See `docs/employees.md` in the repository root. Do not use an older 52 or 73 figure.

## Philosophy

- **One employee per job.** No overlap - UI/UX/Graphic/Visual/A11y Design is ONE employee.
- **Quality over marketing.** Content merged from 6 source repos, reviewed for depth, not README hype.
- **Methodology updates, not logs.** Learnings rewrite the method; they don't append to a pile.
- **Internal + external learning.** Sweeps + market watch = compounding intelligence.
- **Hierarchy is real.** Chief of Staff dispatches; C-suite owns departments; specialists execute.

## Source repos absorbed

- [wshobson/agents](https://github.com/wshobson/agents) - 184 agents
- [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) - 147 agents
- [alirezarezvani/the coding agent-skills](https://github.com/alirezarezvani/the coding agent-skills) - 235 skills + C-suite
- [VoltAgent/awesome-the coding agent-code-subagents](https://github.com/VoltAgent/awesome-the coding agent-code-subagents) - 131+
- [lodetomasi/agents-the coding agent-code](https://github.com/lodetomasi/agents-the coding agent-code) - 100 specialists
- [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) - 1,435+ meta-catalog

Plus continuous absorption from market-researcher's scans.
