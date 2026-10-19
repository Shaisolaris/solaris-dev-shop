#!/usr/bin/env python3
"""M01 r2 adversarial probes (Grok self-validation) against the G01 repair (deb06f6). Findings only; nothing is scored.
Drives `quality_os.py run` / `suite` through the CLI in temp dirs. HOLDS = contract-consistent, GAP = false pass or
silent skip. Usage: PY m01r2_adversarial.py PY ENGINE"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
PY, ENG = sys.argv[1], sys.argv[2]
BAD_LEGAL = "I am your attorney; file this lawsuit now."
FINDING = {"finding_id": "f-9", "defect_kind": "security", "severity": "S1", "title": "IDOR",
           "evidence": ["probe: other tenant record returned"], "accountable_role": "security-auditor",
           "reporter_role": "qa-engineer", "status": "open", "verifier_role": "code-reviewer"}
RECEIPT = {"gate": "security", "role": "security-auditor", "summary": "STRIDE review",
           "artifacts": ["reports/threat-model.md"], "blocking_open": 0}
DONE = {"risk_level": "elevated", "dimensions": ["security"], "completed_gates": ["security"], "evidence": {"security": RECEIPT}}
MISS = {"risk_level": "elevated", "dimensions": ["security"], "completed_gates": [], "evidence": {}}
tmp = Path(tempfile.mkdtemp(prefix="m01r2adv-")).resolve()
res = []


def cli(*a):
    p = subprocess.run([PY, ENG, *a], capture_output=True, text=True, cwd=tmp,
                       env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(tmp)})
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = {}
    return p.returncode, out, "Traceback" in p.stderr


def run(name, obj):
    f = tmp / f"{name}.json"
    f.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)
    rc, out, tb = cli("run", str(f))
    return rc, out.get("ok"), out.get("gate_codes"), tb


def report(cid, holds, desc, obs):
    res.append(holds)
    print(f"{cid} {'HOLDS' if holds else 'GAP  '} {desc}\n      observed: {obs}")


# y01-y03: a legal payload whose kind key is a synonym (below the 0.8 near-miss ratio) or absent becomes a packet
for cid, obj, d in (("y01", {"fixture_type": "legal", "text": BAD_LEGAL}, "kind key 'fixture_type' (synonym) on blocked legal text"),
                    ("y02", {"type": "legal", "legal_text": BAD_LEGAL, "requested_actions": ["file the lawsuit"]}, "kind key 'type' on blocked legal_text + requested_actions"),
                    ("y03", {"text": BAD_LEGAL}, "legal text with no kind key at all")):
    rc, ok, gc, tb = run(cid, obj)
    report(cid, ok is not True, f"F1 residual: {d} is not a pass", (rc, ok, gc, "traceback" if tb else ""))
# y04: control, the same synonym on a closure fixture is caught by the stray-field rule
rc, ok, gc, tb = run("y04", {"fixture_type": "closure", "finding": FINDING, "closer_role": "security-auditor", "expect_blocked": False})
report("y04", ok is not True and gc == ["INVALID_PACKET"], "control: synonym kind key on a closure fixture is INVALID_PACKET", (rc, ok, gc))
# y05: control, documented note keys are accepted on a wrapped packet
rc, ok, gc, tb = run("y05", {"fixture_kind": "packet", "packet": DONE, "notes": "passing security packet", "description": "d", "name": "n"})
report("y05", ok is True, "control: notes/description/name accepted on a wrapped passing packet", (rc, ok, gc))
# y06: control, a wrapped blocked packet with a fail_gate expectation and the right code still passes the suite entry
rc, ok, gc, tb = run("y06", {"fixture_kind": "packet", "packet": MISS, "expectations": {"outcome": "fail_gate", "gate_codes": ["MISSING_SPECIALIST_GATE"]}})
report("y06", ok is True, "control: negative packet fixture with its firing gate passes", (rc, ok, gc))
# y07: an unreadable subdirectory holding a failing fixture
s = tmp / "suite7"; (s / "locked").mkdir(parents=True)
(s / "good.json").write_text(json.dumps({"fixture_kind": "packet", "packet": DONE}))
(s / "locked" / "bad.json").write_text(json.dumps({"fixture_kind": "packet", "packet": MISS}))
os.chmod(s / "locked", 0)
rc, out, tb = cli("suite", str(s))
os.chmod(s / "locked", 0o755)
report("y07", out.get("ok") is not True, "F5 residual: suite with an unreadable subfolder (holding a failing fixture) is not ok", (rc, out.get("ok"), out.get("passed"), out.get("failed"), out.get("error")))
# y08: a symlinked fixture FILE pointing outside the suite dir (reported only)
s8 = tmp / "suite8"; s8.mkdir(); (tmp / "outside.json").write_text(json.dumps({"fixture_kind": "packet", "packet": DONE}))
os.symlink(tmp / "outside.json", s8 / "linked.json")
rc, out, tb = cli("suite", str(s8))
print(f"y08 INFO  suite counts a symlinked fixture file from outside the folder: ok={out.get('ok')} passed={out.get('passed')} failed={out.get('failed')}")
# y09: a bare planted defect (no 'defect' wrapper) with a misspelled defect field
rc, ok, gc, tb = run("y09", {"fixture_kind": "planted_defect", "defect_kind": "security", "severty": "S1", "title": "IDOR",
                             "evidence": ["probe"], "accountable_role": "security-auditor", "expectations": {"outcome": "fail_gate"}})
print(f"y09 INFO  bare planted defect with misspelled 'severty': rc={rc} ok={ok} gates={gc}")
print(f"ADVERSARIAL-M01R2 {sum(res)}/{len(res)} hold")
shutil.rmtree(tmp, ignore_errors=True)
