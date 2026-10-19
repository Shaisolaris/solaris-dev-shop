# G09 offline Kubernetes manifest check

All manifests here are synthetic. Nothing in this folder contacts a cluster or deploys anything.

- `fixtures/clean/`: clean control (Namespace, Deployment, Services, PDBs, HPA, StatefulSet, CronJob).
- `fixtures/broken/shop-broken.yaml`: the same shop with five planted mistakes.
- `k8s_oracle.py`: 17 checks (planted mistakes with exact file and line, quantity arithmetic, namespace
  scoping, 40-namespace scale case, unusable input, 12 seeded unseen bundles, no deployment claims, inputs
  unchanged). `naive_check.py` and `noop_check.py` are controls the oracle must reject.

Demo, from the repository root (`T=employees/infrastructure/kubernetes-specialist/k8s_manifest_check.py`):

```
python3 $T check examples/capabilities/G09/fixtures/clean            # exit 0
python3 $T check examples/capabilities/G09/fixtures/broken           # exit 1
python3 $T check examples/capabilities/G09/fixtures/broken --json    # exit 1
python3 $T check examples/capabilities/G09/README.md                 # exit 2
python3 examples/capabilities/G09/k8s_oracle.py                      # ACCEPTED 17/17
python3 examples/capabilities/G09/k8s_oracle.py --tool examples/capabilities/G09/noop_check.py   # REJECTED 2/17
```

The broken bundle reports, in file order: latest image tag (line 32), no memory limit (38), liveness probe
on port name `htttp` (55), Service selector `tier=front-end` matching no pod (66), and a PDB with
minAvailable 3 for 3 replicas (83). README.md is refused (exit 2, with its line) because it is not a manifest
the reader can read; nothing is reported clean.

No cluster runtime (kubectl, kind, minikube, docker) was present on the build host, so no disposable cluster
behaviour was run; the check is file-only and says so in every result.
