# Shai's AI Employees

A complete virtual AI company. 52 work employees organized into 12 departments (plus the meta orchestration layer and the Alfred personal namespace), each one a Claude plugin with skills, internal self-learning, and external-knowledge absorption.

## The two self-learning loops

**Internal (Knowledge Synthesizer)** - looks inward across employees.
- Every session, employees may observe things worth remembering → `learnings.md`
- When observation hits 2+ occurrences → Knowledge Synthesizer **rewrites `rules.md`** (methodology update, not a log append)
- Cross-employee patterns → promoted to org-wide rules in `hierarchy.md`

**External (Talent Scout)** - looks outward to the world.
- Weekly scheduled GitHub + web scans for new skills, tools, techniques
- Receives gap-requests from Knowledge Synthesizer when "we keep lacking X"
- Reports back with external solutions to absorb per employee

Together: continuous improvement, not a dead log.

## Structure

See `hierarchy.md` for the full org chart. Every employee folder contains:

```
<employee>/
├── SKILL.md          - identity, triggers, quick rules (always loaded on activation)
├── rules.md          - the methodology (how this employee works)
├── learnings.md      - pending observations awaiting promotion to rules
├── plugin.json       - Claude plugin manifest
└── references/       - deep-dive files, loaded on demand
```

## Installation

On any laptop signed into the same Claude account:

```bash
cd ~/Desktop/CTO
git clone <private-github-url> shai-employees
cd shai-employees
./install.sh
```

All employees install as Claude plugins in one shot. Current count is regenerated from disk in meta/roster-manager/references/roster.md (66 total: meta 6 + solaris 52 + alfred 8; gigs are a separate class, not counted).

## Philosophy

- **One employee per job.** No overlap - UI/UX/Graphic/Visual/A11y Design is ONE employee.
- **Quality over marketing.** Content merged from 6 source repos, reviewed for depth, not README hype.
- **Methodology updates, not logs.** Learnings rewrite the method; they don't append to a pile.
- **Internal + external learning.** Synthesizer + Scout = compounding intelligence.
- **Hierarchy is real.** Chief of Staff dispatches; C-suite owns departments; specialists execute.

## Source repos absorbed

- [wshobson/agents](https://github.com/wshobson/agents) - 184 agents
- [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) - 147 agents
- [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) - 235 skills + C-suite
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) - 131+
- [lodetomasi/agents-claude-code](https://github.com/lodetomasi/agents-claude-code) - 100 specialists
- [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) - 1,435+ meta-catalog

Plus continuous absorption from the Talent Scout's weekly scans.
