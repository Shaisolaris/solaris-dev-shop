"""M32 r3 probe (Grok self-validation, not independent review). Usage: m32r3_probe.py WT [PY]"""
import json, os, subprocess, sys, tempfile, shutil, hashlib, glob
WT = sys.argv[1]; PY = sys.argv[2] if len(sys.argv) > 2 else sys.executable
TOOL = os.path.join(WT, "employees/sales-outreach/customer-success/followthrough.py")
def contacts(*cs): return {"schema": "solaris.cs-account/1", "account_id": "northwind-clinic", "owner": "Morgan (synthetic)",
                           "contacts": [{"id": i, "name": n, "handle": h, "consent": "granted"} for i, n, h in cs]}
def ev(i, t, c=None, at="2026-10-01T09:00:00-07:00", **kw):
    d = {"id": i, "type": t, "at": at}; 
    if c: d["contact"] = c
    d.update(kw); return d
class Case:
    def __init__(s): s.d = tempfile.mkdtemp(); s.st = os.path.join(s.d, "st")
    def run(s, acct, evs, now="2026-10-08T12:00:00-07:00"):
        a = os.path.join(s.d, "a.json"); e = os.path.join(s.d, "e.jsonl")
        json.dump(acct, open(a, "w")); open(e, "w").write("".join(json.dumps(x) + "\n" for x in evs))
        r = subprocess.run([PY, TOOL, "run", s.st, "--account", a, "--events", e, "--now", now, "--worker", "w1", "--json"], capture_output=True, text=True)
        try: j = json.loads(r.stdout)
        except Exception: j = {"_err": (r.stdout + r.stderr)[-200:]}
        return r.returncode, j
    def snap(s):
        out = {}
        for p in sorted(glob.glob(s.st + "/**", recursive=True)):
            if os.path.isfile(p): out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        return out
def drafted_for(j, c): return sorted(x["action"] for x in j.get("drafted", []) if x["contact"] == c)
R = []
def rec(name, ok, detail, obs=False): R.append((name, bool(ok), detail, obs))
ANA = ("c-ana", "Ana", "contact-ana")
H1 = [ev("E01", "signup", "c-ana"), ev("E02", "opt_out", "c-ana", at="2026-10-01T09:30:00-07:00", scope="all")]
def merged(handle, scope_ev=None):
    return contacts(("c-ana2", "Ana", handle)), [ev("E10", "signup", "c-ana2", at="2026-10-06T09:00:00-07:00")]
# Q01 history dropped after merge: person stays suppressed
c = Case(); c.run(contacts(ANA), H1); a, e = merged("contact-ana"); rc, j = c.run(a, e)
rec("Q01 merge drops opt-out history: no drafts for the person", rc == 0 and drafted_for(j, "c-ana2") == [], (rc, drafted_for(j, "c-ana2")))
# Q02 same, handle differs in case, width and spaces
c = Case(); c.run(contacts(ANA), H1); a, e = merged(" CONTACT-ＡＮＡ "); rc, j = c.run(a, e)
rec("Q02 merge with case/width/space variant: no drafts", rc == 0 and drafted_for(j, "c-ana2") == [], (rc, drafted_for(j, "c-ana2")))
# Q03 format characters in a duplicate import are refused
for nm, ch in (("ZWSP", "\u200b"), ("ZWJ", "\u200d"), ("SHY", "\u00ad"), ("BOM", "\ufeff"), ("LRM", "\u200e"), ("WJ", "\u2060")):
    c = Case(); rc, j = c.run(contacts(ANA, ("c-ana2", "Ana", "cont" + ch + "act-ana")), H1)
    rec("Q03 duplicate with %s refused (exit 2)" % nm, rc == 2, rc)
# Q04 format character variant after a history-dropping merge: still suppressed
c = Case(); c.run(contacts(ANA), H1); a, e = merged("contact\u200b-ana"); rc, j = c.run(a, e)
rec("Q04 merge to ZWSP variant with history dropped: no drafts", rc == 0 and drafted_for(j, "c-ana2") == [], (rc, drafted_for(j, "c-ana2")))
# Q05 marketing-only durable suppression still allows support ack
c = Case(); c.run(contacts(ANA), [ev("E01", "signup", "c-ana"), ev("E02", "opt_out", "c-ana", at="2026-10-01T09:30:00-07:00", scope="marketing")])
rc, j = c.run(contacts(("c-ana2", "Ana", "contact-ana")), [ev("E10", "signup", "c-ana2", at="2026-10-06T09:00:00-07:00"),
             ev("E11", "ticket_opened", "c-ana2", at="2026-10-06T10:00:00-07:00", thread="T9")])
rec("Q05 durable marketing opt-out: ack drafted, onboarding suppressed", drafted_for(j, "c-ana2") == ["ack"], drafted_for(j, "c-ana2"))
# Q06 hard bounce durable
c = Case(); c.run(contacts(ANA), [ev("E01", "signup", "c-ana"), ev("E02", "bounce", "c-ana", at="2026-10-01T09:30:00-07:00", kind="hard")])
a, e = merged("contact-ana"); rc, j = c.run(a, e)
rec("Q06 durable hard bounce: no drafts", drafted_for(j, "c-ana2") == [], drafted_for(j, "c-ana2"))
# Q07 opt_in after merge is flagged for review and changes nothing
c = Case(); c.run(contacts(ANA), H1); a, e = merged("contact-ana"); e.append(ev("E12", "opt_in", "c-ana2", at="2026-10-07T09:00:00-07:00"))
rc, j = c.run(a, e)
rec("Q07 opt_in after merge: consent_review_required and no drafts", drafted_for(j, "c-ana2") == [] and any(n["note"] == "consent_review_required" for n in j.get("notes", [])), (drafted_for(j, "c-ana2"), j.get("notes")))
# Q08 refused run writes nothing (duplicate import) and file does not grow on reruns
c = Case(); c.run(contacts(ANA), H1); s0 = c.snap(); rc, j = c.run(contacts(ANA, ("c-x", "X", "CONTACT-ANA")), H1); s1 = c.snap()
rec("Q08 refused duplicate run leaves state byte-identical", rc == 2 and s0 == s1, rc)
c.run(contacts(ANA), H1); c.run(contacts(ANA), H1)
pp = os.path.join(c.st, "person_suppressions.jsonl"); n = len(open(pp).read().splitlines()) if os.path.exists(pp) else "no file"
rec("Q09 reruns do not duplicate suppression rows", n == 1, n)
# Q10 state from before r3 (no suppression file) still works
c = Case(); c.run(contacts(ANA), H1); pp = os.path.join(c.st, "person_suppressions.jsonl"); os.path.exists(pp) and os.remove(pp); rc, j = c.run(contacts(ANA), H1)
rec("Q10 state without the suppression file: rc 0 and person suppressed", rc == 0 and drafted_for(j, "c-ana") == [], (rc, drafted_for(j, "c-ana")))
# OBS: corrupt suppression file with history dropped
c = Case(); c.run(contacts(ANA), H1); p = os.path.join(c.st, "person_suppressions.jsonl"); open(p, "w").write("{not json\n")
a, e = merged("contact-ana"); rc, j = c.run(a, e)
rec("Q11 corrupted suppression line + history dropped (what happens)", True, (rc, drafted_for(j, "c-ana2"), j.get("_err")), obs=True)
c = Case(); c.run(contacts(ANA), H1); open(p := os.path.join(c.st, "person_suppressions.jsonl"), "ab").write(b"\xff\xfe garbage\n")
c2rc, j2 = c.run(contacts(ANA), H1)
rec("Q12 garbage line in suppression file, history kept (what happens)", True, (c2rc, j2.get("_err")), obs=True)
# OBS: invisible characters outside category Cf after a history-dropping merge
for nm, ch in (("CGJ U+034F", "\u034f"), ("VS16 U+FE0F", "\ufe0f"), ("Hangul filler U+3164", "\u3164"), ("Braille blank U+2800", "\u2800")):
    c = Case(); c.run(contacts(ANA), H1); a, e = merged("contact" + ch + "-ana"); rc, j = c.run(a, e)
    rec("Q13 merge to %s variant, history dropped (drafts)" % nm, True, (rc, drafted_for(j, "c-ana2")), obs=True)
    c = Case(); rc, j = c.run(contacts(ANA, ("c-ana2", "Ana", "contact" + ch + "-ana")), H1)
    rec("Q13 duplicate with %s (rc, drafts for second record)" % nm, True, (rc, drafted_for(j, "c-ana2")), obs=True)
# OBS: merge that also changes the handle and drops history
c = Case(); c.run(contacts(ANA), H1); a, e = merged("ana-new-handle"); rc, j = c.run(a, e)
rec("Q14 merge that changes handle and drops history (drafts)", True, (rc, drafted_for(j, "c-ana2")), obs=True)
for n, ok, d, obs in R: print("%s %s %s" % ("OBS " if obs else ("PASS" if ok else "FAIL"), n, d))
sc = [r for r in R if not r[3]]; print("PROBE %d/%d" % (sum(r[1] for r in sc), len(sc)))
