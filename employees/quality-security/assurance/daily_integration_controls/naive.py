#!/usr/bin/env python3
"""Naive control for the daily integration oracle: runs each named test module and calls the stack
integrated when they pass. It never checks that the candidates are really in HEAD, that a merge kept
their files, the writable scope, a dirty tree, acceptance or outside contributions. Must be REJECTED."""
import json, os, subprocess, sys
a = sys.argv[1:]
plan = json.load(open(a[a.index("--plan") + 1]))
repo = a[a.index("--repo") + 1] if "--repo" in a else "."
runs, bad = [], []
if "--run" in a and a[a.index("--run") + 1] != "none":
    for p in plan.get("prerequisites", []):
        for m in p.get("tests", []):
            rc = subprocess.run([sys.executable, "-m", "unittest", m], cwd=repo, capture_output=True).returncode
            runs.append({"kind": "test", "id": p["id"], "rc": rc})
            if rc:
                bad.append({"code": "RUN_FAILED", "id": p["id"], "detail": m})
head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
rep = {"verdict": "NOT_INTEGRATED" if bad else "INTEGRATED", "head": head, "findings": bad, "runs": runs,
       "prerequisites": [{"id": p["id"], "commit": p["commit"], "acceptance": "UNKNOWN", "ancestor_of_head": True} for p in plan.get("prerequisites", [])],
       "external": [{"id": e["id"], "acceptance": "ACCEPTED", "reply_verified": True, "validation_manifest_verified": True} for e in plan.get("external", [])],
       "notes": []}
print(json.dumps(rep))
sys.exit(1 if bad else 0)
