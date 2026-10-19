"""M07 teeth tally (Grok self-validation). Recomputes kills from the saved per-mutant oracle JSON, EXCLUDING the OBS row
C11b (temp files after a random SIGKILL), which is timing-dependent: on 3.11.16 it was the only row that 'killed'
retired_alias_reuse_ok and mid_any, and those kills did not reproduce on 3.13.15, so they are not counted."""
import json, sys, glob, os
FLAKY = {"C11b_temp_files_left_after_sigkill"}
def sig(j): return {r["id"]: (r["result"] if r["kind"] == "core" else json.dumps(r["detail"], sort_keys=True)) for r in json.load(open(j)) if r["id"] not in FLAKY}
sets = {}
for d in sys.argv[1:]:
    b = sig(d + "/baseline.json"); t = {r["mutant"]: r for r in json.load(open(d + "/teeth.json"))}; k = {}
    for f in sorted(glob.glob(d + "/m[0-9][0-9]-*.json")):
        n = os.path.basename(f)[4:-5]; s = sig(f); k[n] = sorted(x for x in set(b) | set(s) if b.get(x) != s.get(x))
    sets[d] = {n for n, v in k.items() if v}
    surv = sorted(n for n, v in k.items() if not v)
    print(os.path.basename(d), "mutants", len(k), "my oracle kills", len(sets[d]), "survivors", surv)
    for n in sorted(k): print("  %-34s %s" % (n, ",".join(k[n]) or "SURVIVED (builder tests rc %s)" % t[n].get("builder_tests_rc", "not run: killed in raw run, see note")))
v = list(sets.values()); print("kill sets identical across versions:", all(x == v[0] for x in v))
