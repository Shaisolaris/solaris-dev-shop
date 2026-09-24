# GitOps + Secrets + Telemetry Methodology (depth reference)

> Load this file when ANY work touches GitOps (ArgoCD / Flux), secrets-in-git (SOPS),
> the OpenTelemetry Collector, or Trivy security gating. Methodology absorbed 2026-06-13.
> No upstream source is vendored here. This is the discipline lifted from the canonical
> projects, with self-host notes where a license warrants it.

**Source canon (all verified 2026-06-13):**
- argoproj/argo-cd: 22.9k stars, Apache-2.0, v3.4.2 (2026-05-12), CNCF graduated.
- fluxcd/flux2: 8.2k stars, Apache-2.0, v2.8.8 (2026-05-20), CNCF graduated.
- getsops/sops: ~22k stars, MPL-2.0 (weak-copyleft; methodology referenced, no code vendored), CNCF Sandbox.
- open-telemetry/opentelemetry-collector: 7.1k stars, Apache-2.0, active to 2026-06.
- aquasecurity/trivy: 36.4k stars, Apache-2.0, v0.71.0 (2026-06-01).

---

## 1. GitOps: the model

GitOps means git is the single source of truth for desired cluster state, and an in-cluster agent
continuously reconciles actual state toward git. CI builds + pushes images and bumps a tag in
git; CD (Argo/Flux) pulls and applies. CI never holds prod cluster credentials. The agent runs
inside the cluster and pulls. That is the structural win over push-based CI deploy.

| Aspect | Push CD (CI runs kubectl apply) | Pull CD (GitOps: Argo / Flux) |
|---|---|---|
| Cluster creds | Live in CI (blast radius) | Stay in cluster |
| Drift | Silent until next deploy | Continuously detected, optionally self-healed |
| Source of truth | Whatever last ran | Git, always |
| Rollback | Re-run pipeline | git revert |

### When to reach for it
- Use GitOps when the deploy target is Kubernetes and there is more than one environment or more
  than one person deploying. Below that bar, plain CI deploy (the SKILL.md pipeline) is fine.
- Do NOT bolt GitOps onto Vercel/Railway/Fly.io/FTP targets. Those are not k8s; the SKILL.md
  platform lanes own them.

---

## 2. ArgoCD (primary: UI + ApplicationSet)

Reach for ArgoCD when the team wants a UI, RBAC/SSO, sync visualization, or templated
multi-cluster fan-out (ApplicationSet).

### Application resource (the unit of deploy)
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kellbell-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaisolaris/kellbell-deploy.git
    targetRevision: main            # pin a tag/sha for prod; main only if branch-protected
    path: envs/prod                 # per-env directory (matches terraform envs/ pattern)
  destination:
    server: https://kubernetes.default.svc
    namespace: kellbell
  syncPolicy:
    automated:
      prune: true                   # delete resources removed from git
      selfHeal: true                # revert manual cluster edits back to git
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
      backoff: { duration: 5s, factor: 2, maxDuration: 3m }
```

### Operating discipline
- prune + selfHeal ON for non-prod, deliberate for prod. selfHeal in prod means a human hotfix in
  the cluster gets reverted within minutes. That is the point, but it must be a documented
  expectation, not a surprise. Emergency break-glass = pause auto-sync, not edit live.
- Sync waves (annotation argocd.argoproj.io/sync-wave) order dependent resources (CRDs/DB before
  app). Lower numbers apply first.
- App-of-apps: one root Application points at a directory of child Applications, bootstrapping a
  whole cluster from one commit.
- ApplicationSet templates one Application across many clusters/envs from a generator (list, git
  directory, cluster). The right tool for "same app, N tenants/regions".
- Drift is a first-class signal. An Application showing OutOfSync with selfHeal off is your drift
  alarm; wire it to Slack via Argo notifications instead of a separate terraform plan cron for
  k8s resources.

---

## 3. Flux (the pull-native alternative)

Reach for Flux when the team wants no UI, pure GitOps-toolkit, OCI-artifact-driven delivery, or
automated image updates committed back to git. Flux is a set of controllers, not an app:
source-controller (pulls git/OCI/Helm), kustomize-controller + helm-controller (apply),
image-reflector + image-automation-controller (watch a registry, bump the tag in git).

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata: { name: kellbell-prod, namespace: flux-system }
spec:
  interval: 5m
  path: ./envs/prod
  prune: true
  sourceRef: { kind: GitRepository, name: kellbell-deploy }
  targetNamespace: kellbell
```

### Argo vs Flux: the selection rule
- ArgoCD if you want a UI / SSO-RBAC / visual sync / ApplicationSet fan-out.
- Flux if you want minimal footprint, OCI artifacts, image-automation-writes-back-to-git, and you
  are comfortable operating entirely from manifests.
- Do not run both against the same namespace. They fight over reconciliation.

---

## 4. SOPS: secrets in a GitOps world (MPL-2.0; methodology only)

GitOps has one hard problem: you cannot put plaintext secrets in the git repo the cluster pulls.
SOPS solves it by encrypting only the values in a YAML/JSON/ENV file (keys stay readable, so diffs
are reviewable) using a KMS key, age, or PGP. The encrypted file is safe to commit.

```bash
# encrypt with an age recipient (or --kms <arn> for AWS KMS)
sops --encrypt --age $AGE_PUBLIC_KEY secrets.yaml > secrets.enc.yaml   # commit the .enc file
sops --decrypt secrets.enc.yaml                                        # local read
```

### Discipline
- Only the decrypt key lives outside git. AWS KMS / GCP KMS / Azure Key Vault for cloud; age keys
  for self-host. The cluster decrypts at apply time (Flux has native SOPS support; ArgoCD via the
  argocd-vault-plugin or a SOPS-aware kustomize plugin).
- .sops.yaml creation rules pin which keys encrypt which path globs, preventing a dev encrypting
  prod secrets with a dev key.
- Never commit the unencrypted file. .gitignore the plaintext name; commit only *.enc.* files.
- Rotate by re-encrypting to a new key and revoking the old (sops updatekeys).
- Self-host note (MPL-2.0): SOPS is fine to install and use as a tool; we reference its workflow
  here and vendor no source. For an air-gapped build, build from the upstream repo under MPL-2.0,
  which is file-level copyleft only, with no obligation on your own files.

This replaces the bare "Sealed Secrets / External Secrets Operator" name-drop with a usable
secrets-in-git pattern. Sealed Secrets / ESO remain valid alternatives; SOPS is the default for
multi-format, multi-cloud, review-friendly secrets.

---

## 5. OpenTelemetry Collector: vendor-neutral telemetry pipeline

The SKILL.md observability section names backends (Datadog/Prometheus/Loki/Tempo/Sentry). The
Collector is the missing layer: instrument the app once against OTel, ship to a Collector, and the
Collector fans out to whatever backend(s) you choose. Swapping Datadog for the Grafana stack
becomes a Collector config change, not an app redeploy.

```yaml
# otel-collector-config.yaml: receivers -> processors -> exporters
receivers:
  otlp: { protocols: { grpc: {}, http: {} } }
processors:
  batch: {}
  memory_limiter: { check_interval: 1s, limit_percentage: 80 }
exporters:
  prometheus: { endpoint: "0.0.0.0:8889" }            # metrics
  otlphttp/tempo: { endpoint: "http://tempo:4318" }   # traces
service:
  pipelines:
    metrics: { receivers: [otlp], processors: [memory_limiter, batch], exporters: [prometheus] }
    traces:  { receivers: [otlp], processors: [memory_limiter, batch], exporters: [otlphttp/tempo] }
```

### Discipline
- Always run memory_limiter + batch processors. An unbounded Collector OOMs the node.
- Deploy as a DaemonSet (agent) for node-local collection, optionally plus a Deployment (gateway)
  for org-wide processing/sampling before egress.
- Tail-sampling at the gateway keeps trace cost sane: keep all errors + slow spans, sample the
  rest. Configure once centrally rather than per-service.
- One instrumentation, many backends is the whole reason to adopt it. Never hardcode a vendor SDK
  into app code when the Collector can decouple it.

---

## 6. Trivy security gating (Apache-2.0): operationalized

Trivy is already name-dropped across SKILL.md as a scanner. Here is the actual gate. NOTE: tfsec
has been folded into Trivy's misconfig scanner upstream, so Trivy now covers container + IaC +
secrets + SBOM in one tool.

### SUPPLY-CHAIN WARNING (live 2026 advisory)
The official aquasecurity/trivy-action was compromised twice in March 2026 (TeamPCP campaign).
Pin to a commit SHA, never @master / @v1 / a floating tag. This applies to every third-party
action, but Trivy is the documented active incident.

```yaml
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>
      - name: Trivy IaC + secrets + vuln scan
        uses: aquasecurity/trivy-action@<pinned-commit-sha>   # NOT @master
        with:
          scan-type: fs           # or 'image' for built containers
          scanners: vuln,secret,misconfig
          severity: HIGH,CRITICAL # gate threshold
          exit-code: 1            # fail the build on findings at/above severity
          format: sarif
          output: trivy.sarif
      - uses: github/codeql-action/upload-sarif@<sha>
        with: { sarif_file: trivy.sarif }
```

### Gating discipline
- Gate on HIGH+CRITICAL, report MEDIUM and below. Failing on every LOW finding trains people to
  ignore the gate. Block on what actually matters (exploitable + reachable).
- SARIF to GitHub code scanning so findings show on the PR diff, not buried in logs.
- Pin the action SHA (see warning). Re-pin deliberately after reviewing the new release.
- .trivyignore with a dated justification + owner for any accepted finding. Never silent.

---

## Cross-references inside Solaris
- terraform-skill.md: IaC authoring; Trivy misconfig scanning gates the Terraform CI here.
- rules.md: the one-line "ArgoCD/Flux for GitOps" decision rule now resolves to this file.
- kubernetes-specialist: owns advanced cluster internals; this file owns the GitOps delivery +
  secrets + telemetry layer on top.
- security-auditor: deep IaC/container audits; Trivy here is the in-pipeline first pass.

## Source provenance
- argoproj/argo-cd: https://github.com/argoproj/argo-cd (Apache-2.0)
- fluxcd/flux2: https://github.com/fluxcd/flux2 (Apache-2.0)
- getsops/sops: https://github.com/getsops/sops (MPL-2.0, methodology referenced, no code vendored)
- open-telemetry/opentelemetry-collector: https://github.com/open-telemetry/opentelemetry-collector (Apache-2.0)
- aquasecurity/trivy: https://github.com/aquasecurity/trivy (Apache-2.0)
- Absorbed as methodology 2026-06-13 (depth pass). All facts verified that day.
