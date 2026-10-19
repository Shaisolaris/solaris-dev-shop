#!/usr/bin/env python3
"""Consent-aware customer success follow-through: drafts only, never a send (G32).

Reads an account file (schema solaris.cs-account/1: account id, owner, contacts with consent) and an
append-only event log (JSON lines: signup, ticket_opened, agent_response, reply_received, ticket_closed,
opt_out, opt_in, bounce, owner_change). From the whole event history it derives, deterministically, every
follow-up the playbook calls for (onboarding welcome, check-in and training invite; support acknowledgement;
a nudge when a customer has not replied to our response; a feedback request after a ticket closes), then
applies consent and reply state:

- every contact needs a handle; a second contact with the same handle (ignoring case, spacing and width) is
  the same person imported twice and the account is refused until it is merged;
- an opt-out (scope all or marketing) or a hard bounce suppresses the person from then on, for good; a
  later opt_in is flagged for human review and the contact stays suppressed;
- a reply from the customer cancels the nudge or check-in it would have triggered;
- a draft already written for an action that is now suppressed or cancelled is withdrawn (its file says so);
- an owner change re-renders unsent drafts under the new owner (reassigned).

Each action has a key sha256(account, contact, action, trigger event). The key is looked up in the state
ledger under an exclusive lock before a draft is written, and the draft path is derived from the key, so a
retry, a second worker or a worker that crashed mid-step cannot create a second draft for the same action.
Every run appends a receipt to a hash-chained journal (the G04 journal), so the next worker resumes from
state with `status` or another `run`.

Usage:
  followthrough.py run STATE --account ACCOUNT.json --events EVENTS.jsonl --now ISO-TIME --worker NAME
                   [--json] [--fail-at drafted|ledgered]
  followthrough.py status STATE [--json]
Exit codes: 0 done; 2 invalid input or a state that does not verify (nothing written); 4 another worker
holds the state lock (nothing written); 75 crash drill (--fail-at). Python 3.9+, standard library, POSIX.
Nothing is sent: drafts are files for a person to review and send from their own client.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ACCOUNT = "solaris.cs-account/1"
DRAFT = "solaris.cs-draft/1"
HANDOFF = Path(__file__).resolve().parents[2] / "infrastructure" / "fleet-dispatcher" / "handoff.py"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EVENTS = ("signup", "ticket_opened", "agent_response", "reply_received", "ticket_closed", "opt_out", "opt_in",
          "bounce", "owner_change")
# playbook: action -> (kind, delay); marketing kinds are suppressed by a marketing opt-out, support only by "all"
PLAYBOOK = {"welcome": ("onboarding", dt.timedelta(0)), "checkin": ("onboarding", dt.timedelta(days=3)),
            "training": ("onboarding", dt.timedelta(days=7)), "ack": ("support", dt.timedelta(0)),
            "nudge": ("support", dt.timedelta(days=2)), "feedback": ("feedback", dt.timedelta(days=1))}
MARKETING = ("onboarding", "feedback")
CRASH = 75


class Invalid(Exception):
    pass


def person_key(handle):
    """One person, however the import spelled the handle: NFKC, whitespace collapsed, case folded."""
    return " ".join(unicodedata.normalize("NFKC", handle).split()).casefold()


def _g04():
    if not HANDOFF.is_file():
        raise Invalid("G04 handoff module not found at %s" % HANDOFF)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("g04_handoff", str(HANDOFF))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _time(v, w):
    if not isinstance(v, str):
        raise Invalid("%s must be an ISO time with offset" % w)
    try:
        t = dt.datetime.fromisoformat(v)
    except ValueError:
        raise Invalid("%s is not an ISO time: %r" % (w, v))
    if t.tzinfo is None:
        raise Invalid("%s needs a UTC offset" % w)
    return t.astimezone(dt.timezone.utc)


def load_account(path):
    try:
        a = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as ex:
        raise Invalid("account unreadable: %s" % ex.__class__.__name__)
    if not isinstance(a, dict) or a.get("schema") != ACCOUNT:
        raise Invalid("account schema must be %s" % ACCOUNT)
    if not isinstance(a.get("account_id"), str) or not ID.match(a["account_id"]):
        raise Invalid("account_id must be a short identifier")
    if not isinstance(a.get("owner"), str) or not a["owner"].strip():
        raise Invalid("owner must name the accountable person or role")
    cs, people = {}, {}
    for i, c in enumerate(a.get("contacts") or []):
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not ID.match(c["id"]) or c["id"] in cs:
            raise Invalid("contacts[%d] needs a unique short id" % i)
        if c.get("consent") not in ("granted", "unknown"):
            raise Invalid("contacts.%s.consent must be granted or unknown" % c["id"])
        if not isinstance(c.get("name"), str) or not c["name"].strip():
            raise Invalid("contacts.%s.name is required" % c["id"])
        h = c.get("handle")
        if not isinstance(h, str) or not person_key(h):
            raise Invalid("contacts.%s.handle is required (consent belongs to the person it reaches)" % c["id"])
        k = person_key(h)
        if k in people:
            # a duplicate import of one person: consent is per person, so merge the records before running
            raise Invalid("contacts.%s and contacts.%s have the same handle once case and spaces are ignored; "
                          "merge the duplicate import first" % (people[k], c["id"]))
        people[k] = c["id"]
        c["_person"] = k
        cs[c["id"]] = c
    if not cs:
        raise Invalid("account has no contacts")
    return a, cs


def load_events(path, contacts):
    try:
        raw = Path(path).read_bytes()
    except OSError as ex:
        raise Invalid("events unreadable: %s" % ex.strerror)
    seen, out = {}, []
    for n, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise Invalid("events line %d is not JSON" % n)
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not ID.match(e["id"]):
            raise Invalid("events line %d needs a short id" % n)
        if e.get("type") not in EVENTS:
            raise Invalid("events line %d: unknown type %r" % (n, e.get("type")))
        canon = json.dumps(e, sort_keys=True)
        if e["id"] in seen:
            if seen[e["id"]] != canon:
                raise Invalid("event %s appears twice with different content" % e["id"])
            continue  # exact redelivery of the same event: counted once
        seen[e["id"]] = canon
        e["_t"] = _time(e.get("at"), "event %s at" % e["id"])
        if e["type"] == "owner_change":
            if not isinstance(e.get("owner"), str) or not e["owner"].strip():
                raise Invalid("event %s needs the new owner" % e["id"])
        else:
            if e.get("contact") not in contacts:
                raise Invalid("event %s names unknown contact %r" % (e["id"], e.get("contact")))
        if e["type"] in ("ticket_opened", "agent_response", "reply_received", "ticket_closed"):
            if not isinstance(e.get("thread"), str) or not ID.match(e["thread"]):
                raise Invalid("event %s needs a thread id" % e["id"])
        if e["type"] == "opt_out" and e.get("scope") not in ("all", "marketing"):
            raise Invalid("event %s opt_out scope must be all or marketing" % e["id"])
        if e["type"] == "bounce" and e.get("kind") not in ("hard", "soft"):
            raise Invalid("event %s bounce kind must be hard or soft" % e["id"])
        out.append(e)
    out.sort(key=lambda e: (e["_t"], e["id"]))
    return out, raw


def derive(account, contacts, events, now):
    """Pure function of the inputs: desired actions with their state at `now`."""
    acts, notes = [], []
    supp = {}  # person (normalized handle) -> list of (time, scope, event); follows the person, not the record id
    who = lambda cid: contacts[cid]["_person"]
    owner = account["owner"].strip()
    replies = {}  # (contact, thread) -> [times]
    for e in events:
        if e["_t"] > now:
            continue
        t = e["type"]
        if t == "owner_change":
            owner = e["owner"].strip()
        elif t == "opt_out":
            supp.setdefault(who(e["contact"]), []).append((e["_t"], e["scope"], "%s (opt-out %s)" % (e["id"], e["scope"])))
        elif t == "bounce" and e["kind"] == "hard":
            supp.setdefault(who(e["contact"]), []).append((e["_t"], "all", "%s (hard bounce)" % e["id"]))
        elif t == "opt_in":
            if supp.get(who(e["contact"])):
                notes.append({"note": "consent_review_required", "contact": e["contact"], "event": e["id"],
                              "detail": "opt_in after an opt-out or bounce; the contact stays suppressed until a person reviews it"})
        elif t == "reply_received":
            replies.setdefault((e["contact"], e["thread"]), []).append(e["_t"])
    first = {}
    for e in events:
        if e["_t"] > now:
            continue
        c, t = e.get("contact"), e["type"]
        if t == "signup":
            if c in first:
                continue
            first[c] = e
            for a in ("welcome", "checkin", "training"):
                acts.append({"action": a, "contact": c, "trigger": e["id"], "thread": "onboarding-" + c, "base": e["_t"]})
        elif t == "ticket_opened":
            acts.append({"action": "ack", "contact": c, "trigger": e["id"], "thread": e["thread"], "base": e["_t"]})
        elif t == "agent_response":
            acts.append({"action": "nudge", "contact": c, "trigger": e["id"], "thread": e["thread"], "base": e["_t"]})
        elif t == "ticket_closed":
            acts.append({"action": "feedback", "contact": c, "trigger": e["id"], "thread": e["thread"], "base": e["_t"]})
    closed = {(e["contact"], e["thread"]): e["_t"] for e in events if e["type"] == "ticket_closed" and e["_t"] <= now}
    for x in acts:
        kind, delay = PLAYBOOK[x["action"]]
        x["kind"], x["due"] = kind, x["base"] + delay
        x["state"], x["reason"] = "due" if x["due"] <= now else "scheduled", None
        # consent: any opt-out or hard bounce up to now suppresses the contact for good, including unsent drafts
        for (st, scope, why) in supp.get(who(x["contact"]), []):
            if scope == "all" or kind in MARKETING:
                x["state"], x["reason"] = "suppressed", why
                break
        if x["state"] in ("due", "scheduled") and kind in MARKETING and contacts[x["contact"]]["consent"] != "granted":
            x["state"], x["reason"] = "suppressed", "no recorded consent for %s messages" % kind
        if x["state"] in ("due", "scheduled"):
            rs = [r for r in replies.get((x["contact"], x["thread"]), []) if r > x["base"]]
            if x["action"] == "nudge" and rs:
                x["state"], x["reason"] = "cancelled", "customer replied"
            elif x["action"] == "checkin" and rs:
                x["state"], x["reason"] = "cancelled", "customer replied to onboarding"
            elif x["action"] == "nudge" and (x["contact"], x["thread"]) in closed and closed[(x["contact"], x["thread"])] > x["base"]:
                x["state"], x["reason"] = "cancelled", "ticket closed"
    return acts, notes, owner


def _key(H, account_id, x):
    return H.sha_bytes(H.canon([account_id, x["contact"], x["action"], x["trigger"]]).encode("utf-8"))


SUBJECT = {"welcome": "Welcome aboard", "checkin": "Checking in on your first days", "training": "Training session invitation",
           "ack": "We received your request", "nudge": "Following up on your request", "feedback": "How did we do?"}


def render(account, contacts, x, key, owner):
    c = contacts[x["contact"]]
    body = ["Hello %s," % c["name"], "", "[%s draft for %s, thread %s]" % (x["action"], account["account_id"], x["thread"]), "",
            "%s" % owner]
    if x["kind"] in MARKETING:
        body += ["", "To stop these messages, reply STOP or use the unsubscribe link (inserted by the sending system)."]
    return {"schema": DRAFT, "key": key, "status": "draft", "send": "not performed; a person reviews and sends",
            "account": account["account_id"], "contact": x["contact"], "handle": c.get("handle"), "action": x["action"],
            "kind": x["kind"], "thread": x["thread"], "trigger": x["trigger"], "due": x["due"].isoformat(),
            "owner": owner, "subject": SUBJECT[x["action"]], "body": "\n".join(body) + "\n"}


def _read(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def run(state, account_path, events_path, now_s, worker, fail_at=None):
    H = _g04()
    now = _time(now_s, "--now")
    account, contacts = load_account(account_path)
    events, raw = load_events(events_path, contacts)
    if not isinstance(worker, str) or not ID.match(worker):
        raise Invalid("--worker must be a short name")
    state = Path(state)
    try:
        H.Journal(state / "journal.jsonl")  # verify before taking anything
    except H.OrderError as ex:
        raise Invalid(str(ex))
    fd = H.try_lock(state / ".lock")
    if fd is None:
        return None, 4
    try:
        j = H.Journal(state / "journal.jsonl")
        for ent in j.entries:
            if ent.get("type") == "run" and ent.get("account") != account["account_id"]:
                raise Invalid("state belongs to account %s" % ent.get("account"))
        led = state / "ledger.jsonl"
        recs = [r for r in H.ledger_records(state) if not r.get("unreadable")]
        drafted = {}
        for r in recs:
            if r.get("event") in ("drafted", "reassigned", "withdrawn"):
                drafted.setdefault(r["key"], []).append(r)
        acts, notes, cur_owner = derive(account, contacts, events, now)
        rep = {"drafted": [], "duplicate_suppressed": [], "withdrawn": [], "reassigned": [], "suppressed": [],
               "cancelled": [], "scheduled": []}
        (state / "drafts").mkdir(parents=True, exist_ok=True)

        def ledger(rec):
            if led.exists() and led.stat().st_size and not led.read_bytes().endswith(b"\n"):
                with open(led, "ab") as f:
                    f.write(b"\n")  # a torn last line must not swallow this record
            with open(led, "ab") as f:
                f.write((H.canon(rec) + "\n").encode("utf-8")); f.flush(); os.fsync(f.fileno())

        for x in sorted(acts, key=lambda x: (x["due"], x["contact"], x["action"], x["trigger"])):
            k = _key(H, account["account_id"], x)
            path = state / "drafts" / ("%s-%s.json" % (k[:16], x["action"]))
            hist = drafted.get(k, [])
            last = hist[-1]["event"] if hist else None
            row = {"key": k[:16], "action": x["action"], "contact": x["contact"], "due": x["due"].isoformat()}
            if x["state"] == "due":
                if last is None:
                    d = render(account, contacts, x, k, cur_owner)
                    H.atomic_write(path, (json.dumps(d, indent=1, sort_keys=True) + "\n").encode("utf-8"))
                    if fail_at == "drafted":
                        os._exit(CRASH)
                    ledger({"event": "drafted", "key": k, "owner": d["owner"], "worker": worker, "at": now.isoformat()})
                    if fail_at == "ledgered":
                        os._exit(CRASH)
                    rep["drafted"].append(row)
                elif last == "withdrawn":
                    rep["withdrawn"].append(dict(row, reason="withdrawn earlier; never redrafted"))
                else:
                    cur = _read(path)
                    if cur is None or cur.get("key") != k:
                        notes.append({"note": "draft_file_missing", "contact": x["contact"], "event": x["trigger"],
                                      "detail": "action %s is in the ledger but its draft file is gone or altered; not redrafted" % k[:16]})
                        rep["duplicate_suppressed"].append(row)
                    elif cur.get("owner") != cur_owner and cur.get("status") == "draft":
                        d = render(account, contacts, x, k, cur_owner)
                        H.atomic_write(path, (json.dumps(d, indent=1, sort_keys=True) + "\n").encode("utf-8"))
                        ledger({"event": "reassigned", "key": k, "owner": cur_owner, "worker": worker, "at": now.isoformat()})
                        rep["reassigned"].append(dict(row, owner=cur_owner))
                    else:
                        rep["duplicate_suppressed"].append(row)
            else:
                if last in ("drafted", "reassigned"):
                    cur = _read(path)
                    if cur is not None and cur.get("key") == k:
                        cur.update({"status": "withdrawn", "withdrawn_reason": x["reason"], "send": "do not send"})
                        H.atomic_write(path, (json.dumps(cur, indent=1, sort_keys=True) + "\n").encode("utf-8"))
                    ledger({"event": "withdrawn", "key": k, "reason": x["reason"], "worker": worker, "at": now.isoformat()})
                    rep["withdrawn"].append(dict(row, reason=x["reason"]))
                elif x["state"] == "scheduled":
                    rep["scheduled"].append(row)
                else:
                    rep[x["state"]].append(dict(row, reason=x["reason"]))
        supp = sorted({x["contact"] for x in acts if x["state"] == "suppressed" and "no recorded consent" not in (x["reason"] or "")})
        j.append({"type": "run", "account": account["account_id"], "worker": worker, "now": now.isoformat(),
                  "events_sha256": H.sha_bytes(raw), "owner": cur_owner,
                  "counts": {k: len(v) for k, v in rep.items()}, "suppressed_contacts": supp})
        out = {"account": account["account_id"], "owner": cur_owner, "now": now.isoformat(), "worker": worker,
               "notes": notes, "suppressed_contacts": supp, "sent": 0, **rep}
        return out, 0
    finally:
        os.close(fd)


def status(state):
    H = _g04()
    state = Path(state)
    try:
        j = H.Journal(state / "journal.jsonl")
    except H.OrderError as ex:
        raise Invalid(str(ex))
    runs = [e for e in j.entries if e.get("type") == "run"]
    recs = [r for r in H.ledger_records(state) if not r.get("unreadable")]
    last = {}
    for r in recs:
        last[r["key"]] = r["event"]
    open_drafts = sorted(k[:16] for k, ev in last.items() if ev in ("drafted", "reassigned"))
    return {"runs": len(runs), "last_run": runs[-1] if runs else None, "open_drafts": open_drafts,
            "withdrawn": sorted(k[:16] for k, ev in last.items() if ev == "withdrawn"), "sent": 0}, 0


def text(r):
    if "runs" in r:
        lr = r["last_run"] or {}
        return "status: %d run(s); last by %s at %s; %d open draft(s), %d withdrawn; sent 0" % (
            r["runs"], lr.get("worker"), lr.get("now"), len(r["open_drafts"]), len(r["withdrawn"]))
    L = ["%s (owner %s) at %s by %s: drafted %d, duplicate suppressed %d, withdrawn %d, reassigned %d, suppressed %d, "
         "cancelled %d, scheduled %d; sent 0" % (r["account"], r["owner"], r["now"], r["worker"], len(r["drafted"]),
                                                 len(r["duplicate_suppressed"]), len(r["withdrawn"]), len(r["reassigned"]),
                                                 len(r["suppressed"]), len(r["cancelled"]), len(r["scheduled"]))]
    for n in r["notes"]:
        L.append("  NOTE %s %s: %s" % (n["note"], n["contact"], n["detail"]))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="followthrough.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("state"); r.add_argument("--account", required=True); r.add_argument("--events", required=True)
    r.add_argument("--now", required=True); r.add_argument("--worker", required=True); r.add_argument("--json", action="store_true")
    r.add_argument("--fail-at", choices=("drafted", "ledgered"))
    s = sub.add_parser("status"); s.add_argument("state"); s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "run":
            out, code = run(a.state, a.account, a.events, a.now, a.worker, a.fail_at)
            if code == 4:
                print("BUSY: another worker holds %s; nothing written" % a.state, file=sys.stderr)
                return 4
        elif a.cmd == "status":
            out, code = status(a.state)
        else:
            ap.print_help(); return 2
        print(json.dumps(out, indent=1, sort_keys=True) if a.json else text(out))
        return code
    except Invalid as ex:
        print("INVALID: %s. Nothing was written." % ex, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
