#!/usr/bin/env python3
"""G10 naive stub: the shortcut a hurried diagnosis takes. The oracle must reject it.

It blames the first observation that looks bad in input order, is always certain, judges
certificates against the wall clock, double-checks the host with a live DNS lookup and
copies request headers into the report.
"""
import datetime as dt, json, socket, sys
from pathlib import Path

LAYER = {"dns": "dns", "route": "route", "tcp": "route", "tls": "tls", "http": "application"}

def diagnose(path):
    t = json.loads(Path(path).read_text())
    host = t["target"]["host"]
    try:
        socket.getaddrinfo(host, 443)  # "just to be sure"
    except OSError:
        pass
    for o in t.get("observations", []):
        bad = (o.get("rcode") not in (None, "NOERROR") or o.get("result") in ("timeout", "refused", "unreachable", "reset", "alert", "eof")
               or (o.get("status") or 0) >= 400 or o.get("reached") is False)
        cert = o.get("cert") or {}
        if cert.get("not_after") and dt.datetime.fromisoformat(cert["not_after"]) < dt.datetime.now(dt.timezone.utc):
            bad = True
        if bad:
            return {"verdict": "localized", "layer": LAYER[o["stage"]], "confidence": "high", "candidates": [LAYER[o["stage"]]],
                    "headers": o.get("headers"), "layers": {}}
    return {"verdict": "healthy", "layer": None, "confidence": "high", "candidates": [],
            "layers": {l: {"state": "ok"} for l in ("dns", "route", "tls", "application")}}

def main():
    a = sys.argv[1:]
    if a and a[0] == "diagnose":
        try:
            rep = diagnose(a[1])
        except Exception as exc:
            print(json.dumps({"verdict": "invalid", "error": str(exc)})); return 2
        if "--out" in a:
            Path(a[a.index("--out") + 1]).write_text(json.dumps(rep))
        print(json.dumps(rep, default=str)); return 0 if rep["verdict"] == "healthy" else 1
    if a and a[0] == "batch":
        reps = {p.name: diagnose(p) for p in sorted(Path(a[1]).glob("*.json"))}
        print(json.dumps({"reports": reps}, default=str)); return 0
    return 2

if __name__ == "__main__":
    sys.exit(main())
