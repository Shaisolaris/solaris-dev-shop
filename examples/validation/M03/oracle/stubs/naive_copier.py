#!/usr/bin/env python3
"""M03 negative control: a plausible naive backup tool. snapshot copies *.db files and writes a manifest
with sha256; verify/health only check that files exist; restore copies snapshot files over the live
ones (no confirm check, no verification, no recoverable copy, no journal); recover does nothing."""
import argparse
import hashlib
import json
import os
import shutil
import sys

ap = argparse.ArgumentParser()
ap.add_argument("cmd")
ap.add_argument("target")
ap.add_argument("--out")
ap.add_argument("--snapshot")
ap.add_argument("--confirm")
ap.add_argument("--expect", action="append", default=[])
ap.add_argument("--db", action="append")
ap.add_argument("--lock-timeout")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--json", action="store_true")
a = ap.parse_args()
rc, out = 0, {"status": "ok"}
if a.cmd == "snapshot":
    os.makedirs(a.out)
    dbs = {}
    for n in sorted(os.listdir(a.target)):
        if n.endswith(".db"):
            shutil.copyfile(os.path.join(a.target, n), os.path.join(a.out, n))
            dbs[n] = {"sha256": hashlib.sha256(open(os.path.join(a.out, n), "rb").read()).hexdigest()}
    json.dump({"snapshot_id": "abc123", "databases": dbs}, open(os.path.join(a.out, "manifest.json"), "w"))
    out["snapshot_id"] = "abc123"
elif a.cmd == "health":
    rc = 0 if all(os.path.exists(os.path.join(a.target, n)) for n in a.expect) else 1
elif a.cmd == "restore" and not a.dry_run:
    for n in os.listdir(a.snapshot):
        if n.endswith(".db"):
            shutil.copyfile(os.path.join(a.snapshot, n), os.path.join(a.target, n))
print(json.dumps(out))
sys.exit(rc)
