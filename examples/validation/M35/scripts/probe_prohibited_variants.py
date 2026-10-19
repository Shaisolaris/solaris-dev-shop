"""M35 OBS probe (Grok self-validation): prohibited-wording variants on an otherwise ready creative. Usage: PY probe.py SRC"""
import sys, json, os
SRC = sys.argv[1]; sys.argv = [sys.argv[0], SRC, "/dev/null"]
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "oracle", "m35_oracle.py")).read().split("\nfor f in (f01")[0])
for name, head in (("plain", "Risk-free: search returned 2.00x its cost"), ("nb_hyphen_u2011", "Risk\u2011free: search returned 2.00x its cost"),
                   ("en_dash", "Risk\u2013free: search returned 2.00x its cost"), ("upper", "GUARANTEED: search returned 2.00x its cost"),
                   ("fullwidth_hash_1", "\uff03\uff11 search, 2.00x its cost"), ("no_1", "No. 1 search returned 2.00x its cost")):
    k = Pkg(**base(creatives=[kre(head, "Draft.", [ROAS])])); rc, j = k.run(); k.close(); c = (j.get("creatives") or [{}])[0]
    print(name, c.get("status"), json.dumps(c.get("reasons"))[:160])
