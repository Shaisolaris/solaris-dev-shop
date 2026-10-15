# Make your first contribution

Useful contributions improve a user's task: fix a routing miss, make a skill
easier to use, add a reproducible deliverable example, or propose a missing
specialist. You do not need to add a new role to contribute.

## Pick a task

1. Browse [good first issues](https://github.com/Shaisolaris/solaris-dev-shop/labels/good%20first%20issue)
   or [help wanted](https://github.com/Shaisolaris/solaris-dev-shop/labels/help%20wanted).
2. Read the issue and existing replies. Leave one comment describing the small
   change you intend to make, so contributors can avoid overlapping work.
3. Start with an unclaimed task that has a clear acceptance condition. A standing
   contributor invitation, showcase thread or blocked publishing account is not
   itself a coding task. Larger proposals need maintainer agreement on scope first.

## Set up locally

Fork the repository on GitHub, then use your fork in place of `YOUR-USER`:

```bash
git clone https://github.com/YOUR-USER/solaris-dev-shop.git
cd solaris-dev-shop
git switch -c improve-one-thing
python3 -m venv .venv
```

Activate `.venv/bin/activate` on macOS/Linux, or `.venv\Scripts\Activate.ps1`
on Windows. Use `python` below from that environment. Python 3.10+ is required.

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python control-plane/meta_control_plane.py self-test
```

These checks do not call a model or require an account key. They establish a
baseline; they do not execute specialist skills or prove task quality.

## Change one thing and verify it

| Change | Where to start | What to verify |
|---|---|---|
| Routing defect | `control-plane/policy.json`, `control-plane/meta_control_plane.py`, `tests/` | A synthetic command fails before and behaves correctly after; existing routes and safety gates still pass. |
| Skill guidance | `employees/<department>/<skill>/SKILL.md` and companion files | The user's missing outcome is addressed; referenced files exist; examples distinguish run results from unrun instructions. |
| Discovery metadata | The skill's manifest and contract | Run `python tools/build_skill_catalog.py`, then `python tools/build_skill_catalog.py --check` and `python tools/validate_skill_metadata.py`. |
| New specialist | [Proposal template](../.github/ISSUE_TEMPLATE/new-employee.md) | Explain the gap and boundaries first; build after proposal review using the [skill checklist](new-skill-template/README.md). |

For a new specialist, the implementation must also update the active roster,
routing policy/probes, generated catalog, counts and affected docs together.
The current 61-role checks deliberately catch an incomplete roster change;
update their expected count only as part of the reviewed addition.

Use synthetic or redistributable inputs. Keep credentials, private account
details, provider sessions and paid calls out of examples. If a host or tool is
unavailable, state the blocker. Do not replace a missing run with invented output.

## Open a focused pull request

Describe the user problem, the changed behavior, and the commands and results
you actually observed. Link the issue, include a small before/after example when
relevant, and update docs when behavior changes. Keep unrelated formatting out.

The maintainer reviews changes before merging. No response time is promised.
Check the PR for concrete review feedback; reply with the fix and its evidence
once, without repeated reminders. Read the full [contribution rules](../CONTRIBUTING.md).

After you use a skill, share a redacted result in the
[showcase](https://github.com/Shaisolaris/solaris-dev-shop/issues/18).
Describe which skills were actually used, what they produced, and what did not
work. Routing alone is not a completed project or evidence of agent execution.
