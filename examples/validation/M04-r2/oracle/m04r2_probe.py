#!/usr/bin/env python3
"""M04 r2 probe (Grok self-validation, not independent review). Black-box CLI checks of owner changes on a G04 work
order, written for this pass from the root finding (a same-revision owner change reused a brief naming the old owner)
and the contract (one delivery per order revision; the delivery is the effect that must never be duplicated).
Usage: PY m04r2_probe.py REPO OUT.json [--old-repo REPO_AT_314b4db]"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
OLD = Path(sys.argv[sys.argv.index("--old-repo") + 1]).resolve() if "--old-repo" in sys.argv else None
REL = "employees/infrastructure/fleet-dispatcher/handoff.py"; TOOL = REPO / REL
FIX = REPO / "examples/capabilities/G04/fixtures"; ROWS = []
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
def world():
    d = Path(tempfile.mkdtemp(prefix="m04r2-")) / "w"; shutil.copytree(str(FIX), str(d)); return d
def owner(d, who, name="order.json"):
    p = d / name; o = json.loads(p.read_text()); o["owner"] = who; p.write_text(json.dumps(o, indent=2) + "\n"); return o
def run(d, *a, tool=TOOL):
    p = subprocess.run([sys.executable, str(tool)] + list(a), cwd=str(d), capture_output=True, text=True, env=ENV, timeout=300)
    return p.returncode, p.stdout + p.stderr
def ledger(d):
    p = d / "outbox/ledger.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def briefs(d): return sorted((d / ".handoff").rglob("HANDOFF-BRIEF.md"))
def btext(d): return "\n".join(b.read_text() for b in briefs(d))
def row(rid, desc, ok, detail):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "detail": detail})
    print("%s %s %s %s" % (rid, "PASS" if ok else "FAIL", desc, json.dumps(detail, default=str)[:300]))
A0 = json.loads((FIX / "order.json").read_text())["owner"]; NEW = "support: Someone Else"

# Q1 the root finding: owner changed at the brief handoff point, before delivery
d = world(); r1 = run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief")[0]; owner(d, NEW)
r2, o2 = run(d, "run", "order.json", "--worker", "ben"); L = ledger(d); t = btext(d)
row("Q1", "owner changed after --stop-after brief: resume exits 0, brief names only the new owner, one delivery naming the new owner and that brief",
    r1 == 3 and r2 == 0 and NEW in t and A0 not in t and len(L) == 1 and L[0].get("owner") == NEW and "stale" in o2,
    {"rc": [r1, r2], "ledger_owners": [x.get("owner") for x in L], "old_in_brief": A0 in t})
# Q2 owner changed after activate only
d = world(); r1 = run(d, "run", "order.json", "--worker", "ana", "--stop-after", "activate")[0]; owner(d, NEW)
r2, _ = run(d, "run", "order.json", "--worker", "ben"); L = ledger(d); t = btext(d)
row("Q2", "owner changed after --stop-after activate: brief and the one delivery name the new owner", r1 == 3 and r2 == 0 and NEW in t and A0 not in t and [x.get("owner") for x in L] == [NEW],
    {"rc": [r1, r2], "ledger_owners": [x.get("owner") for x in L]})
# Q3 owner changed after the revision was delivered
d = world(); r1 = run(d, "run", "order.json", "--worker", "ana")[0]; owner(d, NEW)
r2, o2 = run(d, "run", "order.json", "--worker", "ben"); L = ledger(d)
row("Q3", "owner changed after revision 1 was delivered: no second delivery of revision 1 (refused, exit 2, ledger stays 1)",
    r1 == 0 and r2 == 2 and len(L) == 1 and L[0].get("owner") == A0, {"rc": [r1, r2], "ledger": [(x.get("revision"), x.get("owner")) for x in L], "out": o2[-200:]})
# Q4 crash after the delivery effect, then the owner is changed and another worker resumes
d = world(); r1 = run(d, "run", "order.json", "--worker", "ana", "--fail-at", "deliver")[0]; owner(d, NEW)
r2, o2 = run(d, "run", "order.json", "--worker", "ben"); L = ledger(d)
row("Q4", "crash after delivery (75), owner changed, resume: revision 1 is not delivered a second time (exit 2, ledger stays 1)",
    r1 == 75 and r2 == 2 and len(L) == 1, {"rc": [r1, r2], "ledger": [(x.get("revision"), x.get("owner")) for x in L], "out": o2[-200:]})
# Q5 owner changed and changed back before delivery
d = world(); run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief"); owner(d, NEW)
ra = run(d, "run", "order.json", "--worker", "ben", "--stop-after", "brief")[0]; owner(d, A0)
rb = run(d, "run", "order.json", "--worker", "cy")[0]; L = ledger(d); t = btext(d)
row("Q5", "owner changed and changed back before delivery: brief names the original owner, one delivery", ra == 3 and rb == 0 and A0 in t and NEW not in t and [x.get("owner") for x in L] == [A0],
    {"rc": [ra, rb], "ledger_owners": [x.get("owner") for x in L]})
# Q6 control: same owner rerun after delivery reuses everything
d = world(); run(d, "run", "order.json", "--worker", "ana"); r2, o2 = run(d, "run", "order.json", "--worker", "ben")
row("Q6", "control: rerun with the same owner after delivery exits 0, all reused, ledger 1", r2 == 0 and o2.count("reused") == 3 and len(ledger(d)) == 1, {"rc": r2, "ledger": len(ledger(d))})
# Q7 control: a new revision may change the owner and delivers once more, superseding revision 1
d = world(); run(d, "run", "order.json", "--worker", "ana"); owner(d, NEW, "order-rev2.json")
r2, o2 = run(d, "run", "order-rev2.json", "--worker", "cy"); L = ledger(d)
row("Q7", "control: revision 2 with a new owner delivers once (ledger 2, revision 1 noted superseded)",
    r2 == 0 and [(x.get("revision"), x.get("owner")) for x in L] == [(1, A0), (2, NEW)] and "superseded" in o2, {"rc": r2, "ledger": [(x.get("revision"), x.get("owner")) for x in L]})
# Q8 unicode owner change before delivery
d = world(); run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief"); U = "lead: Zo\u00eb \u674e (\u0645\u062f\u064a\u0631)"; owner(d, U)
r2 = run(d, "run", "order.json", "--worker", "ben")[0]; t = btext(d)
row("Q8", "non-ASCII owner set before delivery is written exactly into the brief and the ledger", r2 == 0 and U in t and [x.get("owner") for x in ledger(d)] == [U], {"rc": r2})
# Q9 an order delivered by the pre-r2 tool (receipts without owner) and rerun by r2 with the same owner
if OLD:
    d = world(); r1 = run(d, "run", "order.json", "--worker", "ana", tool=OLD / REL)[0]
    r2, o2 = run(d, "run", "order.json", "--worker", "ben"); L = ledger(d)
    row("Q9", "order delivered by G04 r1 314b4db, rerun by this tool with the same owner: exit 0, no second delivery (deliver reused or duplicate suppressed), ledger 1",
        r1 == 0 and r2 == 0 and len(L) == 1 and ("duplicate suppressed" in o2 or "deliver  reused" in o2), {"rc": [r1, r2], "ledger": len(L), "out": o2[-240:]})
json.dump({"python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M04R2 PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
