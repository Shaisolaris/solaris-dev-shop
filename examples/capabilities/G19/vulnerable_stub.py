#!/usr/bin/env python3
"""DELIBERATELY VULNERABLE stand-in for ledger_api.py (demonstration and negative control only).

Same CLI and endpoints, same happy-path answers, but with the four bugs G19 is about:
  1. Idempotency-Key is accepted and ignored, so a retried or concurrent create/payment runs twice.
  2. GET /api/v1/invoices/{id}, payments and void look the id up without the tenant (IDOR).
  3. A payment reads the balance, waits, then writes it back with no transaction (lost update).
  4. A "tenant_id" field in the body is trusted when creating.
State is a JSON file rewritten after every write. Loopback only. Never use this as a server.
"""
import argparse
import hashlib
import json
import os
import secrets
import signal
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

STATE = {"invoices": []}
KEYS = {}
DB = None


def save():
    with open(DB, "w") as f:
        json.dump(STATE, f)


def view(inv):
    out = dict(inv)
    out["balance_cents"] = inv["amount_cents"] - inv["paid_cents"]
    return out


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, st, body, hdr=None):
        data = json.dumps(body, sort_keys=True).encode()
        self.send_response(st)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        for k, v in (hdr or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def who(self):
        h = self.headers.get("Authorization", "")
        return KEYS.get(hashlib.sha256(h[7:].encode()).hexdigest()) if h.startswith("Bearer ") else None

    def find(self, iid):
        return next((i for i in STATE["invoices"] if i["id"] == iid), None)  # bug 2: no tenant filter

    def do_GET(self):
        u = urlsplit(self.path)
        parts = u.path.strip("/").split("/")
        if u.path == "/api/v1/health":
            return self.send(200, {"ok": True})
        w = self.who()
        if not w:
            return self.send(401, {"error": {"code": "unauthenticated", "message": "no key"}})
        if parts == ["api", "v1", "invoices"]:
            q = parse_qs(u.query)
            limit = int(q.get("limit", ["20"])[0])
            mine = [i for i in STATE["invoices"] if i["tenant"] == w["tenant"]]
            start = 0
            if "after" in q:
                start = next((n + 1 for n, i in enumerate(mine) if i["id"] == q["after"][0]), 0)
            page = mine[start:start + limit]
            nxt = page[-1]["id"] if start + limit < len(mine) else None
            return self.send(200, {"data": [view(i) for i in page], "next_after": nxt})
        if len(parts) == 4 and parts[:3] == ["api", "v1", "invoices"]:
            inv = self.find(parts[3])
            return self.send(200, view(inv)) if inv else self.send(404, {"error": {"code": "not_found", "message": "no such invoice"}})
        return self.send(404, {"error": {"code": "no_route", "message": "no such endpoint"}})

    def do_POST(self):
        u = urlsplit(self.path)
        parts = u.path.strip("/").split("/")
        w = self.who()
        if not w:
            return self.send(401, {"error": {"code": "unauthenticated", "message": "no key"}})
        if w["role"] != "editor":
            return self.send(403, {"error": {"code": "forbidden", "message": "viewer"}})
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if parts == ["api", "v1", "invoices"]:
            inv = {"id": "inv_" + secrets.token_hex(8), "tenant": body.get("tenant_id", w["tenant"]),  # bug 4
                   "customer": body["customer"], "amount_cents": body["amount_cents"], "currency": body["currency"],
                   "paid_cents": 0, "status": "open", "version": 1}
            STATE["invoices"].append(inv)  # bug 1: key ignored
            save()
            return self.send(201, view(inv), {"Location": "/api/v1/invoices/" + inv["id"]})
        if len(parts) == 5 and parts[:3] == ["api", "v1", "invoices"]:
            inv = self.find(parts[3])
            if not inv:
                return self.send(404, {"error": {"code": "not_found", "message": "no such invoice"}})
            if parts[4] == "payments":
                bal = inv["amount_cents"] - inv["paid_cents"]  # bug 3: read ...
                if body["amount_cents"] > bal:
                    return self.send(409, {"error": {"code": "exceeds_balance", "message": "too much"}})
                paid = inv["paid_cents"]
                time.sleep(0.02)
                inv["paid_cents"] = paid + body["amount_cents"]  # ... then write back
                inv["status"] = "paid" if inv["paid_cents"] >= inv["amount_cents"] else "open"
                save()
                return self.send(201, view(inv))
            if parts[4] == "void":
                inv["status"] = "void"
                save()
                return self.send(200, view(inv))
        return self.send(404, {"error": {"code": "no_route", "message": "no such endpoint"}})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128

    def server_bind(self):
        # The address is already numeric loopback. HTTPServer's reverse DNS lookup
        # can block offline/startup on macOS and is unnecessary for these routes.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]



def main():
    global DB
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--db", required=True)
    s.add_argument("--principals", required=True)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--ready-file")
    s.add_argument("--fault-plan")
    a = ap.parse_args()
    if a.host not in ("127.0.0.1", "::1", "localhost"):
        return 2
    DB = a.db
    if os.path.exists(DB) and os.path.getsize(DB):
        STATE.update(json.load(open(DB)))
    for p in json.load(open(a.principals))["principals"]:
        KEYS[hashlib.sha256(p["key"].encode()).hexdigest()] = p
    srv = Server(("127.0.0.1", a.port), H)
    if a.ready_file:
        with open(a.ready_file, "w") as f:
            json.dump({"host": "127.0.0.1", "port": srv.server_address[1], "pid": os.getpid()}, f)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown).start())
    srv.serve_forever(poll_interval=0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
