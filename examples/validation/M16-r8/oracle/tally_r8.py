"""M16 r8 teeth tally (Grok self-validation). Usage: PY tally_r8.py TEETHDIR... A mutant is killed by my oracle when any instrument
other than builder_tests deviates from the unmutated candidate."""
import json, sys
sets = {}
for d in sys.argv[1:]:
    rows = json.load(open(d + "/teeth.json")); mine = {r["mutant"] for r in rows if any(v for k, v in r["kills"].items() if k != "builder_tests")}
    bt = {r["mutant"] for r in rows if r["kills"]["builder_tests"]}; sets[d] = mine
    print(d.split("/")[-1], "mutants", len(rows), "my oracle kills", len(mine), "builder tests kill", len(bt), "my survivors", sorted({r["mutant"] for r in rows} - mine))
    for r in rows: print("  %-34s %s" % (r["mutant"], ",".join(k for k, v in r["kills"].items() if v) or "SURVIVED"))
v = list(sets.values()); print("kill sets identical across versions:", all(x == v[0] for x in v))
