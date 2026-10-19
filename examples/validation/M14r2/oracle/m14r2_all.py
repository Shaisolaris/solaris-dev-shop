#!/usr/bin/env python3
"""M14 r2 combined oracle for teeth (Grok self-validation): the M14 oracle v3 (regression) plus the r2 negative-transaction oracle.
Usage: PY m14r2_all.py REPO OUT.json"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; rows = []
for o in ("m14_oracle.py", "m14r2_negative.py"):
    fd, tmp = tempfile.mkstemp(prefix="m14r2all-", suffix=".json", dir="/tmp"); os.close(fd)
    subprocess.run([sys.executable, str(here / o), sys.argv[1], tmp], capture_output=True, timeout=500)
    try: rows += json.load(open(tmp))
    except Exception: rows.append({"id": o + "_crash", "kind": "core", "result": "FAIL", "detail": "oracle produced no output"})
    os.unlink(tmp)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
core = [r for r in rows if r["kind"] == "core"]; print("M14R2 ALL %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
