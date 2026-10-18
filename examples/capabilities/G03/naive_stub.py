#!/usr/bin/env python3
"""Negative control: a naive backup/restore that really copies files. snapshot copies *.db,
restore copies them back over the target with shutil.copy (follows links, no verification,
no journal, no lock, no intent check). It restores values in the clean case; the oracle
must still reject it on invalid snapshots, containment, crash gaps, locks and intent."""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

a = sys.argv[1:]
cmd, target = a[0], Path(a[1])
opt = lambda k: a[a.index(k) + 1] if k in a else None
if cmd == "snapshot":
    out = Path(opt("--out"))
    out.mkdir()
    for p in target.glob("*.db"):
        shutil.copy(p, out / p.name)
    (out / "manifest.json").write_text(json.dumps({"snapshot_id": "naive"}))
    print(json.dumps({"status": "ok", "snapshot_id": "naive"}))
elif cmd == "verify":
    sys.exit(0 if target.is_dir() else 1)
elif cmd == "health":
    names = [a[i + 1] for i, x in enumerate(a) if x == "--expect"]
    sys.exit(0 if all((target / n).exists() for n in names) else 1)
elif cmd == "restore":
    if "--dry-run" in a:
        print("would restore")
        sys.exit(0)
    snap = Path(opt("--snapshot"))
    for p in snap.glob("*.db"):
        shutil.copy(p, target / p.name)
    print("restored")
elif cmd == "recover":
    print("nothing to recover")
