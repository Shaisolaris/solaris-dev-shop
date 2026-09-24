# Scanning stack + two fleet audit checks

Methodology layer for the security auditor. Five OSS tools operationalized as run-directly workflows (no code bundled per fleet doctrine), plus two fleet rules this employee now OWNS and encodes as audit checks: memory-scope-keys (cross-tenant leak prevention) and SHA-pin all third-party CI actions (post the March 2026 trivy-action compromise). Added 2026-06-13.

Layering doctrine (extends references/trivy-and-dast.md run-order): threat-model-as-code (pytm) at design -> SAST (Semgrep) -> SCA (OSV-Scanner cross-checks Trivy) -> secrets (gitleaks + Trivy, then semantic) -> IaC/container (Trivy + OSV layer-aware) -> DAST (ZAP generic crawl, then Nuclei template sweeps) -> agent-component scanners (snyk + cisco, dims 9-10) -> manual. No single tool is comprehensive; vendor diversity is itself a supply-chain control (see SHA-pin check below).

## SAST - Semgrep [LGPL-2.1, FLAG copyleft -> METHODOLOGY]
The AST taint/pattern engine the layering doctrine already names. Run directly; do NOT vendor the rule packs (separate source-available Semgrep Rules License - keep them as an external dependency, do not fork into closed client deliverables; LGPL on the engine governs linking, not invocation, so calling the CLI is fine).
- Operational: `semgrep --config p/owasp-top-ten --config p/secrets --sarif -o out.sarif <path>`; author custom YAML rules for client-specific patterns; `--baseline-commit <sha>` for diff-aware scans that map onto the existing diff-scoped PR rule. Feeds dim-1 vulnerability detection with real taint analysis (regex secret scans are a floor; Semgrep adds dataflow).
- Self-host note: runs fully local/offline; no telemetry needed for OSS engine. SARIF -> GitHub code scanning.

## SCA / SBOM - OSV-Scanner [Apache-2.0 -> ABSORB methodology]
A second, vendor-independent SCA/SBOM lens beside Trivy. Different DB provenance (OSV.dev: GitHub Advisories + RustSec + distro notices) and call-graph reachability cut FPs. Running both Trivy and OSV is deliberate: after the trivy-action compromise, do not let one scanner's supply chain be a single point of failure.
- Operational: `osv-scanner scan source -r <dir>`; container `osv-scanner scan image <img:tag>` (layer-aware); SBOM scan of SPDX/CycloneDX; `osv-scanner --licenses="MIT,Apache-2.0" <dir>` for the compliance license section; `--offline --download-offline-databases` for air-gapped audits.
- Folds into dim-4 supply-chain. Re-scan a fixed SBOM as new CVEs land WITHOUT rebuild (same "are we affected by CVE-XXXX" answer as Trivy, cross-checked).

## Secrets - gitleaks [MIT -> CONNECT methodology]
The tool that makes the standing "secrets in repo -> rotate + history cleanup + disclosure" rule executable, because it scans git HISTORY not just the working tree.
- Operational: `gitleaks detect --source <repo> --report-format sarif --report-path gl.sarif`; pre-commit hook + GitHub Action for shift-left; custom regex/entropy rules. gitleaks is the regex/entropy floor - the standing "obfuscated secrets evade regex (base64/concat/env-indirect)" gotcha means semantic-context review stays the ceiling.
- Governance watch: original creator stepped back March 2026 and launched Betterleaks; gitleaks stays MIT and maintained, but if it stalls, Betterleaks is the successor. Re-verify next pass.

## Threat modeling as-code - OWASP pytm [NOASSERTION + stale cadence, FLAG -> METHODOLOGY + self-host]
Turns the prose STRIDE/PASTA/LINDDUN coverage into a reproducible, diffable artifact and makes the "threat models rot - re-do after major changes" gotcha tractable.
- Operational: express the system as pytm Python objects (Boundary, Dataflow, Actor, Server, Datastore); `pytm --dfd | dot -Tpng` for the data-flow diagram, `pytm --report` for the auto-generated STRIDE threat list + sequence diagram. The model lives in the repo and re-runs on change.
- Flags: license is "Other" (catalog pulls MITRE CAPEC under CAPEC terms) - methodology only, do not assume permissive catalog reuse. Cadence is slow (last commit ~Nov 2025); self-host/run-directly, and fall back to OWASP Threat Dragon (GUI, maintained) if pytm goes dormant.

## DAST - Nuclei [MIT -> ABSORB methodology]
A template/signature DAST layer complementing ZAP's generic crawl-and-inject. Fast "is this known-vuln present" sweeps + external recon (maps to the pentest recon->scan phase).
- Operational: `nuclei -u https://target -t cves/ -t misconfiguration/ -rl 150` (respect the rate limit; throttle to avoid DoS, same authorization gate as ZAP - unscoped prod scan = incident); import targets from recon; 12k+ community templates, new CVE templates within hours of disclosure. Confirmed findings -> risk register with retest, every hit is a candidate (verify, kill FPs, rate by exploitability x impact).
- Layering: ZAP first (generic active/passive over crawled surface), Nuclei for signature sweeps + freshly disclosed CVE checks. Neither replaces manual logic testing.

---

# Fleet audit checks (this employee OWNS these two)

These are encoded as PASS/FAIL audit checks the auditor runs on every engagement that has a multi-tenant data plane and/or a CI/CD pipeline. Both are red-flag items: a FAIL is at least P1.

## Check FA-1 - Memory-scope-keys (cross-tenant leak prevention)
**Policy:** every cache entry, agent/session memory record, vector-store namespace, and any other shared key-value or retrieval store that holds per-tenant (or per-user) data MUST be keyed by an explicit scope key that includes the tenant/user identity. No global/un-scoped keys for tenant-bearing data. The scope key is derived from a trusted server-side identity (authenticated principal), never from a client-supplied value that can be spoofed.
**Why:** the dominant cross-tenant data-leak class in multi-tenant AI systems is a shared cache or memory store read/written with a key that omits tenant scope (or trusts a client-supplied tenant id), so tenant B's request hits tenant A's cached/remembered data. Maps to OWASP A01 Broken Access Control + LINDDUN Linkability/Disclosure + STRIDE Information Disclosure.
**Audit steps:**
1. Enumerate every shared store: caches (Redis/Memcached/in-proc), agent/conversation memory, embeddings/vector namespaces, rate-limit counters, idempotency keys, signed-URL/object paths.
2. For each, confirm the key includes a server-derived tenant/user scope: `cache:{tenant_id}:{resource}` not `cache:{resource}`. Vector stores: per-tenant namespace/collection or a mandatory tenant filter on every query.
3. Verify the scope component comes from the authenticated principal, not a request header/body/JWT-claim the client controls without server validation.
4. Negative test: as tenant B, attempt to read a key/namespace that tenant A populated (cache poisoning / key-confusion / namespace-traversal). Must fail closed.
5. Check eviction/TTL does not collapse scopes and that default/empty tenant id cannot map to a shared bucket.
**Verdict:** PASS = all tenant-bearing stores scope-keyed from trusted identity + negative test fails closed. FAIL (>= P1) = any tenant-bearing store with a global key, a client-controlled scope, or a passing cross-tenant read. Remediation: introduce mandatory scope-key derivation at the store-access boundary; reject un-scoped access in code review; add a cross-tenant negative test to CI.

## Check FA-2 - SHA-pin all third-party CI actions (post trivy-action compromise)
**Policy:** every third-party GitHub Action (and equivalent third-party CI step in GitLab/CircleCI/etc.) MUST be pinned to a full 40-character commit SHA, never to a mutable tag (`@v1`, `@latest`, `@main`). First-party org-owned actions may use tags only if the org enforces tag-protection; everything external is SHA-pinned.
**Why:** on 2026-03-19 a threat actor with compromised credentials force-pushed 76 of 77 version tags in `aquasecurity/trivy-action` (and all 7 tags in `setup-trivy`) to credential-stealing malware, plus a malicious Trivy v0.69.4 release - a ~12h exposure window. Tags are mutable and were rewritten; commit SHAs are immutable and could not be. Any pipeline pinned to a tag silently pulled malware. This is the canonical reason the fleet SHA-pins. Maps to OWASP A08 Software & Data Integrity Failures + STRIDE Tampering + supply-chain dim-4/5.
**Audit steps:**
1. Grep every CI workflow for `uses:` (and equivalent) third-party steps. Flag any pinned to a tag or branch rather than a 40-char SHA.
2. For SHA-pinned actions, confirm a comment records the intended version (`@<sha> # v0.35.0`) so updates are auditable and the SHA is not opaque-forever.
3. Confirm a maintained pinning automation (Dependabot/Renovate configured to pin-to-SHA, or StepSecurity Harden-Runner / pin-github-action) keeps SHAs current without reverting to tags.
4. Confirm a runner egress-control / least-privilege token posture (read-only `GITHUB_TOKEN` by default; Harden-Runner or equivalent egress policy) so a compromised action cannot freely exfiltrate.
5. Incident-readiness: confirm that if a pinned action's upstream is compromised, secrets reachable by affected pipelines would be rotated (ties to the secrets rule). Note from the incident: SHA-pinning narrows but does not eliminate risk if a malicious commit is later referenced - so pin + egress control + token least-privilege together.
**Verdict:** PASS = all third-party CI actions SHA-pinned with version comments + pinning automation + least-privilege tokens/egress control. FAIL (>= P1, P0 if the pipeline holds production-deploy credentials) = any third-party action on a mutable tag/branch. Remediation: convert all `@tag` to `@<sha> # vX.Y.Z`; enable pin-to-SHA automation; set default token to read-only; add egress policy.
