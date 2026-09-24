# Kubernetes Specialist - Learnings (Pending)

## Memory scope keys (tag every observation)
Prefix each pending observation with a scope key so promotion stays searchable: `[workload]` `[security]` `[autoscaling]` `[gitops]` `[upgrade]` `[troubleshoot]` `[cost]` `[multitenancy]` `[platform]`. A learning with no scope key does not get promoted.

## Pending observations
- **2026-04-24 - Clean build**: Decision discipline around when NOT to use K8s is the highest-leverage rule. Codified explicit criteria (> 10 services OR multi-cloud portability OR advanced orchestration).
  *Proposed rule: K8s employee must gate-keep against over-adoption, not just enable.*
- **2026-04-24 - Clean build**: GitOps (Argo CD / Flux) is now the default rather than kubectl-in-CI. All 9 sources converge on this.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

- **2026-06-09 - Rebuild**: learnk8s/kubernetes-production-best-practices (1.1k stars, MIT, active) is the densest real-source K8s checklist found to date - future K8s content should diff against it before adding anything. Also: sickn33's k8s skills are wshobson mirrors except container-security-hardening; always diff before crediting aggregator repos.

- **2026-06-13 - Depth pass** `[platform][autoscaling][gitops][security]`: added platform-patterns.md from 5 Apache-2.0 Tier-1 sources (karpenter, kyverno/policies, argo-cd, kubescape, helm). Key insight: the existing rules.md asserted GitOps/Helm/Kyverno as DOCTRINE but never operationalized them (no repo structure, no chart CI, no curated policy set, no node-autoscaler-beyond-cluster-autoscaler). Doctrine without an operational layer reads complete but cannot be executed. Future depth passes should grep for asserted-but-unoperationalized doctrine, not just missing topics.
  *Proposed rule: every "X is the default" doctrine line must point to a how-to (its own section or platform-patterns.md), or it is a slogan.*
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
