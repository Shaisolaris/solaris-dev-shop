# Solaris Dev Shop

![CI](https://github.com/Shaisolaris/solaris-dev-shop/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.54-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Employees](https://img.shields.io/badge/employees-61-orange)
[![Featured on DevShelf](https://img.shields.io/badge/Featured%20on-DevShelf-7928CA?style=for-the-badge&logo=googlechrome&logoColor=white)](https://devshelf.ritualdev.in/tools/solaris-dev-shop.html)

61 specialist employees and one chief of staff. Free. MIT.

You send a task. The chief of staff assigns exactly one accountable specialist. That specialist does the work. You still decide.

## Try it (30 seconds)

```bash
./install.sh
solaris-intake intake "Write a test plan for the client portal login regression"
```

That command routes the request. It names `solaris.qa-engineer` as accountable and performs no work of its own. The test plan itself is written by the qa-engineer, but only after you invoke that skill in your own agent. Routing is deterministic: the same request always lands on the same specialist. A saved run is in [`examples/route-a-task/`](examples/route-a-task/).

Add `--explain` to see matched keywords, routing evidence and the runner-up.
Try it without a local install using the [Actions playground](docs/playground.md).
Follow-up routing is [explicitly opt-in and local](docs/architecture.md#opt-in-follow-up-context).

![Demo: one intake command routes to the accountable specialist](assets/demo.gif)

## What you get

| You get | Details |
|---|---|
| 61 employees | 12 departments: engineering, design, data, marketing, sales, leadership, and more. Full list: [`docs/employees.md`](docs/employees.md) |
| 1 chief of staff | Reads your request, emits one typed assignment packet: accountable owner, primary specialist, supporting list, authority bounds, evidence required |
| Deterministic router | Stdlib-only Python. All 61 specialists plus safety, CLI, context and fixture checks in CI. No model calls or API keys |
| Copy-paste skills | Each employee is a `SKILL.md` + `rules.md` + `plugin.json` + `capability.contract.json` + `learnings.md`. Drop one into any coding agent |
| QA loop built in | Every deliverable follows [`docs/QA-LOOP.md`](docs/QA-LOOP.md): build, independent review, fix, repeat until clean |

## How it compares

| | Solaris Dev Shop | Lone prompt | Agent marketplace listing |
|---|---|---|---|
| Who owns the task | One named specialist, accountable | Nobody | Varies by listing |
| Routing | Deterministic, tested, 61/61 reachable | Hope | Manual browsing |
| Cost to route | Zero (stdlib Python) | Per-call model cost | Platform fees |
| Skill portability | Copy a folder into your agent | Rewrite the prompt | Locked to the platform |
| QA | Independent review loop, no self-certification | Self-certified | Varies |

## Install

One command:

```bash
./install.sh
```

Details: [`docs/install.md`](docs/install.md). How a request moves: [`docs/architecture.md`](docs/architecture.md). How to copy a single skill: same doc, step 3.

## Around the community

Solaris Dev Shop is listed on [DevShelf](https://devshelf.ritualdev.in/tools/solaris-dev-shop.html), [SilentStars](https://capuz.github.io/silentstars/projects/shaisolaris--solaris-dev-shop/) and other community directories. See [verified public listings](docs/public-listings.md) for the current entries and their evidence. Directory inclusion does not imply an endorsement.

AI Agents Directory is still verifying a submitted listing. The following badge
is its required verification backlink; it is not a confirmed placement:

[![AI Agents Directory verification pending](https://aiagentsdirectory.com/featured-badge.svg)](https://aiagentsdirectory.com)

Postmake's free listing route also requires its badge. This backlink is in place
for that application; a Postmake listing has not yet been confirmed:

[![Postmake free-listing application backlink, placement not yet confirmed](https://postmake.io/postmake_badge_light.png)](https://postmake.io)

## Quality and evidence

- [Routing architecture and privacy boundaries](docs/architecture.md)
- [Reproducible 100-request benchmark](docs/performance.md)
- [Multi-domain example](examples/multi-domain/README.md) and [safe escalation example](examples/escalation/README.md)
- Structural audit: `python employees/quality-security/assurance/quality_os.py audit --html report.html`

The audit checks documented output contracts and QA gates across the 61 employee
skills. It does not certify their real-world results or guarantee autonomous work.

## Contribute

- Found a routing miss? Open a [bug](.github/ISSUE_TEMPLATE/bug.md) with the command and the expected specialist.
- Want a new specialist? Open a [new employee proposal](.github/ISSUE_TEMPLATE/new-employee.md).
- Improving the router? `python3 tests/test_router.py` must stay green. CI runs it on every push.
- See the public [roadmap](ROADMAP.md) and the 20 open issues: claim one, propose an upgrade, or [show what you built](https://github.com/Shaisolaris/solaris-dev-shop/issues/18).

## Contributors

[![Contributors](https://contrib.rocks/image?repo=Shaisolaris/solaris-dev-shop)](https://github.com/Shaisolaris/solaris-dev-shop/graphs/contributors)

[![Star History](https://api.star-history.com/svg?repos=Shaisolaris/solaris-dev-shop&type=Date)](https://star-history.com/#Shaisolaris/solaris-dev-shop&Date)

## What this is not

- Not 73, 58, 52, or 100 employees. The count is 61 directories.
- Not the newer Solaris work. This is the public edition of V5.2.2.
- Not a marketplace or a patent filing.
- Not a place to paste passwords, API keys, or tokens.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

![You ask. The chief of staff assigns. A specialist does the work.](assets/social-preview.png)
