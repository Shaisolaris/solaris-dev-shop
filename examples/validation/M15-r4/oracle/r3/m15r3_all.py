#!/usr/bin/env python3
"""M15 r3 combined oracle for teeth (Grok self-validation): the M15 v3 oracle and the r2 drift oracle (regression), plus
the r3 scan oracle; slow statistical OBS rows skipped (M15R2_FAST, M15R3_FAST). Usage: PY m15r3_all.py REPO OUT.json"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; rows = []
for o in ("m15_oracle.py", "m15r2_drift.py", "m15r3_scan.py"):
    fd, tmp = tempfile.mkstemp(prefix="m15r3all-", suffix=".json", dir="/tmp"); os.close(fd)
    subprocess.run([sys.executable, str(here / o), sys.argv[1], tmp], capture_output=True, timeout=500, env=dict(os.environ, M15R2_FAST="1", M15R3_FAST="1"))
    try: rows += json.load(open(tmp))
    except Exception: rows.append({"id": o + "_crash", "kind": "core", "result": "FAIL", "detail": "oracle produced no output"})
    os.unlink(tmp)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
core = [r for r in rows if r["kind"] == "core"]; print("M15R3 ALL %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
