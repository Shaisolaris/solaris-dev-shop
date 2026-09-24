# Trivy - unified SCA / secrets / SBOM patterns

Absorbed from aquasecurity/trivy-mcp (MIT, official Aqua Security, commit main @ 2026-06-13) wrapping Trivy. Net-new for code-reviewer: a SINGLE scanner that unifies what the employee previously did with N per-ecosystem CLIs (npm/composer/pip/cargo audit). Trivy is also absorbed by security-auditor - code-reviewer's lens is "block the PR / flag the dependency"; same engine, review-tier framing.

## Scan targets (via the MCP)
- **Filesystem** - scan a local project/repo checkout (the PR working tree).
- **Container image** - scan a built image for OS + app vulnerabilities.
- **Remote repository** - scan a repo without cloning it manually.
Natural-language entry point: "Are there any vulnerabilities or misconfigurations in this project?" - but treat the output as evidence, not verdict.

## What Trivy finds (the four pillars to fold into review)
1. **SCA (dependency vulnerabilities):** one scan across many ecosystems (npm, pip, Composer, Go modules, Cargo, Maven/Gradle, NuGet, RubyGems, etc.) PLUS OS packages - replaces running each ecosystem's audit tool separately. Maps to the existing CVE severity ladder (P0 active-exploit, P1 CVSS 7+, P2 medium/major-behind).
2. **Secret detection:** scans for hardcoded credentials/keys/tokens in the tree - folds into the existing "secrets in code or logs" blocker. A found secret is a P0/blocker AND a rotate-now action, not just a code comment.
3. **Misconfiguration / IaC:** Dockerfile, Kubernetes, Terraform, CloudFormation misconfigs - surface to the author; route infra-policy fixes to devops/cloud-architect.
4. **License scan:** flags dependency licenses - catches a copyleft/GPL pull into a closed product before it ships (pairs with the org's license-flag doctrine).

## SBOM (net-new capability)
- Trivy generates an SBOM (CycloneDX or SPDX) from the project/image. Use it to (a) attach a supply-chain bill-of-materials to a release, (b) re-scan the SBOM later when new CVEs land WITHOUT rebuilding, and (c) answer "are we affected by CVE-XXXX" against a known component inventory.

## Review-tier doctrine
- Run Trivy as the dependency/supply-chain pass; it does NOT replace AST-based SAST (semgrep/CodeQL/Snyk Code still own data-flow/taint) or human logic review - same boundary the existing code-context note draws. Layered, not either/or.
- Severity gating: P0/P1 SCA findings + any detected secret block the PR; P2 + license issues are flagged with an owner. Triage with `--ignore-unfixed` awareness - distinguish "fix available" from "no patch yet" so you don't block on un-actionable noise, but still record it.
- Findings are evidence for the reviewer's judgment, not an auto-verdict (the scanner can't see business-logic abuse or intent).

## CONNECT note (host installs)
Host installs the trivy-mcp server (requires the `trivy` binary; MIT). Optional Aqua Platform integration for assurance-policy compliance (commercial - flag if a client wants it). No account needed for the core OSS scanning.
