"""M16 r3 teeth tally (Grok self-validation): a scorer kills a mutant when the M16 oracle rejects it, the builder oracle
reports a failing check, or the builder tests fail. Usage: python tally_teeth_r3.py TEETH_TSV"""
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
mut = [r for r in rows if r["subject"] not in ("candidate", "r2-df25d6a") and not r["subject"].startswith(("stub-", "builder-"))]
k = lambda r: ("REJECTS" in r["m16_oracle_core"], not r["builder_oracle"].startswith("15/15"), not r["builder_tests"].startswith("rc=0"))
print(f"{'mutant':30s} m16  bld-oracle  bld-tests  union")
for r in mut:
    a, b, c = k(r); print(f"{r['subject']:30s} {'K' if a else '-':4s} {'K' if b else '-':11s} {'K' if c else '-':10s} {'KILLED' if (a or b or c) else 'survived'}")
n = len(mut); s = [sum(k(r)[i] for r in mut) for i in range(3)]
print(f"mutants {n}: m16 oracle core {s[0]}, builder oracle {s[1]}, builder tests {s[2]}, union {sum(any(k(r)) for r in mut)}")
for r in rows:
    if r["subject"] in ("candidate", "r2-df25d6a") or r["subject"].startswith(("stub-", "builder-")):
        print(f"{r['subject']:22s} m16: {r['m16_oracle_core'][:60]} | builder: {r['builder_oracle'][:40]} | tests: {r['builder_tests'][:50]}")
