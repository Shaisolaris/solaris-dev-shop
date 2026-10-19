# no-op stub: claims success, writes nothing
import json, sys
print(json.dumps({"status": "complete", "exit_code": 0}) if "--json" in sys.argv else "Folder: (complete)")
