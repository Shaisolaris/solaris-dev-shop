# DevOps Engineer - Top-5 Verified 2026 Sources (depth pass 2026-06-13)

Scope: strengthen GitOps/ArgoCD/Flux, observability, secrets, IaC/container scanning.
All facts verified via GitHub repo fetch + web search on 2026-06-13. "Gate-0" = grep of this
employee's ACTUAL content (SKILL.md / rules.md / learnings.md / *-skill.md / plugin.json).

| # | Source | URL | Stars | License | Last release/commit | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-----|-------|---------|---------------------|------------|--------------|----------------|-----|
| 1 | argoproj/argo-cd | https://github.com/argoproj/argo-cd | 22.9k | Apache-2.0 | v3.4.2, 2026-05-12 (active, 10.6k commits) | Argo Project (CNCF graduated) | Declarative GitOps CD for k8s: Application/ApplicationSet CRDs, sync waves, auto-sync + self-heal + prune, app-of-apps, drift detection, RBAC, SSO. Turns the "ArgoCD/Flux for GitOps" name-drop into an actual deploy methodology. | Only name-dropped once (rules.md "ArgoCD/Flux for GitOps") + unrelated Flux159 K8s-MCP CONNECT. No methodology/CRD/sync patterns. NET-NEW. | METHODOLOGY |
| 2 | fluxcd/flux2 | https://github.com/fluxcd/flux2 | 8.2k | Apache-2.0 | v2.8.8, 2026-05-20 (active) | Flux project (CNCF graduated) | GitOps Toolkit: source-controller + kustomize-controller + helm-controller + image-automation; pull-based reconciliation, OCI artifacts, Flux-vs-Argo selection rule. Companion to #1 for the "no UI, fully GitOps-native" case. | Same as #1 - name-only. No reconciliation/controller methodology. NET-NEW. | METHODOLOGY |
| 3 | getsops/sops | https://github.com/getsops/sops | ~22k | MPL-2.0 (FLAG: weak-copyleft, file-level - fine to reference as methodology; do NOT vendor source) | 2,575 commits, active 2026; CNCF Sandbox | Encrypt secrets IN git (YAML/JSON/ENV/INI) with KMS/age/PGP, key visible / value encrypted, diff-friendly. The missing piece for GitOps secrets (you cannot put plaintext secrets in a git-driven deploy). Pairs with SOPS-aware ArgoCD/Flux. | Not present. Only "Sealed Secrets / External Secrets Operator" name-dropped (SKILL.md). NET-NEW. | METHODOLOGY (+ self-host note: MPL-2.0, reference the tool, no code bundled) |
| 4 | open-telemetry/opentelemetry-collector | https://github.com/open-telemetry/opentelemetry-collector | 7.1k (core; contrib higher) | Apache-2.0 | releases through 2026-06-09 (active) | OpenTelemetry / CNCF | Vendor-neutral telemetry pipeline: receivers -> processors -> exporters; one agent for metrics+logs+traces; decouples app instrumentation from backend (Datadog/Prometheus/Tempo/Loki) so backend swaps need zero app changes. Operationalizes the "OpenTelemetry" trace name-drop. | Only "OpenTelemetry" listed under Traces (SKILL.md/rules.md). No Collector config / pipeline. NET-NEW for Collector. | METHODOLOGY |
| 5 | aquasecurity/trivy | https://github.com/aquasecurity/trivy | 36.4k | Apache-2.0 | v0.71.0, 2026-06-01 (active) | Aqua Security | All-in-one scanner: container images + filesystem + IaC misconfig (tfsec now folded into Trivy) + secrets + SBOM; SARIF -> GitHub code scanning. SECURITY: official Trivy GitHub Action was supply-chain compromised twice in March 2026 - pin to commit SHA, never @master/@v1. | Name-dropped 5x in tool lists + CI stub `steps: [checkout, snyk, trivy, gitleaks]`. No config/SARIF/gating discipline + no SHA-pinning warning. Tool present (content-partial); methodology NET-NEW. | CONNECT / METHODOLOGY |

## Notes
- #1 + #2 chosen together: GitOps is the single biggest gap (entire competency reduced to one
 rules line). ArgoCD = primary (UI + ApplicationSet), Flux = the pull-native alternative. Both
 Apache-2.0, both CNCF-graduated, both released within ~1 month of this pass.
- #3 SOPS is MPL-2.0 (flagged): referenced as METHODOLOGY only - discipline + workflow lifted,
 no source vendored. Correct treatment per the flagged/self-host rule.
- #5 Trivy carries a live 2026 supply-chain advisory; the action MUST be SHA-pinned. This was
 absent from the employee's CI stub - fixed in this pass.
- All five are permissive or weak-copyleft; none are GPL/AGPL/NOASSERTION.
