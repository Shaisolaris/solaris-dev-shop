# DevOps Engineer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#cicd], [#iac], [#k8s], [#cloud], [#ftp-legacy], [#secrets], [#observability], [#incident], [#cost], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - DevOps clean rebuild (6 repos only)**: First build had the ftp-deploy skill wholesale-absorbed in first pass, violating master plan. This rebuild is clean - 6 repos only. The ftp-deploy skill now lives as GIG #2 (solaris/gigs/ftp-deploy/) with its version tagging + post-deploy verification; devops-engineer cross-references it for the deploy run (doctrine retired 2026-06-04).
  *Proposed rule: Respect the master plan order. 6 repos → clean base. owner skills → deliberate v0.3 upgrade later. Keeps provenance + rollback traceable.*
  Tags: [#master-plan-discipline]

- **2026-04-24 - DevOps clean rebuild**: sickn33 has the richest deployment-skill inventory in the 6-repo set - 10+ per-platform deployment skills (expo, vercel, kubernetes, azd, makepad, odoo-docker, appdeploy, etc.) plus deployment-validation + deployment-procedures + deployment-pipeline-design. Treats deployment as a first-class domain with per-platform nuance.
  *Proposed rule: For specialized ops domains, prefer a platform-specific reference over a generic one. "Deploy to Vercel" ≠ "Deploy to AWS ECS" - don't collapse them.*
  Tags: [#platform-specific-depth]

- **2026-04-24 - DevOps clean rebuild**: Kept a legacy-FTP section in SKILL even without the ftp-deploy skill absorbed - because legacy PHP/WordPress clients on shared hosts are a real Solaris client segment. Built from first principles (lftp + rsync + exclude patterns + version tagging) so it's independent-reference-able.
  *Proposed rule: When a domain has legitimate use cases (legacy clients), build from first principles even without a strong source. Don't let source-availability dictate scope coverage.*
  Tags: [#coverage-completeness]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-04-25 - v0.3.0 absorption (skill scanner v2 catches)
- **wrsmith108/docker-the coding agent-skill** turned a vague "use containers" guideline into a single enforceable rule: never run language tools on the host. Reduces the "works on my machine" failure mode to near-zero.
- **Alpine vs slim decision** is non-obvious and burns hours when wrong. Native modules (sqlite, sharp, bcrypt, node-canvas) need glibc → use slim. Pure JS/TS → alpine for size. Default to slim when unsure.
- **RchGrav/the coding agentbox** solves the multi-client parallel-work problem cleanly. Each client = own image + auth + firewall + venv. Three Cursor/the coding agent tabs running on Kellbell + CTT + Turnpike simultaneously without conflict.
- **15+ a per-project agent box profiles** mean the owner never has to remember stack setup. `the coding agentbox profile python ml database` and the container has Python + Jupyter + uv + DB clients. Saves hours per project bootstrap.
- **GameCI is the only sane way to do Unity CI.** Without it: license activation hell, manual editor installs in CI, 10x slower builds without Library/ cache. With it: declarative GitHub Action handles all three.
- **Library/ cache restore-key hierarchy** is the difference between 2-min and 20-min Unity builds. Key on hash of Assets/Packages/ProjectSettings, fall back to platform-specific, fall back to any.
- **iOS Unity builds need macos-latest runner.** Other platforms (WebGL, Android, Standalone Win/Linux/Mac) build on ubuntu-latest. Split into separate jobs to avoid wasting macOS minutes.
- **Anti-amnesia signal.** Banner added to SKILL.md description because the coding agent historically tells the owner to "just install Node on the Mac" instead of using docker exec. Reinforced in rules.md red flags.
- **Quarterly re-scan targets:** Anthropic-official a coding agent Docker images (when published), devcontainers/cli (alternate per-project pattern), AndreiMaksimovich/Unity-Build-and-Test-Automation (alternate Unity CI).

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-06-13 - v0.7.0 depth pass: GitOps + secrets + telemetry + scanning
- **Biggest gap caught:** GitOps was an entire competency reduced to one rules.md line ("ArgoCD/Flux for GitOps"). Now resolved to a real methodology file (`gitops-skill.md`): Application/ApplicationSet + Kustomization, sync policy (prune/selfHeal), Argo-vs-Flux selection rule.
- **Secrets-in-git was missing.** GitOps cannot use plaintext secrets in the pulled repo. SOPS (MPL-2.0, methodology-only) fills it: encrypt values, keep keys readable, decrypt key in KMS/age. Replaces the bare "Sealed Secrets / ESO" name-drop.
- **OTel Collector is the decoupling layer** the observability section was missing - instrument once, fan out to any backend; config change beats app redeploy. Always run memory_limiter+batch or it OOMs the node.
- **Trivy was name-dropped 5x but never operationalized** + carried a live 2026 supply-chain advisory (action compromised twice, March 2026, TeamPCP). Added SHA-pin discipline as a hard red flag and a real SARIF/gating config. tfsec is now folded into Trivy upstream.
- **Process right-sizing:** added a small-task/prototype lane. Every prior job implicitly assumed the full prod checklist; a POC carrying that is waste. Scale process to blast radius.
- **Hygiene:** docker-skill.md referenced two phantom files (ftp-legacy-playbook.md, deep-discovery-protocol.md) that never existed; fixed. SKILL.md References table listed only rules+learnings, omitting every *-skill.md file that plugin.json already registered; completed.
- *Proposed rule: when a competency is a single name-drop line, that is a depth gap, not coverage. Either operationalize it or cross-reference a methodology file.* Tags: [#cicd], [#k8s], [#secrets], [#observability]
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
## Sources

- Upstream: argoproj/argo-cd (license not stated: 22.9k); fluxcd/flux2 (license not stated: 8.2k); getsops/sops (license not stated: ~22k); open-telemetry/opentelemetry-collector (license not stated: 7.1k (core; contrib higher)); aquasecurity/trivy (license not stated: 36.4k)
- What was used: methodology only: argoproj/argo-cd, fluxcd/flux2, getsops/sops, aquasecurity/trivy; connected as external reference: argoproj/argo-cd; noted: open-telemetry/opentelemetry-collector
- License notes: licenses not recorded in scan for: argoproj/argo-cd, fluxcd/flux2, getsops/sops, open-telemetry/opentelemetry-collector, aquasecurity/trivy - verify before reuse; no code vendored
