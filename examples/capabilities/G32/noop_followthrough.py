#!/usr/bin/env python3
"""G32 no-op control: reports success and drafts nothing. Expected REJECTED."""
import json, sys
print(json.dumps({"drafted": [], "notes": [], "sent": 0, "duplicate_suppressed": [], "reassigned": [], "runs": 0, "open_drafts": []}))
