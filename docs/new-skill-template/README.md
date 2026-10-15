# New Skill Template

After proposal review, create `employees/<department>/<skill-name>/` using this
checklist and a current specialist such as
[QA Engineer](../../employees/quality-security/qa-engineer/SKILL.md) as a structural
reference. This folder contains the checklist, not five finished template files.
All five source files below are required.

## Required files

| File | Purpose |
|---|---|
| `SKILL.md` | The skill: name, description, when to use, workflows, methodology. Start with YAML frontmatter (`name`, `description`). |
| `rules.md` | Hard rules: must/must-not, escalation boundaries, license flags, do-not-invent lists. |
| `learnings.md` | Dated learnings. Start with at least 3 real, non-trivial entries. No placeholders. |
| `plugin.json` | Manifest: `name`, `version`, `description`, `author`, `license` (MIT), `skills: ["SKILL.md"]`, `references`, `tags`, `department`. |
| `capability.contract.json` | Routing contract: capability id, department, description, keywords for the intake router. |

## Checklist before proposing

- [ ] Frontmatter `name`, manifest `name`, and contract `identity.name` match the folder; contract `identity.id` is `solaris.<name>`
- [ ] Description says when the router should pick this skill (trigger phrases included)
- [ ] No references to files that do not exist (run a link check)
- [ ] No personal names, emails, or private anecdotes anywhere in the tree
- [ ] `author` is `Solaris Dev Shop`, `license` is `MIT`
- [ ] `learnings.md` has dated observations from actual worked examples; do not invent experience to fill the file
- [ ] After proposal review, register the capability in `control-plane/roster.json` and add routes and probes in `control-plane/policy.json` and `control-plane/routing-probes.md`
- [ ] Update skill counts and affected docs as part of that reviewed addition
- [ ] Run `python3 tools/build_skill_catalog.py`, then commit the generated catalog
- [ ] `python3 -m unittest discover -s tests -v` and `python3 control-plane/meta_control_plane.py self-test` pass
- [ ] `python3 tools/validate_skill_metadata.py` passes (install `requirements-dev.txt` first)
- [ ] `python3 employees/quality-security/assurance/quality_os.py audit` shows the new skill with 0 gaps

## Propose first

Open a [new employee proposal](../../.github/ISSUE_TEMPLATE/new-employee.md) issue before building. Unproposed skills will not be merged.
