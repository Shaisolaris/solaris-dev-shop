# Adversarial Bounty Hunting (Attacker Mindset)

The MINDSET layer of the audit, distinct from the tool/check catalog in references/scanning-stack.md (Semgrep/OSV/gitleaks/pytm/Nuclei + fleet checks FA-1/FA-2) and from references/trivy-and-dast.md (operational SCA/secrets/SBOM + DAST). Those files are the HOW of running scanners. This file is the HOW of THINKING like an attacker who only gets paid for issues that are real, reachable, and exploitable.

Lifted methodology-only from ECC (affaan-m/ECC, MIT): security-bounty-hunter (adversarial vuln-hunting), plus the license/supply-chain angle from repo-scan (embedded in-tree third-party detection). No code, prompts, or rule packs vendored.

## Why a separate mindset

A compliance/best-practices audit asks "is this theoretically unsafe?" and produces long lists of informational findings the client cannot prioritize. A bounty hunter asks "does this actually pay?" - meaning: can a remote, unauthenticated-or-low-priv attacker reach a meaningful sink with user-controlled input, and can I prove it. The same scanners feed both, but the bounty mindset is the filter that turns scanner noise into a short list of findings that matter. Run this lens AFTER the scanner passes in scanning-stack.md / trivy-and-dast.md have produced candidate findings; this is the triage and exploitation-reasoning layer on top.

## The core bias: remotely reachable + user-controlled

Bias every hour of effort toward attack paths that are (a) reachable from a real network or user boundary and (b) driven by genuinely attacker-controlled input. Throw away patterns that pay nothing even when "technically true". This bias is what separates a report that gets accepted from a noise dump that gets the auditor ignored.

## In-scope patterns (these consistently matter)

| Pattern | CWE | Typical impact |
| --- | --- | --- |
| SSRF via user-controlled URLs | CWE-918 | internal network access, cloud metadata/credential theft |
| Auth bypass in middleware / API guards | CWE-287 | unauthorized account or data access |
| Remote deserialization / upload-to-RCE | CWE-502 | code execution |
| SQL injection in reachable endpoints | CWE-89 | data exfiltration, auth bypass, data destruction |
| Command injection in request handlers | CWE-78 | code execution |
| Path traversal in file-serving paths | CWE-22 | arbitrary file read/write |
| Auto-triggered XSS | CWE-79 | session theft, admin compromise |

(For client work, "in scope" = anything that exposes the client's users or data. The discipline is the same: reachability + control + meaningful sink.)

## Skip these (low-signal / out of scope unless the program says otherwise)

- Local-only pickle.loads / torch.load / equivalent with no remote path
- eval() / exec() in CLI-only tooling
- shell=True on fully hardcoded commands (no user input reaches it)
- Missing security headers in isolation (note them, do not headline them)
- Generic "no rate limiting" with no demonstrated exploit impact
- Self-XSS that requires the victim to paste attacker code by hand
- CI/CD injection outside the target's scope
- Demo / example / test-only code

Discipline note: "skip" does not mean "never log". On a client engagement these go in a low-severity appendix; they must never crowd out or dilute the exploitable findings. A report that buries one real RCE under forty header warnings has failed.

## Workflow (reachability-first)

1. **Check scope first.** Program rules, SECURITY.md, disclosure channel, explicit exclusions. For client work: the engagement letter / authorized scope. Never test outside it.
2. **Find real entrypoints.** HTTP handlers, file uploads, background jobs, webhooks, message/queue consumers, parsers, third-party integration endpoints. These are the boundaries where attacker input enters.
3. **Run static tooling as triage input ONLY.** The scanners in scanning-stack.md produce candidates; they do not produce verdicts. A Semgrep ERROR is a lead, not a finding.
4. **Read the real code path end to end.** From the entrypoint to the sink. This is the step scanners cannot do and where the actual bug is confirmed or dismissed.
5. **Prove user control reaches a meaningful sink.** Trace the taint: does attacker-controlled input actually flow, unsanitized, into the dangerous operation? If a sanitizer or framework guard breaks the chain, it is not a finding.
6. **Confirm exploitability with the smallest safe PoC.** Minimal working request or script that demonstrates impact without causing damage. No PoC = not yet a finding.
7. **Check for duplicates before writing it up.** Existing advisory, CVE, open ticket, or known issue. A duplicate wastes everyone's time.

### Triage loop (scanner -> manual filter)

Run the SAST candidate pass (see scanning-stack.md for the operational Semgrep invocation), then manually filter the output:
- drop tests, demos, fixtures, vendored/third-party code (but see supply-chain note below)
- drop local-only and non-reachable paths
- keep only candidates with a clear network or user-controlled route to a meaningful sink

## Supply-chain / license angle (from repo-scan)

Scanners that read package manifests miss third-party code copied directly into the source tree. On any audit, do a census pass that classifies files as project code vs embedded in-tree third-party vs build artifact, and detect bundled libraries by directory names, file headers, bundled LICENSE files, and version markers, NOT by the manifest. Two attacker-relevant outcomes:
- **Stale vendored library = live attack surface.** A 2015-vintage in-tree copy of a parser/codec/crypto lib carries every CVE shipped since, and no dependency scanner is watching it because it is not declared. Cross-check detected in-tree libs + versions against the OSV/Trivy DBs (scanning-stack.md). Vendored copies are higher-risk than declared deps precisely because nobody is tracking them.
- **License is also a supply-chain finding.** Copyleft (GPL/AGPL) vendored into a closed client product is a legal-exposure finding; route it to the license-flag doctrine and to legal/compliance. Track it alongside the CVE findings, not separately.

This pairs with fleet check FA-2 (SHA-pin third-party CI actions) in scanning-stack.md: the same "untracked third-party code executing in our trust boundary" threat model covers both vendored source and floating CI action tags (post the Mar-2026 aquasecurity/trivy-action tag-rewrite compromise).

## Quality gate (before any finding ships)

A finding ships only when ALL hold:
- The code path is reachable from a real user or network boundary
- The input is genuinely user-controlled
- The sink is meaningful and exploitable
- The PoC works
- It is not already covered by an advisory, CVE, or open ticket
- The target is actually in scope

Anything failing the gate is a lead, not a finding. Leads go in the appendix or get more work; they do not get reported as confirmed.

## Report structure (per confirmed finding)

```
## Description      - what the vuln is and why it matters
## Vulnerable Code  - file path, line range, small snippet
## Proof of Concept - minimal working request or script
## Impact           - what the attacker can actually achieve
## Affected Version - version, commit, or deployment target tested
```

## Cross-references
- references/scanning-stack.md - the tool/check catalog this mindset filters: Semgrep (the triage SAST in step 3), OSV-Scanner (cross-check vendored-lib CVEs), gitleaks (history secrets), pytm (threat model), Nuclei (template DAST), and fleet checks FA-1 (memory-scope-keys) + FA-2 (SHA-pin CI actions). NO tool lists duplicated here on purpose.
- references/trivy-and-dast.md - operational SCA/secrets/SBOM (Trivy) + DAST (ZAP) workflow; the active-testing companion to step 6 PoC work (same authorization gate).
- rules.md - decision rules, red flags, severity. This mindset sharpens the "is it exploitable / is it in scope" judgment behind them.
- code-reviewer references/codebase-takeover-and-audit.md - the inherited-codebase census + silent-failure methods; receive its embedded-third-party + license findings as audit input.

## Memory scope keys
- security-auditor/bounty/<client>/in-scope-entrypoints - confirmed attacker-reachable boundaries
- security-auditor/bounty/<client>/confirmed-findings - findings that passed the quality gate (with PoC + CWE)
- security-auditor/bounty/<client>/vendored-libs - embedded in-tree third-party + versions + CVE/license cross-check
- security-auditor/bounty/<client>/leads - candidates that failed the gate, parked for more work
