# M14 r2 probe (Grok self-validation): every `reason` value seen in the M14 oracle and r2 oracle result details (3.9.6),
# checked against the backticked names in cash-revenue-reconciliation.md. Usage: PY reason_names.py RESULTS_DIR DOC
import json, glob, sys
seen = set()
def walk(o, key=None):
    if isinstance(o, dict): [walk(v, k) for k, v in o.items()]
    elif isinstance(o, list): [walk(x, key) for x in o]
    elif key in ("reason", "unapplied_reasons") and isinstance(o, str): seen.add(o)
for f in (sys.argv[1] + "/oracle-3.9.6.json", sys.argv[1] + "/negative-3.9.6.json"): walk(json.load(open(f)))
doc = open(sys.argv[2]).read()
for r in sorted(seen): print(r, "IN_DOC" if ("`%s`" % r) in doc else "NOT_IN_DOC (G13 reader reason, documented by reference)" if r.startswith("bad_") else "NOT_IN_DOC")
