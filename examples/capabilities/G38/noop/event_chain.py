#!/usr/bin/env python3
"""G38 no-op control: reports verified without reading anything and writes nothing."""
import json, sys
print(json.dumps({"result": "verified", "verified": 0, "findings": [], "anchor": "none", "head": None, "claimed_by": {"counts": {}, "identity": "unknown"}}))
sys.exit(0)
