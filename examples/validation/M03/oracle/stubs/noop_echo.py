#!/usr/bin/env python3
"""M03 negative control: claims success for every command (with a fake snapshot_id) and writes nothing."""
import json
import sys

print(json.dumps({"status": "ok", "snapshot_id": "0123456789abcdef", "argv": sys.argv[1:]}))
sys.exit(0)
