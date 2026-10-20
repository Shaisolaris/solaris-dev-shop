#!/usr/bin/env python3
"""G09 naive control: the line-by-line look the skill prose allows without a tool.

Flags mutable image tags and containers whose text has no 'resources:' or 'readinessProbe:', file by file,
without relating objects to each other. Used only to show that the oracle rejects shallow checking.
"""
import json
import re
import sys

SCOPE = "static manifest files only; no cluster was contacted, nothing was applied or deployed"


def main(argv):
    paths = [a for a in argv[1:] if not a.startswith("--")]
    out = []
    for p in paths:
        text = open(p).read()
        for n, ln in enumerate(text.split("\n"), 1):
            m = re.search(r"image:\s*(\S+)", ln)
            if m and (m.group(1).endswith(":latest") or ":" not in m.group(1).rsplit("/", 1)[-1]):
                out.append({"severity": "error", "code": "IMAGE_TAG_MUTABLE", "file": p, "line": n, "path": "image",
                            "reason": "mutable tag", "suggestion": None, "kind": None, "name": None, "namespace": None})
        if "containers:" in text and "resources:" not in text:
            out.append({"severity": "error", "code": "RESOURCES_MISSING", "file": p, "line": 1, "path": "resources",
                        "reason": "no resources", "suggestion": None, "kind": None, "name": None, "namespace": None})
    e = len(out)
    print(json.dumps({"schema": "g09-k8s-check-v1", "evidence_scope": SCOPE, "cluster_contacted": False,
                      "applied": False, "deployed": False, "files": paths, "objects": 0, "findings": out, "qos": [],
                      "summary": {"errors": e, "warnings": 0, "status": "errors" if e else "clean"}}))
    return 1 if e else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
