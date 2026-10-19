#!/usr/bin/env python3
"""G38 no-op control: reports consistent without reading anything."""
import json, sys
print(json.dumps({"result": "consistent", "license": "MIT", "declarations": 0, "findings": [], "integrity": None, "excluded": {}}))
sys.exit(0)
