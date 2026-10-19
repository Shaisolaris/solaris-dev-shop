"""Tally M10 r4 teeth TSV (Grok self-validation). Usage: python tally_m10r4.py TSV
A subject is killed by: the M10 oracle when it is not ACCEPTED; the builder oracle when not ACCEPTED; the builder tests when
not rc=0 OK; a probe scorer when its HOLDS/GAP pattern differs from the candidate's."""
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
cand = next(r for r in rows if r["subject"] == "candidate")
pat = lambda v: v.split("pattern=")[-1].strip() if "pattern=" in v else None
R2 = set("""""".split())
def kills(r):
    k = {"m10_oracle": "ACCEPTS" not in r["m10_oracle"], "builder_oracle": "ACCEPTED" not in r["builder_oracle"],
         "builder_tests": not r["builder_tests"].startswith("rc=0") if r["builder_tests"] != "n/a" else True,
         "r3_probes": pat(r["r3_probes"]) not in (None, pat(cand["r3_probes"])) if r["r3_probes"] != "n/a" else False,
         "r4_probes": pat(r["r4_probes"]) not in (None, pat(cand["r4_probes"])) if r["r4_probes"] != "n/a" else False}
    return k
r4names = "rv_rg1_other_blocks rg1_other_alone_mismatches rg1_note_dropped rg1_split_every_comma rv_rg3_six_digits rg3_rounded rg3_no_truncate q2_rv_bare_split q2_split_nonhost_too q1_rv_types q1_no_url q1_no_oidname q1_note_old detail_all_san".split()
muts = [r for r in rows if r["subject"] not in ("candidate", "r4-69c6081") and not r["subject"].startswith(("stub-", "builder-"))]
for grp, sel in (("all", muts), ("r2 set (23)", [r for r in muts if r["subject"] not in r4names]),
                 ("r3 set on r5 (7)", [r for r in muts if r["subject"] in r4names[:7]]), ("r5 new (7)", [r for r in muts if r["subject"] in r4names[7:]])):
    tot = {}
    for r in sel:
        for s, v in kills(r).items():
            tot[s] = tot.get(s, 0) + v
    uni = sum(any(kills(r).values()) for r in sel)
    print(f"{grp}: n={len(sel)} " + " ".join(f"{s}={v}" for s, v in tot.items()) + f" union={uni}")
print("survivors (union):", [r["subject"] for r in muts if not any(kills(r).values())])
print("candidate:", {k: cand[k][:40] for k in cand})
for r in rows:
    if r["subject"] in ("r4-69c6081",) or r["subject"].startswith(("stub-", "builder-")):
        print(r["subject"], "killed by:", [s for s, v in kills(r).items() if v])
for n in r4names[7:]:
    r = next(x for x in muts if x["subject"] == n); print(n, [s for s, v in kills(r).items() if v])
