#!/usr/bin/env python3
"""M10 negative control: prints a plausible 'healthy' report for any input and exits 0."""
import json, sys
print(json.dumps({"schema": "solaris.net-diagnosis/1", "verdict": "healthy", "layer": None, "confidence": "high",
                  "candidates": [], "findings": [], "missing_evidence": [], "next_actions": [], "notes": [],
                  "layers": {l: {"state": "ok", "evidence": []} for l in ("dns", "route", "tls", "application")}}))
sys.exit(0)
