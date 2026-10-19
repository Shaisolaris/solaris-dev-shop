#!/usr/bin/env python3
"""Duplicate-safe, tenant-scoped invoice API on loopback (synthetic, local, stdlib only).

A minimal working API, not a hosted service. It binds to a loopback address only, stores its state
in one SQLite file and runs every write as one transaction that also records the idempotency key,
so a replayed or concurrent duplicate request gets the first response back instead of a second
effect. Tenant scope is taken from the caller's key, never from the request, and a record of another
tenant answers exactly like a record that does not exist.

Endpoints (the full list; ROUTES below is the source of truth and the docs are checked against it):
    GET  /api/v1/health
    POST /api/v1/invoices                    Idempotency-Key required
    GET  /api/v1/invoices                    ?limit=1..100 (default 20) &after=<invoice id>
    GET  /api/v1/invoices/{id}
    POST /api/v1/invoices/{id}/payments      Idempotency-Key required
    POST /api/v1/invoices/{id}/void          Idempotency-Key required

Commands:
    ledger_api.py serve --db FILE --principals FILE [--host 127.0.0.1] [--port 0]
                        [--ready-file FILE] [--fault-plan FILE]
    ledger_api.py check --db FILE [--json]

Exit codes: serve 0 on SIGTERM/SIGINT, 2 invalid input; check 0 consistent, 1 violations, 2 invalid.
Python 3.9+, no third-party packages, no outbound network.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import signal
import sqlite3
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

VERSION = "1.0.0"
PRINCIPALS_SCHEMA = "solaris.ledger-principals/1"
FAULT_SCHEMA = "solaris.ledger-fault-plan/1"

# (method, template, handler name, needs idempotency key, needs write role)
ROUTES = [
    ("GET", "/api/v1/health", "health", False, False),
    ("POST", "/api/v1/invoices", "create_invoice", True, True),
    ("GET", "/api/v1/invoices", "list_invoices", False, False),
    ("GET", "/api/v1/invoices/{id}", "get_invoice", False, False),
    ("POST", "/api/v1/invoices/{id}/payments", "pay_invoice", True, True),
    ("POST", "/api/v1/invoices/{id}/void", "void_invoice", True, True),
]
ROLES = {"viewer": False, "editor": True}  # role -> may write
CURRENCIES = ("EUR", "GBP", "USD")
MAX_BODY = 16 * 1024
MAX_AMOUNT = 10 ** 12
KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ID_RE = re.compile(r"^inv_[0-9a-f]{16}$")
TENANT_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
FIELDS = {
    "create_invoice": {"customer", "amount_cents", "currency"},
    "pay_invoice": {"amount_cents"},
    "void_invoice": {"reason"},
}
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS invoices (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  tenant TEXT NOT NULL,
  customer TEXT NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  currency TEXT NOT NULL,
  paid_cents INTEGER NOT NULL DEFAULT 0 CHECK (paid_cents >= 0 AND paid_cents <= amount_cents),
  status TEXT NOT NULL CHECK (status IN ('open', 'paid', 'void')),
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS invoices_tenant_seq ON invoices (tenant, seq);
CREATE TABLE IF NOT EXISTS payments (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant TEXT NOT NULL,
  invoice_id TEXT NOT NULL REFERENCES invoices (id),
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  idem_key TEXT NOT NULL,
  actor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
  tenant TEXT NOT NULL,
  idem_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  status INTEGER NOT NULL,
  response TEXT NOT NULL,
  effect TEXT NOT NULL,
  actor TEXT NOT NULL,
  PRIMARY KEY (tenant, idem_key)
);
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  invoice_id TEXT NOT NULL,
  amount_cents INTEGER,
  idem_key TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
  BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
  BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
"""


class Invalid(Exception):
    """Startup input that cannot be used; exit 2."""


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class InjectedFailure(Exception):
    pass


# ---------------------------------------------------------------- inputs

def _no_dup_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate JSON key {k!r}")
        out[k] = v
    return out


def load_principals(path: str) -> dict:
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise Invalid(f"principals: {path} is not a regular file")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=_no_dup_keys)
    except (ValueError, UnicodeDecodeError) as e:
        raise Invalid(f"principals: not valid JSON ({e})")
    if not isinstance(doc, dict) or doc.get("schema") != PRINCIPALS_SCHEMA:
        raise Invalid(f"principals: schema must be {PRINCIPALS_SCHEMA}")
    items = doc.get("principals")
    if not isinstance(items, list) or not items:
        raise Invalid("principals: 'principals' must be a non-empty list")
    by_digest, names = {}, set()
    for i, it in enumerate(items):
        if not isinstance(it, dict) or set(it) != {"key", "tenant", "user", "role"}:
            raise Invalid(f"principals[{i}]: needs exactly key, tenant, user, role")
        key, tenant, user, role = it["key"], it["tenant"], it["user"], it["role"]
        if not (isinstance(key, str) and 16 <= len(key) <= 200 and key.isprintable() and " " not in key):
            raise Invalid(f"principals[{i}]: key must be 16-200 printable characters without spaces")
        if not (isinstance(tenant, str) and TENANT_RE.match(tenant)):
            raise Invalid(f"principals[{i}]: tenant must match {TENANT_RE.pattern}")
        if not (isinstance(user, str) and TENANT_RE.match(user)):
            raise Invalid(f"principals[{i}]: user must match {TENANT_RE.pattern}")
        if role not in ROLES:
            raise Invalid(f"principals[{i}]: role must be one of {sorted(ROLES)}")
        d = hashlib.sha256(key.encode()).hexdigest()
        if d in by_digest:
            raise Invalid(f"principals[{i}]: key is repeated")
        if (tenant, user) in names:
            raise Invalid(f"principals[{i}]: user {user!r} repeated in tenant {tenant!r}")
        names.add((tenant, user))
        by_digest[d] = {"tenant": tenant, "user": user, "role": role}
    return by_digest


def load_fault_plan(path: str | None) -> dict:
    """Drill only. {"schema": ..., "fail_before_commit": {key: n}, "crash_before_commit": [key],
    "crash_after_commit": [key]}; keys are Idempotency-Key values."""
    if not path:
        return {"fail_before_commit": {}, "crash_before_commit": set(), "crash_after_commit": set()}
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_no_dup_keys)
    except (OSError, ValueError) as e:
        raise Invalid(f"fault plan: {e}")
    if not isinstance(doc, dict) or doc.get("schema") != FAULT_SCHEMA:
        raise Invalid(f"fault plan: schema must be {FAULT_SCHEMA}")
    extra = set(doc) - {"schema", "fail_before_commit", "crash_before_commit", "crash_after_commit"}
    if extra:
        raise Invalid(f"fault plan: unknown fields {sorted(extra)}")
    fails = doc.get("fail_before_commit", {})
    if not isinstance(fails, dict) or not all(isinstance(v, int) and v > 0 for v in fails.values()):
        raise Invalid("fault plan: fail_before_commit maps a key to a positive count")
    out = {"fail_before_commit": dict(fails)}
    for name in ("crash_before_commit", "crash_after_commit"):
        v = doc.get(name, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise Invalid(f"fault plan: {name} must be a list of keys")
        out[name] = set(v)
    return out


def loopback_host(host: str) -> str:
    if host == "localhost":
        return "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise Invalid(f"host {host!r} is not an IP address; only loopback is allowed")
    if not ip.is_loopback:
        raise Invalid(f"host {host} is not loopback; this API never listens beyond this machine")
    return host


# ---------------------------------------------------------------- storage

def connect(db: str) -> sqlite3.Connection:
    con = sqlite3.connect(db, timeout=30, isolation_level=None, check_same_thread=False)
    con.execute("PRAGMA busy_timeout = 30000")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA synchronous = FULL")
    return con


def init_db(db: str) -> None:
    p = Path(db)
    if p.is_symlink() or (p.exists() and not p.is_file()):
        raise Invalid(f"db: {db} is not a regular file")
    if not p.parent.is_dir():
        raise Invalid(f"db: folder {p.parent} does not exist")
    try:
        con = connect(db)
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(SCHEMA_SQL)
        con.close()
    except sqlite3.DatabaseError as e:
        raise Invalid(f"db: {db} is not a usable SQLite file ({e})")


def invoice_view(row) -> dict:
    seq, iid, tenant, customer, amount, currency, paid, status, version, _by = row
    return {"id": iid, "tenant": tenant, "customer": customer, "amount_cents": amount,
            "currency": currency, "paid_cents": paid, "balance_cents": amount - paid,
            "status": status, "version": version}


INVOICE_COLS = "seq, id, tenant, customer, amount_cents, currency, paid_cents, status, version, created_by"


def find_invoice(con, tenant: str, iid: str):
    # Tenant is part of every lookup; another tenant's id is indistinguishable from a missing id.
    if not ID_RE.match(iid):
        return None
    return con.execute(f"SELECT {INVOICE_COLS} FROM invoices WHERE tenant = ? AND id = ?",
                       (tenant, iid)).fetchone()


def not_found():
    return ApiError(404, "not_found", "no such invoice")


# ---------------------------------------------------------------- validation

def _int_amount(body: dict) -> int:
    v = body.get("amount_cents")
    if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= MAX_AMOUNT):
        raise ApiError(422, "invalid_amount", f"amount_cents must be an integer from 1 to {MAX_AMOUNT}")
    return v


def check_fields(handler: str, body: dict) -> None:
    allowed = FIELDS[handler]
    extra = sorted(set(body) - allowed)
    if any(k.lower().replace("-", "_") in ("tenant", "tenant_id", "owner", "created_by") for k in extra):
        raise ApiError(422, "tenant_is_server_derived",
                       "tenant and owner come from the caller's key and cannot be set in the body")
    if extra:
        raise ApiError(422, "unknown_field", f"unknown fields: {', '.join(extra)}")


# ---------------------------------------------------------------- server

class Ledger:
    def __init__(self, db: str, principals: dict, faults: dict):
        self.db, self.principals, self.faults = db, principals, faults
        self.lock = threading.Lock()

    def authenticate(self, header: str | None):
        if not header or not header.startswith("Bearer "):
            raise ApiError(401, "unauthenticated", "send Authorization: Bearer <key>")
        d = hashlib.sha256(header[7:].strip().encode()).hexdigest()
        for known, who in self.principals.items():
            if hmac.compare_digest(known, d):
                return who
        raise ApiError(401, "unauthenticated", "unknown key")

    def _fault(self, point: str, key: str) -> None:
        if point == "before_commit":
            with self.lock:
                left = self.faults["fail_before_commit"].get(key, 0)
                if left:
                    self.faults["fail_before_commit"][key] = left - 1
            if left:
                raise InjectedFailure(key)
            if key in self.faults["crash_before_commit"]:
                os._exit(70)
        elif point == "after_commit" and key in self.faults["crash_after_commit"]:
            os._exit(70)

    def write(self, who: dict, handler: str, iid: str | None, key: str, body: dict, fingerprint: str):
        """One transaction: replay check, effect, idempotency record, audit row. Returns (status, body, replayed)."""
        tenant = who["tenant"]
        con = connect(self.db)
        try:
            con.execute("BEGIN IMMEDIATE")
            try:
                row = con.execute("SELECT fingerprint, status, response FROM idempotency WHERE tenant = ? AND idem_key = ?",
                                  (tenant, key)).fetchone()
                if row:
                    con.execute("ROLLBACK")
                    if row[0] != fingerprint:
                        raise ApiError(422, "idempotency_key_reused",
                                       "this Idempotency-Key was already used for a different request")
                    return row[1], json.loads(row[2]), True
                try:
                    status, resp, effect = getattr(self, handler)(con, who, iid, key, body)
                except ApiError as e:
                    if e.status != 409:
                        raise
                    # A domain conflict is a decided outcome; replays must see the same answer.
                    status, resp, effect = e.status, {"error": {"code": e.code, "message": e.message}}, "none"
                con.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (tenant, key, fingerprint, status, json.dumps(resp, sort_keys=True), effect, who["user"]))
                self._fault("before_commit", key)
                con.execute("COMMIT")
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
            self._fault("after_commit", key)
            return status, resp, False
        finally:
            con.close()

    # handlers run inside the write transaction
    def create_invoice(self, con, who, _iid, key, body):
        cust = body.get("customer")
        if not isinstance(cust, str) or not (1 <= len(cust) <= 80) or not cust.isprintable():
            raise ApiError(422, "invalid_customer", "customer must be 1-80 printable characters")
        amount = _int_amount(body)
        cur = body.get("currency")
        if cur not in CURRENCIES:
            raise ApiError(422, "invalid_currency", f"currency must be one of {', '.join(CURRENCIES)}")
        iid = "inv_" + secrets.token_hex(8)
        con.execute("INSERT INTO invoices (id, tenant, customer, amount_cents, currency, status, created_by) "
                    "VALUES (?, ?, ?, ?, ?, 'open', ?)", (iid, who["tenant"], cust, amount, cur, who["user"]))
        con.execute("INSERT INTO audit (tenant, actor, action, invoice_id, amount_cents, idem_key) VALUES (?, ?, 'create', ?, ?, ?)",
                    (who["tenant"], who["user"], iid, amount, key))
        return 201, invoice_view(find_invoice(con, who["tenant"], iid)), "create:" + iid

    def pay_invoice(self, con, who, iid, key, body):
        amount = _int_amount(body)
        row = find_invoice(con, who["tenant"], iid)
        if row is None:
            raise not_found()
        inv = invoice_view(row)
        if inv["status"] != "open":
            raise ApiError(409, "invoice_not_open", f"invoice is {inv['status']}")
        if amount > inv["balance_cents"]:
            raise ApiError(409, "exceeds_balance", f"payment {amount} is more than the balance {inv['balance_cents']}")
        paid = inv["paid_cents"] + amount
        con.execute("UPDATE invoices SET paid_cents = ?, status = ?, version = version + 1 WHERE tenant = ? AND id = ?",
                    (paid, "paid" if paid == inv["amount_cents"] else "open", who["tenant"], iid))
        con.execute("INSERT INTO payments (tenant, invoice_id, amount_cents, idem_key, actor) VALUES (?, ?, ?, ?, ?)",
                    (who["tenant"], iid, amount, key, who["user"]))
        con.execute("INSERT INTO audit (tenant, actor, action, invoice_id, amount_cents, idem_key) VALUES (?, ?, 'pay', ?, ?, ?)",
                    (who["tenant"], who["user"], iid, amount, key))
        return 201, invoice_view(find_invoice(con, who["tenant"], iid)), "pay:" + iid

    def void_invoice(self, con, who, iid, key, body):
        reason = body.get("reason", "")
        if not isinstance(reason, str) or len(reason) > 200:
            raise ApiError(422, "invalid_reason", "reason must be a string of at most 200 characters")
        row = find_invoice(con, who["tenant"], iid)
        if row is None:
            raise not_found()
        inv = invoice_view(row)
        if inv["status"] != "open" or inv["paid_cents"]:
            raise ApiError(409, "cannot_void", "only an open invoice with no payments can be voided")
        con.execute("UPDATE invoices SET status = 'void', version = version + 1 WHERE tenant = ? AND id = ?",
                    (who["tenant"], iid))
        con.execute("INSERT INTO audit (tenant, actor, action, invoice_id, amount_cents, idem_key) VALUES (?, ?, 'void', ?, NULL, ?)",
                    (who["tenant"], who["user"], iid, key))
        return 200, invoice_view(find_invoice(con, who["tenant"], iid)), "void:" + iid

    def get_invoice(self, who, iid, query):
        con = connect(self.db)
        try:
            row = find_invoice(con, who["tenant"], iid)
        finally:
            con.close()
        if row is None:
            raise not_found()
        return 200, invoice_view(row)

    def list_invoices(self, who, _iid, query):
        bad = sorted(set(query) - {"limit", "after"})
        if bad:
            raise ApiError(422, "unknown_parameter", f"unknown query parameters: {', '.join(bad)}")
        lim = query.get("limit", ["20"])
        if len(lim) != 1 or not lim[0].isdigit() or not (1 <= int(lim[0]) <= 100):
            raise ApiError(422, "invalid_limit", "limit must be an integer from 1 to 100")
        limit = int(lim[0])
        con = connect(self.db)
        try:
            after_seq = 0
            if "after" in query:
                a = query["after"]
                row = find_invoice(con, who["tenant"], a[0]) if len(a) == 1 else None
                if row is None:
                    raise ApiError(422, "invalid_cursor", "after must be an invoice id from a previous page")
                after_seq = row[0]
            rows = con.execute(f"SELECT {INVOICE_COLS} FROM invoices WHERE tenant = ? AND seq > ? ORDER BY seq LIMIT ?",
                               (who["tenant"], after_seq, limit + 1)).fetchall()
        finally:
            con.close()
        items = [invoice_view(r) for r in rows[:limit]]
        return 200, {"data": items, "next_after": items[-1]["id"] if len(rows) > limit else None}


def match_route(method: str, path: str):
    parts = path.rstrip("/").split("/") if path != "/" else [""]
    allowed = []
    for m, tmpl, name, idem, write in ROUTES:
        t = tmpl.split("/")
        if len(t) != len(parts):
            continue
        iid, ok = None, True
        for a, b in zip(t, parts):
            if a == "{id}":
                iid = b
            elif a != b:
                ok = False
                break
        if ok:
            if m == method:
                return name, iid, idem, write
            allowed.append(m)
    if allowed:
        raise ApiError(405, "method_not_allowed", f"allowed: {', '.join(sorted(set(allowed)))}")
    raise ApiError(404, "no_route", "no such endpoint")


class Handler(BaseHTTPRequestHandler):
    server_version = "solaris-ledger/" + VERSION
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet; the audit table is the record
        pass

    def _send(self, status: int, body: dict, extra: dict | None = None):
        data = json.dumps(body, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def _handle(self, method: str):
        led: Ledger = self.server.ledger
        try:
            url = urlsplit(self.path)
            name, iid, needs_key, needs_write = match_route(method, url.path)
            if name == "health":
                return self._send(200, {"ok": True, "version": VERSION})
            who = led.authenticate(self.headers.get("Authorization"))
            query = parse_qs(url.query, keep_blank_values=True)
            if method == "GET":
                status, body = getattr(led, name)(who, iid, query)
                return self._send(status, body)
            if not ROLES[who["role"]]:
                raise ApiError(403, "forbidden", f"role {who['role']} cannot write")
            if url.query:
                raise ApiError(422, "unknown_parameter", "write endpoints take no query parameters")
            length = self.headers.get("Content-Length")
            if length is None or not length.isdigit():
                raise ApiError(411, "length_required", "send Content-Length")
            if int(length) > MAX_BODY:
                raise ApiError(413, "body_too_large", f"body is over {MAX_BODY} bytes")
            raw = self.rfile.read(int(length)) if int(length) else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dup_keys)
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, "invalid_json", "body must be one JSON object")
            if not isinstance(body, dict):
                raise ApiError(400, "invalid_json", "body must be one JSON object")
            check_fields(name, body)
            key = self.headers.get("Idempotency-Key")
            if needs_key and key is None:
                raise ApiError(400, "idempotency_key_required", "send an Idempotency-Key header on this POST")
            if not KEY_RE.match(key or ""):
                raise ApiError(400, "invalid_idempotency_key", "Idempotency-Key must be 1-128 of A-Z a-z 0-9 . _ : -")
            fp = hashlib.sha256(json.dumps([method, name, iid, body], sort_keys=True).encode()).hexdigest()
            status, resp, replayed = led.write(who, name, iid, key, body, fp)
            hdr = {"Idempotent-Replayed": "true" if replayed else "false"}
            if status == 201 and name == "create_invoice":
                hdr["Location"] = f"/api/v1/invoices/{resp['id']}"
            return self._send(status, resp, hdr)
        except ApiError as e:
            return self._send(e.status, {"error": {"code": e.code, "message": e.message}})
        except InjectedFailure:
            return self._send(503, {"error": {"code": "transient_failure",
                                              "message": "write rolled back; retry with the same Idempotency-Key"}},
                              {"Retry-After": "0"})
        except sqlite3.OperationalError:
            return self._send(503, {"error": {"code": "storage_busy", "message": "write rolled back; retry with the same Idempotency-Key"}},
                              {"Retry-After": "1"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_DELETE(self):
        self._handle("DELETE")


class LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128  # the default backlog of 5 resets bursts of concurrent retries


def _atomic_write(path: str, text: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".ledger-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def serve(args) -> int:
    host = loopback_host(args.host)
    principals = load_principals(args.principals)
    faults = load_fault_plan(args.fault_plan)
    init_db(args.db)
    if not 0 <= args.port <= 65535:
        raise Invalid(f"port {args.port} is not 0-65535")
    try:
        httpd = LoopbackServer((host, args.port), Handler)
    except OSError as e:
        raise Invalid(f"cannot listen on {host}:{args.port} ({e.strerror or e})")
    httpd.ledger = Ledger(args.db, principals, faults)
    port = httpd.server_address[1]
    if args.ready_file:
        _atomic_write(args.ready_file, json.dumps({"host": host, "port": port, "pid": os.getpid()}) + "\n")
    print(f"listening on http://{host}:{port} (loopback only, db {os.path.basename(args.db)})", flush=True)

    def stop(*_):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    httpd.serve_forever(poll_interval=0.1)
    httpd.server_close()
    return 0


# ---------------------------------------------------------------- check

def check(db: str) -> dict:
    p = Path(db)
    if p.is_symlink() or not p.is_file():
        raise Invalid(f"db: {db} is not a regular file")
    con = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    try:
        violations = []
        inv = {r[1]: r for r in con.execute(f"SELECT {INVOICE_COLS} FROM invoices")}
        pays = con.execute("SELECT tenant, invoice_id, amount_cents, idem_key FROM payments").fetchall()
        idem = con.execute("SELECT tenant, idem_key, effect FROM idempotency").fetchall()
        audit = con.execute("SELECT tenant, action, invoice_id, amount_cents, idem_key FROM audit").fetchall()
        paid_sum = {}
        for t, iid, amt, key in pays:
            row = inv.get(iid)
            if row is None or row[2] != t:
                violations.append(f"payment {key} in tenant {t} points at invoice {iid} of another tenant or none")
            paid_sum[iid] = paid_sum.get(iid, 0) + amt
        for iid, r in inv.items():
            v = invoice_view(r)
            if paid_sum.get(iid, 0) != v["paid_cents"]:
                violations.append(f"{iid}: paid_cents {v['paid_cents']} but payments add to {paid_sum.get(iid, 0)}")
            want = "void" if v["status"] == "void" else ("paid" if v["paid_cents"] == v["amount_cents"] else "open")
            if v["status"] != want:
                violations.append(f"{iid}: status {v['status']} but amounts say {want}")
        effects = {}
        for t, key, eff in idem:
            if eff != "none":
                effects[(t, key)] = eff
        audit_keys = {}
        for t, action, iid, amt, key in audit:
            audit_keys.setdefault((t, key), []).append(f"{action}:{iid}")
        for k, eff in effects.items():
            if audit_keys.get(k) != [eff]:
                violations.append(f"key {k[1]} in tenant {k[0]}: effect {eff} but audit has {audit_keys.get(k, [])}")
        for k, acts in audit_keys.items():
            if k not in effects:
                violations.append(f"audit rows {acts} for key {k[1]} in tenant {k[0]} have no idempotency record")
        tenants = sorted({r[2] for r in inv.values()})
        per = {t: {"invoices": sum(1 for r in inv.values() if r[2] == t),
                   "payments": sum(1 for x in pays if x[0] == t),
                   "paid_cents": sum(x[2] for x in pays if x[0] == t)} for t in tenants}
        return {"schema": "solaris.ledger-check/1", "ok": not violations, "violations": violations,
                "tenants": per, "idempotency_records": len(idem), "audit_rows": len(audit)}
    finally:
        con.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Duplicate-safe, tenant-scoped invoice API on loopback (synthetic).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the API on a loopback address")
    s.add_argument("--db", required=True)
    s.add_argument("--principals", required=True)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--ready-file")
    s.add_argument("--fault-plan", help="drill: fail or crash around the commit for named Idempotency-Keys")
    c = sub.add_parser("check", help="verify stored invariants (read-only)")
    c.add_argument("--db", required=True)
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "serve":
            return serve(args)
        rep = check(args.db)
    except Invalid as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 2
    except sqlite3.DatabaseError as e:
        print(f"invalid: db: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        print(("consistent" if rep["ok"] else "VIOLATIONS") + f": {sum(t['invoices'] for t in rep['tenants'].values())} invoices, "
              f"{rep['idempotency_records']} idempotency records, {rep['audit_rows']} audit rows")
        for v in rep["violations"]:
            print("  - " + v)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
