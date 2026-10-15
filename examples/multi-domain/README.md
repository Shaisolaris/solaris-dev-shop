# Multiple specialists, one outcome

A compound API, design and QA request produces one accountable lead and two
supporting specialists. One packet does not limit the work to one specialist.

```bash
python3 control-plane/meta_control_plane.py intake --explain "Build a FastAPI REST API backend; design Figma wireframes; write a Playwright test plan"
```

The saved [input](input.md) and [actual JSON result](observed.json) were generated
from engine 1.3.0 in product release 0.58. The packet names:

| Role | Skill | Handoff |
|---|---|---|
| Accountable lead | `solaris.backend-developer` | [Backend Developer](../../employees/engineering/backend-developer/SKILL.md) |
| Supporting | `solaris.ui-ux-designer` | [UI/UX Designer](../../employees/design/ui-ux-designer/SKILL.md) |
| Supporting | `solaris.qa-engineer` | [QA Engineer](../../employees/quality-security/qa-engineer/SKILL.md) |

Primary and supporting source paths are included in the actual packet. IDs and
timestamps change between runs; role selection is deterministic. The older
`fixtures/control-plane/multi_domain_intake.json` remains a separate API and
landing-page regression fixture.

## Hand off in your agent

Open these skills with their companion files and provide the local project and
the packet. Ask the backend lead to define the API contract and integration
boundaries. Design can work on wireframes while QA drafts its plan against that
contract, if your host supports parallel workers and those tasks are independent.
Let the lead integrate results and identify what remains untested. A single
agent may use the skills in sequence instead.

Keep the packet's scope and authority bounds. Do not give each specialist
unrestricted access or claim that a named role ran without an actual invocation
and saved output. The router has performed no API, design or QA work:
`performed_work` is false. These are handoff instructions, not a completed app.

The default limit is five supporting roles. A capped team is flagged in
`budgets_applied`; split or review that task before running it. See
[selection rules and limits](../../docs/architecture.md#multiple-specialists-one-accountable-outcome).
