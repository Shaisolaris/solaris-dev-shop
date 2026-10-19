"""Check that the C01 probes really applied: the reader reads the input (its output changes when re-run after the
change) and the record's claimed_inputs shows whether the input was bound. Grok self-validation."""
import os, sys, json
sys.argv = [sys.argv[0], sys.argv[1], "/dev/null"] + sys.argv[2:]
_h = os.path.dirname(os.path.abspath(__file__)); _s = open(os.path.join(_h, "m39r2_contract.py")).read()
exec(compile(_s[: _s.index("@safe\ndef c01")], "c", "exec"))
for nm, cmd, mut in (("equals", lambda b: ["--src=inp/a.csv"], "a"), ("folder", lambda b: ["inp"], "new"), ("absolute", lambda b: [b.p("inp", "a.csv")], "a"), ("symlink", lambda b: ["inp/link.csv"], "a"), ("positional", lambda b: ["inp/a.csv"], "a")):
    b = B2(); b.order()
    if nm == "symlink": os.symlink("a.csv", b.p("inp", "link.csv"))
    b.rd(cmd(b)); o1 = open(b.p("reports", "r.txt")).read(); ci = json.loads(b.lines()[-1]).get("claimed_inputs")
    w(b, "inp/a.csv" if mut == "a" else "inp/new.csv", "id,v\n1,11\n"); g = b.go()[1]
    b.rd(cmd(b), out="reports/r2.txt"); o2 = open(b.p("reports", "r2.txt")).read(); b.close()
    print(nm, "claimed_inputs", ci, "| reader output changes after the input change:", o1 != o2, "| verdict after change", g)
