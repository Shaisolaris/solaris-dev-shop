#!/usr/bin/env python3
"""M10 negative control: a plausible naive diagnoser. Walks observations in file order and calls the
first failing one 'localized' with high confidence; certificate names by substring; no uncertainty."""
import json, sys
argv = sys.argv[1:]
if not argv or argv[0] not in ("diagnose", "batch"):
    sys.exit(2)
try:
    doc = json.load(open(argv[1]))
    host = doc["target"]["host"].lower()
except Exception:
    print("invalid"); sys.exit(2)
layer, code = None, None
for o in doc.get("observations", []):
    s = o.get("stage")
    if s == "dns" and o.get("rcode") != "NOERROR":
        layer, code = "dns", "DNS_" + o.get("rcode", "")
    elif s == "tcp" and o.get("result") == "timeout":
        layer, code = "route", "ROUTE_TIMEOUT"
    elif s == "tcp" and o.get("result") == "refused":
        layer, code = "application", "APP_NOT_LISTENING"
    elif s == "tls" and o.get("result") != "ok":
        c = o.get("cert") or {}
        layer = "tls"
        code = "TLS_NAME_MISMATCH" if c.get("san") and host not in " ".join(c["san"]).lower() else "TLS_ALERT"
    elif s == "http" and (o.get("status") or 0) >= 500:
        layer, code = "application", "APP_SERVER_ERROR"
    if layer:
        break
rep = {"schema": "solaris.net-diagnosis/1", "verdict": "localized" if layer else "healthy", "layer": layer, "confidence": "high",
       "candidates": [layer] if layer else [], "findings": [{"code": code, "layer": layer, "detail": code, "evidence": code}] if layer else [],
       "missing_evidence": [], "next_actions": [], "notes": [],
       "layers": {l: {"state": "failed" if l == layer else "ok", "evidence": []} for l in ("dns", "route", "tls", "application")}}
print(json.dumps(rep))
sys.exit(1 if layer else 0)
