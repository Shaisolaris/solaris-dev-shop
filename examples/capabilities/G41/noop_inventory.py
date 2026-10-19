#!/usr/bin/env python3
"""No-op control: reads nothing and reports READY. Must fail the G41 oracle."""
import json, sys
print(json.dumps({"release_gate": {"state": "READY", "reasons": [], "applied": False}, "goals": [],
                  "included_if_released": [], "excluded": [], "conflicts": []}))
sys.exit(0)
