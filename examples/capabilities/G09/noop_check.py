#!/usr/bin/env python3
"""G09 no-op control: reports every input clean without reading it. The oracle must reject it."""
import json
import sys

paths = [a for a in sys.argv[2:] if not a.startswith("--")]
print(json.dumps({"schema": "g09-k8s-check-v1", "cluster_contacted": False, "applied": False, "deployed": False,
                  "evidence_scope": "static manifest files only; no cluster was contacted, nothing was applied or deployed",
                  "files": paths, "objects": 0, "findings": [], "qos": [],
                  "summary": {"errors": 0, "warnings": 0, "status": "clean"}}))
sys.exit(0)
