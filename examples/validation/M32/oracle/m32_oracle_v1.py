#!/usr/bin/env python3
"""M32 oracle (Grok self-validation, not independent review). Written from M32.md, G32.md and
consent-follow-through.md before reading the builder's oracle. Every tool run goes through an audit hook
(oracle/audit/sitecustomize.py) that logs any socket, process, mail or URL attempt; any entry fails the run.
Probes withdrawn, expired, partial and conflicting consent, duplicate imports, reopened requests, crash and
concurrency, and tampered state. Usage: PY m32_oracle.py SRC OUT.json [--tool PATH]."""
import copy, glob, json, os, random, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/sales-outreach/customer-success/followthrough.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
FIX = os.path.join(SRC, "examples/capabilities/G32/fixtures"); PY = sys.executable
AUD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit")
ACC = json.load(open(os.path.join(FIX, "account.json"))); EVS = [json.loads(l) for l in open(os.path.join(FIX, "events.jsonl")) if l.strip()]
NOW = "2026-10-08T12:00:00-07:00"; ROWS = []; AUDIT_HITS = []

class W:
    def __init__(s, acc=None, evs=None):
        s.top = tempfile.mkdtemp(prefix="m32o-"); s.st = os.path.join(s.top, "state"); s.acc = copy.deepcopy(acc or ACC); s.evs = copy.deepcopy(EVS if evs is None else evs)
        s.log = os.path.join(s.top, "audit.log"); s.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=AUD, M32_AUDIT_LOG=s.log)
    def files(s, raw_lines=None):
        json.dump(s.acc, open(os.path.join(s.top, "acc.json"), "w"))
        with open(os.path.join(s.top, "ev.jsonl"), "w") as f:
            for l in (raw_lines if raw_lines is not None else [json.dumps(e) for e in s.evs]): f.write(l + "\n")
    def cmd(s, now=NOW, worker="w1", extra=(), raw_lines=None, popen=False):
        s.files(raw_lines); a = [PY, TOOL, "run", s.st, "--account", os.path.join(s.top, "acc.json"), "--events", os.path.join(s.top, "ev.jsonl"), "--now", now, "--worker", worker, "--json"] + list(extra)
        return a
    def run(s, **kw):
        r = subprocess.run(s.cmd(**kw), cwd=s.top, env=s.env, capture_output=True, text=True, timeout=120)
        try: j = json.loads(r.stdout)
        except Exception: j = {}
        return r.returncode, j
    def drafts(s):
        out = []
        for p in sorted(glob.glob(os.path.join(s.st, "drafts", "*.json"))):
            try: out.append(json.load(open(p)))
            except Exception: out.append({"_bad": p})
        return out
    def live(s): return sorted((d.get("contact"), d.get("action"), d.get("trigger")) for d in s.drafts() if d.get("status") == "draft")
    def withdrawn(s): return sorted((d.get("contact"), d.get("action")) for d in s.drafts() if d.get("status") == "withdrawn")
    def audit(s):
        h = open(s.log).read().splitlines() if os.path.exists(s.log) else []; AUDIT_HITS.extend(h); return h
    def close(s): s.audit(); shutil.rmtree(s.top, ignore_errors=True)

def ev(i, typ, at, **kw): d = {"id": i, "type": typ, "at": at}; d.update(kw); return d
def row(name, ok, det): ROWS.append({"row": name, "pass": bool(ok), "detail": det}); print(("PASS " if ok else "FAIL ") + name + " " + json.dumps(det, default=str)[:450], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)})
    return g
def nosend(w):
    ds = w.drafts(); return all(d.get("send") in ("not performed; a person reviews and sends", "do not send") for d in ds) and not w.audit()

@safe
def p01():
    w = W(); rc, j = w.run(); live = sorted((c, a) for c, a, _ in w.live())
    want = sorted([("c-ana", "welcome"), ("c-ben", "welcome"), ("c-ben", "ack"), ("c-ben", "checkin"), ("c-ben", "feedback"), ("c-ana", "training"), ("c-ben", "training")])
    owners = {d.get("owner") for d in w.drafts()}; ok = rc == 0 and live == want and owners == {"Priya (customer success lead, synthetic)"} and j.get("sent") == 0 and nosend(w)
    no_cy_dee_mkt = not any(c in ("c-cy", "c-dee") for c, _ in live); w.close()
    row("P01 clean fixture: exactly the hand-derived drafts, signed by the current owner, no send, no network/process", ok and no_cy_dee_mkt, {"rc": rc, "live": live, "owners": sorted(owners)})

@safe
def p02():
    res = {}
    for nm, extra in (("opt_out_all", ev("X1", "opt_out", "2026-10-05T09:00:00-07:00", contact="c-ana", scope="all")), ("hard_bounce", ev("X1", "bounce", "2026-10-05T09:00:00-07:00", contact="c-ana", kind="hard"))):
        w = W(); w.evs.append(ev("X0", "ticket_opened", "2026-10-04T09:00:00-07:00", contact="c-ana", thread="TA"))
        r1, _ = w.run(now="2026-10-04T12:00:00-07:00"); before = [x for x in w.live() if x[0] == "c-ana"]
        w.evs.append(extra); r2, j2 = w.run(); after_live = [x for x in w.live() if x[0] == "c-ana"]; wd = [x for x in w.withdrawn() if x[0] == "c-ana"]
        wd_send = {d.get("send") for d in w.drafts() if d.get("status") == "withdrawn"}
        r3, j3 = w.run(); again = [x for x in w.live() if x[0] == "c-ana"]; ok = r1 == r2 == r3 == 0 and before and not after_live and len(wd) == len(before) and wd_send == {"do not send"} and not again and nosend(w)
        res[nm] = (ok, {"before": before, "after_live": after_live, "withdrawn": wd, "withdrawn_send": sorted(wd_send), "third_run_live": again}); w.close()
    w = W(); w.evs.append(ev("X1", "bounce", "2026-10-02T09:00:00-07:00", contact="c-ana", kind="soft")); rc, _ = w.run(); soft = sorted(a for c, a, _ in w.live() if c == "c-ana"); w.close()
    res["soft_bounce_no_suppression"] = (rc == 0 and soft == ["training", "welcome"], soft)
    row("P02 withdrawn consent: an opt-out all or hard bounce withdraws every written draft for the contact (do not send) and nothing is redrafted; a soft bounce does not", all(v[0] for v in res.values()), res)

@safe
def p03():
    res = {}
    for val in ("expired", "withdrawn", "revoked", "", None, "GRANTED"):
        w = W(); w.acc["contacts"][0]["consent"] = val; rc, j = w.run(); ana = sorted(a for c, a, _ in w.live() if c == "c-ana"); w.close()
        res[str(val)] = (rc == 2 or not set(ana) & {"welcome", "checkin", "training", "feedback"}, {"rc": rc, "ana": ana})
    w = W(); w.acc["contacts"][0]["consent_expires"] = "2026-09-01"; rc, j = w.run(); ana = sorted(a for c, a, _ in w.live() if c == "c-ana"); w.close()
    res["granted_with_past_expiry_field"] = (True, {"rc": rc, "ana": ana, "note": "OBS only: the doc has no expiry"})
    row("P03 expired or unrecognised consent values never yield onboarding or feedback drafts (refused or treated as no consent)", all(v[0] for v in res.values()), res)

@safe
def p04():
    w = W(); w.acc["contacts"][2]["consent"] = "unknown"
    w.evs += [ev("Y1", "ticket_opened", "2026-10-06T09:00:00-07:00", contact="c-dee", thread="TD"), ev("Y2", "agent_response", "2026-10-06T10:00:00-07:00", contact="c-dee", thread="TD"),
              ev("Y3", "ticket_opened", "2026-10-06T09:00:00-07:00", contact="c-cy", thread="TC"), ev("Y4", "ticket_closed", "2026-10-06T12:00:00-07:00", contact="c-dee", thread="TD")]
    rc, j = w.run(); dee = sorted(a for c, a, _ in w.live() if c == "c-dee"); cy = sorted(a for c, a, _ in w.live() if c == "c-cy"); w.close()
    ok = rc == 0 and dee == ["ack"] and cy == ["ack"]
    row("P04 partial consent: marketing opt-out and unknown consent keep support replies on the customer's own ticket (ack) and nothing else; the closed ticket cancels the nudge and its feedback is suppressed", ok, {"dee": dee, "cy": cy})

@safe
def p05():
    res = {}
    def ana_after(evs_extra):
        w = W(); w.evs += evs_extra; rc, j = w.run(); ana = sorted(a for c, a, _ in w.live() if c == "c-ana"); notes = [n.get("note") for n in j.get("notes", []) if n.get("contact") == "c-ana"]; w.close(); return rc, ana, notes
    t = "2026-10-02T09:00:00-07:00"
    rc, ana, notes = ana_after([ev("Z1", "opt_out", t, contact="c-ana", scope="all"), ev("Z2", "opt_in", "2026-10-03T09:00:00-07:00", contact="c-ana")]); res["out_then_in"] = (rc == 0 and ana == [] and "consent_review_required" in notes, (rc, ana, notes))
    rc, ana, notes = ana_after([ev("Z2", "opt_in", "2026-09-30T09:00:00-07:00", contact="c-ana"), ev("Z1", "opt_out", t, contact="c-ana", scope="all")]); res["in_then_out"] = (rc == 0 and ana == [], (rc, ana, notes))
    rc, ana, notes = ana_after([ev("Z1", "opt_out", t, contact="c-ana", scope="all"), ev("Z2", "opt_in", t, contact="c-ana")]); res["same_instant"] = (rc == 0 and ana == [], (rc, ana, notes))
    rc, ana, notes = ana_after([ev("Z1", "opt_out", t, contact="c-ana", scope="marketing"), ev("Z2", "opt_out", "2026-10-03T09:00:00-07:00", contact="c-ana", scope="all")]); res["marketing_then_all"] = (rc == 0 and ana == [], (rc, ana, notes))
    rc, ana, notes = ana_after([ev("Z1", "opt_out", "2026-10-09T09:00:00-07:00", contact="c-ana", scope="all")]); res["future_opt_out_ignored_at_now"] = (rc in (0, 2), (rc, ana, notes))
    # duplicate import: a second contact record with the same handle, one opted out
    w = W(); w.acc["contacts"].append({"id": "c-ana2", "name": "Ana", "handle": "contact-ana", "consent": "granted"})
    w.evs += [ev("D1", "opt_out", t, contact="c-ana", scope="all"), ev("D2", "signup", "2026-10-03T09:00:00-07:00", contact="c-ana2")]
    rc, j = w.run(); to_handle = sorted((d.get("contact"), d.get("action")) for d in w.drafts() if d.get("status") == "draft" and d.get("handle") == "contact-ana"); w.close()
    res["duplicate_import_same_handle"] = (rc == 2 or to_handle == [], {"rc": rc, "live_drafts_to_opted_out_handle": to_handle})
    w = W(); w.acc["contacts"].append(dict(w.acc["contacts"][0], consent="unknown")); rc, _ = w.run(); n = len(w.drafts()); w.close(); res["duplicate_contact_id"] = (rc == 2 and n == 0, {"rc": rc, "drafts": n})
    lines = [json.dumps(e) for e in EVS]; w = W(); rc_dup, _ = w.run(raw_lines=lines + [lines[0]]); n1 = len(w.live()); w.close(); res["exact_redelivery_once"] = (rc_dup == 0 and n1 == 7, (rc_dup, n1))
    w = W(); alt = dict(EVS[0], at="2026-10-01T09:01:00-07:00"); rc_c, _ = w.run(raw_lines=lines + [json.dumps(alt)]); n2 = len(w.drafts()); w.close(); res["same_id_other_content_refused"] = (rc_c == 2 and n2 == 0, (rc_c, n2))
    row("P05 conflicting consent: suppression wins over any opt-in order or tie; a duplicate import never drafts to an opted-out handle; redelivery once, conflicting ids refused", all(v[0] for v in res.values()), res)

@safe
def p06():
    w = W(); w.evs += [ev("R1", "ticket_opened", "2026-10-07T08:00:00-07:00", contact="c-ben", thread="T1"), ev("R2", "agent_response", "2026-10-07T09:00:00-07:00", contact="c-ben", thread="T1")]
    rc, j = w.run(now="2026-10-10T12:00:00-07:00"); ben = [(a, t) for c, a, t in w.live() if c == "c-ben"]; w.close()
    acks = sorted(t for a, t in ben if a == "ack"); nudges = sorted(t for a, t in ben if a == "nudge")
    row("P06 reopened request: a reopened ticket gets its own ack and nudge (one per trigger), the earlier close's feedback stands", rc == 0 and acks == ["E05", "R1"] and nudges == ["R2"] and ("feedback", "E12") in ben, {"rc": rc, "ben": sorted(ben)})

@safe
def p07():
    res = {}
    w = W(); w.run(); a = sorted(os.listdir(os.path.join(w.st, "drafts"))); l1 = open(os.path.join(w.st, "ledger.jsonl")).read().count("\n"); r2, j2 = w.run(); b = sorted(os.listdir(os.path.join(w.st, "drafts"))); l2 = open(os.path.join(w.st, "ledger.jsonl")).read().count("\n")
    res["rerun_idempotent"] = (r2 == 0 and a == b and l1 == l2 and not j2.get("drafted"), (len(a), l1, l2)); w.close()
    for stage in ("drafted", "ledgered"):
        w = W(); rc1, _ = w.run(extra=["--fail-at", stage]); rc2, _ = w.run(); keys = [d.get("key") for d in w.drafts()]; ok = rc1 == 75 and rc2 == 0 and len(keys) == len(set(keys)) and sorted((c, x) for c, x, _ in w.live()) == sorted([("c-ana", "welcome"), ("c-ben", "welcome"), ("c-ben", "ack"), ("c-ben", "checkin"), ("c-ben", "feedback"), ("c-ana", "training"), ("c-ben", "training")])
        res["crash_" + stage] = (ok, (rc1, rc2, len(keys))); w.close()
    w = W(); ps = [subprocess.Popen(w.cmd(worker="w%d" % i), cwd=w.top, env=w.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(5)]
    rcs = sorted(p.wait(60) for p in ps); keys = [d.get("key") for d in w.drafts()]; rc_after, _ = w.run(); keys2 = [d.get("key") for d in w.drafts()]
    res["five_workers"] = (set(rcs) <= {0, 4} and 0 in rcs and len(keys) == len(set(keys)) and len(keys2) == len(keys) and rc_after == 0, {"rcs": rcs, "drafts": len(keys)}); w.close()
    row("P07 duplicate safety: rerun idempotent, crash at drafted or ledgered resumes to one draft per key, five concurrent workers make no duplicates", all(v[0] for v in res.values()), res)

@safe
def p08():
    w = W(); w.evs = [e for e in EVS if e["id"] != "E11"]; w.run(); old = {d.get("owner") for d in w.drafts()}
    w.evs = copy.deepcopy(EVS); rc, j = w.run(); new = {d.get("owner") for d in w.drafts() if d.get("status") == "draft"}; re = len(j.get("reassigned", [])); w.close()
    row("P08 owner change re-renders unsent drafts under the current owner and reports them reassigned", rc == 0 and old == {"Morgan (customer success, synthetic)"} and new == {"Priya (customer success lead, synthetic)"} and re > 0, {"old": sorted(old), "new": sorted(new), "reassigned": re})

@safe
def p09():
    res = {}
    w = W(); w.run(); jp = os.path.join(w.st, "journal.jsonl"); s = open(jp).read(); open(jp, "w").write(s.replace('"', "'", 1) if s else "x"); before = sorted(os.listdir(os.path.join(w.st, "drafts")))
    w.evs.append(ev("Q1", "ticket_opened", "2026-10-07T08:00:00-07:00", contact="c-ana", thread="TQ")); rc, _ = w.run(); after = sorted(os.listdir(os.path.join(w.st, "drafts"))); res["journal_tampered"] = (rc == 2 and before == after, rc); w.close()
    w = W(); w.run(); other = copy.deepcopy(ACC); other["account_id"] = "other-clinic"; w.acc = other; rc, _ = w.run(); res["other_account_state"] = (rc == 2, rc); w.close()
    w = W(); w.run(); victim = sorted(glob.glob(os.path.join(w.st, "drafts", "*welcome.json")))[0]; os.remove(victim); rc, j = w.run(); notes = [n.get("note") for n in j.get("notes", [])]
    res["draft_file_removed"] = (rc == 0 and "draft_file_missing" in notes and not os.path.exists(victim), notes); w.close()
    w = W(); w.run(now="2026-10-02T12:00:00-07:00"); lp = os.path.join(w.st, "ledger.jsonl"); open(lp, "a").write('{"key": "torn'); rc, _ = w.run(); keys = [d.get("key") for d in w.drafts()]; rc3, j3 = w.run()
    res["torn_ledger_line"] = (rc == 0 and rc3 == 0 and len(keys) == len(set(keys)) and not j3.get("drafted"), (rc, rc3, len(keys))); w.close()
    row("P09 state integrity: a tampered journal or another account's state is refused with nothing written; a removed draft is noted, not redrafted; a torn ledger line swallows nothing", all(v[0] for v in res.values()), res)

@safe
def p10():
    rnd = random.Random(3232); bad = []
    for seed in range(8):
        acc = copy.deepcopy(ACC); acc["contacts"] = [{"id": "c%d" % i, "name": "N%d" % i, "handle": "h%d" % i, "consent": rnd.choice(["granted", "granted", "unknown"])} for i in range(6)]
        evs = []; n = 0
        for d in range(1, 9):
            for _ in range(rnd.randint(1, 4)):
                n += 1; c = "c%d" % rnd.randrange(6); at = "2026-10-%02dT%02d:%02d:00-07:00" % (d, rnd.randint(8, 17), rnd.randint(0, 59)); th = "T%s" % c
                typ = rnd.choice(["signup", "ticket_opened", "agent_response", "reply_received", "ticket_closed", "opt_out", "opt_in", "bounce"])
                e = ev("S%03d" % n, typ, at, contact=c)
                if typ in ("ticket_opened", "agent_response", "reply_received", "ticket_closed"): e["thread"] = th
                if typ == "opt_out": e["scope"] = rnd.choice(["all", "marketing"])
                if typ == "bounce": e["kind"] = rnd.choice(["hard", "soft"])
                evs.append(e)
        w = W(acc, evs); cut = rnd.randint(2, 6); rc1, _ = w.run(now="2026-10-%02dT12:00:00-07:00" % cut); rc2, _ = w.run(now="2026-10-09T12:00:00-07:00")
        full = {c["id"]: c["consent"] for c in acc["contacts"]}; stop = {e["contact"] for e in evs if (e["type"] == "opt_out" and e["scope"] == "all") or (e["type"] == "bounce" and e["kind"] == "hard")}
        mkt = {e["contact"] for e in evs if e["type"] == "opt_out" and e["scope"] == "marketing"}
        viol = [(d.get("contact"), d.get("action")) for d in w.drafts() if d.get("status") == "draft" and (d.get("contact") in stop or (d.get("kind") in ("onboarding", "feedback") and (d.get("contact") in mkt or full.get(d.get("contact")) != "granted")))]
        keys = [d.get("key") for d in w.drafts()]; ns = nosend(w); w.close()
        if not (rc1 == 0 and rc2 == 0 and not viol and len(keys) == len(set(keys)) and ns): bad.append({"seed": seed, "rc": (rc1, rc2), "viol": viol[:5], "dups": len(keys) - len(set(keys)), "nosend": ns})
    row("P10 seeded soak: 8 random histories with a mid-way run; no live draft for a suppressed contact or kind, no duplicate keys, nothing sent", not bad, {"bad": bad[:3]})

@safe
def p11():
    src = open(TOOL).read(); imports = [m for m in ("socket", "smtplib", "urllib", "http.client", "subprocess", "requests", "ftplib", "webbrowser") if ("import " + m) in src or ("from " + m) in src]
    row("P11 nothing is ever sent: no send-capable import in the tool and no audited network/process/mail event in any run of this oracle", not imports and not AUDIT_HITS, {"imports": imports, "audit_hits": AUDIT_HITS[:5]})

for f in (p01, p02, p03, p04, p05, p06, p07, p08, p09, p10, p11): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
n = sum(r["pass"] for r in ROWS); print("M32 ORACLE %d/%d core %s" % (n, len(ROWS), "PASS" if n == len(ROWS) else "FAIL"))
