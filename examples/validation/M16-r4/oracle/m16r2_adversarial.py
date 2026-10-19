"""M16 r2 adversarial probes (Grok self-validation) against G16 r2 grounded_eval.py.
Usage: PY m16r2_adversarial.py PY TOOL. Targets bypasses of the r2 fixes and over-corrections.
Each case prints HOLDS (contract-consistent) or GAP with observed values; nothing here scores mutants."""
import hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m16_world as W
PY, TOOL = sys.argv[1], sys.argv[2]
tmp = Path(tempfile.mkdtemp(prefix="m16r2adv-")).resolve()
def sh(*a, cwd=tmp):
    p = subprocess.run([PY, TOOL] + [str(x) for x in a], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout + p.stderr
docs = dict(W.V1)
docs["pond.md"] = "# Pond\n\nModel boats may be sailed on the pond at weekends; the warden will answer any questions.\n"
W.write_snapshot(tmp / "snap", docs)
T = {n: (t, hashlib.sha256(t.encode()).hexdigest()) for n, t in docs.items()}
def cite(doc, quote):
    s = T[doc][0].index(quote)
    return {"doc": doc, "start": s, "end": s + len(quote), "quote": quote, "doc_sha256": T[doc][1]}
A = lambda i, q, f, d: {"id": i, "question": q, "expect": {"answerable": True, "facts": f, "support_docs": d}}
res = []
def report(cid, holds, desc, obs):
    res.append(holds); print(f"{cid} {'HOLDS' if holds else 'GAP  '} {desc}\n      observed: {obs}")
def grade(qs, recs, meta=None):
    W.write_questions(tmp / "q.jsonl", qs)
    m = {"kind": "meta", "producer": {"kind": "external_model"}}; m.update(meta or {})
    (tmp / "a.jsonl").write_text(json.dumps(m) + "\n" + "".join(json.dumps(r) + "\n" for r in recs))
    rc, out = sh("evaluate", "--corpus", "snap", "--questions", "q.jsonl", "--answers", "a.jsonl", "--json")
    rep = json.loads(out[out.index("{"):])
    return {r["id"]: r for r in rep["results"]}
# a01: negator moved to another clause keeps negated()==True while asserting the forbidden act
r = grade([A("a01", "When may plot holders light bonfires?", ["April"], ["plots.md"])],
          [{"id": "a01", "abstain": False, "answer": "Plot holders must light bonfires between April and September, not later.",
            "citations": [cite("plots.md", "Plot holders must not light bonfires between April and September.")]}])["a01"]
report("a01", r["verdict"] != "correct_supported", "N1 bypass: the 'not' moved to a trailing clause, meaning reversed", (r["verdict"], r.get("support")))
r = grade([A("a02", "Are hosepipes allowed on the Eastside site?", ["Eastside"], ["plots.md"])],
          [{"id": "a02", "abstain": False, "answer": "Hosepipes are allowed on the Eastside site, nothing else is.",
            "citations": [cite("plots.md", "Hosepipes are not allowed on the Eastside site.")]}])["a02"]
report("a02", r["verdict"] != "correct_supported", "N1 bypass: a different negator word ('nothing') in an added clause", (r["verdict"], r.get("support")))
# a03: control, correct negated paraphrase stays supported (no over-correction)
r = grade([A("a03", "Are hosepipes allowed on the Eastside site?", ["Eastside"], ["plots.md"])],
          [{"id": "a03", "abstain": False, "answer": "Hosepipes aren't allowed on the Eastside site.",
            "citations": [cite("plots.md", "Hosepipes are not allowed on the Eastside site.")]}])["a03"]
report("a03", r["verdict"] == "correct_supported", "control: correct contracted negation (aren't) still supported", (r["verdict"], r.get("support")))
# a04: N7 bypass, forger sets meta.corpus_sha256 to any other value so a fabricated quote is 'stale' again
c = cite("plots.md", "A full plot costs 64 pounds per season."); c.update(quote="A full plot costs 64 pounds per season, water included.", doc_sha256="0" * 64)
r = grade([A("a04", "How much does a full plot cost per season?", ["64 pounds"], ["plots.md"])],
          [{"id": "a04", "abstain": False, "answer": "A full plot costs 64 pounds per season, water included.", "citations": [c]}],
          meta={"corpus_sha256": "f" * 64})["a04"]
report("a04", r["verdict"] == "invalid_citation", "N7 bypass: fabricated quote plus a self-declared other corpus_sha256 in meta", (r["verdict"], r.get("citations")))
# a05: N5 bypass via case-variant path on case-insensitive APFS
W.write_questions(tmp / "q.jsonl", W.QV1[:4]); before = (tmp / "snap" / "plots.md").read_bytes()
sh("answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", "a5.jsonl")
up = tmp / "SNAP"; case_insensitive = up.exists()
rc, out = sh("evaluate", "--corpus", "snap", "--questions", "q.jsonl", "--answers", "a5.jsonl", "--json", "--out", "SNAP/plots.md")
after = (tmp / "snap" / "plots.md").read_bytes()
report("a05", after == before and rc == 2, f"N5 bypass: evaluate --out SNAP/plots.md (case variant; fs case-insensitive={case_insensitive})", (rc, "source unchanged" if after == before else "SOURCE DOCUMENT OVERWRITTEN", out.strip()[:120]))
(tmp / "snap" / "plots.md").write_bytes(before)
rc, out = sh("answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", "Snap/new-answers.jsonl")
report("a06", rc == 2 and not (tmp / "snap" / "new-answers.jsonl").exists(), "N5 bypass: answer --out Snap/new-answers.jsonl writes a new file into the snapshot folder", (rc, sorted(p.name for p in (tmp / "snap").iterdir())))
p = tmp / "snap" / "new-answers.jsonl"
if p.exists(): p.unlink()
os.symlink(tmp / "snap", tmp / "snaplink")
rc, out = sh("evaluate", "--corpus", "snap", "--questions", "q.jsonl", "--answers", "a5.jsonl", "--json", "--out", "snaplink/plots.md")
report("a07", rc == 2 and (tmp / "snap" / "plots.md").read_bytes() == before, "control: --out through a symlink to the snapshot is refused", (rc, out.strip()[:100]))
# a08: N11 over-filter, a legitimate sentence that mentions models and 'answer' is dropped
W.write_questions(tmp / "q8.jsonl", [A("a08", "May model boats be sailed on the pond?", ["weekends"], ["pond.md"])])
rc, out = sh("answer", "--corpus", "snap", "--questions", "q8.jsonl", "--out", "a8.jsonl")
rec = [json.loads(l) for l in (tmp / "a8.jsonl").read_text().splitlines()][1]
report("a08", rec.get("abstain") is False, "N11 over-filter: legit pond rule mentioning model boats and 'answer' is still usable", (rec.get("abstain"), rec.get("reason") or rec.get("answer")))
# a09: N4 over-abstain, an extra harmless modifier
W.write_questions(tmp / "q9.jsonl", [A("a09", "How much does a full allotment plot cost per season?", ["64 pounds"], ["plots.md"])])
sh("answer", "--corpus", "snap", "--questions", "q9.jsonl", "--out", "a9.jsonl")
rec = [json.loads(l) for l in (tmp / "a9.jsonl").read_text().splitlines()][1]
report("a09", rec.get("abstain") is False, "N4 over-abstain: 'full allotment plot' (extra modifier) still answered", (rec.get("abstain"), rec.get("reason") or rec.get("answer")))
# a10: N8, a journal with one complete middle entry deleted (chain broken) is refused, not silently redone
W.write_questions(tmp / "q.jsonl", W.QV1)
(tmp / "f.json").write_text('{"retrieve": {"' + W.QV1[6]["id"] + '": 1}}')
sh("answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", "a10.jsonl", "--journal", "j10.jsonl", "--fault-plan", "f.json")
lines = (tmp / "j10.jsonl").read_text().splitlines()
(tmp / "j10.jsonl").write_text("\n".join(lines[:2] + lines[3:]) + "\n")
rc, out = sh("answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", "a10.jsonl", "--journal", "j10.jsonl", "--resume")
report("a10", rc == 2 and not (tmp / "a10.jsonl").exists(), "N8: journal with a middle entry removed is refused on resume", (rc, out.strip()[:140], len(lines)))
# a11: N9 boundaries
outs = []
for v in ("100", "101", "0", '"2"', "2.0", "{}"):
    (tmp / "f11.json").write_text('{"retrieve": {"b01": %s}}' % v)
    rc, out = sh("answer", "--corpus", "snap", "--questions", "q.jsonl", "--out", f"a11-{len(outs)}.jsonl", "--fault-plan", "f11.json")
    outs.append((v, rc, "Traceback" in out))
ok = [o[1] for o in outs] == [3, 2, 0, 2, 2, 2] and not any(o[2] for o in outs)
report("a11", ok, "N9: fault values 100 (fires, exit 3), 101/'2'/2.0/{} exit 2, 0 no fault", outs)
print("ADVERSARIAL", f"{res.count(True)}/{len(res)} hold")
shutil.rmtree(tmp, ignore_errors=True)
