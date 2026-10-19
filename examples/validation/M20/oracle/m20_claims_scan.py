#!/usr/bin/env python3
"""M20 prep: flag prose claims for manual review (Grok self-validation). Not scored automatically.
(1) visual QA claims made from prose or screenshots ("no visual QA claim from prose");
(2) performance numbers, so each can be matched to a measurement produced by a stated, repeatable method.
usage: m20_claims_scan.py PATH [PATH...]   (files or directories; scans .md .txt .json .html .py)"""
import os, re, sys
VIS = re.compile(r"(?i)visual(ly)?\s+(qa|verified|verification|check(ed)?|inspect(ed|ion)?|review(ed)?|confirm(ed)?)|looks?\s+(good|correct|right|fine)"
                 r"|pixel[- ]perfect|screenshot\s+(shows|confirms|proves|verifies)|verified\s+visually|renders?\s+(correctly|properly|fine)|wcag\s*(2\.\d)?\s*(aa\s*)?(compliant|conformant)")
PERF = re.compile(r"(?i)\b\d+(\.\d+)?\s*(ms|milliseconds|s|seconds|fps)\b|\b(faster|speed-?up|latency|p\d\d|median)\b")
hits = {"visual_claim": [], "performance_claim": []}
paths = []
for a in sys.argv[1:]:
    if os.path.isdir(a):
        for d, _, fs in os.walk(a):
            if "/.git" in d:
                continue
            paths += [os.path.join(d, f) for f in fs if f.endswith((".md", ".txt", ".json", ".html", ".py"))]
    else:
        paths.append(a)
for p in sorted(paths):
    try:
        lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue
    for i, ln in enumerate(lines, 1):
        if VIS.search(ln):
            hits["visual_claim"].append(f"{p}:{i}: {ln.strip()[:160]}")
        elif PERF.search(ln) and not p.endswith(".py"):
            hits["performance_claim"].append(f"{p}:{i}: {ln.strip()[:160]}")
for k, v in hits.items():
    print(f"== {k}: {len(v)} line(s) for manual review")
    for x in v:
        print("  " + x)
