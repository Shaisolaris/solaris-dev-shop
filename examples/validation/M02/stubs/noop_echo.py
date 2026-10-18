#!/usr/bin/env python3
"""M02 negative control: echoes its arguments (and a fake 'complete' JSON when asked) and exits 0. Writes nothing."""
import json
import sys

print(json.dumps({"status": "complete", "ok": True, "argv": sys.argv[1:]}) if "--json" in sys.argv else " ".join(sys.argv[1:]))
sys.exit(0)
