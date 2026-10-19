#!/usr/bin/env python3
"""Tally M01 r4 teeth (Grok self-validation). Usage: tally_teeth_r4.py TEETH_DIR (merges s0..s3/teeth.json)"""
import json, os, sys
D = sys.argv[1]
rows = sum((json.load(open(os.path.join(D, f"s{i}", "teeth.json"))) for i in range(4)), [])
base = [json.load(open(os.path.join(D, f"s{i}", "baseline.json"))) for i in range(4)]
print("baselines equal:", all(b == base[0] for b in base))
json.dump(rows, open(os.path.join(D, "teeth.json"), "w"), indent=1)
err = [r for r in rows if "error" in r]; ok = [r for r in rows if "error" not in r]
inst = ["oracle", "probes_r2", "probes_r3", "probes_r4", "fixture_tests", "suite"]
real = [r for r in ok if not r["mutant"].endswith("_EQUIV") and r["mutant"] != "control_noop"]
K = lambda r, keys: any(r["kills"][k] for k in keys)
B, G = ["fixture_tests", "suite"], ["oracle", "probes_r2", "probes_r3", "probes_r4"]
for r in ok:
    print(r["mutant"].ljust(30), " ".join(("KILL" if r["kills"][i] else "-").ljust(8) for i in inst))
print("errors:", [(r["mutant"], r["error"][-80:]) for r in err])
n = len(real)
for i in inst: print(f"{i}: {sum(r['kills'][i] for r in real)}/{n}")
print(f"builder (fixture tests or suite): {sum(K(r, B) for r in real)}/{n}")
print(f"fixture tests alone: {sum(r['kills']['fixture_tests'] for r in real)}/{n}")
print(f"grok (oracle or probes): {sum(K(r, G) for r in real)}/{n}")
print(f"union: {sum(K(r, inst) for r in real)}/{n}")
print("survivors:", [r["mutant"] for r in real if not K(r, inst)])
print("controls:", [(r["mutant"], "survived" if not K(r, inst) else "KILLED") for r in ok if r["mutant"].endswith("_EQUIV") or r["mutant"] == "control_noop"])
print("killed only by Grok:", [r["mutant"] for r in real if K(r, G) and not K(r, B)])
print("killed only by builder:", [r["mutant"] for r in real if K(r, B) and not K(r, G)])
r4 = [r for r in real if r["mutant"].startswith("r4_")]
print(f"r4_* : {len(r4)}, union {sum(K(r, inst) for r in r4)}, builder {sum(K(r, B) for r in r4)}, grok {sum(K(r, G) for r in r4)}")
