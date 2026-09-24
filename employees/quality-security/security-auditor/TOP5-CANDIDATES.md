# TOP-5 Verified 2026 Candidates - Security Auditor

Researched 2026-06-13. Each verified for: established/safe, star count, license (copyleft/NOASSERTION flagged), commit recency (~6mo), maintainer credibility. Gate-0 = grep of THIS employee's actual content -> present / content-duplicate / net-new.

Coverage across the brief's required dimensions: SAST (Semgrep), threat modeling (OWASP pytm), secrets scanning (gitleaks), SCA/SBOM (OSV-Scanner), DAST + container/CVE (Nuclei). OWASP spans pytm (threat modeling) and Nuclei (templates) plus the already-absorbed ZAP. Container scanning is covered by the absorbed Trivy plus OSV-Scanner's layer-aware container scans.

---

## 1. Semgrep - SAST
- **URL:** https://github.com/semgrep/semgrep
- **Stars:** ~14.9k
- **License:** LGPL-2.1 - **FLAG: weak copyleft.** CLI/engine is LGPL; the maintained rule packs carry a separate Semgrep Rules License v1.0 (source-available, not OSI). The engine is safe to invoke as an external tool (LGPL governs linking, not invocation); do NOT vendor or fork the rule packs into closed deliverables.
- **Last commit:** semgrep-rules updated 2026-06-13; core repo active June 2026 (OSS v1.145.0 line). Within 6mo.
- **Maintainer:** Semgrep, Inc. (r2c) - commercial backer, large team, multi-year cadence. Established.
- **What it adds:** Operational SAST workflow - the AST taint/pattern engine the layering doctrine already names ("AST SAST that semgrep/CodeQL own") but never operationalizes. Custom-YAML rule authoring for client-specific patterns, autofix, SARIF for GitHub code scanning, diff-aware `--baseline-commit` mode mapping onto the existing diff-scoped PR rule, `--config p/owasp-top-ten`.
- **Gate-0:** PRESENT-as-name, NOT operationalized. SKILL.md line 30 lists "Semgrep" in the SAST tool line; rules.md names "semgrep/CodeQL/Snyk Code own taint" in the layering doctrine. No HOW anywhere. Not a content-duplicate - the SAST step in the run-order is a bare label.
- **Tag:** **CONNECT / METHODOLOGY** (LGPL flagged - methodology + run-directly note, no bundling)

## 2. OSV-Scanner - SCA / SBOM
- **URL:** https://github.com/google/osv-scanner
- **Stars:** 10.5k
- **License:** **Apache-2.0** (permissive, preferred)
- **Last commit:** release v2.3.8 on 2026-05-08; 1,932 commits, active. Within 6mo.
- **Maintainer:** Google / OSV.dev team. Official frontend to the OSV database. SLSA-3, OpenSSF Scorecard. Highly established.
- **What it adds:** A second, non-Trivy SCA/SBOM lens with different data provenance (OSV.dev aggregates GitHub Advisories, RustSec, distro notices in a machine-readable affected-version format). Call-analysis to cut FPs (confirms the vulnerable function is actually reached), SBOM scanning (SPDX/CycloneDX), `--licenses` allow-list checks, container layer-aware scanning, offline DB mode, guided remediation. Post-Trivy-compromise value: a vendor-independent cross-check so the audit does not rest on one scanner's supply chain.
- **Gate-0:** ABSENT. Zero hits for "osv" anywhere. Net-new. Complements (does not duplicate) the absorbed Trivy SCA - different DB, call-graph reachability, vendor diversity.
- **Tag:** **ABSORB / METHODOLOGY** (permissive; methodology only, no code bundled per fleet doctrine)

## 3. gitleaks - Secrets scanning
- **URL:** https://github.com/gitleaks/gitleaks
- **Stars:** ~25.9k
- **License:** **MIT** (permissive)
- **Last commit:** active 2026.
- **Maintainer:** gitleaks org. **FLAG - governance note:** in March 2026 the original creator (Zach Rice) announced he no longer has full control of the repo/brand and launched a successor, "Betterleaks." gitleaks itself stays MIT, widely used, and maintained, but the governance split is a watchlist item - re-evaluate maintainer trust next pass; consider Betterleaks if the original repo stalls.
- **What it adds:** Operational secrets methodology - git-history-aware scanning (not just working tree); the existing "secrets in repo -> rotate + history cleanup + disclosure" rule needs a tool to FIND them across history, and gitleaks does exactly that. SARIF + JUnit output, official GitHub Action, pre-commit hook, custom regex/entropy rules. Pairs with the standing "obfuscated secrets evade regex" gotcha (gitleaks is the regex/entropy floor; semantic review is the ceiling).
- **Gate-0:** PRESENT-as-name, NOT operationalized. SKILL.md line 36 lists "gitleaks, trufflehog, detect-secrets" with no workflow. Net-new HOW; not a content-duplicate.
- **Tag:** **CONNECT / METHODOLOGY**

## 4. OWASP pytm - Threat modeling (as-code)
- **URL:** https://github.com/OWASP/pytm
- **Stars:** ~1.1k (over 100; OWASP-backed notable project)
- **License:** **FLAG: "Other" / NOASSERTION** - GitHub reports license as "Other." The threat catalog incorporates MITRE CAPEC content under CAPEC's own terms. Treat as methodology-only; do not assume permissive reuse of the catalog. Acceptable as a methodology source.
- **Last commit:** master last commit ~2025-11-13; latest tagged release v1.3.1 (2024-04-25). **FLAG: slowest cadence of the five** - commits are >6mo old as of 2026-06. Included on quality/fit grounds (it is the canonical threat-model-as-code tool and fills a genuine gap) but flagged; re-verify liveness next pass. OWASP Threat Dragon is the maintained GUI fallback if pytm goes dormant.
- **Maintainer:** OWASP Foundation (project lead Izar Tarandach). Canonical, credible.
- **What it adds:** Threat-modeling-AS-CODE - the employee has rich STRIDE/PASTA/LINDDUN narrative but no reproducible, version-controllable, diffable artifact. pytm expresses the system as Python objects (boundaries, dataflows, actors), auto-generates DFDs + a STRIDE threat list + sequence diagrams. Makes "threat models rot - re-do after major changes" (standing gotcha) tractable: the model lives in the repo and re-runs on change.
- **Gate-0:** ABSENT as tool. STRIDE/PASTA/LINDDUN exist as prose only; no threat-model-as-code anywhere. Net-new methodology.
- **Tag:** **METHODOLOGY** (NOASSERTION + stale-cadence flags - methodology + self-host/run-directly note, no bundling)

## 5. Nuclei - DAST / CVE + misconfig templates
- **URL:** https://github.com/projectdiscovery/nuclei
- **Stars:** ~28k
- **License:** **MIT** (permissive)
- **Last commit:** active 2026; 12,000+ community templates, new CVE templates within hours of disclosure.
- **Maintainer:** ProjectDiscovery. Large active community + commercial backer. Established.
- **What it adds:** A complementary DAST/active layer to the already-absorbed ZAP - template-driven, YAML-DSL checks across HTTP/DNS/TCP/SSL/headless, 12k+ templates covering known CVEs, misconfigs, default creds, exposed panels. Where ZAP crawls + injects generically, Nuclei is signature-driven and fast for "is this known-vuln present" sweeps and external recon (maps onto the pentest recon->scan phase). Rapid CVE template coverage for newly disclosed issues.
- **Gate-0:** ABSENT. Zero hits. Net-new. Complements ZAP (generic active/passive crawl) vs Nuclei (signature/template sweeps) - different methods, layered not duplicated.
- **Tag:** **ABSORB / METHODOLOGY** (permissive; methodology only)

---

## Summary table

| # | Tool | Dimension | Stars | License | Last commit | Gate-0 | Tag |
|---|------|-----------|-------|---------|-------------|--------|-----|
| 1 | Semgrep | SAST | ~14.9k | LGPL-2.1 (FLAG copyleft) | Jun 2026 | present-as-name, not operationalized | CONNECT / METHODOLOGY |
| 2 | OSV-Scanner | SCA/SBOM | 10.5k | Apache-2.0 | v2.3.8 May 2026 | absent / net-new | ABSORB / METHODOLOGY |
| 3 | gitleaks | secrets | ~25.9k | MIT (FLAG governance fork) | 2026 | present-as-name, not operationalized | CONNECT / METHODOLOGY |
| 4 | OWASP pytm | threat modeling | ~1.1k | Other/NOASSERTION (FLAG) | Nov 2025 (FLAG stale) | absent as tool / net-new | METHODOLOGY |
| 5 | Nuclei | DAST/CVE templates | ~28k | MIT | 2026 | absent / net-new | ABSORB / METHODOLOGY |

## Doctrine decisions applied
- All five taken as METHODOLOGY (no code bundled) per fleet doctrine; flagged-license items (Semgrep LGPL, pytm NOASSERTION) carry an explicit run-directly / self-host note.
- Threat-modeling slot went to pytm (as-code, diffable) over Threat Dragon (GUI) because the gap is a reproducible artifact, not a drawing tool. Threat Dragon logged as the maintained fallback.
