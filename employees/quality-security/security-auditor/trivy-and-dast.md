# Trivy operational SCA/secrets/SBOM + OWASP ZAP DAST methodology

Two net-new operational layers for the security auditor. Gate-0: Trivy and OWASP ZAP were both already NAMED in the tool catalog (SCA/container/SBOM and DAST respectively), but there was no operational Trivy-MCP workflow and no DAST methodology section - so this adds the HOW, not a duplicate tool listing.

## Part A - Trivy (aquasecurity/trivy-mcp, MIT, official Aqua; main @ 2026-06-13) - ABSORB
The auditor's lens differs from code-reviewer's "block-the-PR" framing: here Trivy is a finding-generator that feeds the audit report + risk register, cross-referenced to OWASP/CWE/CVE.

Scan targets via the MCP: filesystem (project tree), container image (OS + app vulns), remote repository.

Fold the four pillars into the existing 10-dimension secure-code pass:
- **SCA** (dim 4 supply-chain): dependency + OS vulns across ~all ecosystems in one scan - replaces juggling npm/pip/composer/cargo audit; map each to CVE/CVSS severity and "fix available vs unfixed" (`--ignore-unfixed` awareness so the register separates actionable from un-patchable).
- **Secrets** (dim 3): hardcoded creds/keys → existing immediate-rotation + git-history-cleanup + disclosure rule fires. Caveat from standing gotchas: regex-based secret scans miss base64/concatenated/env-indirected secrets - Trivy is a floor, not a ceiling; keep semantic-context review.
- **Misconfig / IaC** (dim 5): Dockerfile/K8s/Terraform/CloudFormation misconfigs → CI-gate recommendation to devops.
- **License**: copyleft/GPL-into-closed-product flags for the compliance section.
- **SBOM** (SPDX/CycloneDX): generate for the supply-chain section; re-scan the SBOM as new CVEs land WITHOUT rebuild, and answer "are we affected by CVE-XXXX" against a fixed component inventory.

Layering doctrine (unchanged): Trivy/SCA does not replace AST SAST (semgrep/CodeQL/Snyk Code own taint), the agent-component scanners (snyk-agent-scan + cisco-ai-skill-scanner, dims 9–10), or manual logic/business-abuse review. Run order in a full audit: SAST → SCA(Trivy) → secrets(Trivy + semantic) → IaC/container(Trivy) → DAST(ZAP, below) → agent-component scanners → manual.

Host installs trivy-mcp (needs the `trivy` binary). Optional Aqua Platform integration is commercial - flag if a client wants assurance-policy compliance.

## Part B - OWASP ZAP DAST methodology (no verified MCP) - METHODOLOGY
DAST tests the RUNNING app (SAST/SCA test code + deps; DAST tests behavior). OWASP ZAP (Apache-2.0) is the OSS reference tool. No verified MCP wrapper exists as of 2026-06-13 - so this is METHODOLOGY: run ZAP directly (CLI/daemon/zap-baseline.py), lift the workflow, not an MCP. (Scout watchlist: re-evaluate if a maintained ZAP MCP appears.)

DAST workflow the auditor runs:
1. **Scope + authorize** - only against environments with written authorization (a pentest without scope+sign-off is an incident). Prefer staging that mirrors prod; never an unscoped prod scan.
2. **Spider/crawl** - traditional + AJAX spider to enumerate the attack surface (URLs, params, forms, APIs). Import an OpenAPI/GraphQL schema for API coverage.
3. **Authenticated scanning** - configure session/auth context so the scan reaches post-login surface (most real vulns are behind auth). Verify the session stays valid mid-scan.
4. **Passive scan** - observe traffic for headers, cookies flags, info leaks (zero-impact, run first).
5. **Active scan** - inject payloads for OWASP Top 10: injection (SQLi/cmd), XSS (reflected/stored/DOM), broken access control / IDOR, SSRF, security misconfig, auth flaws. Throttle to avoid DoSing the target.
6. **Baseline in CI** - `zap-baseline.py` as a passive gate per deploy (fast, low-noise); full active scans on a schedule, not every commit.
7. **Triage** - every ZAP finding is a candidate, not a confirmed vuln: manually verify, kill false positives, rate by real exploitability + business impact, cross-ref OWASP/CWE. Confirmed → risk register with remediation + retest step.

DAST limits to state in the report: it can't see source, misses logic flaws an attacker would find by reasoning, and only covers what the spider reached - so DAST complements SAST + manual, never replaces them.
