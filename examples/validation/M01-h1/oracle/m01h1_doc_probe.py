#!/usr/bin/env python3
"""M01 h1 doc probe (Grok self-validation, not independent review). Checks each example the G01 h1 ASSURANCE.md text
gives, through the quality_os.py run CLI: matched spellings of a kind word are refused (INVALID_PACKET, non-zero),
the listed unmatched spellings are evaluated as an ordinary packet. Usage: PY m01h1_doc_probe.py ENGINE OUT.json"""
import json, os, subprocess, sys, tempfile
ENGINE = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; ROWS = []
MISS = {"risk_level": "elevated", "dimensions": ["security"], "completed_gates": [], "evidence": {}}
def run(extra):
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, "f.json"); json.dump(dict(MISS, **extra), open(f, "w"))
        p = subprocess.run([sys.executable, ENGINE, "run", f], capture_output=True, text=True, cwd=t,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=60)
        return p.returncode, (p.stdout + p.stderr)
CASES = [("legal", True), ("planted_defect", True), ("Planted-Defect", True), ("PLANTED DEFECT", True), ("planted-defect", True),
         ("plantd_defect", False), ("planted.defect", False), ("l\u0435gal", False), ("le\u200bgal", False)]
for v, refused in CASES:
    rc, out = run({"category": v})
    inv = "INVALID_PACKET" in out
    ok = inv if refused else not inv
    ROWS.append({"row": "category=%r documented %s" % (v, "matched (refused)" if refused else "not matched (ordinary field)"),
                 "pass": ok, "detail": {"rc": rc, "invalid_packet": inv}})
    print(("PASS " if ok else "FAIL ") + ROWS[-1]["row"] + " rc=%d invalid=%s" % (rc, inv))
for k in ("Fixture_Kind", "fixture-kind", "FIXTURE KIND"):
    rc, out = run({k: "legal"}); inv = "INVALID_PACKET" in out
    ROWS.append({"row": "misspelled kind key %r caught by the near-miss check" % k, "pass": inv, "detail": {"rc": rc, "invalid_packet": inv}})
    print(("PASS " if inv else "FAIL ") + ROWS[-1]["row"] + " rc=%d" % rc)
json.dump({"rows": ROWS}, open(OUT, "w"), indent=1, ensure_ascii=True)
print("M01H1 DOC PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
