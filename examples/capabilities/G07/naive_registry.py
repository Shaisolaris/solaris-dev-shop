#!/usr/bin/env python3
"""G07 naive control: the common shortcuts, same CLI as registry.py. Not for use.

Keys machines by the alias the caller types, so the same machine can be registered twice under two names; a
register of an existing alias overwrites it; claims check alias and owner but not the machine identity or the
owner_epoch; ownership changes check the named owner but not the epoch; registry.json is rewritten in place
with no intent record, so a crash drill leaves whatever was written. Request ids are ignored.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    for f in ("--root", "--alias", "--identity", "--owner", "--request-id", "--fail-at", "--from-owner",
              "--to-owner"):
        ap.add_argument(f)
    ap.add_argument("--expect-epoch", type=int)
    ap.add_argument("--epoch", type=int)
    a = ap.parse_args()
    root = Path(a.root)
    if not root.is_dir():
        return 2
    p = root / "registry.json"
    st = json.loads(p.read_text()) if p.exists() else {"machines": []}
    ms = {m["alias"]: m for m in st["machines"]}
    if a.cmd == "status":
        print(json.dumps({"machines": st["machines"]}))
        return 0
    m = ms.get(a.alias)
    if a.cmd == "claim":
        return 0 if m and m["owner"] == a.owner and m["status"] == "active" else 2
    if a.cmd == "register":
        try:
            mid = json.loads(Path(a.identity).read_text())["machine_id"]
        except (OSError, ValueError, KeyError):
            return 2
        ms[a.alias] = {"alias": a.alias, "machine_id": mid, "owner": a.owner, "owner_epoch": 1, "status": "active"}
    else:
        if not m or m["owner"] != a.from_owner:
            return 2
        m["owner_epoch"] += 1
        if a.cmd == "transfer":
            m["owner"] = a.to_owner
        else:
            m["status"] = "retired"
    st["machines"] = list(ms.values())
    p.write_text(json.dumps(st))
    if a.fail_at:
        os._exit(75)
    (root / "FLEET.md").write_text("\n".join("| %s | %s | %s |" % (m["alias"], m["machine_id"], m["owner"])
                                             for m in st["machines"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
