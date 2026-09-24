# Static Analysis, Independent CVE DB, History Secrets, and PR Automation

> Methodology reference. NO tool code or rule packs are bundled here. License-flagged tools (semgrep LGPL-2.1, CodeQL proprietary, SonarQube custom) are described as methodology + self-host/CI-integration notes only. Trivy (already absorbed, see `references/trivy-sca-secrets-sbom.md`) owns unified SCA + tree-secret + IaC + SBOM; this file fills the four gaps Trivy does not cover.

Source canon (verified 2026-06-13):
- semgrep/semgrep - 15k stars, LGPL-2.1 CE - AST/data-flow SAST.
- google/osv-scanner - 10.5k stars, Apache-2.0, v2.3.8 (2026-05-08) - open-DB SCA + reachability.
- gitleaks/gitleaks - 26.5k stars, MIT, v8.30.1 (2026-03-21) - git-history secret scanner.
- danger/danger-js - 5.5k stars, MIT, 13.0.5 - PR-hygiene automation in CI.
- github/codeql + SonarSource/sonarqube - both license-FLAGGED - deep SAST + quality gates (CONNECT only).

---

## The review scanning stack (layered, not either/or)

| Layer | Tool | Owns | License posture |
|-------|------|------|-----------------|
| Semantic navigation | claude-context | "find code by intent" on >2,000-file codebases | MIT (absorbed) |
| Unified SCA + tree-secrets + IaC + SBOM | Trivy | one-shot dependency/OS CVE + misconfig + SBOM | MIT (absorbed) |
| AST taint / data-flow SAST | semgrep (CodeQL/Snyk Code alt) | injection/XSS/SSRF via data-flow, custom org rules | LGPL-2.1 FLAG - methodology only |
| Independent CVE cross-check + reachability | osv-scanner | 2nd vuln DB (OSV.dev) + call-analysis false-positive cut | Apache-2.0 - safe |
| Git-history + entropy secrets | gitleaks | secrets in PAST commits, encoded/archived blobs | MIT - safe |
| PR-hygiene automation | danger-js | CHANGELOG/size/label/linked-issue gates as CI comments | MIT - per-project |
| Quality gate / coverage dashboard | SonarQube/SonarCloud | quality-gate status, hotspots, coverage | custom FLAG - CONNECT only |

Doctrine: scanners produce EVIDENCE, not a verdict. The reviewer's judgment (business-logic abuse, intent, severity calibration) is never automatable. P0/P1 SCA + any live secret block the PR; everything else is flagged with an owner.

---

## 1. AST SAST (semgrep) - methodology

What it adds that grep/claude-context/Trivy cannot: taint/data-flow tracking - "does untrusted input REACH a sink (query, shell, eval, HTML)" - across functions and files. This is the exact capability the SKILL repeatedly disclaims ("does NOT do AST SAST").

When to reach for it in a review:
- Security Audit mode, Phase 3: after claude-context enumerates input surfaces, run a taint pass to confirm reachability instead of eyeballing.
- PR Review touching auth, query construction, deserialization, template rendering, or shell-out.
- First-Principles mode: org-specific anti-patterns encoded as custom rules (e.g., "never call `db.raw()` with a template literal").

Self-host / CI note (LGPL-2.1 - do NOT vendor binaries or redistribute Semgrep Registry rule packs as Solaris IP):
- Run as `semgrep ci` or `semgrep scan --config auto` in the client's pipeline; results to SARIF -> GitHub code-scanning.
- For NDA/closed code: Semgrep CE runs fully local, no code leaves the machine - same posture as Ollama for claude-context. Prefer this for client work.
- Alternatives if client mandates: CodeQL (free for OSS only - FLAG) or Snyk Code (commercial). Same data-flow role.

## 2. Independent CVE DB + reachability (osv-scanner) - absorb

Why a SECOND scanner alongside Trivy: different advisory sources catch different CVEs. OSV.dev aggregates GHSA + RustSec + distro notices in a machine-precise version-range format; running osv-scanner AND Trivy and reconciling the diff is the high-assurance dependency pass for a pre-launch or takeover. Call-analysis (`--call-analysis`) marks whether the vulnerable function is actually reached, downgrading un-reachable CVEs out of P0/P1 - directly feeds severity calibration.

Fold into Dependency Audit mode:
- `osv-scanner scan source -r .` for the lockfile pass (11+ ecosystems, one command).
- `osv-scanner --licenses="MIT,Apache-2.0,BSD-3-Clause,..." .` for the copyleft-into-closed-product check (pairs with the org license-flag doctrine).
- Offline mode (`--offline --download-offline-databases`) for air-gapped / NDA clients.
- SARIF output + the official GitHub Action for PR-time new-vuln gating.

## 3. Git-history + entropy secrets (gitleaks) - absorb

Gap vs Trivy: Trivy's secret detection scans the working TREE; gitleaks scans the full `git log -p` HISTORY. A credential committed then "deleted" still lives in history and is still exposed - only a history scanner catches it. Plus entropy scoring, composite/proximity rules, and recursive archive/base64/hex decoding.

Fold into Security Audit + takeover Phase 1:
- `gitleaks git -v <repo>` on any inherited codebase; a hit is P0 AND a rotate-now action (rotating beats redacting - the secret is in every clone).
- `gitleaks dir` for non-git trees; `--baseline-path` to suppress known-accepted findings without muting new ones.
- Pre-commit hook + `gitleaks/gitleaks-action@<SHA>` in CI (org accounts need a free `GITLEAKS_LICENSE` key; personal accounts do not).
- SARIF -> GitHub Advanced Security.

## 4. PR-hygiene automation (danger-js) - connect

Operationalizes the employee's existing decision rules that were previously prose-only:
- "When PR has no description -> comment asking" -> danger rule: fail if PR body empty.
- "When PR has no tests on changed behavior -> request tests" -> warn if `src/**` changed but no `*.test.*` / `*_test.*` touched.
- "When >400 LoC changed -> suggest split" -> warn on diff size.
- CHANGELOG present, linked issue/ticket in body, required labels, no committed `console.log`/`debugger`/`FIXME`.

Per-project `dangerfile.ts` (not bundled - it is client-specific). Runs after CI, posts a single consolidated PR comment. Free, MIT.

## 5. Client-CI integration (CodeQL / SonarQube) - connect, FLAGGED

Use only when the client ALREADY runs these in CI; pull their output into the review rather than standing up new infra.
- SonarQube/SonarCloud MCP: quality-gate status, new-code coverage, hotspots, issue list. License FLAG: SonarSource custom (non-OSI); commercial editions need a key - confirm the client's edition/entitlement, never vendor.
- CodeQL: GitHub's data-flow SAST. License FLAG: free for OSS/research only; private repos need GitHub Advanced Security. If the client has GHAS, read its alerts; do not redistribute queries as Solaris IP.

---

## CI safety doctrine (the code-reviewer must enforce this in every review)

Because this employee gates code into main, it is the natural enforcer of CI supply-chain hygiene. Flag in EVERY PR/audit that touches a workflow file:

- **SHA-pin all third-party GitHub Actions.** `uses: org/action@v2` is a MOVING tag an attacker (or a compromised maintainer) can repoint. Require the full 40-char commit SHA: `uses: gitleaks/gitleaks-action@<full-sha> # v2.x`. A floating tag on a third-party action is a P1 supply-chain finding. (First-party `actions/*` are lower risk but pinning is still preferred.)
- **Least-privilege `GITHUB_TOKEN`.** Default to `permissions: contents: read`; grant write scopes per-job only where needed.
- **No secrets echoed** in workflow logs; gate `pull_request_target` carefully (it runs with write token on untrusted forks).
- **Pin scanner versions** too (Trivy/semgrep/osv-scanner/gitleaks action refs) so a CI result is reproducible.

This doctrine applies to the employee's own absorbed tooling references above: any action ref Solaris recommends must be shown SHA-pinned, never as a bare tag.

---

## Memory scope keys

Per-project findings, index locations, and accepted-risk baselines live under a scoped memory key, never global:
- `code-reviewer/<project>/scan-baseline` - accepted-risk / suppressed findings (gitleaks baseline, osv ignore list, semgrep `.semgrepignore`) so re-scans surface only NEW issues.
- `code-reviewer/<project>/index` - claude-context index location + last-indexed commit.
- `code-reviewer/<project>/severity-calibration` - did a prior "blocker" hold up; tune future calls.
Scope so one client's accepted-risk list never leaks into another client's review.
