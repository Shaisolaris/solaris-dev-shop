#!/usr/bin/env python3
"""Negative control: a naive activation that writes folders and docs with plain
open(..., "w"), a predictable temp name, no journal and no preflight. It does real
work for the clean case, so it is a stronger control than an echo; the oracle
must still reject it on preservation, escape, deploy-default and recovery checks."""
import os
import sys
from pathlib import Path

args = sys.argv[1:]
cmd, root = args[0], Path(args[1])
opts = {}
i = 2
while i < len(args):
    if args[i] in ("--code", "--init-git", "--json"):
        i += 1
        continue
    opts[args[i]] = args[i + 1] if i + 1 < len(args) else ""
    i += 2
name = opts.get("--name", "Project")
deploy = (opts.get("--deploy-model") or "main=live").strip() or "main=live"
for d in ("Scope", "Development", "Delivery", "Assets"):
    (root / d).mkdir(parents=True, exist_ok=True)
for rel, body in (("STATUS.md", f"# {name}\nDEPLOY-MODEL: {deploy}\n"), ("Scope/ROUND-PLAN.md", f"# {name} plan\n"),
                  ("Delivery/CREDENTIALS.md", f"# {name} credentials\n{opts.get('--credential', '')}\n")):
    tmp = root / f".{Path(rel).name}.tmp"
    with open(tmp, "w") as fh:
        fh.write(body)
    os.replace(tmp, root / rel)
print('{"status": "complete"}' if "--json" in args else "done")
