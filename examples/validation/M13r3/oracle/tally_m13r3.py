#!/usr/bin/env python3
"""Tally M13 r3 teeth TSV (Grok self-validation). Usage: python tally_m13r3.py TSV"""
import csv, sys
rows = list(csv.reader(open(sys.argv[1]), delimiter="\t"))[1:]
fixed = ("candidate", "r2-", "stub-", "builder-")
for r in rows:
    if r[0].startswith(fixed):
        print("SUBJECT", r[0], "|", r[1][:60], "|", r[2][:60], "|", r[3][:45], "|", r[4][:60])
mut = [r for r in rows if not r[0].startswith(fixed)]
k = {"m13_oracle": lambda r: "ACCEPTS" not in r[1], "builder_oracle": lambda r: not r[2].strip().startswith("14/14"),
     "builder_tests": lambda r: not r[3].startswith("rc=0"), "r3_probes": lambda r: "SUMMARY OK" not in r[4]}
r3 = [r for r in mut if r[0].startswith(("rv_rt", "rt_", "rv_rd", "rd_"))]
for name, f in k.items():
    print(f"{name}: all {sum(map(f, mut))}/{len(mut)}; r3 fix-revert {sum(map(f, r3))}/{len(r3)}; survivors {[r[0] for r in mut if not f(r)]}")
print("union survivors", [r[0] for r in mut if not any(f(r) for f in k.values())])
print("builder-scorers (oracle or tests) survivors", [r[0] for r in mut if not (k['builder_oracle'](r) or k['builder_tests'](r))])
