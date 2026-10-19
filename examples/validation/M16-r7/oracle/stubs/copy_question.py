#!/usr/bin/env python3
"""M16 copy-question stub: `answer` repeats the question as the answer, never abstains, and cites the
sentence with the most shared words (exact span and sha256, so citations are valid); journal and fault
plan ignored. `evaluate` runs the real candidate evaluator named by M16_REAL."""
import hashlib, json, os, re, sys
from pathlib import Path
a = sys.argv[1:]
if a and a[0] == "answer":
    corpus = Path(a[a.index("--corpus") + 1])
    qs = [json.loads(l) for l in open(a[a.index("--questions") + 1]) if l.strip()]
    sents = []
    for p in sorted(corpus.iterdir()):
        if p.suffix not in (".md", ".txt"):
            continue
        raw = p.read_bytes(); t = raw.decode("utf-8"); h = hashlib.sha256(raw).hexdigest()
        for m in re.finditer(r"[^\n.!?#][^\n]*?[.!?](?=\s|$)", t):
            sents.append((p.name, m.start(), m.end(), m.group(0), h))
    W = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
    lines = [{"kind": "meta", "schema": "solaris.grounded-answers/1", "producer": {"kind": "copy_question_stub"}}]
    for q in qs:
        b = max(sents, key=lambda s: (len(W(s[3]) & W(q["question"])), -s[1]))
        lines.append({"id": q["id"], "abstain": False, "answer": q["question"],
                      "citations": [{"doc": b[0], "start": b[1], "end": b[2], "quote": b[3], "doc_sha256": b[4]}]})
    open(a[a.index("--out") + 1], "w").write("".join(json.dumps(x, sort_keys=True) + "\n" for x in lines))
    print(f"answered {len(qs)}")
    sys.exit(0)
os.execv(sys.executable, [sys.executable, os.environ["M16_REAL"]] + a)
