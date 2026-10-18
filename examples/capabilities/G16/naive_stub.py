#!/usr/bin/env python3
"""G16 naive candidate: the usual RAG-eval shortcuts, on purpose. Must fail the oracle.

answer: always answers with the sentence that shares the most words with the question (never
abstains), offsets correct; ignores the fault plan and the journal.
evaluate: trusts citations without opening the source, counts any cited answer as correct and any
abstention as correct, labels everything "deterministic".
"""
import json
import re
import sys
from pathlib import Path

args = sys.argv[1:]
cmd = args[0]
opt = lambda k: args[args.index(k) + 1] if k in args else None
words = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
qs = [json.loads(l) for l in open(opt("--questions")) if l.strip()]
if cmd == "answer":
    sents = []
    for p in sorted(Path(opt("--corpus")).iterdir()):
        t = p.read_text()
        pos = 0
        for line in t.split("\n"):
            if line and not line.startswith("#"):
                sents.append((p.name, pos, pos + len(line), line))
            pos += len(line) + 1
    out = [{"kind": "meta", "producer": {"kind": "deterministic_baseline"}}]
    for q in qs:
        best = max(sents, key=lambda s: len(words(s[3]) & words(q["question"])))
        out.append({"id": q["id"], "abstain": False, "answer": best[3],
                    "citations": [{"doc": best[0], "start": best[1], "end": best[2], "quote": best[3]}]})
    Path(opt("--out")).write_text("".join(json.dumps(x) + "\n" for x in out))
    sys.exit(0)
recs = {r.get("id"): r for r in (json.loads(l) for l in open(opt("--answers")) if l.strip())}
rows = []
for q in qs:
    r = recs.get(q["id"], {})
    ok = r.get("abstain") or bool(r.get("citations"))
    rows.append({"id": q["id"], "verdict": "correct_supported" if ok else "uncited",
                 "citations": [{"status": "valid"} for _ in r.get("citations", [])]})
rep = {"schema": "solaris.grounded-eval-report/1", "status": "pass" if all(x["verdict"] == "correct_supported" for x in rows) else "fail",
       "results": rows, "counts": {}, "provenance": {"evidence": "deterministic", "evaluator": "model judge"}}
if opt("--out"):
    Path(opt("--out")).write_text(json.dumps(rep))
print(json.dumps(rep))
sys.exit(0 if rep["status"] == "pass" else 1)
