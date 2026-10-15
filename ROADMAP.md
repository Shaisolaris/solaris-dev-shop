# Roadmap

This is the public roadmap for Solaris Dev Shop. Every item below links to a real
issue. Completed work is retained with its evidence; open items welcome contributions.

The [latest release](https://github.com/Shaisolaris/solaris-dev-shop/releases/latest)
identifies the current product version. Versions in completed rows describe when
that work shipped. Useful open invitations and proposals are retained for the
community; a directory's closure-ratio score is not a reason to close them.

## Issue status

| # | Item | Status |
|---|------|--------|
| [#1](https://github.com/Shaisolaris/solaris-dev-shop/issues/1) | Router: non-English requests are not matched | Implemented in 0.54; see the closing PR for CI evidence |
| [#2](https://github.com/Shaisolaris/solaris-dev-shop/issues/2) | Intake: add an --explain flag | Implemented in 0.54; see the closing PR for CI evidence |
| [#3](https://github.com/Shaisolaris/solaris-dev-shop/issues/3) | Document the wordpress-master diagnostics design decision | Implemented in 0.54; see the closing PR for CI evidence |
| [#4](https://github.com/Shaisolaris/solaris-dev-shop/issues/4) | install.sh: Windows support | Implemented in 0.54; see the closing PR for CI evidence |
| [#5](https://github.com/Shaisolaris/solaris-dev-shop/issues/5) | PyPI publish | Blocked on publishing access; current release wheels work without PyPI |
| [#6](https://github.com/Shaisolaris/solaris-dev-shop/issues/6) | Chief of staff: multi-turn conversation memory | Implemented in 0.54; see the closing PR for CI evidence |
| [#7](https://github.com/Shaisolaris/solaris-dev-shop/issues/7) | Router: expose confidence scores | Implemented in 0.54; see the closing PR for CI evidence |
| [#8](https://github.com/Shaisolaris/solaris-dev-shop/issues/8) | Docs: video walkthrough | Completed: [video, captions and transcript](docs/walkthrough.md), [PR34](https://github.com/Shaisolaris/solaris-dev-shop/pull/34) |
| [#9](https://github.com/Shaisolaris/solaris-dev-shop/issues/9) | New employee proposal: developer-relations specialist | Open for a worked proposal and boundary review before implementation |
| [#10](https://github.com/Shaisolaris/solaris-dev-shop/issues/10) | New employee proposal: data-privacy officer | Open for a worked proposal and boundary review before implementation |
| [#11](https://github.com/Shaisolaris/solaris-dev-shop/issues/11) | quality_os: HTML report output | Implemented in 0.54; see the closing PR for CI evidence |
| [#12](https://github.com/Shaisolaris/solaris-dev-shop/issues/12) | Fixtures: expand edge-case coverage | Implemented in 0.54; see the closing PR for CI evidence |
| [#13](https://github.com/Shaisolaris/solaris-dev-shop/issues/13) | Verify the social preview card renders | Existing branded artwork retained; verify the current link card before proposing any image change |
| [#14](https://github.com/Shaisolaris/solaris-dev-shop/issues/14) | Examples: multi-domain and escalation walkthroughs | Implemented in 0.54; see the closing PR for CI evidence |
| [#15](https://github.com/Shaisolaris/solaris-dev-shop/issues/15) | Benchmark intake latency | Implemented in 0.54; see the closing PR for CI evidence |
| [#16](https://github.com/Shaisolaris/solaris-dev-shop/issues/16) | Call for contributors: claim an open issue | Standing invitation; choose a concrete linked task |
| [#17](https://github.com/Shaisolaris/solaris-dev-shop/issues/17) | Upgrade idea: propose a new specialist skill | Standing proposal intake; the library can grow beyond 61 |
| [#18](https://github.com/Shaisolaris/solaris-dev-shop/issues/18) | Showcase: what did you build with a Solaris skill? | Standing showcase; share actual skill outputs and limitations |
| [#19](https://github.com/Shaisolaris/solaris-dev-shop/issues/19) | Compare host-executed skill outputs across providers | Proposal needs bounded scope; deterministic router timing already has a benchmark |
| [#20](https://github.com/Shaisolaris/solaris-dev-shop/issues/20) | Upgrade idea: skill playground (try before you install) | Implemented in 0.54; see the closing PR for CI evidence |
| [#29](https://github.com/Shaisolaris/solaris-dev-shop/issues/29) | Long unknown goals select a backend specialist | Fixed in 0.55; [regression and PR30](https://github.com/Shaisolaris/solaris-dev-shop/pull/30) |
| [#32](https://github.com/Shaisolaris/solaris-dev-shop/issues/32) | Separated production wording misses the risk gate | Fixed in 0.56; [regression and PR33](https://github.com/Shaisolaris/solaris-dev-shop/pull/33) |
| [#36](https://github.com/Shaisolaris/solaris-dev-shop/issues/36) | Invalid skill discovery metadata | Fixed in 0.57; [62 entrypoints validated, PR37](https://github.com/Shaisolaris/solaris-dev-shop/pull/37) |
| [#39](https://github.com/Shaisolaris/solaris-dev-shop/issues/39) | Reviewed Spanish/French task-routing examples | Unclaimed contributor task; start with a small fixture proposal |
| [#40](https://github.com/Shaisolaris/solaris-dev-shop/issues/40) | Reproducible QA skill deliverable on a local demo | Unclaimed contributor task; propose the minimal demo and runner first |

## How to get involved

- **Claim an issue.** Comment on it first so two people don't collide, then open a pull request. See `CONTRIBUTING.md`.
- **Start small.** Use the [contributor quickstart](docs/contributor-quickstart.md). Routing fixtures, documentation and worked examples are useful first contributions.
- **Propose an upgrade.** Open a new issue with the `enhancement` label. Big ideas welcome: new specialists, new router capabilities, new quality checks.
- **Propose a new employee.** The active roster remains 61; additions require a reviewed proposal. Issues #9 and #10 are proposals from the community checklist; add yours the same way: one issue per proposal, with the skill's domain, trigger phrases, and a sample intake.
- **Show off.** If you built something with a skill, tell us in issue #18. Good builds get linked from the README.
- **Report a bug.** Open an issue. Include the intake text, the employee chosen, and what you expected. No template theater.

## What gets merged

Anything that follows the contribution contract in `CONTRIBUTING.md`: tests
cover the change, the router still resolves all 61 employees, and the docs
match the behavior. The maintainer reviews every PR.
