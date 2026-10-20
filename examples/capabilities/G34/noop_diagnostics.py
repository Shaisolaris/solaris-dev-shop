#!/usr/bin/env python3
"""Control for diag_oracle.py: accepts the same arguments, reads nothing, reports no findings, always exits 0."""
import json
import sys

print(json.dumps({"schema": "g34/1", "pages_scanned": 0, "complete": True, "skipped": [], "findings": []}))
sys.exit(0)
