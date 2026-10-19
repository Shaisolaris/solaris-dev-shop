"""M16 r2 (Grok self-validation): test the builder's claim that 3 surviving mutants are equivalent in r2.
Usage: PY m16r2_equivalence_probes.py PY CANDIDATE MUTANT_DIR. Prints candidate vs mutant observations."""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m16_world as W
PY, CAND, MD = sys.argv[1], sys.argv[2], Path(sys.argv[3])
def sh(tool, *a, cwd):
    p = subprocess.run([PY, tool] + [str(x) for x in a], capture_output=True, text=True, cwd=cwd)
    return p.returncode, (p.stdout + p.stderr).strip(), "Traceback" in p.stderr
def world(t):
    docs = {"buses.md": "# Buses\n\nBus K241 to Heron leaves at 23:10 on weekdays.\nBus K7 to Godwit leaves at 06:15.\n",
            "plots.md": W.V1["plots.md"]}
    W.write_snapshot(t / "snap", docs); return docs
def e1(tool):  # identifiers_not_exact: an identifier the snapshot lacks, with no covered neighbour
    t = Path(tempfile.mkdtemp()); world(t)
    W.write_questions(t / "q.jsonl", [{"id": "i1", "question": "Is K99 the late bus to Heron?", "expect": {"answerable": False}},
                                      {"id": "i2", "question": "When does the K99 bus to Heron leave?", "expect": {"answerable": False}}])
    rc, out, tb = sh(tool, "answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", "a.jsonl", cwd=t)
    recs = [json.loads(l) for l in (t / "a.jsonl").read_text().splitlines()[1:]] if (t / "a.jsonl").exists() else []
    return rc, [(r["id"], r["abstain"], r.get("reason") or r.get("answer")) for r in recs]
def e2(tool):  # invalid_input_writes: a fresh run with an existing journal
    t = Path(tempfile.mkdtemp()); world(t); W.write_questions(t / "q.jsonl", W.QV1[:3])
    (t / "j.jsonl").write_text("keep me\n")
    rc, out, tb = sh(tool, "answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", "a.jsonl", "--journal", "j.jsonl", cwd=t)
    return rc, tb, (t / "j.jsonl").read_text() == "keep me\n", (t / "a.jsonl").exists(), out.splitlines()[-1][:110] if out else ""
def e3(tool):  # numbers_not_checked: an answer number that no quote has
    t = Path(tempfile.mkdtemp()); docs = world(t); txt = docs["plots.md"]; q = "A full plot costs 64 pounds per season."
    s = txt.index(q); c = {"doc": "plots.md", "start": s, "end": s + len(q), "quote": q, "doc_sha256": hashlib.sha256(txt.encode()).hexdigest()}
    W.write_questions(t / "q.jsonl", [{"id": "n", "question": "How much does a full plot cost per season?", "expect": {"answerable": True, "facts": ["64 pounds"], "support_docs": ["plots.md"]}}])
    out = []
    for ans in ("A full plot costs 65 pounds per season.", "A full plot costs 64 pounds per season, or 70 pounds late."):
        (t / "a.jsonl").write_text(json.dumps({"kind": "meta", "producer": {"kind": "external_model"}}) + "\n" + json.dumps({"id": "n", "abstain": False, "answer": ans, "citations": [c]}) + "\n")
        rc, o, tb = sh(tool, "evaluate", "--corpus", "snap", "--questions", "q.jsonl", "--answers", "a.jsonl", "--json", cwd=t)
        r = json.loads(o[o.index("{"):])["results"][0]; out.append((ans, r["verdict"], (r.get("support") or {}).get("problem")))
    return out
for name, fn in (("identifiers_not_exact", e1), ("invalid_input_writes", e2), ("numbers_not_checked", e3)):
    a, b = fn(CAND), fn(str(MD / name / "grounded_eval.py"))
    verdict_same = (a == b) if name != "numbers_not_checked" else [x[1] for x in a] == [x[1] for x in b]
    print(f"== {name}: {'EQUIVALENT on this probe' if verdict_same else 'NOT EQUIVALENT (mutant distinguishable)'}")
    print("   candidate:", a); print("   mutant:   ", b)
