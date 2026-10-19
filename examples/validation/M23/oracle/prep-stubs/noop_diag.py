"""M23 no-op stub (Grok-made, not a candidate): always reports a clean scan."""
import json, sys
print(json.dumps([{"id": "DIAG-CLEAN", "severity": "Info", "category": "Diagnostics", "title": "No issues found", "summary": "", "detail": "", "location": ""}]))
