#!/usr/bin/env python3
"""M19 stubs: in-memory invoice APIs that speak the documented CLI and endpoints, each broken on purpose.

Usage: m19_stub.py MODE serve --db F --principals F [--host H] [--port 0] [--ready-file F] [--fault-plan F]
       m19_stub.py MODE check --db F [--json]
MODE: noop        answers every call, stores nothing
      naive       tenant-correct and validating, but no idempotency (every POST is a new effect)
      vulnerable  idempotency keyed globally, lookups ignore the tenant, trusts tenant_id in the body,
                  unlocked read-modify-write on payments
      racy        correct rules, but the idempotency check and the effect are not atomic
Loopback only (binds 127.0.0.1). Written for M19; it does not reuse the candidate or the builder stubs.
"""
import argparse, hashlib, json, os, re, secrets, signal, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

MODE = sys.argv[1]
KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ID_RE = re.compile(r"^inv_[0-9a-f]{16}$")
LOCK = threading.Lock()
INV, ORDER, IDEM = {}, [], {}


class E(Exception):
    def __init__(self, st, code):
        self.st, self.code = st, code


def view(i):
    return dict(i, balance_cents=i["amount_cents"] - i["paid_cents"])


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, st, body, hdr=None):
        d = json.dumps(body).encode()
        self.send_response(st)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(d)))
        self.send_header("Connection", "close")
        for k, v in (hdr or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(d)
        self.close_connection = True

    def who(self):
        a = self.headers.get("Authorization") or ""
        p = self.server.principals.get(a[7:]) if a.startswith("Bearer ") else None
        if not p:
            raise E(401, "unauthenticated")
        return p

    def route(self, method):
        u = urlsplit(self.path)
        parts = u.path.rstrip("/").split("/")[1:]
        q = parse_qs(u.query)
        if parts == ["api", "v1", "health"]:
            return self.send(200, {"ok": True, "version": "stub"})
        if parts[:3] != ["api", "v1", "invoices"] or len(parts) > 5:
            raise E(404, "no_route")
        p = self.who()
        iid = parts[3] if len(parts) >= 4 else None
        action = parts[4] if len(parts) == 5 else None
        if method == "GET":
            if iid is None:
                return self.do_list(p, q)
            i = INV.get(iid)
            if MODE == "noop" or not i or (MODE != "vulnerable" and i["tenant"] != p["tenant"]):
                raise E(404, "not_found")
            return self.send(200, view(i))
        if method != "POST":
            raise E(405, "method_not_allowed")
        if p["role"] != "editor":
            raise E(403, "forbidden")
        n = self.headers.get("Content-Length")
        if n is None or not n.isascii() or not n.isdigit():
            raise E(411, "length_required")
        if int(n) > 16384:
            raise E(413, "body_too_large")
        try:
            body = json.loads(self.rfile.read(int(n)) or b"{}")
        except ValueError:
            raise E(400, "invalid_json")
        if not isinstance(body, dict):
            raise E(400, "invalid_json")
        key = self.headers.get("Idempotency-Key")
        if key is None:
            raise E(400, "idempotency_key_required")
        if not KEY_RE.match(key):
            raise E(400, "invalid_idempotency_key")
        tenant = p["tenant"]
        if MODE == "vulnerable" and isinstance(body.get("tenant_id"), str):
            tenant = body.pop("tenant_id")
        allowed = {None: {"customer", "amount_cents", "currency"}, "payments": {"amount_cents"}, "void": {"reason"}}.get(action)
        if allowed is None:
            raise E(404, "no_route")
        extra = set(body) - allowed
        if extra & {"tenant", "tenant_id", "owner", "created_by"}:
            raise E(422, "tenant_is_server_derived")
        if extra:
            raise E(422, "unknown_field")
        fp = hashlib.sha256(json.dumps([action, iid, body], sort_keys=True).encode()).hexdigest()
        ik = key if MODE == "vulnerable" else (tenant, key)
        if MODE in ("vulnerable", "racy"):
            hit = IDEM.get(ik)
            if hit:
                return self.replay(hit, fp)
            time.sleep(0.01)
            st, res = self.effect(tenant, p, action, iid, body)
            if st in (200, 201, 409):
                IDEM[ik] = (fp, st, res)
        else:
            with LOCK:
                hit = IDEM.get(ik) if MODE != "naive" else None
                if hit:
                    return self.replay(hit, fp)
                st, res = self.effect(tenant, p, action, iid, body)
                if st in (200, 201, 409) and MODE != "naive":
                    IDEM[ik] = (fp, st, res)
        hdr = {"Idempotent-Replayed": "false"}
        if st == 201 and action is None:
            hdr["Location"] = "/api/v1/invoices/" + res["id"]
        return self.send(st, res, hdr)

    def replay(self, hit, fp):
        if hit[0] != fp:
            raise E(422, "idempotency_key_reused")
        hdr = {"Idempotent-Replayed": "true"}
        if hit[1] == 201 and "id" in hit[2] and "paid_cents" in hit[2] and hit[2]["version"] == 1:
            hdr["Location"] = "/api/v1/invoices/" + hit[2]["id"]
        return self.send(hit[1], hit[2], hdr)

    def effect(self, tenant, p, action, iid, body):
        amt = body.get("amount_cents")
        if action is None:
            c = body.get("customer")
            if not isinstance(c, str) or not 1 <= len(c) <= 80:
                raise E(422, "invalid_customer")
            if isinstance(amt, bool) or not isinstance(amt, int) or not 1 <= amt <= 10 ** 12:
                raise E(422, "invalid_amount")
            if body.get("currency") not in ("EUR", "GBP", "USD"):
                raise E(422, "invalid_currency")
            i = {"id": "inv_" + secrets.token_hex(8), "tenant": tenant, "customer": c, "amount_cents": amt,
                 "currency": body["currency"], "paid_cents": 0, "status": "open", "version": 1}
            if MODE != "noop":
                INV[i["id"]] = i
                ORDER.append(i["id"])
            return 201, view(i)
        i = INV.get(iid)
        if MODE == "noop" or not i or (MODE != "vulnerable" and i["tenant"] != tenant):
            raise E(404, "not_found")
        if action == "payments":
            if isinstance(amt, bool) or not isinstance(amt, int) or not 1 <= amt <= 10 ** 12:
                raise E(422, "invalid_amount")
            if i["status"] != "open":
                return 409, {"error": {"code": "invoice_not_open", "message": "not open"}}
            bal = i["amount_cents"] - i["paid_cents"]
            if amt > bal:
                return 409, {"error": {"code": "exceeds_balance", "message": "balance %d" % bal}}
            if MODE == "vulnerable":
                paid = i["paid_cents"]
                time.sleep(0.02)
                i["paid_cents"] = paid + amt
            else:
                i["paid_cents"] += amt
            i["version"] += 1
            if i["paid_cents"] == i["amount_cents"]:
                i["status"] = "paid"
            return 201, view(i)
        r = body.get("reason", "")
        if not isinstance(r, str) or len(r) > 200:
            raise E(422, "invalid_reason")
        if i["status"] != "open" or i["paid_cents"]:
            return 409, {"error": {"code": "cannot_void", "message": "cannot void"}}
        i["status"] = "void"
        i["version"] += 1
        return 200, view(i)

    def do_list(self, p, q):
        if set(q) - {"limit", "after"}:
            raise E(422, "unknown_parameter")
        lim = q.get("limit", ["20"])[0]
        if not lim.isascii() or not lim.isdigit() or not 1 <= int(lim) <= 100:
            raise E(422, "invalid_limit")
        mine = [x for x in ORDER if MODE == "vulnerable" or INV[x]["tenant"] == p["tenant"]]
        start = 0
        if "after" in q:
            a = q["after"][0]
            if a not in mine:
                raise E(422, "invalid_cursor")
            start = mine.index(a) + 1
        page = mine[start:start + int(lim)]
        nxt = page[-1] if start + int(lim) < len(mine) else None
        return self.send(200, {"data": [view(INV[x]) for x in page], "next_after": nxt})

    def handle_any(self, m):
        try:
            self.route(m)
        except E as e:
            self.send(e.st, {"error": {"code": e.code, "message": e.code}})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PUT(self):
        self.handle_any("PUT")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve")
    for a in ("--db", "--principals", "--ready-file", "--fault-plan"):
        s.add_argument(a)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=0)
    c = sub.add_parser("check")
    c.add_argument("--db")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(sys.argv[2:])
    if a.cmd == "check":
        if not a.db or not os.path.isfile(a.db):
            print("invalid: no db", file=sys.stderr)
            return 2
        print("consistent: stub")
        return 0
    if MODE != "noop" and a.host not in ("127.0.0.1", "localhost"):
        print("invalid: host", file=sys.stderr)
        return 2
    try:
        doc = json.load(open(a.principals))
        principals = {x["key"]: x for x in doc["principals"]}
        assert doc["schema"] == "solaris.ledger-principals/1"
    except Exception:
        print("invalid: principals", file=sys.stderr)
        return 2
    open(a.db, "a").close()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    srv.daemon_threads = True
    srv.principals = principals
    if a.ready_file:
        tmp = a.ready_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"host": "127.0.0.1", "port": srv.server_address[1], "pid": os.getpid()}, f)
        os.replace(tmp, a.ready_file)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown, daemon=True).start())
    srv.serve_forever(poll_interval=0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
