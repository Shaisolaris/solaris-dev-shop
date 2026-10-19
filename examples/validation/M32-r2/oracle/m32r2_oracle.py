#!/usr/bin/env python3
"""M32 r2 oracle (Grok self-validation, not independent review). Starts from the M32 v2 oracle unchanged (P01-P14)
and adds r2 rows P15-P17 and OBS O18 for one person, one consent: person-key variants, blank handles, aliases,
plus-addressing, unicode confusables and invisible characters, the merge flow, re-import after merge and
suppression following the person. Original M32 docstring follows. Written from M32.md, G32.md and
consent-follow-through.md before reading the builder's oracle. Every tool run goes through an audit hook
(oracle/audit/sitecustomize.py) that logs any socket, process, mail or URL attempt; any entry fails the run.
Probes withdrawn, expired, partial and conflicting consent, duplicate imports, reopened requests, crash and
concurrency, and tampered state. Usage: PY m32_oracle.py SRC OUT.json [--tool PATH]."""
import copy, glob, hashlib, json, os, random, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/sales-outreach/customer-success/followthrough.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
FIX = os.path.join(SRC, "examples/capabilities/G32/fixtures"); PY = sys.executable
AUD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit")
ACC = json.load(open(os.path.join(FIX, "account.json"))); EVS = [json.loads(l) for l in open(os.path.join(FIX, "events.jsonl")) if l.strip()]
NOW = "2026-10-08T12:00:00-07:00"; ROWS = []; AUDIT_HITS = []

class W:
    def __init__(s, acc=None, evs=None):
        s.top = tempfile.mkdtemp(prefix="m32r2o-"); s.st = os.path.join(s.top, "state"); s.acc = copy.deepcopy(acc or ACC); s.evs = copy.deepcopy(EVS if evs is None else evs)
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
def row(name, ok, det):
    sub = {k: bool(v[0]) for k, v in det.items() if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], bool)} if isinstance(det, dict) else {}
    ROWS.append({"row": name, "pass": bool(ok), "sub": sub, "detail": det}); print(("PASS " if ok else "FAIL ") + name + " " + json.dumps(det, default=str)[:450], flush=True)
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

ONE = {"account_id": ACC["account_id"], "owner": ACC.get("owner"), "contacts": [{"id": "x1", "name": "X One", "handle": "hx1", "consent": "granted"}]}
for k in ACC:
    if k not in ONE: ONE[k] = copy.deepcopy(ACC[k])
ONE["contacts"] = [{"id": "x1", "name": "X One", "handle": "hx1", "consent": "granted"}]

def L(t): return "2026-10-%sT%s:00-07:00" % (t[:2], t[2:])

@safe
def p12():
    evs = [ev("A1", "signup", L("0109:00"), contact="x1"), ev("A2", "signup", L("0209:00"), contact="x1"),
           ev("A3", "ticket_opened", L("0110:00"), contact="x1", thread="T9"), ev("A4", "agent_response", L("0111:00"), contact="x1", thread="T9"),
           ev("A5", "ticket_opened", L("0111:30"), contact="x1", thread="T8"), ev("A6", "agent_response", L("0112:00"), contact="x1", thread="T8"),
           ev("A7", "reply_received", L("0209:00"), contact="x1", thread="T8"), ev("A8", "ticket_closed", L("0509:00"), contact="x1", thread="T9"),
           ev("A9", "opt_out", "2026-10-20T09:00:00-07:00", contact="x1", scope="all")]
    w = W(ONE, evs); res = {}; seen = []
    def acts(): return sorted(a for c, a, t in w.live())
    steps = [("0109:00", ["welcome"]),  # v2 authoring fix (disclosed): the T9 ticket opens at 10:00, after this run
              ("0310:59", ["ack", "ack", "welcome"]), ("0311:00", ["ack", "ack", "nudge", "welcome"]),
             ("0408:59", ["ack", "ack", "nudge", "welcome"]), ("0409:00", ["ack", "ack", "checkin", "nudge", "welcome"]),
             ("0608:59", ["ack", "ack", "checkin", "welcome"]), ("0609:00", ["ack", "ack", "checkin", "feedback", "welcome"]),
             ("0809:00", ["ack", "ack", "checkin", "feedback", "training", "welcome"]), ("0912:00", ["ack", "ack", "checkin", "feedback", "training", "welcome"])]
    for t, want in steps:
        rc, _ = w.run(now=L(t)); got = acts(); seen.append((t, rc, got)); res["at_%s" % t] = (rc == 0 and got == want, (rc, got))
    welc = [d for d in w.drafts() if d.get("action") == "welcome"]; res["second_signup_no_redraft"] = (len(welc) == 1, len(welc))
    res["reply_cancels_T8_nudge"] = (not any(a == "nudge" and t == "A6" for c, a, t in w.live()) and not any(d.get("action") == "nudge" and d.get("trigger") == "A6" and d.get("status") == "draft" for d in w.drafts()), w.live())
    res["closed_ticket_nudge_withdrawn_stays"] = (("x1", "nudge") in w.withdrawn() and not any(a == "nudge" for c, a, t in w.live()), w.withdrawn())
    res["future_opt_out_not_applied"] = (len(w.live()) == 6, len(w.live()))
    res["nothing_sent"] = (nosend(w), None); w.close()
    row("P12 v2 timing and history: welcome +0, checkin +3d, training +7d, nudge +2d, feedback +1d at the exact minute; second signup not redrafted; a reply cancels the nudge; a close withdraws a drafted nudge for good; a future opt-out is not applied yet", all(v[0] for v in res.values()), res)

@safe
def p13():
    res = {}
    cases = {"ticket_without_thread": [ev("B1", "ticket_opened", L("0109:00"), contact="x1")],
             "opt_out_without_scope": [ev("B1", "opt_out", L("0109:00"), contact="x1")],
             "opt_out_scope_sms": [ev("B1", "opt_out", L("0109:00"), contact="x1", scope="sms")],
             "unknown_contact": [ev("B1", "signup", L("0109:00"), contact="zz")],
             "naive_time": [ev("B1", "signup", "2026-10-01T09:00:00", contact="x1")]}
    for k, e in cases.items():
        w = W(ONE, [ev("B0", "signup", L("0108:00"), contact="x1")] + e); rc, _ = w.run(); res[k] = (rc == 2 and not w.drafts(), (rc, len(w.drafts()))); w.close()
    w = W(ONE, [ev("B0", "signup", L("0108:00"), contact="x1")]); rc, _ = w.run(worker="bad name!"); res["bad_worker"] = (rc == 2 and not w.drafts(), (rc, len(w.drafts()))); w.close()
    row("P13 v2 invalid input refused with nothing written: ticket without thread, opt-out without or with an unknown scope, unknown contact, a time without offset, a bad worker name", all(v[0] for v in res.values()), res)

@safe
def p14():
    w = W(); w.run(now="2026-10-02T12:00:00-07:00"); lp = os.path.join(w.st, "ledger.jsonl"); open(lp, "a").write('{"key": "torn'); rc, _ = w.run(now="2026-10-05T12:00:00-07:00")
    good = set()
    for l in open(lp).read().splitlines():
        try: good.add(json.loads(l).get("key"))
        except Exception: pass
    keys = {d.get("key") for d in w.drafts()}; missing = sorted(k for k in keys if k not in good); w.close()
    row("P14 v2 torn ledger: after a torn last line every draft written by the next run has a parseable ledger record", rc == 0 and not missing, {"rc": (rc == 0, rc), "unrecorded": (not missing, missing)})

T0 = "2026-10-02T09:00:00-07:00"
def dup(h1, h2, consent2="granted"):
    """c-ana (handle h1) opts out of everything; a second record c-ana2 (handle h2) then signs up."""
    w = W(); w.acc["contacts"][0]["handle"] = h1; w.acc["contacts"].append({"id": "c-ana2", "name": "Ana", "handle": h2, "consent": consent2})
    w.evs += [ev("D1", "opt_out", T0, contact="c-ana", scope="all"), ev("D2", "signup", "2026-10-03T09:00:00-07:00", contact="c-ana2")]
    rc, j = w.run(); live2 = sorted(a for c, a, _ in w.live() if c == "c-ana2"); n = len(w.drafts()); ns = nosend(w); w.close()
    return rc, live2, n, ns

@safe
def p15():
    res = {}
    for name, h2 in (("lead_space", " contact-ana"), ("upper_tab", "CONTACT-ANA\t"), ("mixed_case", "Contact-Ana"), ("fullwidth_c", "\uff43ontact-ana"),
                     ("all_fullwidth", "".join(chr(ord(ch) + 0xFEE0) for ch in "contact-ana")), ("nbsp_trailing", "contact-ana\u00a0"), ("ideographic_space", "\u3000contact-ana"),
                     ("sharp_s_casefold", None)):
        if h2 is None:
            rc, live2, n, ns = dup("strasse-ana", "STRASSE-ANA".replace("SS", "\u00df"))  # 'STRAßE-ANA' casefolds to 'strasse-ana'
        else:
            rc, live2, n, ns = dup("contact-ana", h2)
        res[name] = (rc == 2 and n == 0 and ns, {"rc": rc, "c-ana2_live": live2, "drafts": n})
    for name, h in (("missing", "<del>"), ("empty", ""), ("spaces", "   "), ("tab_newline", "\t\n"), ("number", 5), ("list", ["contact-x"]), ("null", None)):
        w = W(); c = w.acc["contacts"][1]
        if h == "<del>": c.pop("handle", None)
        else: c["handle"] = h
        rc, _ = w.run(); n = len(w.drafts()); w.close(); res["handle_" + name] = (rc == 2 and n == 0, {"rc": rc, "drafts": n})
    # authoring fix (disclosed): the first version used contact-ben, which is c-ben's handle, and accepted rc 2
    rc, live2, n, ns = dup("contact-ana", "contact-zed"); res["different_people_still_fine"] = (rc == 0 and live2 == ["checkin", "welcome"], {"rc": rc, "c-ana2_live": live2})
    w = W(); rc, _ = w.run(); res["clean_fixture_still_runs"] = (rc == 0 and len(w.live()) == 7, rc); w.close()
    row("P15 r2 person key: a second record whose handle differs only by case, spacing or character width is refused with nothing written; a missing, blank or non-text handle is refused; the clean fixture still runs", all(v[0] for v in res.values()), res)

@safe
def o18():
    res = {}
    base = "ana(at)clinic.example"
    for name, h2 in (("plus_addressing", "ana+billing(at)clinic.example"), ("dot_alias", "a.na(at)clinic.example"), ("other_domain_alias", "ana(at)clinic-mail.example"),
                     ("cyrillic_a", "\u0430na(at)clinic.example"), ("greek_omicron", "ana(at)clinic.ex\u03bfmple"), ("zero_width_space", "ana\u200b(at)clinic.example"),
                     ("zero_width_joiner", "an\u200da(at)clinic.example"), ("soft_hyphen", "ana\u00ad(at)clinic.example"), ("trailing_dot", "ana(at)clinic.example."),
                     ("combining_acute_vs_precomposed", None)):
        # handles are written with "(at)" so the published source holds no address-shaped text; the run uses the real character
        if h2 is None: rc, live2, n, ns = dup(*[x.replace("(at)", chr(64)) for x in ("jos\u00e9(at)clinic.example", "jose\u0301(at)clinic.example")])
        else: rc, live2, n, ns = dup(base.replace("(at)", chr(64)), h2.replace("(at)", chr(64)))
        res[name] = {"rc": rc, "refused": rc == 2, "c-ana2_live_drafts_to_opted_out_person": live2, "nothing_sent": ns}
    row("O18 OBS beyond the builder's probe: aliases, plus-addressing, confusables and invisible characters on a second record of an opted-out person (the doc only promises case, spacing and width)", True, res)

@safe
def p16():
    res = {}
    def snap(w):
        out = {}
        for root, _, fs in os.walk(w.st):
            for f in fs:
                q = os.path.join(root, f)
                if f.endswith(".lock"): continue
                out[os.path.relpath(q, w.st)] = hashlib.sha256(open(q, "rb").read()).hexdigest()
        return out
    w = W(); w.evs += [ev("D1", "opt_out", T0, contact="c-ana", scope="all")]; rc1, _ = w.run(now="2026-10-05T12:00:00-07:00"); s1 = snap(w)
    ana_live1 = [a for c, a, _ in w.live() if c == "c-ana"]
    good = w.acc; dupacc = copy.deepcopy(good); dupacc["contacts"].append({"id": "c-ana2", "name": "Ana", "handle": " CONTACT-ANA ", "consent": "granted"})
    w.acc = dupacc; w.evs.append(ev("D2", "signup", "2026-10-06T09:00:00-07:00", contact="c-ana2")); rc2, _ = w.run(); s2 = snap(w)
    res["duplicate_import_refused_state_untouched"] = (rc1 == 0 and rc2 == 2 and s1 == s2 and ana_live1 == [], {"rc1": rc1, "rc2": rc2, "changed": sorted(k for k in set(s1) | set(s2) if s1.get(k) != s2.get(k))[:5]})
    w.acc = copy.deepcopy(good); w.evs = [e for e in w.evs if e["id"] != "D2"]; rc3, j3 = w.run(); ana3 = [a for c, a, _ in w.live() if c == "c-ana"]
    res["merged_rerun_ok_ana_still_suppressed"] = (rc3 == 0 and ana3 == [], {"rc": rc3, "ana_live": ana3})
    w.acc = dupacc; w.evs.append(ev("D2", "signup", "2026-10-06T09:00:00-07:00", contact="c-ana2")); s3 = snap(w); rc4, _ = w.run(); s4 = snap(w)
    res["reimport_after_merge_refused_again"] = (rc4 == 2 and s3 == s4, rc4)
    keep_new = copy.deepcopy(good); keep_new["contacts"][0]["id"] = "c-ana2"; w.acc = keep_new; w.evs = [e for e in w.evs if e["id"] != "D2"]; rc5, _ = w.run(); s5 = snap(w)
    res["merge_keeping_new_id_with_old_history_fails_closed"] = (rc5 == 2 and s5 == s4 or (rc5 == 0 and not any(c == "c-ana2" for c, a, _ in w.live())), {"rc": rc5})
    moved = copy.deepcopy(good); moved["contacts"][0]["handle"] = "contact-ana-new-crm-id"; w.acc = moved; rc6, _ = w.run(now="2026-10-09T12:00:00-07:00"); ana6 = [a for c, a, _ in w.live() if c == "c-ana"]
    res["suppression_follows_person_after_handle_change"] = (rc6 == 0 and ana6 == [], {"rc": rc6, "ana_live": ana6})
    res["nothing_sent"] = (nosend(w), None); w.close()
    w = W(); acc = copy.deepcopy(ACC); acc["contacts"][0]["id"] = "c-ana2"; w.acc = acc
    evs = [dict(e, contact="c-ana2") if e.get("contact") == "c-ana" else e for e in EVS] + [ev("D1", "opt_out", T0, contact="c-ana2", scope="all")]; w.evs = evs
    rc7, _ = w.run(); res["merged_history_rewritten_to_new_id_suppressed"] = (rc7 == 0 and not any(c == "c-ana2" for c, a, _ in w.live()), rc7); w.close()
    row("P16 r2 merge flow: a duplicate import is refused with state byte-identical; after the merge the rerun is clean and the person stays suppressed; re-importing the duplicate is refused again; suppression follows the person through an id or handle change", all(v[0] for v in res.values()), res)

@safe
def o17():
    w = W(); w.evs += [ev("D1", "opt_out", T0, contact="c-ana", scope="all")]; rc1, _ = w.run(now="2026-10-05T12:00:00-07:00")
    acc = copy.deepcopy(ACC); acc["contacts"][0]["id"] = "c-ana2"; w.acc = acc
    w.evs = [e for e in EVS if e.get("contact") != "c-ana"] + [ev("N1", "signup", "2026-10-06T09:00:00-07:00", contact="c-ana2")]
    rc2, j = w.run(now="2026-10-08T12:00:00-07:00"); live = sorted(a for c, a, _ in w.live() if c == "c-ana2"); w.close()
    row("O17 OBS: same state dir, the person re-imported under a new id with the old history dropped from the event file: does the state remember her opt-out?", True, {"rc1": rc1, "rc2": rc2, "c-ana2_live": live, "notes": [n.get("note") for n in j.get("notes", [])]})

@safe
def p11():
    src = open(TOOL).read(); imports = [m for m in ("socket", "smtplib", "urllib", "http.client", "subprocess", "requests", "ftplib", "webbrowser") if ("import " + m) in src or ("from " + m) in src]
    row("P11 nothing is ever sent: no send-capable import in the tool and no audited network/process/mail event in any run of this oracle", not imports and not AUDIT_HITS, {"imports": imports, "audit_hits": AUDIT_HITS[:5]})

for f in (p01, p02, p03, p04, p05, p06, p07, p08, p09, p10, p12, p13, p14, p15, p16, o17, o18, p11): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
n = sum(r["pass"] for r in ROWS); print("M32R2 ORACLE %d/%d core %s" % (n, len(ROWS), "PASS" if n == len(ROWS) else "FAIL"))
