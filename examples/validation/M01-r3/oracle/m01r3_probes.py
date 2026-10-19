#!/usr/bin/env python3
"""M01 r3 probes (Grok self-validation) for G01 r2 (1621c82). Each case runs on the engine given; run on deb06f6 too
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
tmp = Path(tempfile.mkdtemp(prefix="m01r3p-", dir="/tmp")).resolve(); res = []
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
# z01-z03: G05 packet fields on an unwrapped packet (regression check of the S1 fix)
p1 = dict(DONE, legal_text=OKTXT, requested_actions=["summarize the statute"], sources=SRC)
o = run("z01", p1); report("z01", o[1] is True, "unwrapped packet with legal_text + requested_actions + sources (all G05 packet fields), benign text: passes as a packet", o)
o = run("z02", dict(DONE, requested_actions=["summarize the statute"])); report("z02", o[1] is True, "unwrapped packet with requested_actions only: passes as a packet", o)
o = run("z03", {"fixture_kind": "packet", "packet": p1}); report("z03", o[1] is True, "control: the z01 packet wrapped with fixture_kind packet passes", o)
o = run("z04", dict(DONE, legal_text=BAD, requested_actions=["file the lawsuit"], sources=SRC, expectations={"outcome": "fail_gate"}))
report("z04", True, "unwrapped negative legal packet (blocked text + requested_actions) with a fail_gate expectation", o, graded=False)
# z05-z07: residual variants of S1
o = run("z05", {"fixture_type": "LEGAL", "text": BAD}); report("z05", o[1] is not True, "kind synonym with upper-case value on blocked legal text is not a pass", o)
o = run("z06", {"category": "legal", "text": BAD}); report("z06", o[1] is not True, "kind under a non kind/type name ('category') on blocked legal text is not a pass", o)
pd = {"defect_kind": "security", "severity": "S1", "title": "IDOR", "evidence": ["probe"], "accountable_role": "security-auditor"}
ref = run("z07ref", dict(pd, fixture_kind="planted_defect"))
for cid, k, v in (("z07", "fixture_type", "planted_defect"), ("z08", "fixture_type", "Planted_Defect"), ("z09", "category", "planted_defect")):
    o = run(cid, dict(pd, **{k: v}))
    report(cid, o[2] == ["INVALID_PACKET"] or (o[1], o[2]) == (ref[1], ref[2]), f"bare planted defect with kind under {k!r}={v!r}: refused or same as the fixture_kind form {ref[1:3]}", o)
pd2 = {k: v for k, v in pd.items() if k != "evidence"}; ref2 = run("z13ref", dict(pd2, fixture_kind="planted_defect"))
for cid, k, v in (("z13", "fixture_type", "Planted_Defect"), ("z14", "category", "planted_defect")):
    o = run(cid, dict(pd2, **{k: v}))
    report(cid, o[2] == ["INVALID_PACKET"] or (o[1], o[2]) == (ref2[1], ref2[2]), f"bare planted defect without evidence, kind under {k!r}={v!r}: refused or same as the fixture_kind form {ref2[1:3]}", o)
# z10-z12: S2 variants
s = tmp / "s10"; s.mkdir(); (s / "good.json").write_text(json.dumps({"fixture_kind": "packet", "packet": DONE})); os.chmod(s, 0)
rc, out, tb = cli("suite", str(s)); os.chmod(s, 0o755)
report("z10", out.get("ok") is not True and not tb, "suite whose root folder is unreadable is not ok and has no traceback", (rc, out.get("ok"), out.get("passed"), out.get("failed"), out.get("error"), tb))
s = tmp / "s11"; (s / "a" / "b").mkdir(parents=True); (s / "good.json").write_text(json.dumps({"fixture_kind": "packet", "packet": DONE}))
(s / "a" / "b" / "x.json").write_text("{}"); os.chmod(s / "a" / "b", 0)
rc, out, tb = cli("suite", str(s)); os.chmod(s / "a" / "b", 0o755)
named = [r.get("path") for r in out.get("results", []) if not r.get("ok")]
report("z11", out.get("ok") is not True and any(str(p).endswith("a/b") for p in named), "suite with an unreadable folder two levels down is not ok and names that folder", (rc, out.get("ok"), out.get("passed"), out.get("failed"), named))
s = tmp / "s12"; s.mkdir(); (s / "good.json").write_text(json.dumps({"fixture_kind": "packet", "packet": DONE})); (s / "locked.json").write_text(json.dumps({"fixture_kind": "packet", "packet": DONE})); os.chmod(s / "locked.json", 0)
rc, out, tb = cli("suite", str(s)); os.chmod(s / "locked.json", 0o644)
report("z12", out.get("ok") is not True and not tb, "suite with an unreadable fixture FILE is not ok and has no traceback", (rc, out.get("ok"), out.get("passed"), out.get("failed"), tb))
print(f"PROBES-M01R3 {sum(res)}/{len(res)} hold")
shutil.rmtree(tmp, ignore_errors=True)
