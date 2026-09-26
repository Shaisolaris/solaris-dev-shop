# Security Auditor - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: STRIDE + OWASP + MITRE ATT&CK triad provides threat-modeling coverage across product + operations + adversary-TTPs dimensions.
- **2026-04-24 - Clean build**: Security Auditor goes deeper than Code Reviewer's security pass - adversarial mindset + pen-test methodology + compliance, not just OWASP checklist.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

## 2026-05-13 - Absorbed AgriciDaniel/the coding agent-cybersecurity (scout 2026-05-11)
- 8 parallel specialist agents: vuln detection, authz, secret scan, supply-chain, IaC, +3
- OWASP 2025 + CWE Top 25 + MITRE ATT&CK three-framework cross-ref
- Supply-chain agent feeds Talent Scout's Tier-4 verification
- MIT, established author. Tier 1 PASS.


## 2026-06-13 - Deep quality pass: scanning stack + two fleet checks
- Absorbed top-5 verified 2026 OSS tools as methodology -> references/scanning-stack.md: Semgrep (SAST, LGPL-flag), OSV-Scanner (SCA/SBOM, Apache-2.0), gitleaks (secrets, MIT, gov-fork watch), OWASP pytm (threat-model-as-code, NOASSERTION-flag, stale-cadence-flag), Nuclei (DAST, MIT). Candidate dossier in TOP5-CANDIDATES.md.
- Pattern learned: several "absorbed" tools were only NAMED in the tool catalog, never operationalized (Semgrep, gitleaks). Operationalizing the bare run-order steps is net-new value distinct from listing a tool.
- OWNED two fleet rules as PASS/FAIL audit checks: FA-1 memory-scope-keys (cross-tenant leak prevention), FA-2 SHA-pin third-party CI actions (post trivy-action Mar-2026 compromise). Both now red-flag/P1 items.
- Found + fixed a phantom reference: references/trivy-and-dast.md existed since v0.6.0 but was never registered in plugin.json references[]. Lesson: when a reference file is created, register it the same commit.
- Doctrine: vendor diversity (Trivy + OSV-Scanner side by side) is itself a supply-chain control - do not let one scanner's supply chain be a single point of failure.

- **2026-08-13 - named-heading protocol**: measured D5 gap was job-two omitting contract-required artifact headings; closed by named-heading protocol in `job-two-improvement.md`.
## Sources

- Upstream: Semgrep (license not recorded); OSV (license not recorded); gitleaks (license not recorded); OWASP pytm (license not recorded); Nuclei (license not recorded)
- What was used: noted: Semgrep, OSV, gitleaks, OWASP pytm, Nuclei
- License notes: licenses not recorded in scan for: Semgrep, OSV, gitleaks, OWASP pytm, Nuclei - verify before reuse; no code vendored
