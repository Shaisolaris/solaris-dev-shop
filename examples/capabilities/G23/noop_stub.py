#!/usr/bin/env python3
"""G23 noop stub: speaks the CLI shape, finds nothing, and claims every comparison as a speedup. The oracle must fail it."""
import json
import sys

if len(sys.argv) > 1 and sys.argv[1] == "compare":
    rep = {"schema": "solaris.wp-compare/1", "comparable": True, "speedup_claimed": True, "urls": [], "not_comparable_because": [],
           "evidence_scope": "offline; no PHP, WordPress, WP-CLI or database was run; synthetic"}
else:
    rep = {"schema": "solaris.wp-diagnosis/1", "verdict": "healthy", "findings": [], "notes": [],
           "evidence_scope": "offline; no PHP, WordPress, WP-CLI or database was run; synthetic"}
print(json.dumps(rep))
sys.exit(0)
