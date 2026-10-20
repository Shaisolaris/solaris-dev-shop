# Offline manifest check before rollout (G09)

`k8s_manifest_check.py` reads rendered Kubernetes manifests (YAML or JSON) and reports concrete mistakes
with file, line and field path. It is standard-library Python 3.9+, contacts no cluster, runs no kubectl,
helm or container runtime, and never writes to its inputs. Its output always says
`cluster_contacted: false, applied: false, deployed: false`. A clean result means these files passed these
checks. It is not dry-run evidence, not an apply and not proof that a rollout is healthy; the OUTPUT
CONTRACT still needs `kubectl apply --dry-run=server` (or `BLOCKED <no cluster>`) before `Gate: passed`.

```
python3 k8s_manifest_check.py check rendered/ [more files] [--json] [--namespace NS]
```

Exit 0: no errors (warnings may remain). Exit 1: errors found. Exit 2: input unusable (unreadable file,
unrendered `{{ }}` template, YAML it does not read, no objects); nothing is reported as clean then.

## What it checks

Errors (each would break the rollout or is rejected by the API server):

| Code | Mistake |
|---|---|
| SERVICE_SELECTOR_NO_MATCH | Service selector matches no pod template in its namespace (no endpoints); the nearest workload labels are suggested |
| SERVICE_TARGETPORT_NAME_UNKNOWN | named targetPort is not a container port name of the selected pods |
| SERVICE_PORT_NAME_REQUIRED | multi-port Service with an unnamed port |
| WORKLOAD_SELECTOR_MISSING / WORKLOAD_SELECTOR_TEMPLATE_MISMATCH | apps/v1 selector absent or not matching its own template labels |
| PROBE_PORT_NAME_UNKNOWN, PROBE_PORT_MISSING, PROBE_PORT_INVALID | probe port name not on that container, missing or out of range |
| PROBE_HANDLER_INVALID, PROBE_SUCCESS_THRESHOLD, PROBE_VALUE_INVALID | zero or two handlers; liveness/startup successThreshold not 1; values below their minimum |
| READINESS_PROBE_MISSING | container behind a Service with no readinessProbe |
| RESOURCES_MISSING | no cpu request, memory request or memory limit (a limit stands in for its request, as Kubernetes defaults it) |
| REQUEST_EXCEEDS_LIMIT, RESOURCE_QUANTITY_INVALID | request above limit (exact quantity arithmetic: 0.5Gi vs 384Mi), or a value such as `256MB` |
| HPA_TARGET_NO_REQUEST, HPA_MIN_GT_MAX | HPA on cpu/memory utilization for a target container without that request; min above max |
| PDB_SELECTOR_NO_MATCH, PDB_BLOCKS_EVICTION | budget selecting nothing; minAvailable >= replicas, 100% or maxUnavailable 0 (drains hang) |
| IMAGE_TAG_MUTABLE, IMAGE_MISSING | `:latest` or untagged image (a registry port is not a tag) |
| CONTAINER_NAME_DUPLICATE, CONTAINER_PORT_NAME_DUPLICATE, PORT_NAME_INVALID, CONTAINER_PORT_INVALID | rejected by the API server |
| DUPLICATE_KEY, OBJECT_DUPLICATE, OBJECT_INVALID, POD_TEMPLATE_MISSING | a repeated key or object silently hides one value |

Warnings: SERVICE_SELECTOR_UNRESOLVED and HPA_TARGET_UNRESOLVED (the selected workload is not in these
files, so nothing can be confirmed), SERVICE_TARGETPORT_UNDECLARED and PROBE_PORT_UNDECLARED (numeric port
the container does not declare), LIVENESS_PROBE_MISSING, PROBES_IDENTICAL, PROBE_TIMEOUT_GT_PERIOD,
PDB_MISSING (more than one replica), RESOURCES_DEFAULTED (relies on a LimitRange in these files). Each pod
template's QoS class (Guaranteed, Burstable, BestEffort) is printed so a resource change does not move it
silently.

Suggestions are printed as `suggestion (not applied)`. The tool never edits a manifest; recovery is a
reviewed edit of the file, then a rerun.

## Limits (say them in the deliverable)
- Only rendered manifests. Helm and Kustomize output must be rendered first; `{{ }}` is refused (exit 2).
- The YAML reader covers what manifests use: block and flow mappings and sequences, quoted and plain
  scalars, `|` and `>` blocks, comments, `---` documents, `kind: List`. Anchors, aliases, tags, merge keys,
  complex keys and multi-line plain scalars are refused with their line rather than guessed. Booleans
  follow YAML 1.1 (`yes`, `no`, `on`, `off`), as the Kubernetes YAML reader does.
- It knows only the objects in the files given. Objects already in the cluster, admission policies,
  webhooks, CRDs and defaulting beyond LimitRange are not seen; that is what a server dry run is for.
- Not checked: RBAC, NetworkPolicy, PSA, API deprecations (use Pluto), Ingress/Gateway routing, node
  capacity or scheduling.

## Hand-offs
- devops-engineer: a pipeline runs this before its own preflight; for local release drills see
  `local_deploy.py` (G08), which is a different, local-fixture tool.
- site-reliability-engineer: a probe or PDB finding on an SLO-bearing service goes to the reliability review
  before rollout.
