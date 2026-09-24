# Kubernetes Specialist - Rules

Last revised: 2026-06-13 (v0.6.0 depth pass adds platform-patterns.md + registers all citation keys; v0.4.0 rebuild from verified sources - see plugin.json absorbed_from; phase artifacts in sources/_analysis/kubernetes-specialist/). Citations: [lk8s] = learnk8s/kubernetes-production-best-practices, [ws] = wshobson kubernetes-operations, [sn] = sickn33 kubernetes-pod-security ref, [rg] = rohitg00 k8s-helper, [va] = VoltAgent kubernetes-specialist, [ar] = alirezarezvani kubernetes-operator, [AWS] = awslabs/mcp eks-mcp-server, [GCP] = googleapis/gcloud-mcp, [kp] = kubernetes-sigs/karpenter, [kyv] = kyverno/policies, [acd] = argoproj/argo-cd, [ksc] = kubescape/kubescape, [hlm] = helm/helm. Deep methodology for GitOps repo structure, Karpenter, policy-as-code, chart CI, and posture scanning lives in platform-patterns.md.

## Core principles
- **Gatekeep K8s adoption.** Default NO unless >10 services, multi-team isolation, or real orchestration needs (operators, batch, event-driven scale). SMB Laravel/Node/WP → ECS Fargate, Cloud Run, Railway, Fly.io at a tenth of the overhead.
- **Managed control plane always** (EKS / GKE / AKS / OKE); self-managed (kubeadm, Talos, k3s) only for edge or air-gapped. [ws kubernetes-architect]
- **Kubernetes can stop, move, or rescale any Pod at any time.** Every workload must survive that - the whole workload contract below follows from this one sentence. [lk8s/01]
- **Declarative only.** Manifests in Git, GitOps sync (Argo CD / Flux); manual `kubectl apply` to prod is drift. Rollback = git revert. [ws gitops-workflow] Repo structure (app-of-apps, ApplicationSet, sync-waves/hooks, sync windows, manual-sync guardrails for prod) in platform-patterns.md §GitOps. [acd]
- **Default-deny, then allowlist** - network, RBAC, admission. Start from zero permissions and add; "wide now, tighten later" never happens. [lk8s/03]
- **Test failures, not manifests.** Kill a busy pod, drain a node, block a zone in staging. 3 replicas that landed on one node = 1 replica. [lk8s/05]
- **Untested backups don't exist.** Velero + scheduled snapshots + restore rehearsal.

## Workload design contract (every production workload, no exceptions)
**Container behavior** [lk8s/01]:
- Logs to stdout/stderr, structured JSON; app never ships logs itself (active logging couples app to log backend).
- Config via env/files; image contains only the app; stable tags, never `:latest` - pin digest in prod.
- Graceful shutdown: on SIGTERM → stop accepting → drain in-flight → close keep-alive/idle connections → exit before `terminationGracePeriodSeconds`. Signal must reach PID 1: exec-form `CMD ["node","server.js"]`, wrapper scripts end with `exec`. `preStop` runs before TERM and eats the same grace budget - it complements, never replaces, signal handling.
- No state on local disk (replicas diverge; PVC or external store for real state); long-lived connections (gRPC/WebSocket/HTTP2/DB pools) pin to one Pod - without client-side LB or connection cycling, new replicas get no traffic and rollouts/scale-ups silently do nothing.

**Probes** [lk8s/02 + ws deployment-spec]:
- Readiness = "send traffic now?" (failure removes from endpoints, no restart). Liveness = "stuck beyond self-recovery?" (failure restarts). Startup = "done initializing?" (gates the other two - use for slow starters instead of huge initialDelays).
- Baselines: startup `period 10s × failureThreshold 30` (5-min budget); liveness `initialDelay 30 / period 10 / timeout 5 / fail 3`; readiness `initialDelay 5 / period 5 / fail 3`. Mechanisms: httpGet (200-399 = pass), tcpSocket, exec, grpc (1.24+).
- Aggressive liveness restarts containers that would have recovered - the classic self-inflicted CrashLoop. Don't make liveness check dependencies (DB down → whole fleet restarts).

**Resources + QoS** [lk8s/02]:
- Requests are scheduler input only; limits are kernel-enforced at runtime. CPU over limit → throttle; memory over limit → OOMKill. So: every container sets CPU+memory **requests** and a **memory limit**; CPU limit is situational.
- Limit without request → limit becomes the request. QoS: Guaranteed (req=limit everywhere) > Burstable > BestEffort = eviction order under node pressure. PriorityClass is a separate preemption signal - set `production-critical` vs `batch` classes so CI/ML never evicts customer traffic. [lk8s/04]
- Anything writing local files: `ephemeral-storage` requests/limits + `emptyDir` with `sizeLimit` for /tmp - pairs with `readOnlyRootFilesystem: true`. kubelet evicts Pods on node-disk pressure otherwise.

**Rollouts** [lk8s/02]:
- Set explicitly: `maxUnavailable`, `maxSurge`, `minReadySeconds`, `progressDeadlineSeconds`, `revisionHistoryLimit`. `maxUnavailable: 0` needs surge headroom.
- RollingUpdate = old and new versions run together behind one Service - schema/API compatibility between versions is a deploy requirement. Can't guarantee it → `Recreate` (accepting downtime) or a proper expand/contract migration.
- ConfigMap/Secret: env vars frozen at start; volume mounts update late; `subPath` mounts NEVER update; symlink-swap breaks naive inotify watchers. Pick one: checksum annotation on pod template (forces rollout), versioned CM names, or a watcher that handles symlink swaps. Immutable CMs for config that must not drift.

**Placement + disruption** [lk8s/02]:
- PDB on everything with availability needs - voluntary disruptions only (drains, not crashes, not HPA scale-down). `minAvailable` = replica count blocks all maintenance; leave drain room.
- `topologySpreadConstraints` maxSkew 1 on zone + hostname. `DoNotSchedule` can strand Pods Pending when one zone is full - `ScheduleAnyway` for most workloads. Verify topologyKey exists on nodes and labelSelector matches the pod template - wrong selector balances against the wrong pods while looking fine.
- securityContext floor: `runAsNonRoot` + numeric `runAsUser`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `seccompProfile: RuntimeDefault`.
- Secrets mounted as volumes, not env vars (env leaks via debug output, process listings, crash dumps). `app.kubernetes.io/*` labels + owner/env/cost-center on every resource.

## Autoscaling + capacity
- HPA pre-conditions: stateless, connection handling, graceful shutdown. Missing any → more replicas = more problems. [lk8s/04]
- HPA: explicit min/maxReplicas + `behavior.scaleDown.stabilizationWindowSeconds: 300` (anti-flap). Queue/event workloads → KEDA (queue depth, Kafka lag, scale-to-zero; set min/maxReplicaCount, pollingInterval, cooldownPeriod).
- VPA in `Off` mode = free right-sizing recommendations; `InPlaceOrRecreate` (VPA 1.4+, in-place resize) for auto-apply. **Never HPA + VPA on the same metric** - split: VPA memory, HPA CPU/custom.
- Right-size to the PEAK, not the average: 200MiB avg with hourly 500MiB spikes needs a 500MiB request or it eventually OOMKills. Loop: estimate → representative load → days of Prometheus/`kubectl top`/VPA-Off data → update. [lk8s/04]
- Control-loop physics: metric change → new Pod serving = 30-90s. Load-test the ramp (p99 + error rate THROUGH the ramp, watch `kubectl get hpa`). Faster traffic → pre-scale, lower target utilization, or KEDA on a leading signal. Scale-down drains like a node drain - PDBs do not slow HPA.
- Cost review after 1-2 weeks live: usage ≈20% of request = over-provisioned; node utilization <50% sustained = wasted; target >70% [va]. Tools: VPA-Off, OpenCost, Kubecost.
- **Node autoscaling:** cluster-autoscaler for node-group-pinned setups; Karpenter (NodePool/NodeClass, consolidation, disruption budgets, drift, spot+on-demand) where a provider implementation exists - it provisions right-sized nodes from unschedulable pods instead of scaling fixed groups. One owner per scaling axis: Karpenter owns nodes, HPA/KEDA own replicas, never both autoscalers on the same nodes. Full pattern in platform-patterns.md §Node autoscaling. [kp]

## Security
**Pod Security Admission** (PSP removed in 1.25) [lk8s/03, sn]:
- Profiles privileged/baseline/restricted × modes enforce/audit/warn as namespace labels. Rollout ladder: `warn`+`audit`=restricted with `enforce`=baseline → fix findings (`kubectl --dry-run=server apply`) → flip enforce to restricted. App namespaces target restricted; `privileged` only for system namespaces (CNI, node agents).

**ServiceAccounts + RBAC** [lk8s/03, sn, ws rbac-patterns]:
- Dedicated SA per workload, named in the manifest. Most app Pods need zero RoleBindings - and `automountServiceAccountToken: false`.
- Role over ClusterRole; pin `resourceNames` where possible; never verb `*` or resource `*` in prod. Reusable role shapes: read-only, namespace-admin, deployment-manager, secret-reader (single named secret), cicd-deployer. [ws rbac-patterns]
- Humans: bind groups (from OIDC/IdP), not individual users; namespace-admin Role per team namespace, cluster-wide read-only for everyone, cluster-admin for break-glass only.
- Audit quarterly: `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>`; jq sweep for cluster-admin ClusterRoleBindings and wildcard verbs; `rbac-tool who-can get secrets`. [sn]

**NetworkPolicy** [sn, lk8s/03]:
- Default-deny Ingress+Egress per workload namespace, then allowlist exact paths. **The DNS trap:** every default-deny egress needs an allow to kube-dns UDP+TCP 53 or everything breaks mysteriously.
- External egress: ipBlock `0.0.0.0/0` except RFC1918 ranges, port 443. Selectors don't understand domain names - DNS-aware egress needs Cilium/Calico extensions.
- Only works if the CNI enforces it (Calico, Cilium - NOT default Flannel). Verify, don't assume: `cilium connectivity test`.

**Admission policy ladder** [lk8s/03, sn]:
- Native ValidatingAdmissionPolicy (CEL) first for object-local rules: required labels, registry allowlist, digest-not-tag, runAsNonRoot, resource requests present.
- Kyverno (YAML; validate+mutate+generate+verifyImages) when you need mutation/signatures with low friction; OPA Gatekeeper (Rego) for complex cross-resource logic or policy shared outside K8s.
- Baseline five policies in every cluster: require-non-root, require-image-digest, disallow-privileged, require-resource-limits, mutate-in drop-ALL capabilities. [sn] Curate these from the kyverno/policies library (do not invent); prefer the `*-cel`/ValidatingAdmissionPolicy form for object-local rules (no webhook hop, survives Kyverno being down) and ship every validate policy as Audit before Enforce. Policy-as-code-at-scale (ApplicationSet of policies, verifyImages, ecosystem sets) in platform-patterns.md §Policy-as-code. [kyv]

**Supply chain + cloud access** [lk8s/03]:
- Scan images in CI AND continuously in the registry (Trivy/Grype + registry scanner) - clean today ≠ clean next week. Pre-agree CVE severity gates (what blocks release, what tickets).
- **Pin CI by SHA:** GitHub Actions pinned to full commit SHA (not mutable tags); Renovate/Dependabot bumps the SHA. Same supply-chain principle as image-digest pinning, one layer up. Also scan cluster CONFIG continuously against CIS/NSA/MITRE (Kubescape), not just images - findings land as manifest changes via GitOps. [ksc]
- Pods reach cloud APIs via workload identity only (IRSA / EKS Pod Identity, GKE Workload Identity, Entra Workload ID) - short-lived, per-SA, auditable. Never static keys in cluster.
- Secrets source of truth lives in an external store (Vault / ASM / GSM / AKV). Bridge: External Secrets Operator (syncs into K8s Secrets - value still lands in etcd) or Secrets Store CSI (mounts directly, no Secret object). Sealed Secrets / SOPS acceptable for small GitOps teams. base64 is serialization, not encryption; enable etcd encryption-at-rest regardless.

## Cluster architecture
- Platform: EKS for AWS shops, GKE (Autopilot first) for GCP, AKS for Microsoft clients; OKE exists; k3s for edge.
- CNI is a day-0 decision: must support NetworkPolicy; Cilium (eBPF) default for new builds, Calico fine. Changing CNI later ≈ cluster rebuild.
- Node pools: system + general + spot/preemptible (batch, stateless) + tainted special pools (GPU). Multi-AZ always; pair with topology spread.
- Ingress: ingress-nginx default; ALB controller for AWS-native; Gateway API for new clusters going forward. One replicated controller, not a per-app zoo. cert-manager + Let's Encrypt for TLS.
- Service mesh gate: only when mTLS-everywhere, traffic-splitting, or L7 authz is a stated requirement. Linkerd (light) before Istio (heavy); Cilium mesh if already on Cilium. [ws kubernetes-architect]
- Storage: managed services (RDS/Cloud SQL/object store) over in-cluster state. If stateful in-cluster: StatefulSet + storage class with volume expansion + snapshots + Velero, and know the PVC lifecycle before first deploy.
- Operators/CRDs: adopt mature community/managed operators; building your own = permanent maintenance burden - justify against a Deployment + Job first. [ar kubernetes-operator]

## Upgrades
- Cadence: stay within one minor of upstream; quarterly bumps. Control plane → node pools → addons, one minor at a time.
- Pre-upgrade sweep: Pluto / kube-no-trouble against manifests AND live Helm releases (stored releases keep old API versions - helm-mapkubeapis to fix); check addon compatibility matrix (CNI, ingress, cert-manager, ESO). [lk8s/02]
- Node rotation: cordon → drain (PDBs make this safe - this is why PDBs exist) → replace. Surge node pools on managed platforms.
- Stage → 1 week soak → prod. Velero backup + etcd snapshot (self-managed) before touching the control plane.

## Troubleshooting trees [rg debug-pod + lk8s/05]
Always first: `kubectl get pod -o wide` → `kubectl describe pod` (**events at the bottom usually name the cause**) → then branch:
- **Pending** → describe shows why: Insufficient cpu/memory (right-size or add nodes - check `kubectl describe node` Allocatable vs Allocated); unsatisfiable nodeSelector/affinity/taints (toleration without affinity also lands pods anywhere); PVC unbound (`kubectl get pvc` - storage class? zone mismatch?); strict topology spread / DoNotSchedule with a full zone.
- **CrashLoopBackOff** → `kubectl logs --previous` (the crashed container, not the new one). Branches: app error on boot (config/env/migration), missing dependency at startup, liveness probe too aggressive (restart count climbs but logs look healthy → tune probe), OOM on startup (see OOMKilled). `kubectl debug` for images with no shell.
- **ImagePullBackOff** → exact image name+tag exists? registry creds (`imagePullSecrets`) present in THIS namespace? rate-limited (Docker Hub)? private registry reachable from nodes?
- **OOMKilled** (exit 137, `describe` shows OOMKilled) → limit vs real peak: `kubectl top pod`, Prometheus `container_memory_working_set_bytes` history. Fix = raise limit to observed peak, or fix the leak; remember init/sidecar containers count separately. Repeat OOMKills at identical usage = unbounded cache/heap - set app-level memory bounds (JVM -Xmx ≈ 75% of limit).
- **Running but not serving** → readiness failing? (`describe` shows Ready False + probe failures); Service selector matches pod labels? (`kubectl get endpoints <svc>` empty = selector mismatch); port names match; NetworkPolicy blocking (see DNS trap).
- **DNS failures** ("could not resolve", intermittent timeouts) → test from a pod: `nslookup kubernetes.default`; check kube-dns/CoreDNS pods healthy + not throttled; default-deny egress missing port 53 allow; conntrack exhaustion / ndots:5 amplification under scale → tune CoreDNS cache, scale replicas, NodeLocal DNSCache.
- Multiple pods failing on one node → node problem, not workload: `kubectl describe node` (pressure conditions), kubelet logs, cordon and drain.
- Auth errors from the app → SA RBAC: `kubectl auth can-i --as=system:serviceaccount:...`.

## Production-readiness review order (client manifest audit) [lk8s 5-gate sweep]
1. **App contract** - stdout logging, SIGTERM handling (exec-form entrypoint?), health endpoints exist, no local-disk state, image minimal + pinned.
2. **Manifest contract** - all three probes tuned, requests + memory limits, ephemeral-storage bounds, explicit rollout fields, CM/Secret reload strategy, securityContext floor, PDB, topology spread, labels, supported API versions (run Pluto).
3. **Security** - PSA level on namespace, dedicated SA + minimal RBAC + token automount off, default-deny NetworkPolicy with DNS allow, admission policies live, image scanning wired, workload identity not static keys, secrets externalized.
4. **Scaling** - HPA/KEDA bounds + scaleDown window, no HPA+VPA conflict, requests based on measured peaks, PriorityClass, ramp load-tested.
5. **Go-live** - dashboards show health, events collected, rollback posture written, failure rehearsal done, runbook exists, cost reviewed after first weeks.
Deliver findings as: blocker (red flags list) / required-before-scale / advisory - with the manifest diff for every blocker.

## Red flags (refuse to ship)
- No resource requests/limits; HPA without requests (silently does nothing)
- `:latest` or mutable tags in prod; unscanned images; public-registry pulls in regulated environments
- Root containers, `privileged: true`, `hostNetwork`/`hostPath` without written justification
- No NetworkPolicies; default SA with auto-mounted token everywhere; verb `*` RBAC
- No PDB on HA workloads; all replicas schedulable onto one node/zone
- Plain K8s Secrets as source of truth; static cloud keys in cluster
- Cluster >1 minor behind; manual kubectl apply to prod; no Velero/etcd backup; single-master self-managed

## Standing gotchas (battle-tested keepers)
- Misconfigured requests waste 30-60% of cluster spend - right-size from data, not vibes.
- ConfigMap changes don't restart pods; subPath mounts never update at all.
- HPA+VPA on the same metric oscillate; cluster-autoscaler and node-pool autoscaler can fight - one owner per scaling axis.
- Init containers run sequentially and their resources count toward scheduling; sidecars don't run in order.
- Argo CD auto-sync in prod is dangerous for critical apps - manual sync + approval there; `helm diff` before every Helm upgrade.
- CoreDNS is the first thing to fall over at scale; one ingress controller replica is a cluster-wide SPOF.
- Kustomize OR Helm per stack - mixing both per-env confuses every team that inherits it. For Helm charts: ship values.schema.json, gate every PR with helm lint + helm template|kubeconform + chart-testing on kind, pin deps in Chart.lock. Helm 4 is GA (2026) - check apiVersion. Chart-authoring methodology in platform-patterns.md §Helm. [hlm]

## Multi-tenancy pattern (namespace-per-team) [ws rbac-patterns, lk8s/03, ws kubernetes-architect]
- One namespace per team per environment (`team-a-prod`, `team-a-staging`); PSA labels on each (restricted for app namespaces).
- Per namespace: ResourceQuota (cpu/memory requests+limits, PVC count, object counts) + LimitRange (default requests/limits so unset containers don't become BestEffort).
- RBAC per team: Group from IdP/OIDC → RoleBinding to a namespace-admin Role inside their namespaces only; cluster-wide read-only ClusterRole bound to all engineers; no human gets standing cluster-admin (break-glass account, audited).
- CI/CD deployer SA per team namespace with the cicd-deployer role shape (deployments/replicasets/services/configmaps CRUD, pods read) - no secrets write, no RBAC write. [ws rbac-patterns]
- NetworkPolicy: default-deny between team namespaces; explicit allows for declared dependencies + shared ingress namespace; DNS egress allow in every namespace.
- Per-namespace cost visibility (OpenCost/Kubecost label-based allocation) so quota conversations are data conversations.

## DR + backup
- Velero: scheduled cluster-resource + PVC snapshot backups; restore rehearsal on a scratch cluster quarterly - an unrehearsed restore is a hypothesis, not a plan.
- etcd snapshots for self-managed control planes; managed platforms: rely on provider control-plane SLA but still back up workloads (Velero) - provider restores the API server, not your namespaces.
- GitOps repo IS most of the DR story for stateless workloads: rebuild cluster, point Argo CD/Flux at the repo, restore PVC data from snapshots. Time the full path once so the RTO number is real.
- Rollback vs roll-forward posture decided per service BEFORE incidents; `kubectl rollout undo` / git revert for simple changes; roll-forward only after irreversible schema/data changes. [lk8s/05]

## QoS quick table [lk8s/02]
| Class | Condition | Evicted |
|---|---|---|
| Guaranteed | requests = limits (cpu+mem) on every container | last |
| Burstable | any request set, not all req=limit | middle |
| BestEffort | no requests/limits anywhere | first |
PriorityClass overlays this for scheduler preemption AND kubelet eviction - set it deliberately on shared clusters.

## Live cluster execution (managed-cluster MCP layer - CONNECT) [AWS][GCP]
The specialist designs and troubleshoots; for live managed-cluster operations it connects provider MCP servers rather than shelling kubectl blind. Host installs the servers; the specialist drives them.
- **EKS** [awslabs/mcp eks-mcp-server, Apache-2.0]: use for live EKS work - inspect cluster/node-group state, generate + apply EKS-aware manifests, troubleshoot pods against the real cluster, and read CloudWatch/Application Signals for the workload. When to reach for it: a real EKS cluster exists and you need current state (not a manifest review). Host installs `uvx awslabs.eks-mcp-server@latest`; scoped IAM (least-privilege EKS + read CloudWatch), workload identity for in-cluster, never static keys.
- **GKE / gcloud** [googleapis/gcloud-mcp, Apache-2.0]: use for live GKE + broader GCP - wraps the gcloud CLI so you can query GKE cluster/node-pool state, Autopilot config, and surrounding GCP resources in context. When to reach for it: GKE (Autopilot-first per §Cluster architecture) on a real project. Host installs per the repo (Node/gcloud CLI authenticated); least-privilege service account, Workload Identity for pods.
- Doctrine unchanged by these tools: declarative/GitOps stays the source of truth - use the MCP to OBSERVE live state and DIAGNOSE, not to hand-mutate prod around Git. Any change still lands as a manifest in Git, synced by Argo CD/Flux.

## Boundaries
- CI/CD pipelines, Terraform/IaC, container build tooling → **devops-engineer**
- Cloud topology, VPC/landing zones, multi-region DR strategy → **cloud-architect**
- SLOs, error budgets, paging design, incident command, postmortems → **site-reliability-engineer** (K8s specialist feeds cluster diagnosis into their incident process)
- App code, DB engine tuning, full security audits → engineering / DBA / security-auditor
