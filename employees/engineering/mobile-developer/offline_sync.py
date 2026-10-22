#!/usr/bin/env python3
"""Offline-first client outbox for the G19 ledger API (synthetic, local, stdlib only).

A state engine, not a mobile app: it is what a device keeps in its local SQLite file while it is
offline, and how it hands those changes to the server without losing or doubling any of them.

- Every user change is written to the local outbox first (`enqueue`), with its own idempotency key
  (`<install id>:<seq>`) fixed at that moment, and its exact request body. Retries, restarts and a
  second concurrent sync reuse that key and body, so the server makes the effect once.
- `sync` sends pending changes in the order they were made. A change to an invoice created offline
  waits until that create is acknowledged and the server id is known. A change that the server
  refuses (409 conflict, 404, 4xx validation) becomes an explicit conflict or rejection with the
  server's answer kept; it is never dropped or silently retried. Later changes to the same invoice
  are held behind it until the user resolves it (`resolve`). Auth failures and outages stop the run
  with everything still pending.
- Server state pulled back (`sync` pull or `apply-snapshot`) is applied per invoice only when its
  `version` is newer, so late or out-of-order answers cannot roll the local view back.

Commands:
    offline_sync.py init --db FILE --device NAME
    offline_sync.py enqueue --db FILE create --ref REF --customer TEXT --amount CENTS --currency CUR
    offline_sync.py enqueue --db FILE pay --ref REF --amount CENTS
    offline_sync.py enqueue --db FILE void --ref REF [--reason TEXT]
    offline_sync.py sync --db FILE --base-url URL --key-file FILE [--no-pull] [--timeout S]
                         [--crash-before-send N] [--crash-after-send N]
    offline_sync.py status --db FILE [--json]
    offline_sync.py resolve --db FILE --op SEQ --action discard|retry
    offline_sync.py apply-snapshot --db FILE SNAPSHOT.json
    offline_sync.py check --db FILE [--json]

Exit codes: 0 done; 1 conflicts or rejections await the user (sync), violations (check); 2 invalid
input; 3 auth refused (nothing changed); 4 server unreachable or transient (changes stay pending);
5 another sync holds this outbox; 70 deliberate crash drill.
Python 3.9+, no third-party packages; talks to loopback URLs only.
"""
from __future__ import annotations

import argparse
import fcntl
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "solaris.offline-outbox/1"
STATES = ("pending", "acked", "conflict", "rejected", "discarded", "superseded")
OPEN_PROBLEMS = ("conflict", "rejected")
CURRENCIES = ("EUR", "GBP", "USD")
REF_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DEVICE_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
SERVER_ID_RE = re.compile(r"^inv_[0-9a-f]{16}$")
API = "/api/v1/invoices"

DDL = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ops (
  seq INTEGER PRIMARY KEY, idem TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, ref TEXT NOT NULL,
  body TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  http_status INTEGER, response TEXT, replayed INTEGER NOT NULL DEFAULT 0, reason TEXT,
  retry_of INTEGER, superseded_by INTEGER);
CREATE TABLE IF NOT EXISTS refs (ref TEXT PRIMARY KEY, server_id TEXT NOT NULL UNIQUE, create_seq INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS server (id TEXT PRIMARY KEY, version INTEGER NOT NULL, doc TEXT NOT NULL);
"""


class Invalid(Exception):
    pass


class Stop(Exception):
    def __init__(self, code, why):
        super().__init__(why)
        self.code, self.why = code, why


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db, create=False):
    p = Path(db)
    if not create and not p.is_file():
        raise Invalid("no outbox at %s (run init first)" % db)
    con = sqlite3.connect(str(p), timeout=30, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    if not create:
        try:
            row = con.execute("SELECT v FROM meta WHERE k = 'schema'").fetchone()
        except sqlite3.DatabaseError as e:
            raise Invalid("%s is not an outbox: %s" % (db, e))
        if not row or row[0] != SCHEMA:
            raise Invalid("%s is not a %s outbox" % (db, SCHEMA))
    return con


def meta(con, k):
    return con.execute("SELECT v FROM meta WHERE k = ?", (k,)).fetchone()[0]


def cmd_init(a):
    if not DEVICE_RE.match(a.device):
        raise Invalid("--device must be 1-40 of A-Z a-z 0-9 _ -")
    if Path(a.db).exists():
        raise Invalid("%s already exists; an outbox is never re-initialised over pending changes" % a.db)
    con = connect(a.db, create=True)
    con.executescript(DDL)
    install = "%s-%s" % (a.device, secrets.token_hex(4))
    con.execute("BEGIN IMMEDIATE")
    con.executemany("INSERT INTO meta VALUES (?, ?)", [("schema", SCHEMA), ("device", a.device),
                                                     ("install", install), ("created_at", now())])
    con.execute("COMMIT")
    print(json.dumps({"db": a.db, "device": a.device, "install": install}))
    return 0


def known_ref(con, ref):
    if con.execute("SELECT 1 FROM ops WHERE kind = 'create' AND ref = ?", (ref,)).fetchone():
        return True
    return bool(con.execute("SELECT 1 FROM server WHERE id = ?", (ref,)).fetchone())


def amount(v, lo=1):
    try:
        n = int(v, 10)
    except (TypeError, ValueError):
        raise Invalid("amount must be a whole number of cents, got %r" % v)
    if not lo <= n <= 10 ** 12:
        raise Invalid("amount must be %d..10^12 cents, got %d" % (lo, n))
    return n


def append_op(con, kind, ref, body, retry_of=None):
    """Append inside the caller's write transaction."""
    if kind == "create" and retry_of is None and known_ref(con, ref):
        raise Invalid("ref %s already names an invoice" % ref)
    if kind != "create" and not known_ref(con, ref):
        raise Invalid("ref %s is not an invoice this device created or has pulled" % ref)
    seq = con.execute("SELECT COALESCE(MAX(seq), 0) FROM ops").fetchone()[0] + 1
    idem = "%s:%06d" % (meta(con, "install"), seq)
    con.execute("INSERT INTO ops (seq, idem, kind, ref, body, created_at, state, retry_of) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)", (seq, idem, kind, ref, body, now(), retry_of))
    return seq, idem


def add_op(con, kind, ref, body):
    """Validate and append atomically, including the local invoice namespace."""
    con.execute("BEGIN IMMEDIATE")
    try:
        result = append_op(con, kind, ref, body)
        con.execute("COMMIT")
        return result
    except BaseException:
        con.execute("ROLLBACK")
        raise


def cmd_enqueue(a):
    con = connect(a.db)
    if not REF_RE.match(a.ref or ""):
        raise Invalid("--ref must be 1-64 of A-Z a-z 0-9 _ -")
    if a.kind == "create":
        if SERVER_ID_RE.match(a.ref):
            raise Invalid("ref %s looks like a server id; pick a local name" % a.ref)
        cust = a.customer or ""
        if not 1 <= len(cust) <= 80:
            raise Invalid("--customer must be 1-80 characters")
        if a.currency not in CURRENCIES:
            raise Invalid("--currency must be one of %s" % ", ".join(CURRENCIES))
        body = {"customer": cust, "amount_cents": amount(a.amount), "currency": a.currency}
    else:
        if a.kind == "pay":
            body = {"amount_cents": amount(a.amount)}
        else:
            if a.reason is not None and len(a.reason) > 200:
                raise Invalid("--reason must be at most 200 characters")
            body = {} if a.reason is None else {"reason": a.reason}
    seq, idem = add_op(con, a.kind, a.ref, json.dumps(body, sort_keys=True, separators=(",", ":")))
    print(json.dumps({"seq": seq, "kind": a.kind, "ref": a.ref, "idempotency_key": idem, "state": "pending"}))
    return 0


def loopback_url(url):
    u = urlsplit(url)
    if u.scheme != "http" or not u.hostname or u.path not in ("", "/") or u.query or u.username:
        raise Invalid("--base-url must be http://<loopback host>:<port>")
    host = u.hostname
    try:
        ok = ipaddress.ip_address(host).is_loopback
    except ValueError:
        ok = host == "localhost"
    if not ok:
        raise Invalid("--base-url must be a loopback address; this demo client never leaves the host")
    return "http://%s" % u.netloc


def apply_server_doc(con, doc):
    """Keep the newest server state per invoice; an older or equal version is ignored."""
    if not isinstance(doc, dict) or not SERVER_ID_RE.match(str(doc.get("id", ""))):
        raise Invalid("not an invoice: %r" % (doc,))
    v = doc.get("version")
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise Invalid("invoice %s has no usable version" % doc["id"])
    cur = con.execute("SELECT version FROM server WHERE id = ?", (doc["id"],)).fetchone()
    if cur and cur[0] >= v:
        return False
    con.execute("INSERT INTO server (id, version, doc) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "version = excluded.version, doc = excluded.doc", (doc["id"], v, json.dumps(doc, sort_keys=True)))
    return True


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(base, key, method, path, body, idem, timeout):
    req = urllib.request.Request(base + path, data=None if body is None else body.encode(), method=method)
    req.add_header("Authorization", "Bearer " + key)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if idem:
        req.add_header("Idempotency-Key", idem)
    try:
        # Ignore environment proxies and never forward this demo bearer through redirects.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers.get("Idempotent-Replayed") == "true"
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            e.close()
            raise Stop(4, "server redirect refused; pending changes retained")
        return e.code, e.read().decode("utf-8", "replace"), e.headers.get("Idempotent-Replayed") == "true"
    except (urllib.error.URLError, http.client.HTTPException, ConnectionError, socket.timeout, OSError) as e:
        raise Stop(4, "server unreachable: %s" % (getattr(e, "reason", None) or e))


def error_code(text):
    try:
        return json.loads(text)["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return None


def blocking_reason(con, op):
    """Why a pending op cannot be sent yet, or None. Order of intent is kept per invoice."""
    seq, kind, ref = op
    if kind != "create":
        made = con.execute("SELECT seq, state FROM ops WHERE kind = 'create' AND ref = ? "
                           "AND state != 'superseded' ORDER BY seq DESC LIMIT 1", (ref,)).fetchone()
        mapped = con.execute("SELECT 1 FROM refs WHERE ref = ?", (ref,)).fetchone()
        if made and not mapped:
            return "waits for create op %d (%s)" % made
        if not made and not mapped and not con.execute("SELECT 1 FROM server WHERE id = ?", (ref,)).fetchone():
            return "unknown invoice %s" % ref
    prior = con.execute("SELECT seq, state FROM ops WHERE ref = ? AND seq < ? AND state IN ('conflict', 'rejected') "
                        "ORDER BY seq LIMIT 1", (ref, seq)).fetchone()
    if prior:
        return "held behind op %d (%s) on the same invoice" % prior
    return None


def server_id(con, ref):
    row = con.execute("SELECT server_id FROM refs WHERE ref = ?", (ref,)).fetchone()
    return row[0] if row else ref


def push(con, base, key, a):
    sent = 0
    while True:
        rows = con.execute("SELECT seq, kind, ref FROM ops WHERE state = 'pending' ORDER BY seq").fetchall()
        op = next((r for r in rows if blocking_reason(con, r) is None), None)
        if op is None:
            return sent
        seq, kind, ref = op
        idem, body = con.execute("SELECT idem, body FROM ops WHERE seq = ?", (seq,)).fetchone()
        path = API if kind == "create" else "%s/%s/%s" % (API, server_id(con, ref), "payments" if kind == "pay" else "void")
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE ops SET attempts = attempts + 1 WHERE seq = ?", (seq,))
        con.execute("COMMIT")
        sent += 1
        if a.crash_before_send == sent:
            os._exit(70)
        status, text, replayed = request(base, key, "POST", path, body, idem, a.timeout)
        if a.crash_after_send == sent:
            os._exit(70)
        code = error_code(text)
        if status in (401, 403):
            raise Stop(3, "server refused the key (%d %s); nothing was changed" % (status, code))
        if status >= 500 or status in (408, 429):
            raise Stop(4, "server answered %d %s; op %d stays pending" % (status, code, seq))
        con.execute("BEGIN IMMEDIATE")
        try:
            if status in (200, 201):
                doc = json.loads(text)
                if kind == "create":
                    con.execute("INSERT INTO refs (ref, server_id, create_seq) VALUES (?, ?, ?)", (ref, doc["id"], seq))
                apply_server_doc(con, doc)
                state, reason = "acked", None
            elif status in (404, 409):
                state, reason = "conflict", code or str(status)
            else:
                state, reason = "rejected", code or str(status)
            con.execute("UPDATE ops SET state = ?, http_status = ?, response = ?, replayed = ?, reason = ? "
                        "WHERE seq = ? AND state = 'pending'", (state, status, text, int(replayed), reason, seq))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise


def pull(con, base, key, timeout):
    after, applied, stale = None, 0, 0
    for _ in range(100000):
        path = API + "?limit=100" + ("" if after is None else "&after=" + after)
        status, text, _r = request(base, key, "GET", path, None, None, timeout)
        if status in (401, 403):
            raise Stop(3, "server refused the key on pull (%d)" % status)
        if status != 200:
            raise Stop(4, "pull answered %d %s" % (status, error_code(text)))
        page = json.loads(text)
        con.execute("BEGIN IMMEDIATE")
        for doc in page["data"]:
            if apply_server_doc(con, doc):
                applied += 1
            else:
                stale += 1
        con.execute("COMMIT")
        after = page.get("next_after")
        if not after:
            return applied, stale
    raise Stop(4, "pull did not terminate")


def cmd_sync(a):
    base = loopback_url(a.base_url)
    try:
        key = Path(a.key_file).read_text().strip()
    except OSError as e:
        raise Invalid("cannot read --key-file: %s" % e)
    if not key:
        raise Invalid("--key-file is empty")
    con = connect(a.db)
    lock = open(a.db + ".lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"result": "busy", "detail": "another sync holds this outbox"}))
        return 5
    out = {"sent": 0, "pulled": None}
    try:
        try:
            problems = violations(con)
            if problems:
                raise Stop(2, "inconsistent outbox; no requests sent: " + "; ".join(problems))
            out["sent"] = push(con, base, key, a)
            if not a.no_pull:
                applied, stale = pull(con, base, key, a.timeout)
                out["pulled"] = {"applied": applied, "stale_ignored": stale}
        except Stop as s:
            out.update(summary(con), result="stopped", detail=s.why)
            print(json.dumps(out, sort_keys=True))
            return s.code
        out.update(summary(con))
        rc = 1 if out["open_problems"] else 0
        out["result"] = "needs_user" if rc else "ok"
        print(json.dumps(out, sort_keys=True))
        return rc
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def summary(con):
    counts = {s: 0 for s in STATES}
    for s, n in con.execute("SELECT state, COUNT(*) FROM ops GROUP BY state"):
        counts[s] = n
    return {"counts": counts, "open_problems": counts["conflict"] + counts["rejected"], "pending": counts["pending"]}


def projected(con):
    """Server view plus this device's unsent intent, per invoice."""
    view = {}
    for (doc,) in con.execute("SELECT doc FROM server ORDER BY id"):
        d = json.loads(doc)
        view[d["id"]] = {"ref": d["id"], "server_id": d["id"], "server": d, "status": d["status"],
                         "balance_cents": d["balance_cents"], "pending_ops": [], "problems": []}
    for ref, sid in con.execute("SELECT ref, server_id FROM refs"):
        if sid in view:
            view[ref] = view.pop(sid)
            view[ref]["ref"] = ref
    for seq, kind, ref, body, state in con.execute("SELECT seq, kind, ref, body, state FROM ops ORDER BY seq"):
        b = json.loads(body)
        if ref not in view:
            if kind != "create":
                continue
            view[ref] = {"ref": ref, "server_id": None, "server": None, "status": "not_on_server",
                         "balance_cents": b["amount_cents"], "pending_ops": [], "problems": []}
        e = view[ref]
        if state == "pending":
            e["pending_ops"].append(seq)
            if kind == "pay":
                e["balance_cents"] -= b["amount_cents"]
            elif kind == "void":
                e["status"] = "void (pending)"
        elif state in OPEN_PROBLEMS:
            e["problems"].append(seq)
    return sorted(view.values(), key=lambda e: e["ref"])


def op_rows(con):
    out = []
    for r in con.execute("SELECT seq, idem, kind, ref, body, state, attempts, http_status, replayed, reason, "
                         "retry_of, superseded_by FROM ops ORDER BY seq"):
        d = dict(zip(("seq", "idempotency_key", "kind", "ref", "body", "state", "attempts", "http_status",
                      "replayed", "reason", "retry_of", "superseded_by"), r))
        d["body"] = json.loads(d["body"])
        d["replayed"] = bool(d["replayed"])
        if d["state"] == "pending":
            d["waiting"] = blocking_reason(con, (d["seq"], d["kind"], d["ref"]))
        out.append(d)
    return out


def cmd_status(a):
    con = connect(a.db)
    rep = {"schema": SCHEMA, "device": meta(con, "device"), "install": meta(con, "install")}
    rep.update(summary(con))
    rep["ops"] = op_rows(con)
    rep["invoices"] = projected(con)
    if a.json:
        print(json.dumps(rep, indent=1, sort_keys=True))
    else:
        c = rep["counts"]
        print("%s: %d pending, %d acked, %d conflict, %d rejected" % (rep["device"], c["pending"], c["acked"],
                                                                        c["conflict"], c["rejected"]))
        for o in rep["ops"]:
            if o["state"] in OPEN_PROBLEMS or o["state"] == "pending":
                print("  op %d %s %s: %s %s" % (o["seq"], o["kind"], o["ref"], o["state"],
                                               o.get("waiting") or o["reason"] or ""))
    return 0


def cmd_resolve(a):
    con = connect(a.db)
    con.execute("BEGIN IMMEDIATE")
    try:
        row = con.execute("SELECT kind, ref, body, state FROM ops WHERE seq = ?", (a.op,)).fetchone()
        if not row:
            raise Invalid("no op %d" % a.op)
        kind, ref, body, state = row
        if state not in OPEN_PROBLEMS:
            raise Invalid("op %d is %s; only a conflict or rejection can be resolved" % (a.op, state))
        if a.action == "discard":
            con.execute("UPDATE ops SET state = 'discarded' WHERE seq = ?", (a.op,))
            also = []
            if kind == "create":
                also = [r[0] for r in con.execute(
                    "SELECT seq FROM ops WHERE ref = ? AND state = 'pending' ORDER BY seq", (ref,))]
                con.executemany("UPDATE ops SET state = 'discarded', reason = ? WHERE seq = ?",
                                [("discarded with create op %d" % a.op, q) for q in also])
            result = {"seq": a.op, "state": "discarded", "also_discarded": also}
        else:
            # A new key and the old refusal's supersession must survive or roll back together.
            new, idem = append_op(con, kind, ref, body, retry_of=a.op)
            con.execute("UPDATE ops SET state = 'superseded', superseded_by = ? WHERE seq = ?", (new, a.op))
            result = {"seq": a.op, "state": "superseded", "retry_seq": new, "idempotency_key": idem}
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    print(json.dumps(result))
    return 0


def cmd_apply_snapshot(a):
    con = connect(a.db)
    try:
        snap = json.loads(Path(a.snapshot).read_text())
    except (OSError, ValueError) as e:
        raise Invalid("cannot read snapshot: %s" % e)
    docs = snap.get("data") if isinstance(snap, dict) else None
    if not isinstance(docs, list):
        raise Invalid("snapshot must be a list answer: {\"data\": [invoice, ...]}")
    con.execute("BEGIN IMMEDIATE")
    try:
        res = [apply_server_doc(con, d) for d in docs]
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    print(json.dumps({"applied": sum(res), "stale_ignored": len(res) - sum(res)}))
    return 0


def violations(con):
    v = []
    ops = con.execute("SELECT seq, idem, kind, ref, body, state, http_status, response, retry_of, superseded_by, "
                      "reason FROM ops ORDER BY seq").fetchall()
    by_seq = {o[0]: o for o in ops}
    install = meta(con, "install")
    roots = {}
    for o in ops:
        if o[2] == "create" and o[8] is None:
            roots.setdefault(o[3], []).append(o[0])
    for ref, seqs in roots.items():
        if len(seqs) > 1:
            v.append("ref %s has duplicate create roots %s" % (ref, seqs))
    for seq, idem, kind, ref, body, state, hs, resp, retry_of, sup, reason in ops:
        if state not in STATES:
            v.append("op %d has unknown state %s" % (seq, state))
        if idem != "%s:%06d" % (install, seq):
            v.append("op %d key %s is not this install's key for that seq" % (seq, idem))
        if kind not in ("create", "pay", "void"):
            v.append("op %d has unknown kind %s" % (seq, kind))
        if state == "pending" and (hs is not None or resp is not None):
            v.append("op %d is pending but has a server answer" % seq)
        if state == "acked" and (hs not in (200, 201) or not resp):
            v.append("op %d is acked without a 2xx answer" % seq)
        cascade = state == "discarded" and hs is None and str(reason).startswith("discarded with create op ")
        if state in ("conflict", "rejected", "discarded") and not cascade and (hs is None or hs < 400):
            v.append("op %d is %s without a refusal" % (seq, state))
        if retry_of is not None:
            old = by_seq.get(retry_of)
            if (not old or retry_of >= seq or old[5] != "superseded" or old[9] != seq
                    or old[2:5] != (kind, ref, body)):
                v.append("op %d has no matching superseded predecessor" % seq)
        if state == "superseded":
            n = by_seq.get(sup)
            if not n or n[8] != seq or n[2:5] != (kind, ref, body):
                v.append("op %d is superseded without a matching retry op" % seq)
        if state == "acked" and kind == "create":
            m = con.execute("SELECT server_id FROM refs WHERE ref = ? AND create_seq = ?", (ref, seq)).fetchone()
            try:
                rid = json.loads(resp)["id"]
            except (ValueError, KeyError, TypeError):
                rid = None
            if not m or m[0] != rid:
                v.append("acked create op %d is not mapped to its server id" % seq)
    for ref, sid, cs in con.execute("SELECT ref, server_id, create_seq FROM refs"):
        o = by_seq.get(cs)
        if not o or o[2] != "create" or o[3] != ref or o[5] != "acked":
            v.append("ref %s maps to %s without an acked create" % (ref, sid))
    return v


def cmd_check(a):
    try:
        con = sqlite3.connect("file:%s?mode=ro" % Path(a.db).resolve(), uri=True)
        if con.execute("SELECT v FROM meta WHERE k = 'schema'").fetchone() != (SCHEMA,):
            raise Invalid("%s is not a %s outbox" % (a.db, SCHEMA))
        v = violations(con)
    except sqlite3.DatabaseError as e:
        raise Invalid("cannot read %s: %s" % (a.db, e))
    if a.json:
        print(json.dumps({"consistent": not v, "violations": v}, indent=1))
    else:
        print("consistent" if not v else "\n".join(["VIOLATIONS"] + v))
    return 1 if v else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="offline_sync.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--db", required=True); s.add_argument("--device", required=True)
    s = sub.add_parser("enqueue"); s.add_argument("--db", required=True)
    s.add_argument("kind", choices=("create", "pay", "void")); s.add_argument("--ref", required=True)
    s.add_argument("--customer"); s.add_argument("--amount"); s.add_argument("--currency"); s.add_argument("--reason")
    s = sub.add_parser("sync"); s.add_argument("--db", required=True); s.add_argument("--base-url", required=True)
    s.add_argument("--key-file", required=True); s.add_argument("--no-pull", action="store_true")
    s.add_argument("--timeout", type=float, default=10.0)
    s.add_argument("--crash-before-send", type=int, default=0); s.add_argument("--crash-after-send", type=int, default=0)
    s = sub.add_parser("status"); s.add_argument("--db", required=True); s.add_argument("--json", action="store_true")
    s = sub.add_parser("resolve"); s.add_argument("--db", required=True); s.add_argument("--op", type=int, required=True)
    s.add_argument("--action", choices=("discard", "retry"), required=True)
    s = sub.add_parser("apply-snapshot"); s.add_argument("--db", required=True); s.add_argument("snapshot")
    s = sub.add_parser("check"); s.add_argument("--db", required=True); s.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    fn = {"init": cmd_init, "enqueue": cmd_enqueue, "sync": cmd_sync, "status": cmd_status, "resolve": cmd_resolve,
          "apply-snapshot": cmd_apply_snapshot, "check": cmd_check}[a.cmd]
    try:
        return fn(a)
    except Invalid as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
