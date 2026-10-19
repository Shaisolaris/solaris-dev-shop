#!/usr/bin/env python3
"""M11 r3 combined oracle for teeth (Grok self-validation): the M11 oracle and the r2 per-source oracle (regression)
plus the r3 expected-sources oracle. Usage: PY m11r3_all.py REPO OUT.json"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; rows = []
for o in ("m11_oracle.py", "m11r2_sources.py", "m11r3_sources.py"):
    fd, tmp = tempfile.mkstemp(prefix="m11r3all-", suffix=".json", dir="/tmp"); os.close(fd)
    subprocess.run([sys.executable, str(here / o), sys.argv[1], tmp], capture_output=True, timeout=500)
    try: rows += json.load(open(tmp))
    except Exception: rows.append({"id": o + "_crash", "kind": "core", "result": "FAIL", "detail": "oracle produced no output"})
    os.unlink(tmp)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
core = [r for r in rows if r["kind"] == "core"]; print("M11R3 ALL %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
