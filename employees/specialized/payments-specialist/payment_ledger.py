#!/usr/bin/env python3
"""Signed-webhook order ledger with exact money and conserved stock (synthetic, local, stdlib only).

A local stand-in for the part of a store backend that receives payment-provider webhooks. It never
talks to a provider: events are local JSON files signed with a local test secret. It shows the rules
that keep money and stock right when webhooks arrive twice, late, out of order or forged:

- Signature first. Each envelope carries `t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">`.
  A wrong signature or a timestamp outside the tolerance (default 300 s) is refused before the body
  is read; nothing is stored.
- One effect per event id. The event id, its body hash and its effect are written in one SQLite
  transaction. The same id with the same body again is a duplicate (no effect); the same id with a
  different body is refused and named.
- Exact amounts. Prices and amounts are decimal strings with at most two places ("12.50"), held as
  integer cents; floats are refused.
- Out of order is held, not dropped. A capture, refund or cancel that arrives before its order (or a
  refund before its capture) is held and applied as soon as what it needs arrives.
- Stock is conserved. An order reserves stock only if it is available (no oversell, also under
  concurrent ingests); a capture ships it; a cancel releases it; a refund can restock at most what
  was shipped. Per SKU: initial = on_hand + shipped - restocked, and reserved = open orders.
- Anomalies are exceptions, never silent: capture amount not equal to the order total, capture on a
  cancelled order, refund above what was captured, restock above what was shipped, out of stock.
  Their money is kept visible as unapplied.
- Open events are resolved on the record. `resolve --action retry` applies an open event again once what
  blocked it has changed; `resolve --action close` closes it with who, why and, when it carries money,
  where that money was settled (`--reference`) or which applied event re-delivered it (`--superseded-by`).
  Each resolution is a row of its own; closed money stays listed in the report as closed, never dropped.

Commands:
    payment_ledger.py init --db FILE --catalog CATALOG.json
    payment_ledger.py sign --secret-file FILE --body-file EVENT.json [--t UNIX]   (prints one envelope line)
    payment_ledger.py ingest --db FILE --secret-file FILE --events ENVELOPES.jsonl [--now UNIX]
                             [--tolerance S] [--crash-after N]
    payment_ledger.py report --db FILE [--json]
    payment_ledger.py check --db FILE [--json]
    payment_ledger.py export-g14 --db FILE --out DIR --period-start ISO --period-end ISO
    payment_ledger.py resolve --db FILE --event ID --action retry|close --by WHO --note TEXT
                              [--reference REF | --superseded-by EVENT_ID] [--now UNIX]

Exit codes: ingest 0 all applied or duplicate; 1 some held or exceptions; 3 any envelope refused
(signature, timestamp or conflicting replay); check 0 consistent, 1 violations; export-g14 0 written,
1 refused because held or exception events or unapplied money are open (nothing written);
resolve 0 resolved, 1 retry did not apply (nothing changed); 2 invalid input; 70 drill.
Python 3.9+, no third-party packages, no network.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "solaris.payment-ledger/1"
CATALOG_SCHEMA = "solaris.store-catalog/1"
TYPES = ("order.placed", "payment.captured", "refund.succeeded", "order.cancelled")
AMOUNT_RE = re.compile(r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,2})?$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SIG_RE = re.compile(r"^t=([0-9]{1,12}),v1=([0-9a-f]{64})$")
CURRENCIES = ("EUR", "GBP", "USD")

DDL = """
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE skus (sku TEXT PRIMARY KEY, price_cents INTEGER NOT NULL, initial INTEGER NOT NULL,
  on_hand INTEGER NOT NULL, reserved INTEGER NOT NULL DEFAULT 0, shipped INTEGER NOT NULL DEFAULT 0,
  restocked INTEGER NOT NULL DEFAULT 0, CHECK (reserved >= 0 AND on_hand >= reserved));
CREATE TABLE events (id TEXT PRIMARY KEY, type TEXT NOT NULL, created INTEGER NOT NULL, body_sha TEXT NOT NULL,
  body TEXT NOT NULL, state TEXT NOT NULL, reason TEXT, received_seq INTEGER NOT NULL);
CREATE TABLE orders (id TEXT PRIMARY KEY, currency TEXT NOT NULL, total_cents INTEGER NOT NULL, status TEXT NOT NULL,
  placed_event TEXT NOT NULL, placed_at INTEGER NOT NULL, captured_cents INTEGER NOT NULL DEFAULT 0,
  refunded_cents INTEGER NOT NULL DEFAULT 0, captured_at INTEGER);
CREATE TABLE lines (order_id TEXT NOT NULL, sku TEXT NOT NULL, qty INTEGER NOT NULL, unit_cents INTEGER NOT NULL,
  restocked INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (order_id, sku));
CREATE TABLE money (event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL UNIQUE,
  cents INTEGER NOT NULL, at INTEGER NOT NULL, applied INTEGER NOT NULL);
CREATE TABLE stock_moves (event_id TEXT NOT NULL, sku TEXT NOT NULL, d_on_hand INTEGER NOT NULL, d_reserved INTEGER NOT NULL);
"""
# one audited row per resolved event; created on demand for ledgers made before resolve existed
RESOLUTIONS_DDL = """CREATE TABLE IF NOT EXISTS resolutions (event_id TEXT PRIMARY KEY, action TEXT NOT NULL,
  prior_state TEXT NOT NULL, prior_reason TEXT, resolved_by TEXT NOT NULL, note TEXT NOT NULL, reference TEXT,
  superseded_by TEXT, money_kind TEXT, money_cents INTEGER, at INTEGER NOT NULL, seq INTEGER NOT NULL)"""


class Invalid(Exception):
    pass


def cents(v, what):
    if not isinstance(v, str) or not AMOUNT_RE.match(v):
        raise Invalid("%s must be a decimal string with at most 2 places, got %r" % (what, v))
    whole, _, frac = v.partition(".")
    return int(whole) * 100 + int((frac + "00")[:2])


def money_str(c):
    return "%s%d.%02d" % ("-" if c < 0 else "", abs(c) // 100, abs(c) % 100)


def connect(db):
    if not Path(db).is_file():
        raise Invalid("no ledger at %s (run init first)" % db)
    con = sqlite3.connect(db, timeout=60, isolation_level=None)
    con.execute("PRAGMA synchronous=FULL")  # WAL is set once at init; switching it here would race other openers
    try:
        ok = con.execute("SELECT v FROM meta WHERE k='schema'").fetchone() == (SCHEMA,)
    except sqlite3.DatabaseError:
        ok = False
    if not ok:
        raise Invalid("%s is not a %s ledger" % (db, SCHEMA))
    return con


def cmd_init(a):
    if Path(a.db).exists():
        raise Invalid("%s already exists" % a.db)
    try:
        cat = json.loads(Path(a.catalog).read_text())
    except (OSError, ValueError) as e:
        raise Invalid("cannot read catalog: %s" % e)
    if not isinstance(cat, dict) or cat.get("schema") != CATALOG_SCHEMA or cat.get("currency") not in CURRENCIES:
        raise Invalid("catalog must be %s with currency in %s" % (CATALOG_SCHEMA, CURRENCIES))
    skus = cat.get("skus")
    if not isinstance(skus, list) or not skus:
        raise Invalid("catalog.skus must be a non-empty list")
    rows, seen = [], set()
    for s in skus:
        sku, stock = s.get("sku"), s.get("on_hand")
        if not isinstance(sku, str) or not ID_RE.match(sku) or sku in seen:
            raise Invalid("bad or duplicate sku %r" % (sku,))
        if not isinstance(stock, int) or isinstance(stock, bool) or stock < 0:
            raise Invalid("%s.on_hand must be a whole number >= 0" % sku)
        price = cents(s.get("price"), sku + ".price")
        if price <= 0:
            raise Invalid("%s.price must be above 0" % sku)
        seen.add(sku)
        rows.append((sku, price, stock, stock))
    con = sqlite3.connect(a.db, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(DDL)
    con.execute(RESOLUTIONS_DDL)
    con.execute("BEGIN IMMEDIATE")
    con.executemany("INSERT INTO meta VALUES (?, ?)", [("schema", SCHEMA), ("currency", cat["currency"]), ("seq", "0")])
    con.executemany("INSERT INTO skus (sku, price_cents, initial, on_hand) VALUES (?, ?, ?, ?)", rows)
    con.execute("COMMIT")
    print(json.dumps({"db": a.db, "currency": cat["currency"], "skus": len(rows)}))
    return 0


def read_secret(path):
    try:
        s = Path(path).read_text().strip()
    except OSError as e:
        raise Invalid("cannot read --secret-file: %s" % e)
    if len(s) < 16:
        raise Invalid("--secret-file must hold at least 16 characters")
    return s.encode()


def signature(secret, t, body):
    return hmac.new(secret, ("%d." % t).encode() + body.encode(), hashlib.sha256).hexdigest()


def cmd_sign(a):
    secret = read_secret(a.secret_file)
    body = Path(a.body_file).read_text().strip()
    t = int(time.time()) if a.t is None else a.t
    print(json.dumps({"signature": "t=%d,v1=%s" % (t, signature(secret, t, body)), "body": body}))
    return 0


def parse_event(body):
    try:
        ev = json.loads(body, parse_float=lambda s: (_ for _ in ()).throw(Invalid("float %s in event; amounts are strings" % s)))
    except ValueError as e:
        raise Invalid("event body is not JSON: %s" % e)
    if not isinstance(ev, dict) or set(ev) != {"id", "type", "created", "data"}:
        raise Invalid("event must have exactly id, type, created, data")
    if not isinstance(ev["id"], str) or not ID_RE.match(ev["id"]) or ev["type"] not in TYPES:
        raise Invalid("bad event id or type")
    if not isinstance(ev["created"], int) or isinstance(ev["created"], bool) or not isinstance(ev["data"], dict):
        raise Invalid("bad created or data")
    d = ev["data"]
    if not isinstance(d.get("order_id"), str) or not ID_RE.match(d["order_id"]):
        raise Invalid("data.order_id is required")
    return ev


def qty_lines(v, what):
    if not isinstance(v, list):
        raise Invalid("%s must be a list" % what)
    out = {}
    for ln in v:
        if not isinstance(ln, dict) or set(ln) != {"sku", "qty"} or not isinstance(ln["qty"], int) \
                or isinstance(ln["qty"], bool) or ln["qty"] < 1 or not isinstance(ln["sku"], str):
            raise Invalid("%s entries are {sku, qty>=1}" % what)
        if ln["sku"] in out:
            raise Invalid("%s repeats sku %s" % (what, ln["sku"]))
        out[ln["sku"]] = ln["qty"]
    return out


def move(con, eid, sku, d_on_hand, d_reserved, field=None, n=0):
    con.execute("UPDATE skus SET on_hand = on_hand + ?, reserved = reserved + ?%s WHERE sku = ?" %
                ("" if not field else ", %s = %s + %d" % (field, field, n)), (d_on_hand, d_reserved, sku))
    con.execute("INSERT INTO stock_moves VALUES (?, ?, ?, ?)", (eid, sku, d_on_hand, d_reserved))


def apply(con, ev):
    """Try one event. Returns (state, reason): applied | held | exception. Caller owns the transaction."""
    eid, typ, d, at = ev["id"], ev["type"], ev["data"], ev["created"]
    oid = d["order_id"]
    order = con.execute("SELECT currency, total_cents, status, captured_cents, refunded_cents FROM orders WHERE id = ?",
                        (oid,)).fetchone()
    cur = con.execute("SELECT v FROM meta WHERE k='currency'").fetchone()[0]
    if typ == "order.placed":
        if order:
            return "exception", "order_already_placed"
        if set(d) != {"order_id", "currency", "lines"} or d["currency"] != cur:
            return "exception", "bad_order (fields or currency %s)" % d.get("currency")
        want = qty_lines(d["lines"], "lines")
        rows = {}
        for sku, q in want.items():
            r = con.execute("SELECT price_cents, on_hand - reserved FROM skus WHERE sku = ?", (sku,)).fetchone()
            if not r:
                return "exception", "unknown_sku %s" % sku
            if r[1] < q:
                return "exception", "out_of_stock %s (want %d, available %d)" % (sku, q, r[1])
            rows[sku] = r[0]
        total = sum(rows[s] * q for s, q in want.items())
        con.execute("INSERT INTO orders (id, currency, total_cents, status, placed_event, placed_at) VALUES (?, ?, ?, 'placed', ?, ?)",
                    (oid, cur, total, eid, at))
        for sku, q in want.items():
            con.execute("INSERT INTO lines (order_id, sku, qty, unit_cents) VALUES (?, ?, ?, ?)", (oid, sku, q, rows[sku]))
            move(con, eid, sku, 0, q)
        return "applied", None
    if not order:
        return "held", "order_not_seen_yet"
    currency, total, status, captured, refunded = order
    if typ == "payment.captured":
        if set(d) != {"order_id", "payment_id", "amount"} or not isinstance(d["payment_id"], str) or not ID_RE.match(d["payment_id"]):
            return "exception", "bad_capture_fields"
        amt = cents(d["amount"], "amount")
        if con.execute("SELECT 1 FROM money WHERE ref = ?", (d["payment_id"],)).fetchone():
            return "exception", "payment_id_already_recorded"
        why = None
        if status == "cancelled":
            why = "capture_on_cancelled_order"
        elif status != "placed":
            why = "order_already_captured"
        elif amt != total:
            why = "capture_amount_mismatch (order %s, captured %s)" % (money_str(total), money_str(amt))
        con.execute("INSERT INTO money VALUES (?, ?, 'capture', ?, ?, ?, ?)", (eid, oid, d["payment_id"], amt, at, int(why is None)))
        if why:
            return "exception", why
        con.execute("UPDATE orders SET status = 'captured', captured_cents = ?, captured_at = ? WHERE id = ?", (amt, at, oid))
        for sku, q in con.execute("SELECT sku, qty FROM lines WHERE order_id = ?", (oid,)).fetchall():
            move(con, eid, sku, -q, -q, "shipped", q)
        return "applied", None
    if typ == "order.cancelled":
        if set(d) != {"order_id"}:
            return "exception", "bad_cancel_fields"
        if status != "placed":
            return "exception", "cannot_cancel_%s_order" % status
        con.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (oid,))
        for sku, q in con.execute("SELECT sku, qty FROM lines WHERE order_id = ?", (oid,)).fetchall():
            move(con, eid, sku, 0, -q)
        return "applied", None
    # refund.succeeded
    if set(d) != {"order_id", "refund_id", "amount", "restock"} or not isinstance(d["refund_id"], str) or not ID_RE.match(d["refund_id"]):
        return "exception", "bad_refund_fields"
    amt = cents(d["amount"], "amount")
    restock = qty_lines(d["restock"], "restock")
    if amt <= 0 and not restock:
        return "exception", "empty_refund"
    if status == "placed":
        return "held", "not_captured_yet"
    if con.execute("SELECT 1 FROM money WHERE ref = ?", (d["refund_id"],)).fetchone():
        return "exception", "refund_id_already_recorded"
    why = None
    if status == "cancelled":
        why = "refund_on_uncaptured_order"
    elif refunded + amt > captured:
        why = "refund_exceeds_captured (captured %s, refunded %s, this %s)" % (money_str(captured), money_str(refunded), money_str(amt))
    else:
        for sku, q in restock.items():
            ln = con.execute("SELECT qty, restocked FROM lines WHERE order_id = ? AND sku = ?", (oid, sku)).fetchone()
            if not ln or ln[1] + q > ln[0]:
                why = "restock_exceeds_shipped %s" % sku
                break
    con.execute("INSERT INTO money VALUES (?, ?, 'refund', ?, ?, ?, ?)", (eid, oid, d["refund_id"], amt, at, int(why is None)))
    if why:
        return "exception", why
    con.execute("UPDATE orders SET refunded_cents = refunded_cents + ?, status = CASE WHEN refunded_cents + ? = captured_cents "
                "THEN 'refunded' ELSE 'captured' END WHERE id = ?", (amt, amt, oid))
    for sku, q in restock.items():
        con.execute("UPDATE lines SET restocked = restocked + ? WHERE order_id = ? AND sku = ?", (q, oid, sku))
        move(con, eid, sku, q, 0, "restocked", q)
    return "applied", None


def retry_held(con):
    while True:
        progressed = False
        for eid, body in con.execute("SELECT id, body FROM events WHERE state = 'held' ORDER BY created, received_seq").fetchall():
            con.execute("SAVEPOINT h")
            try:
                state, reason = apply(con, json.loads(body))
            except Invalid as e:
                con.execute("ROLLBACK TO h")
                state, reason = "exception", "invalid: %s" % e
            if state == "held":
                con.execute("ROLLBACK TO h")
                con.execute("RELEASE h")
                continue
            con.execute("RELEASE h")
            con.execute("UPDATE events SET state = ?, reason = ? WHERE id = ?", (state, reason, eid))
            progressed = True
        if not progressed:
            return


def ingest_one(con, secret, line, now, tol):
    try:
        env = json.loads(line)
        sig, body = env["signature"], env["body"]
        if not isinstance(sig, str) or not isinstance(body, str):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return {"result": "refused", "reason": "not an envelope {signature, body}"}
    m = SIG_RE.match(sig)
    if not m or not hmac.compare_digest(signature(secret, int(m.group(1)), body), m.group(2)):
        return {"result": "refused", "reason": "bad_signature"}
    if abs(now - int(m.group(1))) > tol:
        return {"result": "refused", "reason": "timestamp_outside_tolerance"}
    try:
        ev = parse_event(body)
    except Invalid as e:
        return {"result": "refused", "reason": "invalid_event: %s" % e}
    sha = hashlib.sha256(body.encode()).hexdigest()
    con.execute("BEGIN IMMEDIATE")
    try:
        prior = con.execute("SELECT body_sha, state FROM events WHERE id = ?", (ev["id"],)).fetchone()
        if prior:
            con.execute("ROLLBACK")
            if prior[0] == sha:
                return {"id": ev["id"], "result": "duplicate", "state": prior[1]}
            return {"id": ev["id"], "result": "refused", "reason": "conflicting_replay (same id, different body)"}
        con.execute("SAVEPOINT e")
        try:
            state, reason = apply(con, ev)
        except Invalid as e:
            state, reason = "exception", "invalid: %s" % e
        if state != "applied":
            con.execute("ROLLBACK TO e")
            if state == "exception" and ev["type"] in ("payment.captured", "refund.succeeded") and not reason.startswith(("bad_", "invalid", "payment_id_", "refund_id_", "empty")):
                apply(con, ev)  # re-run to record the unapplied money row only (apply returns the same exception)
        con.execute("RELEASE e")
        seq = int(con.execute("SELECT v FROM meta WHERE k='seq'").fetchone()[0]) + 1
        con.execute("UPDATE meta SET v = ? WHERE k='seq'", (str(seq),))
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (ev["id"], ev["type"], ev["created"], sha, body, state, reason, seq))
        if state == "applied":
            retry_held(con)
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return {"id": ev["id"], "result": state, "reason": reason}


def cmd_ingest(a):
    secret = read_secret(a.secret_file)
    con = connect(a.db)
    try:
        lines = [l for l in Path(a.events).read_text().splitlines() if l.strip()]
    except OSError as e:
        raise Invalid("cannot read --events: %s" % e)
    now = int(time.time()) if a.now is None else a.now
    out, done = [], 0
    for line in lines:
        r = ingest_one(con, secret, line, now, a.tolerance)
        out.append(r)
        done += 1
        if a.crash_after == done:
            os._exit(70)
    # held events may have become applicable by events applied in other runs
    final = {r["id"]: con.execute("SELECT state, reason FROM events WHERE id = ?", (r["id"],)).fetchone()
             for r in out if r.get("id") and r["result"] != "refused"}
    for r in out:
        if r.get("id") in final and r["result"] != "refused" and final[r["id"]]:
            r["state_now"] = final[r["id"]][0]
    refused = sum(r["result"] == "refused" for r in out)
    open_ = con.execute("SELECT COUNT(*) FROM events WHERE state IN ('held', 'exception')").fetchone()[0]
    print(json.dumps({"events": out, "refused": refused, "open_held_or_exceptions": open_}, sort_keys=True))
    return 3 if refused else (1 if open_ else 0)


def report(con):
    cur = con.execute("SELECT v FROM meta WHERE k='currency'").fetchone()[0]
    tot = {k: 0 for k in ("captured", "refunded", "unapplied_captures", "unapplied_refunds", "closed_unapplied_captures",
                          "closed_unapplied_refunds")}
    for kind, applied, closed, c in con.execute("SELECT m.kind, m.applied, COALESCE(e.state, '') = 'resolved', SUM(m.cents) FROM money m "
                                                "LEFT JOIN events e ON e.id = m.event_id GROUP BY 1, 2, 3"):
        word = "captures" if kind == "capture" else "refunds"
        key = ("captured" if kind == "capture" else "refunded") if applied else ("closed_unapplied_" if closed else "unapplied_") + word
        tot[key] += c
    stock = [dict(zip(("sku", "initial", "on_hand", "reserved", "available", "shipped", "restocked"), r)) for r in
             con.execute("SELECT sku, initial, on_hand, reserved, on_hand - reserved, shipped, restocked FROM skus ORDER BY sku")]
    orders = [dict(zip(("id", "status", "total", "captured", "refunded"), (r[0], r[1], money_str(r[2]), money_str(r[3]), money_str(r[4]))))
              for r in con.execute("SELECT id, status, total_cents, captured_cents, refunded_cents FROM orders ORDER BY id")]
    open_ = [dict(zip(("id", "type", "state", "reason"), r)) for r in
             con.execute("SELECT id, type, state, reason FROM events WHERE state IN ('held', 'exception') ORDER BY received_seq")]
    return {"schema": SCHEMA, "currency": cur, "money": {k: money_str(v) for k, v in tot.items()},
            "net_cash": money_str(tot["captured"] - tot["refunded"]), "stock": stock, "orders": orders, "open": open_,
            "events": dict(con.execute("SELECT state, COUNT(*) FROM events GROUP BY state").fetchall()),
            "resolutions": resolutions(con)}


def cmd_report(a):
    r = report(connect(a.db))
    if a.json:
        print(json.dumps(r, indent=1, sort_keys=True))
    else:
        print("%s net cash %s (captured %s, refunded %s); %d held or exception events" % (
            r["currency"], r["net_cash"], r["money"]["captured"], r["money"]["refunded"], len(r["open"])))
        for x in r["resolutions"]:
            print("  resolved %(event_id)s by %(action)s (%(prior_state)s: %(prior_reason)s), %(resolved_by)s: %(note)s" % x
                  + ("; closed %s %s, %s" % (x["money_kind"], x["amount"], x["reference"] or "superseded by " + x["superseded_by"]) if x["amount"] else ""))
        for s in r["stock"]:
            print("  %(sku)s on_hand %(on_hand)d reserved %(reserved)d shipped %(shipped)d restocked %(restocked)d" % s)
    return 0


def violations(con):
    v = []
    for sku, init, on_hand, reserved, shipped, restocked in con.execute("SELECT sku, initial, on_hand, reserved, shipped, restocked FROM skus"):
        if init != on_hand + shipped - restocked:
            v.append("%s: initial %d != on_hand %d + shipped %d - restocked %d" % (sku, init, on_hand, shipped, restocked))
        mv = con.execute("SELECT COALESCE(SUM(d_on_hand),0), COALESCE(SUM(d_reserved),0) FROM stock_moves WHERE sku = ?", (sku,)).fetchone()
        if (init + mv[0], mv[1]) != (on_hand, reserved):
            v.append("%s: counters differ from stock moves" % sku)
        open_q = con.execute("SELECT COALESCE(SUM(l.qty),0) FROM lines l JOIN orders o ON o.id = l.order_id "
                             "WHERE o.status = 'placed' AND l.sku = ?", (sku,)).fetchone()[0]
        if open_q != reserved:
            v.append("%s: reserved %d != open order quantity %d" % (sku, reserved, open_q))
        rs = con.execute("SELECT COALESCE(SUM(restocked),0) FROM lines WHERE sku = ?", (sku,)).fetchone()[0]
        if rs != restocked:
            v.append("%s: restocked %d != order lines %d" % (sku, restocked, rs))
        if on_hand < reserved or reserved < 0:
            v.append("%s: on_hand %d below reserved %d" % (sku, on_hand, reserved))
    for oid, total, status, cap, ref in con.execute("SELECT id, total_cents, status, captured_cents, refunded_cents FROM orders"):
        lt = con.execute("SELECT COALESCE(SUM(qty * unit_cents),0) FROM lines WHERE order_id = ?", (oid,)).fetchone()[0]
        mc = con.execute("SELECT COALESCE(SUM(cents),0) FROM money WHERE order_id = ? AND kind='capture' AND applied=1", (oid,)).fetchone()[0]
        mr = con.execute("SELECT COALESCE(SUM(cents),0) FROM money WHERE order_id = ? AND kind='refund' AND applied=1", (oid,)).fetchone()[0]
        if lt != total:
            v.append("order %s: total %s != lines %s" % (oid, money_str(total), money_str(lt)))
        if (mc, mr) != (cap, ref):
            v.append("order %s: captured/refunded differ from money rows" % oid)
        if ref > cap:
            v.append("order %s: refunded %s above captured %s" % (oid, money_str(ref), money_str(cap)))
        if cap not in (0, total):
            v.append("order %s: captured %s is neither 0 nor the total" % (oid, money_str(cap)))
    applied = {r[0] for r in con.execute("SELECT id FROM events WHERE state = 'applied'")}
    for (eid,) in con.execute("SELECT DISTINCT event_id FROM stock_moves"):
        if eid not in applied:
            v.append("stock move from event %s that is not applied" % eid)
    for eid, applied_flag in con.execute("SELECT event_id, applied FROM money"):
        st = con.execute("SELECT state FROM events WHERE id = ?", (eid,)).fetchone()
        if not st or (st[0] == "applied") != bool(applied_flag):
            v.append("money row of event %s does not match the event state" % eid)
    res = {}
    if has_resolutions(con):
        res = {r[0]: r[1:] for r in con.execute("SELECT event_id, action, reference, superseded_by, money_cents FROM resolutions")}
    for (eid,) in con.execute("SELECT id FROM events WHERE state = 'resolved' ORDER BY id"):
        if res.get(eid, ("",))[0] != "close":
            v.append("resolved event %s has no close record" % eid)
    for eid, (action, ref, sup, mc) in sorted(res.items()):
        st = con.execute("SELECT state FROM events WHERE id = ?", (eid,)).fetchone()
        if not st or st[0] != {"close": "resolved", "retry": "applied"}.get(action):
            v.append("resolution of %s (%s) does not match the event state" % (eid, action))
        m = con.execute("SELECT cents FROM money WHERE event_id = ? AND applied = 0", (eid,)).fetchone()
        if action == "close" and (m[0] if m else None) != mc:
            v.append("closed money of %s differs from its money row" % eid)
        if action == "close" and mc is not None and not (ref or sup):
            v.append("closed money of %s has no reference or superseding event" % eid)
    return v


def cmd_check(a):
    try:
        con = sqlite3.connect("file:%s?mode=ro" % Path(a.db).resolve(), uri=True)
        if con.execute("SELECT v FROM meta WHERE k='schema'").fetchone() != (SCHEMA,):
            raise Invalid("not a %s ledger" % SCHEMA)
        v = violations(con)
    except sqlite3.DatabaseError as e:
        raise Invalid("cannot read %s: %s" % (a.db, e))
    print(json.dumps({"consistent": not v, "violations": v}, indent=1) if a.json else ("consistent" if not v else "\n".join(["VIOLATIONS"] + v)))
    return 1 if v else 0


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def open_items(con):
    """What keeps the books from being final: held or exception events and unapplied money rows."""
    events = [dict(zip(("id", "type", "state", "reason"), r)) for r in
              con.execute("SELECT id, type, state, reason FROM events WHERE state IN ('held', 'exception') ORDER BY received_seq")]
    money = [{"event_id": e, "kind": k, "amount": money_str(c)} for e, k, c in
             con.execute("SELECT m.event_id, m.kind, m.cents FROM money m LEFT JOIN events e ON e.id = m.event_id "
                         "WHERE m.applied = 0 AND COALESCE(e.state, '') != 'resolved' ORDER BY m.event_id")]
    return events, money


def has_resolutions(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resolutions'").fetchone() is not None


def resolutions(con):
    if not has_resolutions(con):
        return []
    keys = ("event_id", "action", "prior_state", "prior_reason", "resolved_by", "note", "reference", "superseded_by",
            "money_kind", "money_cents", "at")
    out = []
    for r in con.execute("SELECT %s FROM resolutions ORDER BY seq" % ", ".join(keys)):
        d = dict(zip(keys, r))
        d["amount"] = None if d.pop("money_cents") is None else money_str(r[9])
        d["at"] = iso(d["at"])
        out.append(d)
    return out


def cmd_resolve(a):
    """Resolve one held or exception event on the record: retry it now, or close it with who and why."""
    if not a.by.strip() or not a.note.strip():
        raise Invalid("--by and --note must name who resolves and why")
    if a.action == "retry" and (a.reference or a.superseded_by):
        raise Invalid("--reference and --superseded-by belong to --action close")
    if a.reference is not None and a.superseded_by is not None:
        raise Invalid("give --reference or --superseded-by, not both")
    if a.reference is not None and not a.reference.strip():
        raise Invalid("--reference must not be empty")
    con = connect(a.db)
    now = int(time.time()) if a.now is None else a.now
    con.execute(RESOLUTIONS_DDL)
    con.execute("BEGIN IMMEDIATE")
    try:
        row = con.execute("SELECT body, state, reason FROM events WHERE id = ?", (a.event,)).fetchone()
        if not row:
            raise Invalid("no event %s in this ledger" % a.event)
        body, state, reason = row
        if state not in ("held", "exception"):
            raise Invalid("event %s is %s, not held or in exception; nothing to resolve" % (a.event, state))
        ev = json.loads(body)
        money = con.execute("SELECT kind, cents FROM money WHERE event_id = ?", (a.event,)).fetchone()
        seq = int(con.execute("SELECT v FROM meta WHERE k='seq'").fetchone()[0]) + 1
        if a.action == "retry":
            con.execute("SAVEPOINT r")
            con.execute("DELETE FROM money WHERE event_id = ?", (a.event,))  # apply records its own money row again
            try:
                new, why = apply(con, ev)
            except Invalid as e:
                new, why = "exception", "invalid: %s" % e
            if new != "applied":
                con.execute("ROLLBACK TO r")
                con.execute("RELEASE r")
                con.execute("ROLLBACK")
                print(json.dumps({"event": a.event, "action": "retry", "resolved": False, "state": new, "reason": why}, sort_keys=True))
                print("error: retry of %s did not apply (%s: %s); nothing changed" % (a.event, new, why), file=sys.stderr)
                return 1
            con.execute("RELEASE r")
            con.execute("UPDATE events SET state = 'applied', reason = NULL WHERE id = ?", (a.event,))
            money = None
        else:
            if money and a.reference is None and a.superseded_by is None:
                raise Invalid("event %s carries unapplied %s %s; close it with --reference (where that money was settled) "
                              "or --superseded-by (the applied event that re-delivered it)" % (a.event, money[0], money_str(money[1])))
            if a.superseded_by is not None:
                s = con.execute("SELECT state, body FROM events WHERE id = ?", (a.superseded_by,)).fetchone()
                if a.superseded_by == a.event or not s or s[0] != "applied":
                    raise Invalid("--superseded-by %s must be another event that is applied" % a.superseded_by)
                if json.loads(s[1])["data"]["order_id"] != ev["data"]["order_id"]:
                    raise Invalid("--superseded-by %s is for another order" % a.superseded_by)
            con.execute("UPDATE events SET state = 'resolved' WHERE id = ?", (a.event,))
        con.execute("INSERT INTO resolutions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (a.event, a.action, state, reason, a.by.strip(), a.note.strip(), a.reference, a.superseded_by,
                     money[0] if money else None, money[1] if money else None, now, seq))
        con.execute("UPDATE meta SET v = ? WHERE k='seq'", (str(seq),))
        if a.action == "retry":
            retry_held(con)
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    events, open_money = open_items(con)
    print(json.dumps({"event": a.event, "action": a.action, "resolved": True, "prior_state": state, "prior_reason": reason,
                      "money_closed": None if not money else {"kind": money[0], "amount": money_str(money[1])},
                      "open_now": len(events), "unapplied_money_now": len(open_money)}, sort_keys=True))
    return 0


def cmd_export_g14(a):
    con = connect(a.db)
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        raise Invalid("--out %s is not empty" % out)
    # Books with open exceptions are not final: an unapplied refund or a refused order would vanish from
    # the export and G14 would reconcile the rest as clean. Refuse before writing anything.
    events, money = open_items(con)
    if events or money:
        print(json.dumps({"refused": "open held or exception events or unapplied money; resolve them (payment_ledger.py resolve) before export",
                          "open": events, "unapplied_money": money}, sort_keys=True))
        print("error: export-g14 refused: %d open event(s) %s, %d unapplied money row(s); nothing written"
              % (len(events), ",".join(e["id"] for e in events), len(money)), file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    cur = con.execute("SELECT v FROM meta WHERE k='currency'").fetchone()[0]

    def write(name, header, rows):
        with open(out / name, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
    # one invoice per captured order; goods ship at capture, so delivery evidence = capture time
    write("invoices.csv", ["invoice_id", "customer_id", "currency", "amount", "issued_at", "delivered_at", "status", "loaded_at"],
          [(o, "store", cur, money_str(t), iso(p), iso(c), "issued", iso(c)) for o, t, p, c in
           con.execute("SELECT id, total_cents, placed_at, captured_at FROM orders WHERE captured_at IS NOT NULL ORDER BY id")])
    write("payments.csv", ["payment_id", "invoice_id", "currency", "amount", "received_at", "loaded_at"],
          [(r, o, cur, money_str(c), iso(t), iso(t)) for r, o, c, t in
           con.execute("SELECT ref, order_id, cents, at FROM money WHERE kind='capture' AND applied=1 ORDER BY ref")])
    # a refund returns goods and cash: a credit note (contra-revenue) plus the cash refund it settles
    rows = []
    for r, o, c, t in con.execute("SELECT ref, order_id, cents, at FROM money WHERE kind='refund' AND applied=1 ORDER BY ref"):
        rows += [(r + "-cn", o, "credit_note", cur, money_str(c), iso(t), iso(t)), (r, o, "refund", cur, money_str(c), iso(t), iso(t))]
    write("credits.csv", ["credit_id", "invoice_id", "kind", "currency", "amount", "issued_at", "loaded_at"], rows)
    (out / "package.json").write_text(json.dumps({"schema": "solaris.cash-revenue/1", "timezone": "UTC",
        "period": {"start": a.period_start, "end": a.period_end}, "invoices": {"file": "invoices.csv"},
        "payments": {"file": "payments.csv"}, "credits": {"file": "credits.csv"}}, indent=1) + "\n")
    closed = [{k: x[k] for k in ("event_id", "money_kind", "amount", "reference", "superseded_by")} for x in resolutions(con) if x["amount"]]
    print(json.dumps({"out": str(out), "files": ["invoices.csv", "payments.csv", "credits.csv", "package.json"],
                      "closed_money_not_in_books": closed}))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="payment_ledger.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--db", required=True); s.add_argument("--catalog", required=True)
    s = sub.add_parser("sign"); s.add_argument("--secret-file", required=True); s.add_argument("--body-file", required=True)
    s.add_argument("--t", type=int)
    s = sub.add_parser("ingest"); s.add_argument("--db", required=True); s.add_argument("--secret-file", required=True)
    s.add_argument("--events", required=True); s.add_argument("--now", type=int); s.add_argument("--tolerance", type=int, default=300)
    s.add_argument("--crash-after", type=int, default=0)
    s = sub.add_parser("report"); s.add_argument("--db", required=True); s.add_argument("--json", action="store_true")
    s = sub.add_parser("check"); s.add_argument("--db", required=True); s.add_argument("--json", action="store_true")
    s = sub.add_parser("export-g14"); s.add_argument("--db", required=True); s.add_argument("--out", required=True)
    s.add_argument("--period-start", required=True); s.add_argument("--period-end", required=True)
    s = sub.add_parser("resolve"); s.add_argument("--db", required=True); s.add_argument("--event", required=True)
    s.add_argument("--action", required=True, choices=("retry", "close")); s.add_argument("--by", required=True)
    s.add_argument("--note", required=True); s.add_argument("--reference"); s.add_argument("--superseded-by")
    s.add_argument("--now", type=int)
    a = p.parse_args(argv)
    fn = {"init": cmd_init, "sign": cmd_sign, "ingest": cmd_ingest, "report": cmd_report, "check": cmd_check,
          "export-g14": cmd_export_g14, "resolve": cmd_resolve}[a.cmd]
    try:
        return fn(a)
    except Invalid as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
