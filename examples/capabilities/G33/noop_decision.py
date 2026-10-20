#!/usr/bin/env python3
"""G33 no-op control: names the first option preferred with no evidence work. Expected REJECTED."""
import json, sys
a = sys.argv[1:]
if a[0] == "verify":
    print("IDENTICAL"); sys.exit(0)
p = json.load(open(a[1]))
rep = {"status": "preferred", "preferred": p["options"][0]["id"], "totals": {}, "excluded": [], "verify_before_use": [], "findings": [],
       "contrary_evidence": [], "cells": [], "deciding_evidence": [], "estimates_made": "none", "claim_confidence": {}}
if "--out" in a:
    open(a[a.index("--out") + 1], "w").write(json.dumps(rep))
print(json.dumps(rep))
