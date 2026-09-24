# Kubernetes Specialist - Platform Patterns (deep methodology)

Created 2026-06-13. Methodology distilled from five Tier-1 Apache-2.0 sources (see plugin.json absorbed_from). NO code is bundled here; these are patterns the specialist applies and tools the host installs. Citations: [kp] = kubernetes-sigs/karpenter, [kyv] = kyverno/policies, [acd] = argoproj/argo-cd, [ksc] = kubescape/kubescape, [hlm] = helm/helm. Load alongside rules.md when a request touches GitOps repo design, node autoscaling beyond cluster-autoscaler, policy-as-code at scale, chart authoring, or compliance posture scanning.

## GitOps repository structure [acd]
Doctrine in rules.md says "GitOps default"; this is the operational layer beneath it.
- **App-of-apps**: one root Application points at a directory of child Application manifests; bootstrapping a cluster = apply one root. Children are owned per team/per stack. Keeps cluster onboarding to a single declarative entry point.
- **ApplicationSet** over hand-written Applications when the same app deploys across many clusters/namespaces/regions: generators (list, cluster, git-directory, matrix) template the Applications. One change propagates fleet-wide; this is how you avoid 30 near-identical Application YAMLs drifting.
- **Sync waves + resource hooks**: annotate `argocd.argoproj.io/sync-wave` to order apply (CRDs and namespaces in early waves, workloads later); PreSync/PostSync/SyncFail hooks run migrations and smoke checks inside the sync, not around it. Without waves, a workload can apply before its CRD exists and fail the whole sync.
- **Sync policy by environment**: dev/staging may auto-sync + self-heal + prune; prod uses manual sync with approval (matches rules.md "Argo CD auto-sync in prod is dangerous"). Self-heal reverts manual hotfixes - that is the point, but say so to the client before enabling it.
- **Sync windows** to block prod syncs during business hours / freeze periods. **Drift detection** is the daily value even when sync is manual: OutOfSync status is the alert.
- Keep staging and prod manifests structurally identical (same overlay shape, env-specific values only) or staging is not testing prod. Repo separation: app source code repo != deployment-config repo.
- Self-host note: Argo CD is Apache-2.0; host installs and runs it. The specialist designs the repo layout and Application/ApplicationSet shapes; the host's GitOps controller does the syncing.

## Node autoscaling with Karpenter [kp]
Supersedes cluster-autoscaler reasoning for AWS/Azure and multi-cloud where a provider implementation exists; cluster-autoscaler still valid for node-group-pinned setups.
- **Model**: NodePool (scheduling constraints, limits, disruption policy) + a provider NodeClass (AMI/image, subnets, security groups). Karpenter watches unschedulable pods and provisions right-sized nodes directly, no pre-defined node groups.
- **Consolidation** is the cost lever: `disruption.consolidationPolicy: WhenEmptyOrUnderutilized` repacks pods onto fewer/cheaper nodes. Pair with `consolidateAfter` to avoid thrash.
- **Disruption budgets**: cap how many nodes Karpenter may disrupt at once (by percent or count, optionally by reason and schedule) - the node-level analogue of a PDB, and it works WITH PDBs (PDBs still gate the pod evictions during a node disruption).
- **Spot + on-demand**: allow both instance types in requirements and let Karpenter weight; spot for interruptible/batch, on-demand fallback. Set `expireAfter` to force node rotation (security patching) and `terminationGracePeriod` to bound drains.
- **Drift**: when a NodePool/NodeClass changes (new AMI), Karpenter marks existing nodes drifted and rolls them - this is how node config stays declarative. Respects disruption budgets + PDBs during the roll.
- Pre-conditions mirror HPA: workloads must tolerate node churn (graceful shutdown, PDBs, topology spread). Karpenter moving a pod is the same contract as "Kubernetes can move any pod at any time" (rules.md core principle).
- Single owner per scaling axis still holds (rules.md gotcha): Karpenter owns nodes, HPA/KEDA own replicas. Do not also run cluster-autoscaler on the same nodes.
- Self-host note: upstream karpenter is Apache-2.0; the host installs the provider implementation (aws/karpenter-provider-aws, Azure, etc.). The specialist authors NodePool/NodeClass/disruption budgets as manifests in Git.

## Policy-as-code at scale with Kyverno [kyv]
Operationalizes the "5 baseline policies" + admission ladder in rules.md.
- **Baseline set as code** (curate from the library, do not invent): require-non-root, require-image-digest (digest-not-tag), disallow-privileged / disallow-capabilities, require-resource-requests-limits, mutate-add-drop-ALL-capabilities, plus generate-default-PDB and add-safe-to-evict for cluster operability.
- **CEL variants** (`*-cel` in the library): prefer the CEL/ValidatingAdmissionPolicy form for object-local rules - lower runtime overhead, no extra webhook hop, and it survives if Kyverno is down. Use full Kyverno (YAML) only where you need mutate/generate/verifyImages.
- **Rollout discipline**: ship every validate policy as `Audit` first (the library's own contribution rule), watch PolicyReports, then flip to `Enforce`. Same warn-then-enforce ladder as PSA. Never land a new Enforce policy straight to prod.
- **verifyImages** for supply chain: Kyverno can require cosign signatures + attestations at admission - the admission-time complement to registry scanning.
- Ecosystem policy sets exist for Velero (backup-all-volumes), External Secrets, Karpenter, Kubecost labels, Istio/Linkerd, cert-manager - reach for the curated set before writing your own.
- Self-host note: kyverno/policies is Apache-2.0; the host installs Kyverno and applies a curated subset via GitOps. The specialist selects/tunes policies and owns the Audit-to-Enforce promotion, not a vendored copy of the whole library.

## Helm chart authoring + chart CI [hlm]
Operationalizes "Helm or Kustomize, never both" and "helm diff before upgrade" from rules.md. Note: Helm 4 is GA as of 2026 - check chart apiVersion and provider-tooling compatibility before assuming v3.
- **Schema-validate values**: ship `values.schema.json` so bad values fail at lint/template time, not at apply time. This is the cheapest guardrail for client-handed charts.
- **CI gate per chart**: `helm lint` -> `helm template | kubeconform` (or the cluster's policy engine in dry-run) -> chart-testing (`ct lint`/`ct install` on an ephemeral kind cluster) on every PR. A chart that never rendered against a real API server is untested.
- **Upgrade safety**: `helm diff upgrade` before every prod upgrade (already in rules.md) - wire it as a required step, not a habit. Pin chart + subchart dependency versions in Chart.lock; never float `*`.
- **OCI registries**: charts as OCI artifacts in the same registry as images - one supply chain, one set of credentials, signable with cosign.
- One packaging tool per stack remains the rule; Helm for templated/parameterized apps, Kustomize for overlay-only. Document which and why so inheritors do not mix them.
- Self-host note: Helm is Apache-2.0; the host runs helm/CI. The specialist authors the chart contract (templates, schema, CI steps).

## Compliance posture scanning with Kubescape [ksc]
Adds the cluster-config half of "scan continuously, not once" (rules.md supply chain covers image scanning only).
- **Frameworks**: scan live cluster + manifests against CIS Kubernetes Benchmark, NSA-CISA hardening guidance, and MITRE ATT&CK; produces a posture score per framework. This operationalizes the [va] "CIS benchmark" mastery target.
- **Where it runs**: in CI on manifests/Helm output (fail the build on regressions, SARIF output into the security tab), AND continuously against the running cluster (config drift = new findings, same logic as continuous image scanning).
- **Air-gapped mode** exists for regulated/offline clusters; Prometheus `/v1/metrics` endpoint exposes posture as a time series for dashboards.
- Boundary: Kubescape OBSERVES and SCORES. Findings become manifest changes in Git (admission policy, securityContext, RBAC tightening), synced by Argo CD/Flux - it never mutates the cluster directly. Same doctrine as the EKS/GKE MCP servers in rules.md.
- Self-host note: kubescape is Apache-2.0; host installs the CLI/operator. The specialist reads the report and drives remediation through GitOps.

## CI hardening (fleet doctrine)
- Pin GitHub Actions to a full commit SHA, not a tag (`uses: actions/checkout@<40-char-sha>`); tags are mutable. Renovate/Dependabot can bump the SHA with a readable comment. Applies to every CI workflow this specialist scaffolds (chart CI, scan gates, GitOps bootstrap).
- Image digest pinning in prod (rules.md) and Action SHA pinning are the same principle at two layers of the supply chain.
