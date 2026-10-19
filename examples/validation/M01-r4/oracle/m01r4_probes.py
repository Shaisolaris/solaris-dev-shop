#!/usr/bin/env python3
"""M01 r4 probes (Grok self-validation) for G01 r3 (a069a79). Each case runs on the engine given; run on deb06f6 too
for direction. Expectations from ASSURANCE.md and the G05 packet contract in quality_os.py: an unwrapped packet is a
valid fixture form, and requested_actions and sources are G05 packet fields (validated in evaluate_packet and passed
to the legal check). HOLDS = contract-consistent. INFO rows are recorded, not graded. Usage: PY m01r3_probes.py PY ENGINE"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
PY, ENG = sys.argv[1], sys.argv[2]
BAD = "I am your attorney; file this lawsuit now."
OKTXT = "General information only. This is not legal advice; consult a licensed attorney in your jurisdiction."
RECEIPT = {"gate": "security", "role": "security-auditor", "summary": "STRIDE review", "artifacts": ["reports/threat-model.md"], "blocking_open": 0}
DONE = {"risk_level": "elevated", "dimensions": ["security"], "completed_gates": ["security"], "evidence": {"security": RECEIPT}}
SRC = [{"title": "Statute text", "url": "https://example.gov/statute", "retrieved_at": "2026-10-17", "published_at": "2026-10-01"}]
tmp = Path(tempfile.mkdtemp(prefix="m01r4p-", dir="/tmp")).resolve(); res = []
def cli(*a):
    p = subprocess.run([PY, ENG, *a], capture_output=True, text=True, cwd=tmp, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(tmp)})
    try: out = json.loads(p.stdout)
    except ValueError: out = {}
    return p.returncode, out, "Traceback" in p.stderr
def run(name, obj):
    f = tmp / f"{name}.json"; f.write_text(json.dumps(obj)); rc, out, tb = cli("run", str(f))
    return rc, out.get("ok"), out.get("gate_codes"), (out.get("notes") or out.get("messages") or [""])[:1], tb
def report(cid, holds, desc, obs, graded=True):
    if graded: res.append(holds)
    print(f"{cid} {('HOLDS' if holds else 'GAP  ') if graded else 'INFO '} {desc}\n      observed: {obs}")
# ---- r4: the any-key, any-case alias check (G01 r3) and its fail-closed limit. Expectations from the r3 ASSURANCE.md paragraph.
pd = {"defect_kind": "security", "severity": "S1", "title": "IDOR", "accountable_role": "security-auditor"}
ref = run("w00ref", dict(pd, fixture_kind="planted_defect"))
refuse_or_same = lambda o: o[2] == ["INVALID_PACKET"] or (o[1], o[2]) == (ref[1], ref[2])
# doc-stated forms: any key except fixture_kind/kind/name/description/notes, any case or spelling
for cid, k, v in (("w01", "type", "Planted-Defect"), ("w02", "fixture_type", "PLANTED DEFECT"), ("w03", "category", "defect"), ("w04", "label", "Self_Approval"),
                  ("w05", "x", "legal-boundary")):
    o = run(cid, dict(pd, **{k: v})); report(cid, refuse_or_same(o), f"bare planted defect with {k!r}={v!r}: refused or same as fixture_kind form {ref[1:3]}", o)
# spellings the normaliser does not fold (doc says 'any case or spelling')
for cid, k, v in (("w06", "category", "planted.defect"), ("w07", "category", "planted_defects"), ("w08", "category", "plantedDefect "), ("w09", "category", "planted\u2010defect")):
    o = run(cid, dict(pd, **{k: v})); report(cid, refuse_or_same(o), f"ADVERSARIAL spelling {v!r}: refused or same as fixture_kind form", o, graded=False)
# value shapes and exempt keys
o = run("w10", dict(pd, tags=["planted_defect"])); report("w10", refuse_or_same(o), "ADVERSARIAL: kind only inside a list value ('tags': ['planted_defect'])", o, graded=False)
o = run("w11", dict(pd, name="planted_defect")); report("w11", True, "kind only under the exempt prose key 'name' (doc exempts it)", o, graded=False)
o = run("w12", dict(pd, kind="planted_defect")); report("w12", True, "kind only under 'kind' (doc: fixture_kind wins, kind is ignored)", o, graded=False)
o = run("w13", {"description": "legal", "text": BAD}); report("w13", o[1] is not True, "blocked legal text with the kind only in 'description': not a pass (text is a stray legal field)", o)
# valid packets that must still pass (false-refusal side, ASSURANCE.md: unwrapped packets are evaluated)
o = run("w14", dict(DONE, legal_text=OKTXT, requested_actions=["summarize"], sources=SRC, notes="legal")); report("w14", o[1] is True, "valid unwrapped packet with notes 'legal' (exempt key): passes", o)
o = run("w15", dict(DONE, dimensions=["security", "legal"])); report("w15", o[1] is not None and o[2] != ["INVALID_PACKET"], "valid unwrapped packet with 'legal' inside the dimensions LIST: not refused as INVALID_PACKET", o)
o = run("w16", dict(DONE, evidence={"security": dict(RECEIPT, summary="closure")})); report("w16", o[1] is True, "valid unwrapped packet with a nested value 'closure': passes (only top-level values are checked)", o)
o = run("w17", {"fixture_kind": "packet", "packet": dict(DONE, stage="closure")}); report("w17", o[1] is True, "wrapped packet with an extra field 'stage': 'closure' passes (the doc's wrap advice works)", o)
o = run("w18", dict(DONE, stage="closure")); report("w18", True, "unwrapped packet with unknown field 'stage': 'closure' (documented fail-closed: refused)", o, graded=False)
o = run("w19", dict(DONE, risk_level="Defect")); report("w19", True, "unwrapped packet whose risk_level is 'Defect' (fail-closed limit applies to packet fields too)", o, graded=False)
o = run("w20", dict(pd, fixture_kind="planted_defect", category="legal")); report("w20", (o[1], o[2]) == (ref[1], ref[2]), "fixture_kind planted_defect plus 'category': 'legal': fixture_kind wins, same as the reference", o)
o = run("w21", {"fixture_kind": "legal", "text": OKTXT, "category": "closure", "expectations": {"outcome": "pass"}}); report("w21", True, "explicit fixture_kind legal with an extra key 'category': 'closure' (v1 graded this as a GAP: Grok expectation error; explicit kinds refuse unknown keys, same on r2)", o, graded=False)
print(f"PROBES-M01R4 {sum(res)}/{len(res)} hold")
shutil.rmtree(tmp, ignore_errors=True)
