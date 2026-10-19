#!/usr/bin/env python3
"""G32 naive control: a scheduler that drafts every due playbook step from the events, with no consent check,
no reply state, no ledger and no lock (each run writes its own draft files). Expected REJECTED."""
import argparse, datetime as dt, json, os, sys
from pathlib import Path

DELAY = {"welcome": 0, "checkin": 3, "training": 7, "ack": 0, "nudge": 2, "feedback": 1}
ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
r = sub.add_parser("run"); r.add_argument("state"); r.add_argument("--account"); r.add_argument("--events"); r.add_argument("--now")
r.add_argument("--worker"); r.add_argument("--json", action="store_true"); r.add_argument("--fail-at")
s = sub.add_parser("status"); s.add_argument("state"); s.add_argument("--json", action="store_true")
a = ap.parse_args()
if a.cmd == "status":
    print(json.dumps({"runs": 0, "open_drafts": []})); sys.exit(0)
acc = json.load(open(a.account)); now = dt.datetime.fromisoformat(a.now)
ev = [json.loads(l) for l in open(a.events) if l.strip()]
d = Path(a.state) / "drafts"; d.mkdir(parents=True, exist_ok=True); n = len(list(d.iterdir()))
out = []
for e in ev:
    at = dt.datetime.fromisoformat(e["at"])
    acts = {"signup": ["welcome", "checkin", "training"], "ticket_opened": ["ack"], "agent_response": ["nudge"], "ticket_closed": ["feedback"]}.get(e["type"], [])
    for x in acts:
        if at + dt.timedelta(days=DELAY[x]) <= now:
            n += 1
            (d / ("%05d.json" % n)).write_text(json.dumps({"contact": e["contact"], "action": x, "trigger": e["id"], "status": "draft", "owner": acc["owner"],
                                                           "kind": "support" if x in ("ack", "nudge") else "onboarding", "body": "", "send": "draft"}))
            out.append(x)
print(json.dumps({"drafted": out, "notes": [], "sent": 0, "duplicate_suppressed": [], "reassigned": [], "owner": acc["owner"]}))
