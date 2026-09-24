# SARIF aggregation, reachability/exploitability triage, and the CodeQL deep-query tier

> Methodology reference. NO tool code, queries, or rule packs are bundled here. License-flagged tools (CodeQL proprietary - free for OSS only) are described as methodology + CI-integration notes only. This file is the ELITE DELIVERY layer that sits on top of the scanning stack: it turns many tools' raw output into ONE normalized, de-duplicated, exploitability-ranked finding set, and adds the deep cross-file dataflow tier that the fast PR scanners cannot reach.

Source canon (verified 2026-06-20):
- OASIS SARIF 2.1.0 - the static-analysis interchange standard every modern scanner can emit.
- microsoft/sarif-sdk + sarif-tools (multitool merge) - merge/normalize/dedup SARIF across tools.
- EPSS (FIRST.org) + CISA KEV - exploit-probability and known-exploited cross-references for triage.
- Reachability/call-graph analysis (osv-scanner --call-analysis, Semgrep Pro taint, commercial Endor/Snyk equivalents) - "is the vulnerable function actually called."
- github/codeql - QL semantic dataflow/taint engine (LICENSE FLAG: free for OSS/research only; private repos need GitHub Advanced Security).

Gate-0 (what the cluster already had, so this does NOT duplicate it):
- static-analysis-and-pr-automation.md = the scanning STACK (how to RUN Semgrep/OSV/gitleaks/danger to produce evidence; names SARIF as an output of each tool but never describes merging many SARIF files into one report).
- variant-analysis-and-fix-verification.md = per-finding CLASS-closure and fix PROOF (operates on ONE confirmed finding).
- codebase-takeover-and-audit.md = first-contact reasoning on inherited code.
- trivy-sca-secrets-sbom.md = the unified Trivy scan.
NONE carried: (1) the multi-tool SARIF normalize+dedup+rank report build, (2) the exploitability triage matrix that cuts the finding set before a human reads it, (3) the deep cross-file CodeQL nightly tier distinct from the fast PR Semgrep tier. All three are NET-NEW.

---

## 1. SARIF aggregation - one normalized, de-duplicated finding set

The elite-delivery problem: a real review runs five-plus tools (claude-context, Trivy, Semgrep, osv-scanner, gitleaks, plus the client's own CodeQL/Sonar). Each emits its own SARIF with its own rule ids, severity scale, and location format. Handing the client five raw reports is amateur-hour: the same vulnerability appears under three different names and three different severities, producing "remediation paralysis" - the team cannot tell what to fix first or how many real problems exist. The elite move is to merge into ONE report.

### The aggregation pipeline (methodology, run in the client's CI or locally)
1. **Emit SARIF from every tool.** Each scanner in static-analysis-and-pr-automation.md already supports `--sarif`/`-f sarif`. Standardize on SARIF 2.1.0 so every result is a comparable object (rule id, level, location, message, optional codeFlows).
2. **Merge.** Combine all SARIF files into one (e.g. `sarif-tools` multitool merge, or the microsoft/sarif-sdk merge). The merged file keeps each tool as a distinct `run` so provenance is never lost.
3. **Normalize the severity scale.** SARIF `level` is only error/warning/note - too coarse. Map each tool's native severity (Trivy CRITICAL/HIGH, Semgrep ERROR, CVSS bands) onto ONE house scale (P0..P3 / the rules.md taxonomy) via a documented mapping table, so "HIGH" from tool A and "ERROR" from tool B sort together.
4. **De-duplicate.** The same defect found by two tools must collapse to one finding. Dedup key = normalized (file path + region + rule-class), NOT raw rule id (rule ids differ per tool). For CVEs, dedup on the CVE/GHSA id across Trivy and osv-scanner. Keep a `seenBy: [toolA, toolB]` list - a finding two independent tools agree on is higher-confidence, which feeds triage in section 2.
5. **Attach context.** Enrich each surviving finding with the data triage needs: CVE id, EPSS score, KEV membership, reachability verdict (section 2), and the variant class (from variant-analysis-and-fix-verification.md).
6. **Render the deliverable.** One ranked table the client can act on: finding, normalized severity, confidence (single-tool vs corroborated), exploitability, location, owner, fix. SARIF stays the machine artifact (upload to GitHub code-scanning); the ranked table is the human artifact.

### SARIF limitation to state honestly in the deliverable
SARIF normalizes the TRANSPORT, not the MEANING. Two tools' notions of "the same finding" can legitimately differ (different sink, different path to it). Dedup is heuristic; never silently drop a finding because a fuzzy match called it a duplicate - merge with both provenances attached and let the reviewer's judgment (never automatable, per the stack doctrine) make the final call. Scanners produce evidence, not a verdict.

---

## 2. Reachability + exploitability triage - cut the set before a human reads it

The elite differentiator over a commodity review: a raw multi-tool scan on a real codebase returns hundreds to thousands of findings, most of which are not exploitable in this deployment. Dumping all of them on the client is noise. The mature pipeline ranks on SEVEN dimensions and surfaces only the high-confidence, actionable set (industry reporting puts the reduction at 70-95 percent of raw volume). The reviewer triages every finding through:

| Dimension | Question | Source |
|-----------|----------|--------|
| Severity | how bad if exploited | CVSS / house P-scale |
| Exploitability | how likely to be exploited in the wild | EPSS score (FIRST.org) |
| Known-exploited | is it being exploited NOW | CISA KEV membership |
| Reachability | does our code actually CALL the vulnerable function | call-graph / taint (below) |
| Deployment context | internet-facing? handling sensitive data? | architecture knowledge |
| Business impact | revenue / compliance blast radius | client context |
| Fix availability | is there a safe upgrade / patch path | SCA fixedVersion |

### Reachability is the highest-leverage filter
The precise question: does the application actually invoke the vulnerable code path in the dependency (SCA) or reach the sink from a real input boundary (SAST)? If no, the finding is deprioritized, not deleted.
- SCA reachability: `osv-scanner --call-analysis` (already named in static-analysis-and-pr-automation.md) marks whether the vulnerable function is on a live call path; an unreachable CVE drops out of P0/P1. Commercial Endor/Snyk equivalents do the same with deeper call graphs - CONNECT only if the client already runs them.
- SAST reachability: the three taint questions from variant-analysis-and-fix-verification.md (user-controlled input, reaches sink unsanitized, reachable from a real boundary). A Semgrep taint hit broken by a real sanitizer is not a live finding.

### The triage verdict per finding
- **P0/P1 (block):** high severity AND (reachable OR KEV OR high EPSS). Any live secret (gitleaks history hit) is always block-and-rotate regardless of the matrix.
- **P2 (fix, not blocking):** real but unreachable-in-this-deployment, or low EPSS and not KEV.
- **P3 / accepted-risk:** documented suppression with an owner and an expiry, written to the scan-baseline memory key so re-scans surface only NEW findings.

Never suppress on reachability alone for a dependency the client may call later, or for anything KEV - state the residual risk instead. Reachability calibrates priority; it does not grant a pass on a known-exploited bug.

---

## 3. The CodeQL deep-query tier (nightly), distinct from the fast PR tier

The cluster's SAST is Semgrep, chosen for speed: a Semgrep rule is authored in under an hour and a CI scan finishes in 10-30 seconds, which is exactly right for a per-PR gate. But Semgrep's taint, even Pro cross-file mode, is shallower than a full semantic dataflow engine. The elite review runs a SECOND, deeper tier on a slower cadence.

### Two-tier doctrine
- **Fast tier (per PR):** Semgrep (static-analysis-and-pr-automation.md) - sub-minute, blocks the PR, catches the common injection/secret/anti-pattern classes and runs the WE-authored variant rules.
- **Deep tier (nightly / pre-release / audit):** CodeQL - compiles the codebase into a queryable database and runs genuine whole-program dataflow and taint across files and functions. Catches the multi-hop injection and logic flaws that span modules and that the fast tier misses. Scan time is minutes-to-hours, so it does NOT run on every PR; it runs nightly, before a release, and inside a full audit.

### Custom-query authoring (the elite tier above default packs)
The default CodeQL query suites are the floor. The elite move mirrors the variant-analysis-and-fix-verification.md rule-authoring discipline, raised to QL: take a confirmed finding, abstract its root cause, and write a custom QL query that uses the full type system + dataflow library to find every semantic sibling across the whole compiled database - including siblings spelled differently that a Semgrep pattern would miss. Author test-first (true-positive cases from the confirmed finding and its variants must fire; true-negative safe idioms from the same codebase must not), exactly as in the Semgrep rule discipline. QL is harder and slower to author than a Semgrep pattern (a day vs an hour for a proficient author), so reserve custom QL for the deep, high-value classes; keep the fast, cheap classes in Semgrep.

### LICENSE FLAG (read before reuse)
CodeQL is free for OSS and research ONLY. Private/commercial client repos require GitHub Advanced Security (a paid entitlement). CONNECT posture: run CodeQL only where the client ALREADY has GHAS, read its alerts into the aggregated report (section 1), and do NOT redistribute Solaris-authored QL queries as a client deliverable without confirming the engagement IP terms. If the client lacks GHAS, the deep tier falls back to Semgrep Pro taint (commercial) or a manual cross-file trace; never stand up unlicensed CodeQL.

---

## Cross-references
- references/static-analysis-and-pr-automation.md - the scanning STACK that emits the SARIF this file merges, and the Semgrep fast tier that this file's CodeQL deep tier sits above. The SHA-pin CI doctrine there also pins the CodeQL/scanner action refs. NO tool list duplicated here.
- references/variant-analysis-and-fix-verification.md - the per-finding class-closure and fix-proof discipline; this file's custom-QL authoring is that same rule-authoring discipline raised to the deep semantic tier, and the triage verdict feeds the write-up there.
- references/trivy-sca-secrets-sbom.md - Trivy SARIF and CVE ids are inputs to the dedup (section 1 step 4) and the SBOM is the source for fix-availability in the triage matrix.
- claude-context-operator.md - index >2,000-file repos first so reachability tracing and the deep-tier query targeting run by intent across the whole tree.
- rules.md - the P0..P3 severity taxonomy this file normalizes onto, plus the accepted-risk baseline doctrine.
- security-auditor references/elite-audit-delivery.md - the AUDIT-scale mirror: the same aggregated SARIF report + EPSS/KEV/reachability triage matrix + CodeQL tier, run at full-engagement scale with a client-facing risk register rather than a PR gate. Hand cross-scope findings across the line.

## Memory scope keys
- code-reviewer/<project>/sarif-mapping - the per-tool severity-to-house-scale mapping and the dedup key rules used for this project's report (so successive reports are consistent and comparable)
- code-reviewer/<project>/triage-baseline - per-finding triage verdict (severity/EPSS/KEV/reachability/context) + accepted-risk suppressions with owner+expiry, so re-scans surface only NEW or newly-reachable findings
- code-reviewer/<project>/deep-tier-queries - WE-authored CodeQL queries born from this project's confirmed findings (provenance + TP/TN cases + CWE); kept separate from default query suites per the license posture
