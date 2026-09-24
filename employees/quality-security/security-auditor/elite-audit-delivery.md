# Elite audit delivery: aggregated SARIF report, exploitability triage matrix, and the deep-query tier

> Methodology reference. NO tool code, queries, or rule packs are bundled (fleet doctrine). License-flagged tools (CodeQL - free for OSS only) are methodology + entitlement notes only. This is the ENGAGEMENT-DELIVERY layer of a top security firm: how dozens of tool outputs become ONE normalized, de-duplicated, exploitability-ranked risk register, and how the deep semantic dataflow tier extends the scanning catalog. It is the audit-scale mirror of the code-reviewer SARIF/triage/CodeQL file; that file is PR-scale, this file is full-engagement scale with a client-facing register.

Source canon (verified 2026-06-20):
- OASIS SARIF 2.1.0 - the result-interchange standard every scanner in scanning-stack.md can emit.
- microsoft/sarif-sdk + sarif-tools multitool merge - merge/normalize/dedup across tools.
- EPSS (FIRST.org) + CISA KEV - exploit-probability + known-exploited cross-reference for prioritization.
- Reachability/call-graph (osv-scanner --call-analysis, Semgrep Pro taint; commercial Endor/Snyk equivalents) - "is the vulnerable function reachable."
- github/codeql - QL semantic dataflow engine (LICENSE FLAG: free for OSS/research only; private repos need GitHub Advanced Security).

Gate-0 (what this auditor already had, so this is NET-NEW not a re-listing):
- scanning-stack.md = tool/check CATALOG (the WHAT: Semgrep/OSV/gitleaks/pytm/Nuclei + fleet checks FA-1/FA-2; names SARIF as a per-tool output, never the cross-tool merge).
- trivy-and-dast.md = single-scanner run workflow (HOW-to-run one tool).
- adversarial-bounty-hunting.md = attacker MINDSET on ONE finding (does-it-pay).
- audit-firm-methodology.md = the post-finding LOOP (variant analysis + custom rule + fix-verification on a CONFIRMED finding).
NONE carried: (1) the multi-tool SARIF normalize+dedup+rank into one risk register, (2) the seven-dimension exploitability triage matrix (EPSS + KEV + reachability + context) that cuts the set before the client reads it, (3) the deep CodeQL nightly dataflow tier distinct from the fast Semgrep tier. All three NET-NEW.

---

## 1. Aggregated risk register - one normalized, de-duplicated report

A real firm engagement runs the whole catalog: Semgrep (SAST), Trivy + OSV (SCA/SBOM, deliberate vendor diversity), gitleaks (secrets), Nuclei + ZAP (DAST), the agent-component scanners (dims 9-10), plus any client CodeQL/Sonar. Each emits its own SARIF with its own rule ids and severity scale. Delivering ten raw reports is a commodity output and produces remediation paralysis - the same vulnerability appears under three names and three severities and the client cannot count real problems or sequence the fix. The firm-grade deliverable is ONE risk register.

### The aggregation pipeline (methodology)
1. **Emit SARIF 2.1.0 from every tool.** Every scanner in scanning-stack.md already supports SARIF output; standardize the version so results are comparable objects (rule id, level, location, message, codeFlows).
2. **Merge, preserving provenance.** Combine into one SARIF (sarif-tools multitool merge / microsoft sarif-sdk), keeping each tool as a distinct `run`. Provenance is never lost - the client must be able to see which tool found what.
3. **Normalize severity.** SARIF `level` (error/warning/note) is too coarse. Map each tool's native severity onto the rules.md severity taxonomy + the audit P-scale via a documented table, so cross-tool severities sort together.
4. **De-duplicate.** Collapse the same defect found by multiple tools to one register row. Dedup key = normalized (path + region + rule-class); for CVEs, dedup on CVE/GHSA id across Trivy and OSV. Record `corroboratedBy: [...]` - two independent tools agreeing raises confidence (feeds triage in section 2). Vendor diversity is a supply-chain control (post the March-2026 trivy-action compromise, see FA-2); the merge is where that diversity pays off.
5. **Enrich.** Attach to each surviving finding: CVE id, EPSS, KEV membership, reachability verdict (section 2), the variant CLASS from audit-firm-methodology.md, and the custom rule that detects it.
6. **Render two artifacts.** The machine artifact = the merged SARIF (upload to GitHub code-scanning / hand to the client's pipeline). The human artifact = the ranked client risk register: finding, normalized severity, confidence, exploitability, location, owner, remediation, retest status. The register is the engagement deliverable; per-finding write-ups use the bounty report structure from adversarial-bounty-hunting.md.

### Honest limitation in the report
SARIF normalizes transport, not meaning. Dedup is heuristic - never silently drop a finding because a fuzzy match called it a duplicate; merge with both provenances and let the auditor's judgment make the final call. Scanners produce evidence; the verdict is the firm's.

---

## 2. Exploitability triage matrix - rank before the client reads

The differentiator between an elite firm and a scan-and-dump vendor: a raw multi-tool scan returns hundreds-to-thousands of findings, most not exploitable in this deployment. Surfacing all of them buries the real risk and burns the client's remediation budget. The firm ranks every finding on seven dimensions and presents the high-confidence actionable set first (industry reporting: 70-95 percent volume reduction):

| Dimension | Question | Source |
|-----------|----------|--------|
| Severity | impact if exploited | CVSS / audit P-scale |
| Exploitability | likelihood of exploitation in the wild | EPSS (FIRST.org) |
| Known-exploited | exploited right now | CISA KEV membership |
| Reachability | does the app actually reach the vulnerable code | call-graph / taint |
| Deployment context | internet-facing? sensitive data? trust boundary crossed? | architecture + DFD (pytm) |
| Business impact | revenue / compliance / regulatory blast radius | client context |
| Fix availability | safe upgrade / patch path | SCA fixedVersion |

### Reachability is the highest-leverage cut
The precise question: is the vulnerable dependency function on a live call path (SCA), or does the sink receive user-controlled input across a real boundary (SAST)?
- SCA: `osv-scanner --call-analysis` (scanning-stack.md) flags reachable CVEs; unreachable ones drop out of P0/P1 with the residual risk stated. Commercial Endor/Snyk reachability is CONNECT-only where the client already runs it.
- SAST: the three taint questions from adversarial-bounty-hunting.md - user-controlled, reaches sink unsanitized, reachable from a real boundary. A Semgrep/CodeQL taint hit broken by a real sanitizer is not a live finding.

### The register verdict per finding
- **P0/P1 (critical/high, report first):** high severity AND (reachable OR KEV OR high EPSS). Any live secret (gitleaks history hit) is always P0 + rotate-now regardless of the matrix (history secret = exposed in every clone).
- **P2 (fix, scheduled):** real but unreachable-in-this-deployment, or low EPSS and not KEV.
- **P3 / accepted-risk:** documented, owner + expiry, written to the audit baseline memory key so retests surface only new or newly-reachable findings.

Never suppress on reachability alone for KEV items or for a dependency the client may invoke after a code change - state the residual risk. Reachability calibrates priority, it does not pardon a known-exploited bug. This triage maps cleanly onto compliance evidence (SOC 2 / ISO risk register, PCI prioritized remediation).

---

## 3. The deep-query tier (CodeQL nightly), above the fast Semgrep tier

scanning-stack.md names Semgrep as the SAST engine - correctly, for speed: sub-minute scans suit a PR/CI gate and the diff-aware `--baseline-commit` flow. But Semgrep taint, even Pro cross-file, is shallower than full semantic dataflow. An elite audit runs a deeper second tier.

### Two-tier doctrine
- **Fast tier:** Semgrep - sub-minute, diff-aware, runs the WE-authored custom rules from audit-firm-methodology.md Part 2, gates PRs.
- **Deep tier:** CodeQL - compiles the codebase into a queryable database and runs whole-program dataflow/taint across files and functions, catching the multi-hop injection and cross-module logic flaws the fast tier misses. Minutes-to-hours, so it runs nightly / pre-release / inside the full audit, not per PR.

### Custom-query authoring (elite, above default packs)
Default CodeQL suites are the floor. The elite move mirrors the audit-firm-methodology.md custom-rule discipline raised to QL: from a confirmed finding, abstract the root cause and write a QL query using the full type system + dataflow library to find every semantic sibling across the whole database (including siblings spelled differently that a textual pattern misses). Author test-first - true-positive cases (the finding + its variants) must fire, true-negative safe idioms from the same codebase must not. QL costs more to author than a Semgrep pattern (a day vs an hour), so reserve custom QL for the deep, high-value classes and keep the cheap classes in Semgrep. WE-authored QL is engagement work product (subject to IP terms), kept separate from default suites - the same house-ruleset asset doctrine as the Semgrep rules.

### LICENSE FLAG (read before reuse)
CodeQL is free for OSS/research ONLY; private client repos require GitHub Advanced Security (paid). CONNECT posture: run CodeQL only where the client ALREADY has GHAS, read its alerts into the aggregated register (section 1), and confirm engagement IP terms before treating Solaris-authored QL as a deliverable. No GHAS -> deep tier falls back to Semgrep Pro taint (commercial) or a manual cross-file trace. Never stand up unlicensed CodeQL.

---

## Cross-references
- references/scanning-stack.md - the tool/check catalog that emits the SARIF this file merges and the Semgrep fast tier the CodeQL deep tier sits above; fleet checks FA-1/FA-2 (memory-scope-keys, SHA-pin) are themselves codified detectors whose results enter the register. NO tool list duplicated here.
- references/audit-firm-methodology.md - the post-finding LOOP (variant analysis + custom rule + fix-verification); this file's triage decides WHICH findings enter that loop first, the custom QL is that file's rule-authoring at the deep tier, and the fix-verification verdict (CLOSED/REOPEN/PARTIAL) is a register column.
- references/adversarial-bounty-hunting.md - the attacker mindset + three taint questions used in the reachability cut; per-finding write-ups use its report structure.
- references/trivy-and-dast.md - single-scanner runs whose SARIF and CVE ids feed the dedup and whose re-scan is the retest.
- rules.md - severity taxonomy this file normalizes onto + red flags; the register IS the risk register referenced there.
- code-reviewer references/sarif-aggregation-and-reachability-triage.md - the PR-scale mirror (same merge + triage + CodeQL tier as a per-PR gate rather than a full-engagement register). Hand findings across the line by scope.

## Memory scope keys
- security-auditor/audit/<client>/sarif-mapping - per-tool severity-to-house-scale mapping + dedup rules used for this client's register (kept consistent across retests)
- security-auditor/audit/<client>/triage-matrix - per-finding seven-dimension verdict (severity/EPSS/KEV/reachability/context/impact/fix) + accepted-risk suppressions with owner+expiry, so retests surface only new or newly-reachable risk
- security-auditor/audit/<client>/deep-tier-queries - WE-authored CodeQL queries from this client's confirmed findings (provenance + TP/TN + CWE); engagement work product, separate from default suites per license posture
