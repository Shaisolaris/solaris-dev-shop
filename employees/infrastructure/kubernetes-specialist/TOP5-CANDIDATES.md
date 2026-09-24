# Kubernetes Specialist - TOP-5 Verified 2026 Sources

Researched 2026-06-13. Every figure verified live against GitHub (HTML repo + releases pages, not memory). Gate-0 grepped against the employee's actual SKILL.md + rules.md content, not just trigger keywords. Doctrine constraint: this employee DESIGNS and DIAGNOSES; live cluster mutation stays GitOps, so CONNECT-class tools observe/scan/scaffold, never hand-mutate prod.

Legend: ABSORB = pull methodology into rules/reference; CONNECT = wire as host-installed tool the specialist drives; METHODOLOGY = extract patterns, no code bundled.

| # | Source | URL | Stars | License | Last release / commit | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-----|-------|---------|-----------------------|------------|--------------|----------------|-----|
| 1 | kubernetes-sigs/karpenter | https://github.com/kubernetes-sigs/karpenter | 1.9k | Apache-2.0 (safe) | v1.13.0 on 2026-06-10 (3d) | k8s-sigs (CNCF upstream) | NodePool/NodeClass model, consolidation + disruption budgets, drift, spot+on-demand weighting, WhenEmptyOrUnderutilized, expireAfter node lifecycle; the modern reasoning that replaces cluster-autoscaler | Karpenter appears ONLY as a SKILL.md trigger word + one "autoscalers can fight" gotcha. No Karpenter methodology. Not a content-duplicate. | ABSORB (methodology) |
| 2 | kyverno/policies | https://github.com/kyverno/policies | 473 | Apache-2.0 (safe) | active, 1,596 commits; CEL/VAP + Velero/ESO/Karpenter/Kubecost sets | Kyverno (CNCF) | The named, tested policy library behind the "5 baseline policies": PSS baseline/restricted as code, require-image-digest, disallow-capabilities, *-cel CEL variants, mutate-drop-ALL, generate-default-PDB; the artifacthub-pkg + Audit-first contribution discipline | rules.md names 5 baseline policies conceptually + the admission ladder. The library, CEL variants, and test pattern are thin. Partial overlap, not a duplicate. | CONNECT + light methodology |
| 3 | argoproj/argo-cd | https://github.com/argoproj/argo-cd | 22.9k | Apache-2.0 (safe) | v3.4.2 on 2026-05-12; SLSA-3, OpenSSF | Argo (CNCF graduated) | GitOps repo structure (app-of-apps, ApplicationSet, sync-waves + resource hooks, sync windows, manual-sync guardrails for prod, drift detect / self-heal trade-offs); the operational layer under the existing "GitOps default" doctrine | rules.md asserts GitOps as doctrine but has no repo-structure / app-of-apps / sync-wave / ApplicationSet methodology. Net-new depth. | METHODOLOGY (deepen) |
| 4 | kubescape/kubescape | https://github.com/kubescape/kubescape | 11.3k | Apache-2.0 (safe) | v4.0.3 on 2026-03-17 (+ ongoing dependabot) | Kubescape (CNCF, ex-ARMO) | Cluster + manifest + image posture scanning against CIS / NSA-CISA / MITRE ATT&CK; SARIF/JUnit output for CI gating; the "scan continuously, not once" half of the supply-chain rule, at cluster-config level | CIS benchmark is a [va] mastery target only; Trivy/Grype named for images. No cluster-posture/CIS-scan tool wired. Complements, no duplicate. | CONNECT |
| 5 | helm/helm | https://github.com/helm/helm | 29.9k | Apache-2.0 (safe) | v4.2.1 on 2026-06-12 (Helm 4 GA) | Helm (CNCF graduated) | Chart authoring contract referenced everywhere but never operationalized: values.schema.json, helm lint / helm template in CI, chart-testing, helm diff upgrade gate, OCI chart registries, dependency pinning; canonical "one tool per stack" packaging methodology. Helm 4 is now GA - a version reality to track | SKILL.md/rules.md say "Helm or Kustomize, never both" and "helm diff before upgrade" but give no chart-authoring or chart-CI methodology. Net-new. | METHODOLOGY (deepen) |

## Flags
- No GPL / AGPL / NOASSERTION in the top 5. All five are Apache-2.0 (permissive, safe to absorb-as-methodology and to CONNECT).
- kyverno/policies and kubescape ship policy/scanner CONTENT under Apache-2.0; per fleet doctrine we still register them as METHODOLOGY + self-host note (host runs the tool / curates the policy set), never bundled copies.
- Service mesh (Linkerd/Istio) deliberately excluded: already gated correctly in rules.md, no single-repo methodology gap large enough to displace the five above.

## Sources
- https://github.com/kubernetes-sigs/karpenter
- https://github.com/kyverno/policies
- https://github.com/argoproj/argo-cd
- https://github.com/kubescape/kubescape
- https://github.com/helm/helm

## RESOLVED 2026-06-15 (do NOT re-recommend)
All 5 (kubernetes-sigs/karpenter, argoproj/argo-cd, helm/helm, kyverno/policies, kubescape/kubescape) were ABSORBED into platform-patterns.md at v0.6.0 (Wave 2, 2026-06-13). This dossier is a historical candidate list, NOT an open queue. Gate-0 against platform-patterns.md before any re-recommendation. Status: CLOSED.
