#!/usr/bin/env python3
"""G32 oracle: consent-aware follow-through checked against an independent reference simulation of the
documented playbook, with crash drills, concurrent workers, lock, torn ledger, invalid input and seeded
unseen accounts at scale. Usage: followthrough_oracle.py [--tool PATH] [--seed N]. Prints one line per check
and ACCEPTED n/n or REJECTED k/n. Standard library only; everything happens in a temporary folder."""
import argparse, datetime as dt, fcntl, json, os, random, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOL = ROOT / "employees" / "sales-outreach" / "customer-success" / "followthrough.py"
FIX = HERE / "fixtures"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
DAY = dt.timedelta(days=1)
RUNS = ["2026-10-02T12:00:00-07:00", "2026-10-05T12:00:00-07:00", "2026-10-08T12:00:00-07:00"]


def T(s):
    return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)


class Ref:
    """Independent reference: replays runs and tracks which actions hold an open or withdrawn draft."""

    def __init__(self, account, events):
        self.acc = account
        self.consent = {c["id"]: c["consent"] for c in account["contacts"]}
        uniq = {}
        for e in events:
            uniq.setdefault(e["id"], e)
        self.ev = sorted(uniq.values(), key=lambda e: (T(e["at"]), e["id"]))
        self.drafts = {}  # (contact, action, trigger) -> [status, owner]

    def run(self, now_s):
        now = T(now_s)
        ev = [e for e in self.ev if T(e["at"]) <= now]
        owner = self.acc["owner"]
        for e in ev:
            if e["type"] == "owner_change":
                owner = e["owner"]
        acts, seen = [], set()
        for e in ev:
            c, t, at = e.get("contact"), e["type"], T(e["at"])
            if t == "signup" and c not in seen:
                seen.add(c)
                acts += [(c, "welcome", e["id"], at, at, "onboarding-" + c), (c, "checkin", e["id"], at + 3 * DAY, at, "onboarding-" + c),
                         (c, "training", e["id"], at + 7 * DAY, at, "onboarding-" + c)]
            elif t == "ticket_opened":
                acts.append((c, "ack", e["id"], at, at, e["thread"]))
            elif t == "agent_response":
                acts.append((c, "nudge", e["id"], at + 2 * DAY, at, e["thread"]))
            elif t == "ticket_closed":
                acts.append((c, "feedback", e["id"], at + DAY, at, e["thread"]))
        for (c, a, trig, due, base, th) in acts:
            mk = a in ("welcome", "checkin", "training", "feedback")
            stop = any(e.get("contact") == c and ((e["type"] == "opt_out" and (e["scope"] == "all" or mk)) or
                                                  (e["type"] == "bounce" and e["kind"] == "hard")) for e in ev)
            stop = stop or (mk and self.consent[c] != "granted")
            if a == "nudge":
                stop = stop or any(e.get("contact") == c and e.get("thread") == th and e["type"] in ("reply_received", "ticket_closed")
                                   and T(e["at"]) > base for e in ev)
            if a == "checkin":
                stop = stop or any(e.get("contact") == c and e.get("thread") == th and e["type"] == "reply_received" and T(e["at"]) > base for e in ev)
            k = (c, a, trig)
            d = self.drafts.get(k)
            if stop:
                if d and d[0] == "draft":
                    d[0] = "withdrawn"
            elif due <= now and d is None:
                self.drafts[k] = ["draft", owner]
        for d in self.drafts.values():
            if d[0] == "draft":
                d[1] = owner


def tool_state(state):
    out = {}
    for f in sorted((Path(state) / "drafts").glob("*.json")) if (Path(state) / "drafts").exists() else []:
        d = json.loads(f.read_text())
        k = (d["contact"], d["action"], d["trigger"])
        if k in out:
            out[k] = ["DUPLICATE", None]
        else:
            out[k] = [d["status"], d["owner"]]
    return out


def ledger_dupes(state):
    p = Path(state) / "ledger.jsonl"
    if not p.exists():
        return 0
    keys = []
    for l in p.read_bytes().splitlines():
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get("event") == "drafted":
            keys.append(r["key"])
    return len(keys) - len(set(keys))


class Ctx:
    def __init__(self, tool):
        self.tool, self.tmp, self.n = tool, Path(tempfile.mkdtemp(prefix="g32-oracle-")), 0

    def dir(self):
        self.n += 1; d = self.tmp / ("w%d" % self.n); d.mkdir(); return d

    def run(self, state, acc, evs, now, worker="w1", *extra):
        if not Path(self.tool).is_file():
            return 127, "", ""
        r = subprocess.run([sys.executable, str(self.tool), "run", str(state), "--account", str(acc), "--events", str(evs),
                            "--now", now, "--worker", worker, "--json"] + list(extra), capture_output=True, text=True, env=ENV, timeout=300)
        return r.returncode, r.stdout, r.stderr

    def popen(self, state, acc, evs, now, worker):
        return subprocess.Popen([sys.executable, str(self.tool), "run", str(state), "--account", str(acc), "--events", str(evs),
                                 "--now", now, "--worker", worker], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ENV)


def write(d, account, events):
    a = d / "account.json"; a.write_text(json.dumps(account))
    e = d / "events.jsonl"; e.write_text("".join(json.dumps(x) + "\n" for x in events))
    return a, e


def fixture():
    return json.loads((FIX / "account.json").read_text()), [json.loads(l) for l in (FIX / "events.jsonl").read_text().splitlines() if l.strip()]


def o1(c):
    acc, ev = fixture(); d = c.dir(); a, e = write(d, acc, ev); ref = Ref(acc, ev); ok = True; outs = []
    for i, now in enumerate(RUNS):
        rc, out, err = c.run(d / "s", a, e, now, "w%d" % (i % 2 + 1)); ref.run(now)
        ok = ok and rc == 0 and tool_state(d / "s") == ref.drafts
        outs.append(json.loads(out) if rc == 0 else {})
    want = {("c-ana", "welcome", "E01"): ["draft", "Priya (customer success lead, synthetic)"],
            ("c-dee", "welcome", "E04"): ["withdrawn", "Morgan (customer success, synthetic)"],
            ("c-ben", "nudge", "E08"): ["withdrawn", "Priya (customer success lead, synthetic)"]}
    st = tool_state(d / "s")
    ok = ok and all(st.get(k) == v for k, v in want.items()) and ("c-ben", "nudge", "E06") not in st and not any(k[0] == "c-cy" for k in st)
    ok = ok and len(st) == 9 and sum(1 for v in st.values() if v[0] == "draft") == 7
    ok = ok and outs[2].get("notes", [{}])[0].get("note") == "consent_review_required" and all(o.get("sent") == 0 for o in outs)
    return ok, "fixture over three runs and two workers matches the reference (9 drafts, 7 open, 2 withdrawn)"


def o2(c):
    acc, ev = fixture(); d = c.dir(); a, e = write(d, acc, ev + ev[:5])
    for now in RUNS:
        c.run(d / "s", a, e, now)
    before = tool_state(d / "s"); rc, out, _ = c.run(d / "s", a, e, RUNS[-1], "w9")
    r = json.loads(out) if rc == 0 else {}
    bad = dict(ev[2]); bad["contact"] = "c-ana"; a2, e2 = write(c.dir(), acc, ev + [bad])
    rc2, _, err2 = c.run(d / "s2", a2, e2, RUNS[-1])
    ok = (rc == 0 and r.get("drafted") == [] and len(r.get("duplicate_suppressed", [])) == 7 and tool_state(d / "s") == before
          and ledger_dupes(d / "s") == 0 and rc2 == 2 and not (d / "s2").exists())
    return ok, "rerun and redelivered events draft nothing new; a reused event id with new content is refused"


def o3(c):
    acc, ev = fixture()
    ev2 = ev + [{"id": "E20", "type": "ticket_opened", "contact": "c-dee", "thread": "T9", "at": "2026-10-07T09:00:00-07:00"},
                {"id": "E21", "type": "bounce", "contact": "c-ana", "kind": "hard", "at": "2026-10-07T10:00:00-07:00"},
                {"id": "E22", "type": "opt_in", "contact": "c-ana", "at": "2026-10-07T11:00:00-07:00"},
                {"id": "E23", "type": "ticket_opened", "contact": "c-ana", "thread": "T8", "at": "2026-10-07T12:00:00-07:00"}]
    d = c.dir(); a, e = write(d, acc, ev2); ref = Ref(acc, ev2); ok = True
    for now in RUNS:
        rc, out, _ = c.run(d / "s", a, e, now); ref.run(now); ok = ok and rc == 0
    st = tool_state(d / "s")
    ok = (ok and st == ref.drafts and st.get(("c-dee", "ack", "E20"), [None])[0] == "draft" and ("c-ana", "ack", "E23") not in st
          and all(v[0] == "withdrawn" for k, v in st.items() if k[0] == "c-ana"))
    files = [json.loads(f.read_text()) for f in (d / "s" / "drafts").glob("*.json")]
    ok = ok and all(f["send"] == "do not send" for f in files if f["status"] == "withdrawn")
    ok = ok and all("unsubscribe" in f["body"] for f in files if f["kind"] in ("onboarding", "feedback"))
    notes = json.loads(out)["notes"] if out else []
    ok = ok and sorted(n["contact"] for n in notes if n["note"] == "consent_review_required") == ["c-ana", "c-dee"]
    return ok, "hard bounce and opt-out stay suppressed after opt_in; support still reaches a marketing opt-out"


def o4(c):
    acc, ev = fixture(); ok = True; drills = 0
    for point in ("drafted", "ledgered"):
        d = c.dir(); a, e = write(d, acc, ev); ref = Ref(acc, ev)
        for now in RUNS:
            # "ledgered" crashes progress one action per run; a "drafted" crash repeats on the same action,
            # so it is drilled once per run and the next worker resumes
            for _ in range(20 if point == "ledgered" else 1):
                rc, _, _ = c.run(d / "s", a, e, now, "w1", "--fail-at", point)
                drills += 1
                if rc != 75:
                    break
            ok = ok and rc in (0, 75)
            rc, _, _ = c.run(d / "s", a, e, now, "w2"); ref.run(now); ok = ok and rc == 0
        ok = ok and tool_state(d / "s") == ref.drafts and ledger_dupes(d / "s") == 0
    return ok, "%d crash drills after the draft and after the ledger record: no duplicate, state converges" % drills


def o5(c):
    acc, ev = fixture(); ok = True
    for rnd in range(3):
        d = c.dir(); a, e = write(d, acc, ev); ref = Ref(acc, ev)
        for now in RUNS:
            ps = [c.popen(d / "s", a, e, now, "w%d" % i) for i in range(8)]
            codes = [p.wait(120) for p in ps]
            ok = ok and set(codes) <= {0, 4} and 0 in codes
            c.run(d / "s", a, e, now, "wfinal"); ref.run(now)
        ok = ok and tool_state(d / "s") == ref.drafts and ledger_dupes(d / "s") == 0
    return ok, "8 concurrent workers per run (3 rounds): exit 0 or 4 only, one draft per action"


def o6(c):
    acc, ev = fixture(); d = c.dir(); a, e = write(d, acc, ev)
    c.run(d / "s", a, e, RUNS[0], "w1")
    rc, out, _ = c.run(d / "s", a, e, RUNS[1], "w2")
    r = json.loads(out) if rc == 0 else {}
    st = subprocess.run([sys.executable, str(c.tool), "status", str(d / "s"), "--json"], capture_output=True, text=True, env=ENV)
    s = json.loads(st.stdout) if st.returncode == 0 else {}
    opened = [v for v in tool_state(d / "s").values() if v[0] == "draft"]
    ok = (rc == 0 and r.get("owner") == "Priya (customer success lead, synthetic)" and len(r.get("reassigned", [])) == 3
          and all(v[1] == r["owner"] for v in opened) and s.get("runs") == 2 and s.get("last_run", {}).get("worker") == "w2"
          and len(s.get("open_drafts", [])) == 5)
    return ok, "ownership handoff: next worker resumes, unsent drafts re-rendered for the new owner, status shows state"


def o7(c):
    acc, ev = fixture(); bad = []
    x = json.loads(json.dumps(acc)); x["schema"] = "other"; bad.append((x, ev, "w1"))
    bad.append((acc, ev + [{"id": "E99", "type": "signup", "contact": "c-zed", "at": "2026-10-01T09:00:00-07:00"}], "w1"))
    bad.append((acc, ev + [{"id": "E99", "type": "signup", "contact": "c-ana", "at": "2026-10-01T09:00:00"}], "w1"))
    bad.append((acc, ev + [{"id": "E99", "type": "sent", "contact": "c-ana", "at": "2026-10-01T09:00:00-07:00"}], "w1"))
    bad.append((acc, ev + [{"id": "E99", "type": "opt_out", "contact": "c-ana", "at": "2026-10-01T09:00:00-07:00"}], "w1"))
    bad.append((acc, ev + [{"id": "E99", "type": "ticket_opened", "contact": "c-ana", "at": "2026-10-01T09:00:00-07:00"}], "w1"))
    x = json.loads(json.dumps(acc)); x["contacts"][0]["consent"] = "yes"; bad.append((x, ev, "w1"))
    bad.append((acc, ev, "bad worker"))
    ok = True
    for acc_, ev_, w in bad:
        d = c.dir(); a, e = write(d, acc_, ev_)
        rc, _, err = c.run(d / "s", a, e, RUNS[0], w)
        ok = ok and rc == 2 and not (d / "s").exists()
    d = c.dir(); a, e = write(d, acc, ev); c.run(d / "s", a, e, RUNS[0])
    j = d / "s" / "journal.jsonl"; lines = j.read_text().splitlines(); r = json.loads(lines[0]); r["entry"]["worker"] = "forged"
    j.write_text(json.dumps(r) + "\n" + "\n".join(lines[1:]) + ("\n" if lines[1:] else "")); led = (d / "s" / "ledger.jsonl").read_bytes()
    rc, _, _ = c.run(d / "s", a, e, RUNS[1]); ok = ok and rc == 2 and (d / "s" / "ledger.jsonl").read_bytes() == led
    acc2 = json.loads(json.dumps(acc)); acc2["account_id"] = "other-account"; a2, _ = write(c.dir(), acc2, ev)
    d3 = c.dir(); a3, e3 = write(d3, acc, ev); c.run(d3 / "s", a3, e3, RUNS[0])
    rc, _, _ = c.run(d3 / "s", a2, e3, RUNS[1]); ok = ok and rc == 2
    return ok, "%d invalid inputs create nothing; a forged journal and another account's state are refused" % len(bad)


def o8(c):
    acc, ev = fixture(); d = c.dir(); a, e = write(d, acc, ev); (d / "s").mkdir()
    fd = os.open(str(d / "s" / ".lock"), os.O_RDWR | os.O_CREAT); fcntl.flock(fd, fcntl.LOCK_EX)
    rc, _, _ = c.run(d / "s", a, e, RUNS[0]); os.close(fd)
    empty = sorted(x.name for x in (d / "s").iterdir()) == [".lock"]
    rc2, _, _ = c.run(d / "s", a, e, RUNS[0])
    with open(d / "s" / "ledger.jsonl", "ab") as f:
        f.write(b'{"event":"drafted","key":"tor')
    rc3, out3, _ = c.run(d / "s", a, e, RUNS[1]); ref = Ref(acc, ev); ref.run(RUNS[0]); ref.run(RUNS[1])
    ok = rc == 4 and empty and rc2 == 0 and rc3 == 0 and tool_state(d / "s") == ref.drafts and ledger_dupes(d / "s") == 0
    return ok, "held lock exits 4 with nothing written; a torn ledger tail does not swallow the next record"


def gen(rng, n):
    contacts = [{"id": "c%03d" % i, "name": "Contact %d" % i, "handle": "h%03d" % i, "consent": rng.choice(["granted"] * 4 + ["unknown"])} for i in range(n)]
    acc = {"schema": "solaris.cs-account/1", "account_id": "acct-%d" % rng.randrange(10 ** 6), "owner": "Owner A", "contacts": contacts}
    t0 = T("2026-10-01T08:00:00-07:00"); ev = []; k = 0
    def add(**kw):
        nonlocal k
        k += 1; kw["id"] = "X%05d" % k; kw["at"] = (t0 + dt.timedelta(minutes=kw.pop("m"))).isoformat(); ev.append(kw)
    for c in contacts:
        add(type="signup", contact=c["id"], m=rng.randrange(0, 2000))
        for tn in range(rng.randrange(0, 3)):
            th = "T%s-%d" % (c["id"], tn); m = rng.randrange(0, 12000)
            add(type="ticket_opened", contact=c["id"], thread=th, m=m)
            for _ in range(rng.randrange(0, 3)):
                m += rng.randrange(30, 4000); add(type="agent_response", contact=c["id"], thread=th, m=m)
                if rng.random() < 0.5:
                    add(type="reply_received", contact=c["id"], thread=th, m=m + rng.randrange(10, 4000))
            if rng.random() < 0.5:
                add(type="ticket_closed", contact=c["id"], thread=th, m=m + rng.randrange(60, 5000))
        if rng.random() < 0.3:
            add(type="reply_received", contact=c["id"], thread="onboarding-" + c["id"], m=rng.randrange(0, 9000))
        r = rng.random()
        if r < 0.12:
            add(type="opt_out", contact=c["id"], scope=rng.choice(["all", "marketing"]), m=rng.randrange(0, 14000))
        elif r < 0.17:
            add(type="bounce", contact=c["id"], kind=rng.choice(["hard", "soft"]), m=rng.randrange(0, 14000))
        if r < 0.17 and rng.random() < 0.4:
            add(type="opt_in", contact=c["id"], m=14500)
    for i in range(rng.randrange(1, 4)):
        add(type="owner_change", owner="Owner %s" % "BCD"[i], m=rng.randrange(0, 14000))
    dupes = rng.sample(ev, 20)
    rng.shuffle(ev)
    return acc, ev + dupes


def o9(c, seed):
    rng = random.Random(seed); ok = True; total = 0; nev = 0
    for i in range(3):
        acc, ev = gen(rng, rng.randint(120, 180)); nev += len(ev); d = c.dir(); a, e = write(d, acc, ev); ref = Ref(acc, ev)
        nows = sorted((T("2026-10-01T08:00:00-07:00") + dt.timedelta(minutes=rng.randrange(0, 16000))).isoformat() for _ in range(4))
        for now in nows:
            rc, _, _ = c.run(d / "s", a, e, now, "w%d" % rng.randrange(3)); ref.run(now); ok = ok and rc == 0
        st = tool_state(d / "s"); total += len(st)
        if st != ref.drafts:
            ok = False
            diff = [k for k in set(st) | set(ref.drafts) if st.get(k) != ref.drafts.get(k)][:3]
            print("    unseen %d: %s" % (i, [(k, st.get(k), ref.drafts.get(k)) for k in diff]))
        ok = ok and ledger_dupes(d / "s") == 0
    return ok, "3 seeded unseen accounts (120 to 180 contacts, %d event lines incl. redeliveries, 4 runs each, %d drafts) match the reference" % (nev, total)


def s1(c):
    src = Path(c.tool).read_text() if Path(c.tool).is_file() else ""
    banned = [w for w in ("smtplib", "import socket", "urllib", "http.client", "import subprocess", "os.system", "webbrowser") if w in src]
    return bool(src) and not banned, "no mail, network or process use in the tool%s" % (": " + ", ".join(banned) if banned else "")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tool", default=str(TOOL)); ap.add_argument("--seed", type=int, default=32)
    a = ap.parse_args(); c = Ctx(a.tool)
    before = {p: p.read_bytes() for p in FIX.rglob("*") if p.is_file()}
    checks = [("o1", o1), ("o2", o2), ("o3", o3), ("o4", o4), ("o5", o5), ("o6", o6), ("o7", o7), ("o8", o8), ("o9", lambda c: o9(c, a.seed)), ("s1", s1)]
    passed = 0
    for nm, fn in checks:
        try:
            ok, msg = fn(c)
        except Exception as ex:
            ok, msg = False, "error %s: %s" % (type(ex).__name__, ex)
        if nm == "s1":
            ok = ok and before == {p: p.read_bytes() for p in FIX.rglob("*") if p.is_file()}; msg += "; fixtures byte-identical"
        passed += bool(ok); print("%s %s %s" % ("PASS" if ok else "FAIL", nm, msg))
    shutil.rmtree(str(c.tmp), ignore_errors=True)
    print("%s %d/%d" % ("ACCEPTED" if passed == len(checks) else "REJECTED", passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
