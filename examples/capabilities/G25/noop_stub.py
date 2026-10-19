#!/usr/bin/env python3
"""G25 noop stub: speaks the CLI shape, claims nothing, reports everything clean. The oracle must fail it."""
import json
import sys

rep = {"schema": "solaris.device-protocol-report/1", "status": "clean", "claims": [], "anomalies_found": {},
       "counts": {}, "devices": {}, "commands_unacknowledged": [],
       "claim_scope": "simulated valve actuations from a synthetic event stream; not hardware evidence",
       "simulation": {"claims_match_ground_truth": True, "verdict": "claims equal ground truth, exactly once"}}
print(json.dumps(rep) if "--json" in sys.argv else "clean")
sys.exit(0)
