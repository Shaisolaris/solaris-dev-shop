#!/usr/bin/env python3
"""G25 naive stub: claims an effect for every 'done' ack line it can parse.

No sequence ordering, no boot sessions, no dedupe by command id, no device binding, no checkpoint.
This is the at-least-once mistake the real tool exists to prevent. The oracle must fail it.
"""
import argparse
import json
import sys

ap = argparse.ArgumentParser()
ap.add_argument("mode")
ap.add_argument("--commands")
ap.add_argument("--events")
ap.add_argument("--state")
ap.add_argument("--crash-after", type=int)
ap.add_argument("--out")
ap.add_argument("--json", action="store_true")
a, _ = ap.parse_known_args()
if a.mode != "ingest":
    print("simulate not supported", file=sys.stderr)
    sys.exit(2)
claims, bad = [], 0
for line in open(a.events, "rb"):
    try:
        r = json.loads(line)
    except Exception:
        bad += 1
        continue
    if isinstance(r, dict) and r.get("kind") == "ack" and r.get("result") == "done":
        claims.append({"cmd": r.get("cmd"), "device": r.get("device")})
rep = {"status": "anomalies" if bad else "clean", "claims": claims, "anomalies_found": {"quarantined": bad},
       "claim_scope": "simulated valve actuations; not hardware evidence", "counts": {}, "devices": {}}
print(json.dumps(rep))
sys.exit(1 if bad else 0)
