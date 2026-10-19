#!/usr/bin/env python3
"""Tally M10 r3 teeth TSV (Grok self-validation). Usage: python tally_m10r3.py TSV"""
import csv, re, sys
rows = list(csv.reader(open(sys.argv[1]), delimiter="\t"))[1:]
fixed = ("candidate", "r3-", "stub-", "builder-")
cand = next(r for r in rows if r[0] == "candidate")
pat = re.search(r"pattern=(\w+)", cand[4]).group(1)
for r in rows:
    if r[0].startswith(fixed):
        print("SUBJECT", r[0], "|", r[1][:55], "|", r[2][:55], "|", r[3][:45], "|", r[4][:50])
mut = [r for r in rows if not r[0].startswith(fixed)]
k = {"m10_oracle": lambda r: "ACCEPTS" not in r[1], "builder_oracle": lambda r: "ACCEPTED" not in r[2],
     "builder_tests": lambda r: not r[3].startswith("rc=0"), "r3_probes": lambda r: f"pattern={pat}" not in r[4]}
r4 = [r for r in mut if r[0].startswith(("rv_rg", "rg1_", "rg3_"))]
for name, f in k.items():
    print(f"{name}: all {sum(map(f, mut))}/{len(mut)}; r4 fix-revert {sum(map(f, r4))}/{len(r4)}; survivors {[r[0] for r in mut if not f(r)]}")
print("union survivors", [r[0] for r in mut if not any(f(r) for f in k.values())])
print("builder-scorers survivors", [r[0] for r in mut if not (k['builder_oracle'](r) or k['builder_tests'](r))])
