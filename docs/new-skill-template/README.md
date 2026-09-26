# New Skill Template

Copy this folder to `employees/<department>/<skill-name>/` and fill every file. All five files are required.

## Required files

| File | Purpose |
|---|---|
| `SKILL.md` | The skill: name, description, when to use, workflows, methodology. Start with YAML frontmatter (`name`, `description`). |
| `rules.md` | Hard rules: must/must-not, escalation boundaries, license flags, do-not-invent lists. |
| `learnings.md` | Dated learnings. Start with at least 3 real, non-trivial entries. No placeholders. |
| `plugin.json` | Manifest: `name`, `version`, `description`, `author`, `license` (MIT), `skills: ["SKILL.md"]`, `references`, `tags`, `department`. |
| `capability.contract.json` | Routing contract: capability id, department, description, keywords for the intake router. |

## Checklist before proposing

- [ ] `name` in frontmatter, `plugin.json`, and `capability.contract.json` all match the folder name
- [ ] Description says when the router should pick this skill (trigger phrases included)
- [ ] No references to files that do not exist (run a link check)
- [ ] No personal names, emails, or private anecdotes anywhere in the tree
- [ ] `author` is `Solaris Dev Shop`, `license` is `MIT`
- [ ] `learnings.md` has dated entries with real substance, not filler
- [ ] `python3 tests/test_router.py` passes with the new capability registered
- [ ] `python3 control-plane/quality_os.py audit --quiet` shows the new skill with 0 gaps

## Propose first

Open a [new employee proposal](../../.github/ISSUE_TEMPLATE/new-employee.md) issue before building. Unproposed skills will not be merged.
