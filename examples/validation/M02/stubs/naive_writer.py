#!/usr/bin/env python3
"""M02 negative control: a plausible naive activation. Creates the folders and docs with plain
open('w') (follows links, overwrites owner files), no journal, no lock, no secret checks, and
treats a blank deploy answer as the old default 'main=live'. resume reruns nothing."""
import argparse
import json
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("cmd")
ap.add_argument("root")
for opt in ("--name", "--type", "--deploy-model", "--brief", "--within"):
    ap.add_argument(opt)
ap.add_argument("--credential", action="append", default=[])
for flag in ("--code", "--init-git", "--json", "--dry-run"):
    ap.add_argument(flag, action="store_true")
a = ap.parse_args()
if a.cmd == "activate":
    os.makedirs(a.root, exist_ok=True)
    for f in ("Scope", "Development", "Delivery", "Assets"):
        os.makedirs(os.path.join(a.root, f), exist_ok=True)
    deploy = (a.deploy_model or "").strip() or "main=live"
    with open(os.path.join(a.root, "STATUS.md"), "w") as fh:
        fh.write(f"# Project status: {a.name}\n\nDEPLOY-MODEL: {deploy}\n")
    with open(os.path.join(a.root, "Scope", "ROUND-PLAN.md"), "w") as fh:
        fh.write(f"# Round plan: {a.name}\n- DEPLOY-MODEL: {deploy}\n")
    with open(os.path.join(a.root, "Delivery", "CREDENTIALS.md"), "w") as fh:
        fh.write(f"# Credential references: {a.name}\n" + "".join(f"- {c}\n" for c in a.credential))
print(json.dumps({"status": "complete"}) if a.json else "done")
