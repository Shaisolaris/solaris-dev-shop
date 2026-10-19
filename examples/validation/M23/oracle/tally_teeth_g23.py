#!/usr/bin/env python3
"""Tally M23 r1 teeth (Grok self-validation). Usage: tally_teeth_g23.py teeth.json"""
import json, sys
rows = json.load(open(sys.argv[1]))
real = [r for r in rows if not r["mutant"].endswith("_EQUIV")]
k = lambda r, i: bool(r["kills"][i])
inst = ["probes", "prep", "builder_tests", "builder_oracle"]
print("mutant".ljust(30), " ".join(i[:13].ljust(13) for i in inst))
for r in rows:
    print(r["mutant"].ljust(30), " ".join(("KILL" if k(r, i) else "-").ljust(13) for i in inst))
n = len(real)
for i in inst:
    print(f"{i}: {sum(k(r, i) for r in real)}/{n}")
print(f"builder (tests or oracle): {sum(k(r,'builder_tests') or k(r,'builder_oracle') for r in real)}/{n}")
print(f"grok (probes or prep): {sum(k(r,'probes') or k(r,'prep') for r in real)}/{n}")
print(f"union: {sum(any(k(r, i) for i in inst) for r in real)}/{n}")
print("survivors:", [r["mutant"] for r in real if not any(k(r, i) for i in inst)])
print("EQUIV controls:", [(r["mutant"], "survived" if not any(k(r, i) for i in inst) else "KILLED") for r in rows if r["mutant"].endswith("_EQUIV")])
print("killed only by Grok:", [r["mutant"] for r in real if (k(r,'probes') or k(r,'prep')) and not (k(r,'builder_tests') or k(r,'builder_oracle'))])
print("killed only by builder:", [r["mutant"] for r in real if not (k(r,'probes') or k(r,'prep')) and (k(r,'builder_tests') or k(r,'builder_oracle'))])
