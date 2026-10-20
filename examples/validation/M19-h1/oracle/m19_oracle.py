#!/usr/bin/env python3
"""M19 oracle (v2): black-box checks of a duplicate-safe, tenant-scoped invoice API (G19 contract).

Written for M19 from duplicate-safe-api.md only; it does not import or read the builder's oracle,
tests, probe or stubs. It starts the candidate with its own seeded principals (four unseen tenants),
talks HTTP to 127.0.0.1 only, and compares every answer with its own model.

Usage: PY m19_oracle.py [--only k1,x3] [--scale N] [--seeds 7,2026,31337] [--tmp DIR] [--probe P] -- <candidate command...>
The candidate command must accept `serve --db F --principals F --port 0 --ready-file F [--fault-plan F] [--host H]`
and `check --db F`.

Core checks (k*) decide ACCEPT/REJECT. Adversarial checks (x*) are reported as OK (attack rejected)
or FINDING and never change the core score. Exit 0 when every core check passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import random
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ID_RE = re.compile(r"^inv_[0-9a-f]{16}$")
TENANTS = ("kestrel", "marlow", "quillon", "tarn-4")
LEAK_RE = re.compile(rb"Traceback|sqlite|File \"|Exception|<html", re.I)


class Fail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def principals(seed):
    r = random.Random(seed)
    items, keys = [], {}
    for t in TENANTS:
        for user, role in (("ed1", "editor"), ("ed2", "editor"), ("vw", "viewer")):
            k = "m19-%s-%s-%016x" % (t, user, r.getrandbits(64))
            items.append({"key": k, "tenant": t, "user": user, "role": role})
            keys[(t, user)] = k
    return {"schema": "solaris.ledger-principals/1", "principals": items}, keys


class Resp:
    def __init__(self, status, headers, body, err=""):
        self.status, self.h, self.body, self.err = status, headers, body, err
        try:
            self.js = json.loads(body) if body else None
        except ValueError:
            self.js = None

    @property
    def code(self):
        try:
            return self.js["error"]["code"]
        except (TypeError, KeyError):
            return None

    def __repr__(self):
        return "<%s %s %s>" % (self.status, self.code or "", (self.body[:120] if self.body else self.err))


class Ctx:
    def __init__(self, cmd, tmp, seed, scale, seeds):
        self.cmd, self.tmp, self.seed, self.scale, self.seeds = cmd, tmp, seed, scale, seeds


class Server:
    def __init__(self, ctx, seed=None):
        self.ctx = ctx
        self.dir = tempfile.mkdtemp(prefix="m19-oracle-", dir=ctx.tmp)
        self.db = os.path.join(self.dir, "ledger.db")
        doc, self.keys = principals(ctx.seed if seed is None else seed)
        self.pf = os.path.join(self.dir, "principals.json")
        with open(self.pf, "w") as f:
            json.dump(doc, f)
        self.proc, self.port, self.n = None, None, 0
        self.err = os.path.join(self.dir, "server.err")

    def k(self, tenant, user="ed1"):
        return self.keys[(tenant, user)]

    def start(self, fault=None, extra=()):
        self.n += 1
        rf = os.path.join(self.dir, "ready-%d.json" % self.n)
        args = list(self.ctx.cmd) + ["serve", "--db", self.db, "--principals", self.pf, "--port", "0", "--ready-file", rf]
        if fault is not None:
            fp = os.path.join(self.dir, "fault-%d.json" % self.n)
            with open(fp, "w") as f:
                json.dump(dict({"schema": "solaris.ledger-fault-plan/1"}, **fault), f)
            args += ["--fault-plan", fp]
        args += list(extra)
        with open(self.err, "ab") as ef:
            self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=ef, stdin=subprocess.DEVNULL)
        t0 = time.time()
        while time.time() - t0 < 20:
            if os.path.exists(rf) and os.path.getsize(rf) > 0:
                try:
                    with open(rf) as f:
                        self.port = int(json.load(f)["port"])
                    return self
                except (ValueError, KeyError):
                    pass
            if self.proc.poll() is not None:
                raise Fail("server exited %s before it was ready" % self.proc.returncode)
            time.sleep(0.03)
        self.stop()
        raise Fail("server not ready in 20s")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        return self.proc.returncode if self.proc else None

    def kill9(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()

    def wait_exit(self, t=10):
        try:
            return self.proc.wait(t)
        except subprocess.TimeoutExpired:
            return None

    def req(self, method, path, key=None, body=None, idem=None, headers=None, raw=None, timeout=30):
        h = {}
        if key:
            h["Authorization"] = "Bearer " + key
        if idem is not None:
            h["Idempotency-Key"] = idem
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        try:
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            b = r.read()
            hd = {k.lower(): v for k, v in r.getheaders()}
            st = r.status
            c.close()
        except (OSError, http.client.HTTPException) as e:
            return Resp(0, {}, b"", "%s: %s" % (type(e).__name__, e))
        return Resp(st, hd, b)

    def raw(self, data, timeout=10):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        try:
            s.sendall(data)
            out = b""
            try:
                while True:
                    ch = s.recv(65536)
                    if not ch:
                        break
                    out += ch
            except socket.timeout:
                out += b"<timeout>"
            except OSError as e:
                out += ("<%s>" % type(e).__name__).encode()
            return out
        finally:
            s.close()

    def until(self, method, path, key, body=None, idem=None, tries=30, headers=None):
        """A careful client: retry a dropped connection or a 503 with the same key, as the doc says."""
        for _ in range(tries):
            r = self.req(method, path, key, body, idem, headers=headers)
            if r.status not in (0, 503):
                return r
            time.sleep(0.05)
        return r

    def create(self, tenant, customer, amount=1000, idem=None, user="ed1", currency="USD"):
        return self.until("POST", "/api/v1/invoices", self.k(tenant, user),
                          {"customer": customer, "amount_cents": amount, "currency": currency},
                          idem or ("c-%s-%s" % (tenant, hashlib.sha1(customer.encode()).hexdigest()[:12])))

    def pay(self, tenant, iid, amount, idem, user="ed1"):
        return self.until("POST", "/api/v1/invoices/%s/payments" % iid, self.k(tenant, user), {"amount_cents": amount}, idem)

    def void(self, tenant, iid, idem, body=None, user="ed1"):
        return self.until("POST", "/api/v1/invoices/%s/void" % iid, self.k(tenant, user), body if body is not None else {}, idem)

    def get(self, tenant, iid, user="ed1"):
        return self.req("GET", "/api/v1/invoices/%s" % iid, self.k(tenant, user))

    def all(self, tenant, user="ed1", limit=100):
        out, after, pages = [], None, 0
        while True:
            q = "/api/v1/invoices?limit=%d" % limit + ("&after=%s" % after if after else "")
            r = self.req("GET", q, self.k(tenant, user))
            need(r.status == 200 and isinstance(r.js, dict), "list %s: %r" % (tenant, r))
            out += r.js["data"]
            after = r.js.get("next_after")
            pages += 1
            need(pages < 1000, "list never ends")
            if not after:
                return out

    def check(self, *extra, db=None):
        p = subprocess.run(list(self.ctx.cmd) + ["check", "--db", db or self.db] + list(extra),
                           capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout + p.stderr

    def close(self):
        self.stop()


def rand_id(r=random):
    return "inv_%016x" % r.getrandbits(64)


def err_shape_ok(r):
    return (isinstance(r.js, dict) and set(r.js) == {"error"} and isinstance(r.js["error"], dict)
            and set(r.js["error"]) == {"code", "message"} and isinstance(r.js["error"]["code"], str)
            and isinstance(r.js["error"]["message"], str) and not LEAK_RE.search(r.body))


def burst(fn, n):
    bar = threading.Barrier(n)

    def go(i):
        bar.wait()
        return fn(i)
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(go, range(n)))


def stopped_check(s):
    s.stop()
    rc, out = s.check()
    need(rc == 0 and "consistent" in out.lower() and "violation" not in out.lower(), "check after traffic: rc=%s %s" % (rc, out.strip()[:300]))


# ------------------------------------------------------------------ core checks

def k1_clean_control(ctx):
    s = Server(ctx).start()
    try:
        A, AV = s.k("kestrel"), s.k("kestrel", "vw")
        body = {"customer": "Fenwick & Daughters", "amount_cents": 12345, "currency": "GBP"}
        r1 = s.req("POST", "/api/v1/invoices", A, body, "k1-create-1")
        need(r1.status == 201 and isinstance(r1.js, dict), "create: %r" % r1)
        iid = r1.js.get("id", "")
        need(ID_RE.match(iid), "id %r is not inv_ + 16 hex" % iid)
        exp = {"id": iid, "tenant": "kestrel", "customer": "Fenwick & Daughters", "amount_cents": 12345, "currency": "GBP",
               "paid_cents": 0, "balance_cents": 12345, "status": "open", "version": 1}
        need(r1.js == exp, "create body %r" % r1.js)
        need(r1.h.get("location") == "/api/v1/invoices/" + iid, "Location %r" % r1.h.get("location"))
        need(r1.h.get("idempotent-replayed") == "false", "first create replayed=%r" % r1.h.get("idempotent-replayed"))
        r2 = s.req("POST", "/api/v1/invoices", A, body, "k1-create-1")
        need(r2.status == 201 and r2.js == exp and r2.h.get("idempotent-replayed") == "true", "replay: %r %r" % (r2, r2.h))
        need(r2.h.get("location") == r1.h.get("location"), "replay Location differs")
        for k in (A, AV):
            g = s.req("GET", "/api/v1/invoices/" + iid, k)
            need(g.status == 200 and g.js == exp, "get: %r" % g)
        lst = s.all("kestrel")
        need([x["id"] for x in lst] == [iid] and lst[0] == exp, "list: %r" % lst)
        p1 = s.req("POST", "/api/v1/invoices/%s/payments" % iid, A, {"amount_cents": 300}, "k1-pay-1")
        need(p1.status == 201 and p1.js == dict(exp, paid_cents=300, balance_cents=12045, version=2), "pay: %r" % p1)
        p2 = s.req("POST", "/api/v1/invoices/%s/payments" % iid, A, {"amount_cents": 12045}, "k1-pay-2")
        need(p2.status == 201 and p2.js == dict(exp, paid_cents=12345, balance_cents=0, status="paid", version=3), "pay rest: %r" % p2)
        p3 = s.req("POST", "/api/v1/invoices/%s/payments" % iid, A, {"amount_cents": 1}, "k1-pay-3")
        need(p3.status == 409 and p3.code == "invoice_not_open", "pay a paid invoice: %r" % p3)
        v1 = s.req("POST", "/api/v1/invoices/%s/void" % iid, A, {}, "k1-void-1")
        need(v1.status == 409 and v1.code == "cannot_void", "void a paid invoice: %r" % v1)
        c2 = s.create("kestrel", "Ostler Ltd", 500, "k1-create-2")
        v2 = s.req("POST", "/api/v1/invoices/%s/void" % c2.js["id"], A, {"reason": "duplicate order"}, "k1-void-2")
        need(v2.status == 200 and v2.js["status"] == "void" and v2.js["version"] == 2 and v2.js["paid_cents"] == 0, "void: %r" % v2)
        h = s.req("GET", "/api/v1/health")
        need(h.status == 200 and isinstance(h.js, dict) and h.js.get("ok") is True and "version" in h.js, "health: %r" % h)
        stopped_check(s)
        return "create/replay/get/list/pay/pay-rest/void exact; 409s exact; Location and Idempotent-Replayed right; check consistent"
    finally:
        s.close()


def k2_concurrent_replays(ctx):
    s = Server(ctx).start()
    try:
        A = s.k("marlow")
        body = {"customer": "Brightwater Mill", "amount_cents": 4200, "currency": "EUR"}
        rs = burst(lambda i: s.req("POST", "/api/v1/invoices", A, body, "k2-burst"), 48)
        need(all(r.status == 201 for r in rs), "48 concurrent duplicates, first attempt (doc: they get the first answer back): statuses %s %s" % (
            sorted({r.status for r in rs}), [r for r in rs if r.status != 201][:2]))
        ids = {r.js["id"] for r in rs}
        need(len(ids) == 1, "48 concurrent replays made %d invoices" % len(ids))
        fresh = sum(1 for r in rs if r.h.get("idempotent-replayed") == "false")
        need(fresh == 1, "%d responses claim to be the first (want 1)" % fresh)
        iid = ids.pop()
        ps = burst(lambda i: s.req("POST", "/api/v1/invoices/%s/payments" % iid, A, {"amount_cents": 250}, "k2-pay"), 32)
        need(all(p.status == 201 for p in ps), "32 concurrent payment duplicates, first attempt: statuses %s" % sorted({p.status for p in ps}))
        g = s.get("marlow", iid)
        need(g.js["paid_cents"] == 250 and g.js["version"] == 2, "32 replays of one payment: %r" % g.js)
        bx = {"customer": "Variant X", "amount_cents": 111, "currency": "USD"}
        by = {"customer": "Variant Y", "amount_cents": 222, "currency": "USD"}
        mixed = burst(lambda i: s.req("POST", "/api/v1/invoices", A, bx if i % 2 else by, "k2-mixed"), 32)
        made = [x for x in s.all("marlow") if x["customer"] in ("Variant X", "Variant Y")]
        need(len(made) == 1, "same key, two bodies, 32 concurrent: %d invoices" % len(made))
        win = bx if made[0]["customer"] == "Variant X" else by
        for i, r in enumerate(mixed):
            mine = bx if i % 2 else by
            if mine is win:
                need(r.status == 201 and r.js["id"] == made[0]["id"], "winner-body answer %r" % r)
            else:
                need(r.status == 422 and r.code == "idempotency_key_reused", "loser-body answer %r" % r)
        need(len(s.all("marlow")) == 2, "marlow holds %d invoices (want 2)" % len(s.all("marlow")))
        stopped_check(s)
        return "48-way create replay (first attempts all 201): 1 invoice, 1 first answer; 32-way payment replay: paid once; 32-way same key with 2 bodies: 1 effect, losers 422 reused"
    finally:
        s.close()


def k3_overspend_race(ctx):
    s = Server(ctx).start()
    try:
        iid = s.create("quillon", "Saltmarsh Coop", 1000, "k3-c").js["id"]
        rs = burst(lambda i: s.req("POST", "/api/v1/invoices/%s/payments" % iid, s.k("quillon"), {"amount_cents": 300}, "k3-p%02d" % i), 20)
        ok = [r for r in rs if r.status == 201]
        no = [r for r in rs if r.status == 409 and r.code == "exceeds_balance"]
        need(len(ok) == 3 and len(no) == 17, "20 x 300 on 1000: %d accepted, %d exceeds_balance, other %s" % (
            len(ok), len(no), [r for r in rs if r not in ok and r not in no][:3]))
        g = s.get("quillon", iid).js
        need(g["paid_cents"] == 900 and g["balance_cents"] == 100 and g["version"] == 4 and g["status"] == "open", "after race %r" % g)
        for i, r in enumerate(rs):
            again = s.pay("quillon", iid, 300, "k3-p%02d" % i)
            need(again.status == r.status and again.js == r.js, "replay of k3-p%02d: %r vs %r" % (i, again, r))
        last = s.pay("quillon", iid, 100, "k3-last")
        need(last.status == 201 and last.js["status"] == "paid", "final payment %r" % last)
        i409 = next(i for i, r in enumerate(rs) if r.status == 409)
        again = s.pay("quillon", iid, 300, "k3-p%02d" % i409)
        need(again.status == 409 and again.js == rs[i409].js, "a stored 409 replayed after the invoice changed: %r" % again)
        i201 = next(i for i, r in enumerate(rs) if r.status == 201)
        again = s.pay("quillon", iid, 300, "k3-p%02d" % i201)
        need(again.status == 201 and again.js == rs[i201].js and again.h.get("idempotent-replayed") == "true", "a 201 replayed: %r" % again)
        need(s.get("quillon", iid).js["paid_cents"] == 1000, "paid total moved after replays")
        stopped_check(s)
        return "20-way 300-on-1000 race: exactly 3 accepted, paid 900; replays of all 20 identical; stored 409 stays 409 after the balance changed"
    finally:
        s.close()


def k4_cross_tenant_reads(ctx):
    s = Server(ctx).start()
    try:
        ia = s.create("kestrel", "Hollin Farm", 700, "k4-a").js["id"]
        B, BV = s.k("marlow"), s.k("marlow", "vw")
        s.create("marlow", "Marlow Own", 900, "k4-b")
        ref = s.req("GET", "/api/v1/invoices/" + rand_id(), B)
        need(ref.status == 404 and ref.code == "not_found", "random id: %r" % ref)
        for k in (B, BV, s.k("quillon")):
            r = s.req("GET", "/api/v1/invoices/" + ia, k)
            need(r.status == 404 and r.body == ref.body, "other tenant reads %s: %r" % (ia, r))
        for t in ("marlow", "quillon", "tarn-4"):
            need(all(x["id"] != ia and x["tenant"] == t for x in s.all(t)), "%s list leaks" % t)
        c1 = s.req("GET", "/api/v1/invoices?after=" + ia, B)
        c2 = s.req("GET", "/api/v1/invoices?after=" + rand_id(), B)
        need(c1.status == 422 and c1.code == "invalid_cursor" and c1.body == c2.body, "foreign cursor %r vs made-up %r" % (c1, c2))
        made = [s.create("quillon", "Q page %d" % i, 100 + i, "k4-q%d" % i).js["id"] for i in range(7)]
        p, after, pages = [], None, []
        while True:
            r = s.req("GET", "/api/v1/invoices?limit=3" + ("&after=" + after if after else ""), s.k("quillon", "vw"))
            need(r.status == 200, "page %r" % r)
            pages.append(len(r.js["data"]))
            p += [x["id"] for x in r.js["data"]]
            after = r.js["next_after"]
            if not after:
                break
            need(after == r.js["data"][-1]["id"], "next_after is not the last id")
        need(p == made and pages == [3, 3, 1], "paging %s order ok=%s" % (pages, p == made))
        need([x["id"] for x in s.all("kestrel")] == [ia], "kestrel list %r" % s.all("kestrel"))
        stopped_check(s)
        return "other tenants' reads byte-identical to a missing id (editor, viewer, third tenant); lists never leak; foreign cursor = made-up cursor; paging 3/3/1 in order"
    finally:
        s.close()


def k5_cross_tenant_writes(ctx):
    s = Server(ctx).start()
    try:
        ia = s.create("kestrel", "Copperline", 1000, "k5-a").js["id"]
        before = s.get("kestrel", ia).js
        B = s.k("marlow")
        ref = s.req("POST", "/api/v1/invoices/%s/payments" % rand_id(), B, {"amount_cents": 100}, "k5-ref")
        need(ref.status == 404 and ref.code == "not_found", "pay a missing id: %r" % ref)
        r = s.req("POST", "/api/v1/invoices/%s/payments" % ia, B, {"amount_cents": 100}, "k5-x1")
        need(r.status == 404 and r.body == ref.body, "cross-tenant pay: %r" % r)
        r = s.req("POST", "/api/v1/invoices/%s/void" % ia, B, {}, "k5-x2")
        need(r.status == 404 and r.code == "not_found", "cross-tenant void: %r" % r)
        base = {"customer": "Smuggler", "amount_cents": 50, "currency": "USD"}
        for i, f in enumerate(("tenant_id", "tenant", "owner", "created_by")):
            r = s.req("POST", "/api/v1/invoices", B, dict(base, **{f: "kestrel"}), "k5-s%d" % i)
            need(r.status == 422 and r.code == "tenant_is_server_derived", "body %s: %r" % (f, r))
        for i, f in enumerate(("Tenant_ID", "tenantId", "tenant-id", "TENANT", "org")):
            r = s.req("POST", "/api/v1/invoices", B, dict(base, **{f: "kestrel"}), "k5-v%d" % i)
            need(r.status == 422, "body %s: %r" % (f, r))
        r = s.req("POST", "/api/v1/invoices/%s/payments" % ia, s.k("kestrel"), {"amount_cents": 10, "tenant_id": "marlow"}, "k5-p")
        need(r.status == 422, "pay with tenant_id: %r" % r)
        hdrs = {"X-Tenant-Id": "kestrel", "X-Tenant": "kestrel", "Tenant": "kestrel", "X-Org": "kestrel", "X-Forwarded-User": "ed1@kestrel"}
        r = s.req("POST", "/api/v1/invoices", B, dict(base, customer="Header Probe"), "k5-h", headers=hdrs)
        need(r.status == 201 and r.js["tenant"] == "marlow", "tenant headers: %r" % r)
        hid = r.js["id"]
        r = s.req("GET", "/api/v1/invoices/" + hid, s.k("kestrel"), headers={"X-Tenant-Id": "marlow"})
        need(r.status == 404, "header-switched read: %r" % r)
        r = s.req("GET", "/api/v1/invoices?tenant=kestrel", B)
        need(r.status == 422 or (r.status == 200 and all(x["tenant"] == "marlow" for x in r.js["data"])), "list ?tenant=: %r" % r)
        r = s.req("GET", "/api/v1/invoices/%s?tenant=kestrel" % ia, B)
        need(r.status == 404, "get ?tenant=: %r" % r)
        r = s.req("POST", "/api/v1/invoices?tenant=kestrel", B, dict(base, customer="Query Probe"), "k5-q")
        need(r.status == 422 or (r.status == 201 and r.js["tenant"] == "marlow"), "create ?tenant=: %r" % r)
        need(s.get("kestrel", ia).js == before, "kestrel invoice changed")
        need([x["id"] for x in s.all("kestrel")] == [ia], "kestrel list %r" % s.all("kestrel"))
        stopped_check(s)
        return "cross-tenant pay/void = missing id; 4 tenant fields 422 tenant_is_server_derived, 5 variants 422; tenant headers and ?tenant ignored or refused; victim unchanged"
    finally:
        s.close()


def k6_key_scope(ctx):
    s = Server(ctx).start()
    try:
        body = {"customer": "Shared Key Co", "amount_cents": 800, "currency": "USD"}
        a = s.req("POST", "/api/v1/invoices", s.k("kestrel"), body, "shared-key-1")
        b = s.req("POST", "/api/v1/invoices", s.k("marlow"), body, "shared-key-1")
        need(a.status == 201 and b.status == 201 and a.js["id"] != b.js["id"], "same key in two tenants: %r %r" % (a, b))
        need(a.js["tenant"] == "kestrel" and b.js["tenant"] == "marlow", "tenants %r %r" % (a.js, b.js))
        need(a.h.get("idempotent-replayed") == "false" and b.h.get("idempotent-replayed") == "false", "second tenant got a replay")
        r = s.req("POST", "/api/v1/invoices", s.k("kestrel"), dict(body, amount_cents=801), "shared-key-1")
        need(r.status == 422 and r.code == "idempotency_key_reused", "reuse with another body: %r" % r)
        r = s.req("POST", "/api/v1/invoices/%s/payments" % a.js["id"], s.k("kestrel"), {"amount_cents": 1}, "shared-key-1")
        need(r.status == 422 and r.code == "idempotency_key_reused", "create key reused for a payment: %r" % r)
        r = s.req("POST", "/api/v1/invoices", s.k("kestrel", "ed2"), body, "shared-key-1")
        need(r.status == 201 and r.js["id"] == a.js["id"], "second editor, same tenant, same request: %r" % r)
        r = s.req("POST", "/api/v1/invoices", s.k("marlow"), body, "shared-key-1")
        need(r.status == 201 and r.js["id"] == b.js["id"], "marlow replay: %r" % r)
        p1 = s.pay("kestrel", a.js["id"], 100, "pk-1")
        p2 = s.req("POST", "/api/v1/invoices/%s/payments" % b.js["id"], s.k("marlow"), {"amount_cents": 100}, "pk-1")
        need(p1.status == 201 and p2.status == 201 and p2.h.get("idempotent-replayed") == "false", "payment key in two tenants %r %r" % (p1, p2))
        r = s.req("POST", "/api/v1/invoices/%s/payments" % a.js["id"], s.k("kestrel"), {"amount_cents": 100}, "pk-1")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "true", "payment replay %r" % r)
        a2 = s.create("kestrel", "Second Invoice", 800, "k6-second").js["id"]
        r = s.req("POST", "/api/v1/invoices/%s/payments" % a2, s.k("kestrel"), {"amount_cents": 100}, "pk-1")
        need(r.status == 422 and r.code == "idempotency_key_reused", "payment key reused on another invoice, same body: %r" % r)
        need(s.get("kestrel", a2).js["paid_cents"] == 0, "second invoice changed by a reused key")
        need(s.get("kestrel", a.js["id"]).js["paid_cents"] == 100 and len(s.all("kestrel")) == 2, "kestrel state")
        stopped_check(s)
        return "keys scoped per tenant; reuse with another body, endpoint or invoice 422 reused; same tenant other editor replays; no cross-tenant replay"
    finally:
        s.close()


def k7_auth(ctx):
    s = Server(ctx).start()
    try:
        body = {"customer": "Auth Probe", "amount_cents": 300, "currency": "EUR"}
        A = s.k("tarn-4")
        for k, hdr in ((None, None), ("not-a-key-" + "x" * 20, None), (None, {"Authorization": "Basic " + A}),
                       (A[:-1], None), (A + "x", None), (None, {"Authorization": "Bearer"}), (A + " " + A, None)):
            r = s.req("POST", "/api/v1/invoices", k, body, "k7-a", headers=hdr)
            need(r.status == 401 and r.code == "unauthenticated", "bad credential %r: %r" % ((k or hdr), r))
        r = s.req("GET", "/api/v1/invoices", None)
        need(r.status == 401 and r.code == "unauthenticated", "anonymous list %r" % r)
        V = s.k("tarn-4", "vw")
        r = s.req("POST", "/api/v1/invoices", V, body, "k7-v")
        need(r.status == 403 and r.code == "forbidden", "viewer create %r" % r)
        iid = s.create("tarn-4", "Real One", 1000, "k7-real").js["id"]
        for path, b in (("/payments", {"amount_cents": 1}), ("/void", {})):
            r = s.req("POST", "/api/v1/invoices/%s%s" % (iid, path), V, b, "k7-v2")
            need(r.status == 403 and r.code == "forbidden", "viewer %s %r" % (path, r))
        need(s.req("GET", "/api/v1/invoices/" + iid, V).status == 200, "viewer read")
        need(len(s.all("tarn-4")) == 1 and s.get("tarn-4", iid).js["paid_cents"] == 0, "rejected requests changed state")
        r = s.req("POST", "/api/v1/invoices", A, body, "k7-a")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "false", "key after a 401: %r" % r)
        r = s.req("POST", "/api/v1/invoices", A, dict(body, customer="After 403"), "k7-v")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "false", "key after a 403: %r" % r)
        r = s.req("POST", "/api/v1/invoices", A, dict(body, amount_cents="12"), "k7-bad")
        need(r.status == 422 and r.code == "invalid_amount", "string amount %r" % r)
        r = s.req("POST", "/api/v1/invoices", A, dict(body, customer="After 422"), "k7-bad")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "false", "key after a 422: %r" % r)
        r = s.req("POST", "/api/v1/invoices/%s/payments" % rand_id(), A, {"amount_cents": 5}, "k7-404")
        need(r.status == 404, "pay missing %r" % r)
        r = s.req("POST", "/api/v1/invoices/%s/payments" % iid, A, {"amount_cents": 5}, "k7-404")
        need(r.status == 201 and r.js["paid_cents"] == 5, "key after a 404: %r" % r)
        stopped_check(s)
        return "7 bad credentials 401, viewer writes 403, nothing changed; keys stay usable after 401/403/422/404"
    finally:
        s.close()


def k8_crash_recovery(ctx):
    s = Server(ctx)
    try:
        T = "kestrel"
        s.start(fault={"fail_before_commit": {"k8-fb": 2}, "crash_before_commit": ["k8-cb"]})
        b_fb = {"customer": "FB Ltd", "amount_cents": 100, "currency": "USD"}
        A = s.k(T)
        st = [s.req("POST", "/api/v1/invoices", A, b_fb, "k8-fb") for _ in range(4)]
        need([r.status for r in st] == [503, 503, 201, 201], "fail_before_commit x2: %s" % [r.status for r in st])
        need(st[0].code == "transient_failure" and st[2].h.get("idempotent-replayed") == "false"
             and st[3].h.get("idempotent-replayed") == "true" and st[2].js == st[3].js, "transient answers %r" % st)
        cbb = {"customer": "CB Ltd", "amount_cents": 200, "currency": "USD"}
        r = s.req("POST", "/api/v1/invoices", A, cbb, "k8-cb")
        need(r.status == 0, "crash_before_commit answered %r" % r)
        need(s.wait_exit() == 70, "crash exit code %r" % s.proc.returncode)
        s.start()
        need([x["customer"] for x in s.all(T)] == ["FB Ltd"], "after a crash before commit %r" % s.all(T))
        r = s.req("POST", "/api/v1/invoices", A, cbb, "k8-cb")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "false", "retry after crash before commit %r" % r)
        cb = r.js["id"]
        s.stop()
        cab = {"customer": "CA Ltd", "amount_cents": 900, "currency": "GBP"}
        s.start(fault={"crash_after_commit": ["k8-ca"]})
        r = s.req("POST", "/api/v1/invoices", A, cab, "k8-ca")
        need(r.status == 0 and s.wait_exit() == 70, "crash_after_commit: %r exit %r" % (r, s.proc.returncode))
        rc, out = s.check()
        need(rc == 0 and "consistent" in out.lower(), "check right after the crash (server down): rc=%s %s" % (rc, out.strip()[:200]))
        s.start()
        ca = [x for x in s.all(T) if x["customer"] == "CA Ltd"]
        need(len(ca) == 1, "committed before the crash: %d copies" % len(ca))
        r = s.req("POST", "/api/v1/invoices", A, cab, "k8-ca")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "true" and r.js["id"] == ca[0]["id"], "retry after crash after commit %r" % r)
        s.stop()
        cid = ca[0]["id"]
        plan = {"crash_before_commit": ["k8-cbp"], "crash_after_commit": ["k8-cap"]}
        s.start(fault=plan)
        r = s.req("POST", "/api/v1/invoices/%s/payments" % cid, A, {"amount_cents": 100}, "k8-cbp")
        need(r.status == 0 and s.wait_exit() == 70, "pay crash before commit %r" % r)
        s.start()
        need(s.get(T, cid).js["paid_cents"] == 0, "payment survived a crash before commit")
        r = s.pay(T, cid, 100, "k8-cbp")
        need(r.status == 201 and r.js["paid_cents"] == 100 and r.h.get("idempotent-replayed") == "false", "pay retry %r" % r)
        s.stop()
        s.start(fault=plan)
        r = s.req("POST", "/api/v1/invoices/%s/payments" % cid, A, {"amount_cents": 200}, "k8-cap")
        need(r.status == 0 and s.wait_exit() == 70, "pay crash after commit %r" % r)
        s.start()
        r = s.pay(T, cid, 200, "k8-cap")
        need(r.status == 201 and r.h.get("idempotent-replayed") == "true" and r.js["paid_cents"] == 300, "pay replay after crash %r" % r)
        need(s.get(T, cid).js["paid_cents"] == 300, "payment applied twice or lost: %r" % s.get(T, cid).js)
        n = 64
        keys = ["k8-kill-%02d" % i for i in range(n)]
        out = [None] * n

        def bodyi(i):
            return {"customer": "Kill %02d" % i, "amount_cents": 10 + i, "currency": "USD"}

        def go(i):
            out[i] = s.req("POST", "/api/v1/invoices", s.k("marlow"), bodyi(i), keys[i])
        ths = [threading.Thread(target=go, args=(i,)) for i in range(n)]
        for t in ths:
            t.start()
        time.sleep(0.12)
        s.kill9()
        for t in ths:
            t.join()
        answered = sum(1 for r in out if r and r.status == 201)
        rc, txt = s.check()
        need(rc == 0, "check after SIGKILL mid-burst: rc=%s %s" % (rc, txt.strip()[:200]))
        s.start()
        ids = {}
        for i in range(n):
            r = s.until("POST", "/api/v1/invoices", s.k("marlow"), bodyi(i), keys[i])
            need(r.status == 201, "retry %s %r" % (keys[i], r))
            if out[i] and out[i].status == 201:
                need(out[i].js["id"] == r.js["id"], "%s answered %s before the kill, %s after" % (keys[i], out[i].js["id"], r.js["id"]))
            ids[keys[i]] = r.js["id"]
        lst = s.all("marlow")
        need(len(lst) == n and len(set(ids.values())) == n and sorted(x["id"] for x in lst) == sorted(ids.values()),
             "after kill -9 and retries: %d invoices for %d keys" % (len(lst), n))
        need(len(s.all(T)) == 3 and s.get(T, cb).status == 200, "kestrel state after drills")
        stopped_check(s)
        return ("fail x2 then one effect; crash before commit: no effect, retry makes it once; crash after commit: committed, "
                "retry replays; same for payments; exit 70; kill -9 mid-burst of 64 (%d answered) then retries: exactly 64" % answered)
    finally:
        s.close()


def _sqlite_copy(db, dst):
    for suf in ("", "-wal", "-shm"):
        if os.path.exists(db + suf):
            shutil.copyfile(db + suf, dst + suf)


def _sha_files(d):
    return {f: hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest() for f in os.listdir(d) if f.startswith("ledger.db")}


def k9_check_command(ctx):
    s = Server(ctx).start()
    try:
        iid = s.create("quillon", "Check Me", 1000, "k9-c").js["id"]
        s.pay("quillon", iid, 300, "k9-p")
        v = s.create("quillon", "Void Me", 10, "k9-v").js["id"]
        s.void("quillon", v, "k9-vv")
        s.stop()
        before = _sha_files(s.dir)
        rc, out = s.check()
        need(rc == 0 and "consistent" in out.lower(), "clean check rc=%s %s" % (rc, out[:200]))
        need(before.get("ledger.db") == _sha_files(s.dir).get("ledger.db"), "check changed the database file")
        t1 = os.path.join(s.dir, "tamper1.db")
        _sqlite_copy(s.db, t1)
        con = sqlite3.connect(t1)
        con.execute("UPDATE invoices SET paid_cents = paid_cents + 1 WHERE id = ?", (iid,))
        con.commit()
        con.close()
        rc, out = s.check(db=t1)
        need(rc == 1 and iid in out, "paid_cents tamper: rc=%s %s" % (rc, out[:300]))
        t2 = os.path.join(s.dir, "tamper2.db")
        _sqlite_copy(s.db, t2)
        con = sqlite3.connect(t2)
        keep = [r[1] for r in con.execute("PRAGMA table_info(audit)") if r[1] != "seq"]
        con.execute("INSERT INTO audit (%s) SELECT %s FROM audit WHERE rowid = (SELECT max(rowid) FROM audit)" % (",".join(keep), ",".join(keep)))
        con.commit()
        con.close()
        rc, out = s.check(db=t2)
        need(rc == 1, "duplicated audit row: rc=%s %s" % (rc, out[:300]))
        junk = os.path.join(s.dir, "junk.db")
        with open(junk, "wb") as f:
            f.write(b"this is not a database\n" * 50)
        rc, out = s.check(db=junk)
        need(rc == 2, "garbage file: rc=%s" % rc)
        rc, out = s.check(db=os.path.join(s.dir, "missing.db"))
        need(rc == 2 and not os.path.exists(os.path.join(s.dir, "missing.db")), "missing file: rc=%s" % rc)
        return "clean consistent and read-only; paid_cents tamper names the invoice (exit 1); duplicated audit row exit 1; garbage and missing exit 2"
    finally:
        s.close()


def k10_invalid_input(ctx):
    s = Server(ctx)
    try:
        for host in ("0.0.0.0", "10.1.2.3", "example.invalid", "::"):
            rf = os.path.join(s.dir, "ready-host.json")
            p = subprocess.run(list(ctx.cmd) + ["serve", "--db", os.path.join(s.dir, "h.db"), "--principals", s.pf, "--host", host,
                                                "--port", "0", "--ready-file", rf], capture_output=True, timeout=15)
            need(p.returncode == 2 and not os.path.exists(rf), "--host %s: rc=%s ready=%s" % (host, p.returncode, os.path.exists(rf)))
        bad = {"wrong-schema.json": {"schema": "x", "principals": []},
               "dup-key.json": {"schema": "solaris.ledger-principals/1", "principals": [
                   {"key": "dup-dup-dup-dup-0001", "tenant": "a", "user": "u", "role": "editor"},
                   {"key": "dup-dup-dup-dup-0001", "tenant": "b", "user": "v", "role": "editor"}]},
               "bad-role.json": {"schema": "solaris.ledger-principals/1", "principals": [
                   {"key": "role-role-role-0001", "tenant": "a", "user": "u", "role": "admin"}]}}
        for name, doc in list(bad.items()) + [("missing.json", None)]:
            pf = os.path.join(s.dir, name)
            if doc is not None:
                with open(pf, "w") as f:
                    json.dump(doc, f)
            rf = os.path.join(s.dir, "ready-p.json")
            p = subprocess.run(list(ctx.cmd) + ["serve", "--db", os.path.join(s.dir, "p.db"), "--principals", pf, "--port", "0", "--ready-file", rf],
                               capture_output=True, timeout=15)
            need(p.returncode == 2 and not os.path.exists(rf), "principals %s: rc=%s" % (name, p.returncode))
        s.start()
        A = s.k("marlow")
        iid = s.create("marlow", "Baseline", 1000, "k10-base").js["id"]
        good = {"customer": "Valid", "amount_cents": 100, "currency": "USD"}
        P = "/api/v1/invoices"
        cases = [
            ("POST", P, None, b"{not json", "k10-1", 400, "invalid_json"),
            ("POST", P, None, b'{"customer":"a","customer":"b","amount_cents":1,"currency":"USD"}', "k10-2", 400, "invalid_json"),
            ("POST", P, None, b"[1,2]", "k10-3", 400, "invalid_json"),
            ("POST", P, None, b"\xff\xfe", "k10-3b", 400, "invalid_json"),
            ("POST", P, good, None, None, 400, "idempotency_key_required"),
            ("POST", P, good, None, "has space", 400, "invalid_idempotency_key"),
            ("POST", P, good, None, "k" * 129, 400, "invalid_idempotency_key"),
            ("POST", P, good, None, "", 400, "invalid_idempotency_key"),
            ("POST", P, dict(good, amount_cents=True), None, "k10-4", 422, "invalid_amount"),
            ("POST", P, dict(good, amount_cents=1.5), None, "k10-5", 422, "invalid_amount"),
            ("POST", P, dict(good, amount_cents=100.0), None, "k10-5b", 422, "invalid_amount"),
            ("POST", P, dict(good, amount_cents=0), None, "k10-6", 422, "invalid_amount"),
            ("POST", P, dict(good, amount_cents=-5), None, "k10-6b", 422, "invalid_amount"),
            ("POST", P, dict(good, amount_cents=10 ** 12 + 1), None, "k10-7", 422, "invalid_amount"),
            ("POST", P, dict(good, currency="JPY"), None, "k10-8", 422, "invalid_currency"),
            ("POST", P, dict(good, customer=""), None, "k10-9", 422, "invalid_customer"),
            ("POST", P, dict(good, customer="c" * 81), None, "k10-10", 422, "invalid_customer"),
            ("POST", P, dict(good, note="x"), None, "k10-11", 422, "unknown_field"),
            ("POST", P, None, json.dumps(dict(good, pad="p" * 17000)).encode(), "k10-12", 413, "body_too_large"),
            ("POST", P + "/%s/payments" % iid, {"amount_cents": "5"}, None, "k10-13", 422, "invalid_amount"),
            ("POST", P + "/%s/void" % iid, {"reason": "r" * 201}, None, "k10-14", 422, "invalid_reason"),
            ("GET", "/api/v1/nothing", None, None, None, 404, "no_route"),
            ("PUT", P, good, None, "k10-15", 405, "method_not_allowed"),
            ("DELETE", P + "/" + iid, None, None, None, 405, "method_not_allowed"),
            ("GET", P + "?limit=0", None, None, None, 422, "invalid_limit"),
            ("GET", P + "?limit=101", None, None, None, 422, "invalid_limit"),
            ("GET", P + "?limit=abc", None, None, None, 422, "invalid_limit"),
            ("GET", P + "?limit=-1", None, None, None, 422, "invalid_limit"),
        ]
        for m, path, body, raw, idem, st, code in cases:
            r = s.req(m, path, A, body, idem, raw=raw)
            need(r.status == st and r.code == code and err_shape_ok(r), "%s %s %s: %r" % (m, path[:40], str(raw or body)[:60], r))
        g = s.get("marlow", iid).js
        need([x["id"] for x in s.all("marlow")] == [iid] and g["paid_cents"] == 0 and g["status"] == "open", "invalid requests changed state")
        stopped_check(s)
        return "4 non-loopback hosts and 4 bad principals exit 2 with no ready file; %d invalid requests exact status/code/shape, nothing made" % len(cases)
    finally:
        s.close()


def k11_enumeration(ctx):
    s = Server(ctx).start()
    try:
        ids = [s.create("kestrel", "Enum %02d" % i, 100 + i, "k11-%02d" % i).js["id"] for i in range(40)]
        need(len(set(ids)) == 40 and all(ID_RE.match(i) for i in ids), "ids not unique or malformed")
        asc = sum(1 for a, b in zip(ids, ids[1:]) if a < b)
        need(asc < 34 and len({i[:10] for i in ids}) > 20, "ids look sequential (%d/39 ascending)" % asc)
        B = s.k("marlow")
        refs = [s.req("GET", "/api/v1/invoices/" + rand_id(), B) for _ in range(5)]
        need(len({r.body for r in refs}) == 1 and refs[0].status == 404, "random-id 404s differ")
        hk = sorted(k for k in refs[0].h if k != "date")
        for iid in ids[:12]:
            for k in (B, s.k("marlow", "vw"), s.k("tarn-4")):
                r = s.req("GET", "/api/v1/invoices/" + iid, k)
                need(r.status == 404 and r.body == refs[0].body and sorted(x for x in r.h if x != "date") == hk
                     and all(r.h[x] == refs[0].h[x] for x in hk), "existence leak on %s: %r %r" % (iid, r, r.h))
        w1 = s.req("POST", "/api/v1/invoices/%s/payments" % ids[0], B, {"amount_cents": 1}, "k11-w1")
        w2 = s.req("POST", "/api/v1/invoices/%s/payments" % rand_id(), B, {"amount_cents": 1}, "k11-w2")
        v1 = s.req("POST", "/api/v1/invoices/%s/void" % ids[1], B, {}, "k11-v1")
        v2 = s.req("POST", "/api/v1/invoices/%s/void" % rand_id(), B, {}, "k11-v2")
        need(w1.status == w2.status == 404 and w1.body == w2.body and v1.body == v2.body and v1.status == 404,
             "write-path existence leak %r %r %r %r" % (w1, w2, v1, v2))
        stopped_check(s)
        return "40 ids random (%d/39 ascending); other tenants' ids answer byte-identical to random ids (status, body, headers) on read, pay and void" % asc
    finally:
        s.close()


def k12_seeded_load(ctx):
    notes = []
    for seed in ctx.seeds:
        r = random.Random(seed)
        s = Server(ctx, seed=seed).start()
        try:
            per = max(8, ctx.scale // 40)
            model, ops = {}, []
            for t in TENANTS:
                for i in range(per):
                    key = "L%d-%s-c%03d" % (seed, t, i)
                    body = {"customer": "%s cust %03d %x" % (t, i, r.getrandbits(16)), "amount_cents": r.randint(500, 5000),
                            "currency": r.choice(("EUR", "GBP", "USD"))}
                    model[(t, key)] = dict(body, paid=0, status="open")
                    ops += [(t, key, body, r.choice(("ed1", "ed2")))] * r.randint(1, 4)
            r.shuffle(ops)
            res, lk = {}, threading.Lock()

            def do_create(op):
                t, key, body, user = op
                x = s.until("POST", "/api/v1/invoices", s.k(t, user), body, key)
                with lk:
                    res.setdefault((t, key), set()).add((x.status, x.js.get("id") if isinstance(x.js, dict) else None))
            with ThreadPoolExecutor(16) as ex:
                list(ex.map(do_create, ops))
            bad = {k: v for k, v in res.items() if len(v) != 1 or next(iter(v))[0] != 201}
            need(not bad, "seed %d: keys with mixed answers %s" % (seed, list(bad.items())[:3]))
            ids = {k: next(iter(v))[1] for k, v in res.items()}
            ops2 = []
            for (t, key), m in model.items():
                if r.random() < 0.2:
                    m["status"] = "void"
                    ops2 += [("void", t, ids[(t, key)], key + "-void", None)] * r.randint(1, 3)
                else:
                    for j in range(r.randint(0, 3)):
                        amt = m["amount_cents"] // 4
                        m["paid"] += amt
                        ops2 += [("pay", t, ids[(t, key)], "%s-p%d" % (key, j), amt)] * r.randint(1, 3)
            r.shuffle(ops2)
            res2 = {}

            def do_write(op):
                kind, t, iid, key, amt = op
                x = s.pay(t, iid, amt, key) if kind == "pay" else s.void(t, iid, key)
                with lk:
                    res2.setdefault((t, key), set()).add(x.status)
            with ThreadPoolExecutor(16) as ex:
                list(ex.map(do_write, ops2))
            odd = [v for v in res2.values() if v not in ({201}, {200})]
            need(not odd, "seed %d: write answers %s" % (seed, odd[:3]))
            for t in TENANTS:
                got = {x["id"]: x for x in s.all(t)}
                want = {ids[(tt, k)]: m for (tt, k), m in model.items() if tt == t}
                need(set(got) == set(want), "seed %d %s: %d listed, %d expected" % (seed, t, len(got), len(want)))
                for iid, m in want.items():
                    g = got[iid]
                    need(g["tenant"] == t and g["customer"] == m["customer"] and g["paid_cents"] == m["paid"] and g["status"] == m["status"],
                         "seed %d %s: %r vs model %r" % (seed, iid, g, m))
            stopped_check(s)
            notes.append("seed %d: %d+%d requests" % (seed, len(ops), len(ops2)))
        finally:
            s.close()
    return "shuffled duplicate-laden load over 4 tenants, 16 threads, matches the model; " + ", ".join(notes)


CORE = [k1_clean_control, k2_concurrent_replays, k3_overspend_race, k4_cross_tenant_reads, k5_cross_tenant_writes,
        k6_key_scope, k7_auth, k8_crash_recovery, k9_check_command, k10_invalid_input, k11_enumeration, k12_seeded_load]


# ------------------------------------------------------------------ adversarial checks (findings only)

def _alive(s):
    return s.req("GET", "/api/v1/health").status == 200


def _line(b):
    return b.split(b"\r\n", 1)[0].decode("latin-1") or "<no response>"


def x1_unicode_digit_limit(ctx):
    s = Server(ctx).start()
    try:
        out = []
        for lim in ("%C2%B2", "%D9%A3", "%EF%BC%95"):
            r = s.req("GET", "/api/v1/invoices?limit=" + lim, s.k("kestrel"))
            out.append((lim, r.status, r.code or r.err[:40]))
        ok = all(st in (200, 422) for _, st, _ in out) and _alive(s)
        return ok, "(a finding only if a request gets no answer) limit = superscript two / Arabic-Indic three / fullwidth five: %s" % out
    finally:
        s.close()


def x2_unicode_content_length(ctx):
    s = Server(ctx).start()
    try:
        out = []
        for cl in (b"\xb2", "\u0663".encode("utf-8")):
            raw = (b"POST /api/v1/invoices HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + s.k("kestrel").encode()
                   + b"\r\nIdempotency-Key: x2\r\nContent-Length: " + cl + b"\r\nConnection: close\r\n\r\n{}")
            out.append(_line(s.raw(raw)))
        ok = all(o.startswith("HTTP/1.1 4") for o in out) and _alive(s)
        return ok, "Content-Length superscript two / Arabic-Indic three: %s" % out
    finally:
        s.close()


def x3_deep_json(ctx):
    s = Server(ctx).start()
    try:
        r = s.req("POST", "/api/v1/invoices", s.k("kestrel"), None, "x3", raw=b"[" * 8000 + b"]" * 8000)
        r2 = s.req("POST", "/api/v1/invoices", s.k("kestrel"), None, "x3b", raw=b'{"a":' * 2500 + b"1" + b"}" * 2500)
        alive = _alive(s)
        ok = all(400 <= x.status < 500 and err_shape_ok(x) for x in (r, r2)) and alive
        return ok, "8000-deep array: %r; 2500-deep object (under 16 KiB): %r; server alive after: %s" % (r, r2, alive)
    finally:
        s.close()


def x4_other_methods(ctx):
    s = Server(ctx).start()
    try:
        out = []
        for m in ("HEAD", "OPTIONS", "TRACE", "BREW"):
            got = s.raw(("%s /api/v1/invoices HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer %s\r\nConnection: close\r\n\r\n" % (m, s.k("kestrel"))).encode())
            head, _, body = got.partition(b"\r\n\r\n")
            out.append((m, _line(head), body[:70]))
        ok = all((not b or b.startswith(b"{")) and not LEAK_RE.search(b) for _, _, b in out if True)
        return ok, "unsupported methods (doc: errors always use {error:{code,message}}): %s" % out
    finally:
        s.close()


def x5_malformed_request(ctx):
    s = Server(ctx).start()
    try:
        out = []
        for raw in (b"GARBAGE\r\n\r\n", b"GET /api/v1/invoices HTTP/9.9\r\n\r\n", b"GET /" + b"a" * 70000 + b" HTTP/1.1\r\n\r\n"):
            head, _, body = s.raw(raw).partition(b"\r\n\r\n")
            out.append((_line(head)[:40], body[:60]))
        ok = all(not b or b.startswith(b"{") for _, b in out) and _alive(s)
        return ok, "malformed requests: %s" % out
    finally:
        s.close()


def x6_double_authorization(ctx):
    s = Server(ctx).start()
    try:
        A, B = s.k("kestrel"), s.k("marlow")
        ia = s.create("kestrel", "Double Auth", 100, "x6-a").js["id"]
        got = s.raw(("GET /api/v1/invoices/%s HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer %s\r\nAuthorization: Bearer %s\r\n"
                     "Connection: close\r\n\r\n" % (ia, B, A)).encode())
        body = b'{"customer": "DA", "amount_cents": 1, "currency": "USD"}'
        got2 = s.raw(("POST /api/v1/invoices HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer %s\r\nAuthorization: Bearer %s\r\n"
                      "Idempotency-Key: x6-b\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (B, A, len(body))).encode() + body)
        m = re.search(rb'"tenant": ?"([a-z0-9-]+)"', got2)
        ok = not _line(got).startswith("HTTP/1.1 200") and not _line(got2).startswith("HTTP/1.1 201")
        return ok, "two Authorization headers (marlow first, kestrel second): GET kestrel invoice -> %s; create -> %s tenant=%s" % (
            _line(got), _line(got2), m.group(1).decode() if m else None)
    finally:
        s.close()


def x7_double_idempotency_key(ctx):
    s = Server(ctx).start()
    try:
        A = s.k("kestrel").encode()
        body = b'{"customer": "DK", "amount_cents": 7, "currency": "USD"}'

        def send(k1, k2):
            hdr = b"Idempotency-Key: " + k1 + b"\r\n" + ((b"Idempotency-Key: " + k2 + b"\r\n") if k2 else b"")
            return s.raw(b"POST /api/v1/invoices HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + A + b"\r\n" + hdr
                         + b"Content-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
        a = _line(send(b"x7-one", b"x7-two"))
        n = len([x for x in s.all("kestrel") if x["customer"] == "DK"])
        b = _line(send(b"x7-two", None))
        n2 = len([x for x in s.all("kestrel") if x["customer"] == "DK"])
        ok = not a.startswith("HTTP/1.1 201")
        return ok, "two different Idempotency-Key headers -> %s (invoices %d); then x7-two alone -> %s (invoices %d)" % (a, n, b, n2)
    finally:
        s.close()


def x8_scheme_case(ctx):
    s = Server(ctx).start()
    try:
        out = [(sch, s.req("GET", "/api/v1/invoices", None, headers={"Authorization": sch + " " + s.k("kestrel")}).status)
               for sch in ("bearer", "BEARER")]
        return True, "auth scheme case (observation; RFC 7235 says case-insensitive, the doc says 'Bearer'): %s" % out
    finally:
        s.close()


def x9_path_confusion(ctx):
    s = Server(ctx).start()
    try:
        ia = s.create("kestrel", "Path Probe", 100, "x9-a").js["id"]
        B = s.k("marlow")
        out, leak = [], False
        for p in ("/api/v1/invoices/%s/" % ia, "/api/v1//invoices/%s" % ia, "/api/v1/invoices/%s" % ia.upper(),
                  "/api/v1/invoices/%%69nv_%s" % ia[4:], "/api/v1/invoices/../invoices/%s" % ia, "/api/v1/invoices/%s;tenant=kestrel" % ia,
                  "/API/V1/invoices/%s" % ia, "/api/v1/invoices/%s%%00" % ia, "/api/v1/invoices/%s?tenant=kestrel&tenant=marlow" % ia):
            r = s.req("GET", p, B)
            leak |= r.status == 200
            out.append((p.replace(ia, "<id>").replace(ia[4:], "<hex>")[:46], r.status, r.code))
        got = s.raw(("GET http://other.invalid/api/v1/invoices/%s HTTP/1.1\r\nHost: other.invalid\r\nAuthorization: Bearer %s\r\n"
                     "Connection: close\r\n\r\n" % (ia, B)).encode())
        leak |= _line(got).startswith("HTTP/1.1 200")
        out.append(("absolute-form http://other.invalid/...", _line(got)))
        ok = not leak and _alive(s)
        return ok, "other tenant, path variants: %s" % out
    finally:
        s.close()


def _tamper(ctx, sql_fn, label):
    s = Server(ctx).start()
    try:
        iid = s.create("quillon", "Tamper Base", 1000, "xt-c").js["id"]
        s.pay("quillon", iid, 400, "xt-p")
        other = s.create("quillon", "Tamper Other", 50, "xt-o").js["id"]
        s.stop()
        t = os.path.join(s.dir, "t.db")
        _sqlite_copy(s.db, t)
        con = sqlite3.connect(t)
        sql_fn(con, iid, other)
        con.commit()
        con.close()
        rc, out = s.check(db=t)
        return rc == 1, "%s: check rc=%s %s" % (label, rc, out.strip().replace("\n", " | ")[:220])
    finally:
        s.close()


def x10_check_orphan_invoice(ctx):
    def f(con, iid, other):
        cols = [r[1] for r in con.execute("PRAGMA table_info(invoices)") if r[1] != "seq"]
        sel = ",".join("'inv_00000000deadbeef'" if c == "id" else c for c in cols)
        con.execute("INSERT INTO invoices (%s) SELECT %s FROM invoices WHERE id = ?" % (",".join(cols), sel), (other,))
    return _tamper(ctx, f, "an invoice row with no idempotency record and no audit row (an unrecorded second effect)")


def x11_check_deleted_invoice(ctx):
    return _tamper(ctx, lambda con, iid, other: con.execute("DELETE FROM invoices WHERE id = ?", (other,)),
                   "a created invoice deleted (its idempotency record and audit row remain)")


def x12_check_orphan_payment(ctx):
    def f(con, iid, other):
        cols = [r[1] for r in con.execute("PRAGMA table_info(payments)") if r[1] != "seq"]
        con.execute("INSERT INTO payments (%s) SELECT %s FROM payments WHERE invoice_id = ?" % (",".join(cols), ",".join(cols)), (iid,))
        con.execute("UPDATE invoices SET paid_cents = paid_cents + 400 WHERE id = ?", (iid,))
    return _tamper(ctx, f, "a duplicated payment row with paid_cents raised to match (a double charge without its own key)")


def x13_slow_clients(ctx):
    s = Server(ctx).start()
    try:
        socks = []
        for i in range(40):
            c = socket.create_connection(("127.0.0.1", s.port), timeout=5)
            c.sendall(b"POST /api/v1/invoices HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + s.k("kestrel").encode()
                      + b"\r\nIdempotency-Key: slow-%d\r\nContent-Length: 200\r\n\r\n{" % i)
            socks.append(c)
        t0 = time.time()
        r = s.create("marlow", "While Slow", 10, "x13-ok")
        dt = time.time() - t0
        time.sleep(20)
        held = 0
        for c in socks:
            c.setblocking(False)
            try:
                if c.recv(10) != b"":
                    pass
            except BlockingIOError:
                held += 1
            except OSError:
                pass
            c.close()
        ok = r.status == 201 and held == 0
        return ok, "40 clients sent 1 of 200 body bytes: a normal create took %.2fs (%s); after 20s %d/40 still held open (no read timeout)" % (dt, r.status, held)
    finally:
        s.close()


def x14_burst_over_backlog(ctx):
    s = Server(ctx).start()
    try:
        body = {"customer": "Big Burst", "amount_cents": 99, "currency": "USD"}
        first = burst(lambda i: s.req("POST", "/api/v1/invoices", s.k("tarn-4"), body, "x14"), 256)
        drops = sum(1 for r in first if r.status == 0)
        made = [x for x in s.all("tarn-4") if x["customer"] == "Big Burst"]
        ok = drops == 0 and len(made) == 1
        return ok, "256 simultaneous replays of one create: statuses %s, %d reset or refused; invoices made %d" % (
            sorted({r.status for r in first}), drops, len(made))
    finally:
        s.close()


def x15_ipv6_loopback(ctx):
    s = Server(ctx)
    try:
        rf = os.path.join(s.dir, "r6.json")
        p = subprocess.Popen(list(ctx.cmd) + ["serve", "--db", s.db, "--principals", s.pf, "--host", "::1", "--port", "0", "--ready-file", rf],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        t0 = time.time()
        while time.time() - t0 < 8 and p.poll() is None and not (os.path.exists(rf) and os.path.getsize(rf)):
            time.sleep(0.05)
        served = os.path.exists(rf) and os.path.getsize(rf) > 0
        if p.poll() is None:
            p.terminate()
            p.wait(5)
        err = p.stderr.read().decode(errors="replace").strip().splitlines()[-1:]
        return served, "--host ::1 (loopback, so allowed by the doc): served=%s rc=%s %s" % (served, p.returncode, err)
    finally:
        s.close()


def x16_probe_url_guard(ctx):
    if not ctx.probe:
        return True, "probe not given (skipped)"
    s = Server(ctx)
    out, ok = [], True
    for url in ("http://127.0.0.1" + "@" + "example.invalid:9/", "http://user@127.0.0.1:9/", "http://localhost.example.invalid:9/",
                "http://0.0.0.0:9/", "http://127.0.0.1.example.invalid:9/", "https://127.0.0.1:9/", "http://[::ffff:10.0.0.1]:9/",
                "http://2130706433:9/", "http://127.0.0.1:9/api?x=1", "http://example.invalid:9/"):
        p = subprocess.run(ctx.py + [ctx.probe, "--base-url", url, "--principals", s.pf], capture_output=True, text=True, timeout=30)
        out.append((url, p.returncode))
        ok &= p.returncode == 2
    s.close()
    return ok, "probe base URLs that are not plain loopback -> exit (2 = refused before sending): %s" % out


def x17_probe_teeth(ctx):
    if not ctx.probe:
        return True, "probe not given (skipped)"
    res = []
    for label, cmd in [("candidate", ctx.cmd)] + [(m, [os.path.join(ctx.stubdir, m + ".sh")]) for m in ("vulnerable", "racy", "naive", "noop")]:
        s = Server(Ctx(cmd, ctx.tmp, ctx.seed, ctx.scale, ctx.seeds))
        try:
            s.start()
            p = subprocess.run(ctx.py + [ctx.probe, "--base-url", "http://127.0.0.1:%d" % s.port, "--principals", s.pf],
                               capture_output=True, text=True, timeout=180)
            res.append((label, p.returncode))
        except Fail as e:
            res.append((label, "start failed: %s" % e))
        finally:
            s.close()
    want = {"candidate": 0, "vulnerable": 1, "racy": 1, "naive": 1}
    d = dict(res)
    ok = all(d.get(k) == v for k, v in want.items()) and d.get("noop") in (1, 3)
    return ok, "boundary_probe exit codes vs candidate and M19 stubs (0 none, 1 findings, 3 inconclusive): %s" % res


def x18_pay_void_race(ctx):
    s = Server(ctx).start()
    try:
        bad = []
        for rnd in range(5):
            iid = s.create("marlow", "Race %d" % rnd, 1000, "x18-c%d" % rnd).js["id"]
            rs = burst(lambda i: s.req("POST", "/api/v1/invoices/%s/%s" % (iid, "void" if i % 2 else "payments"), s.k("marlow"),
                                       {} if i % 2 else {"amount_cents": 100}, "x18-%d-%d" % (rnd, i)), 20)
            g = s.get("marlow", iid).js
            voids = sum(1 for i, r in enumerate(rs) if i % 2 and r.status == 200)
            pays = sum(1 for i, r in enumerate(rs) if not i % 2 and r.status == 201)
            if not ((g["status"] == "void" and g["paid_cents"] == 0 and pays == 0 and voids == 1)
                    or (g["status"] == ("paid" if pays == 10 else "open") and voids == 0 and g["paid_cents"] == 100 * pays)):
                bad.append((rnd, g["status"], g["paid_cents"], pays, voids))
        s.stop()
        rc, out = s.check()
        return not bad and rc == 0, "5 rounds of 10 payments racing 10 voids: inconsistent rounds %s; check rc=%s" % (bad, rc)
    finally:
        s.close()


def x19_two_processes_one_db(ctx):
    s1 = Server(ctx).start()
    s2 = Server(ctx)
    s2.db, s2.pf, s2.keys = s1.db, s1.pf, s1.keys
    try:
        s2.start()
        body = {"customer": "Two Procs", "amount_cents": 77, "currency": "USD"}
        rs = burst(lambda i: (s1 if i % 2 else s2).until("POST", "/api/v1/invoices", s1.k("kestrel"), body, "x19"), 32)
        ids = {r.js["id"] for r in rs if r.status == 201}
        made = [x for x in s1.all("kestrel") if x["customer"] == "Two Procs"]
        s1.stop(); s2.stop()
        rc, out = s1.check()
        ok = len(ids) == 1 and len(made) == 1 and rc == 0
        return ok, "two server processes on one db, 32 concurrent duplicates split across them: statuses %s, %d ids, %d invoices, check rc=%s" % (
            sorted({r.status for r in rs}), len(ids), len(made), rc)
    finally:
        s1.close(); s2.close()


ADV = [x1_unicode_digit_limit, x2_unicode_content_length, x3_deep_json, x4_other_methods, x5_malformed_request,
       x6_double_authorization, x7_double_idempotency_key, x8_scheme_case, x9_path_confusion, x10_check_orphan_invoice,
       x11_check_deleted_invoice, x12_check_orphan_payment, x13_slow_clients, x14_burst_over_backlog, x15_ipv6_loopback,
       x16_probe_url_guard, x17_probe_teeth, x18_pay_void_race, x19_two_processes_one_db]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--scale", type=int, default=600)
    ap.add_argument("--seeds", default="7,2026,31337")
    ap.add_argument("--seed", type=int, default=19)
    ap.add_argument("--tmp")
    ap.add_argument("--probe", help="path to boundary_probe.py for x16/x17")
    ap.add_argument("--core-only", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        ap.error("give the candidate command after --")
    tmp = tempfile.mkdtemp(prefix="m19-oracle-run-", dir=a.tmp)
    ctx = Ctx(cmd, tmp, a.seed, a.scale, [int(x) for x in a.seeds.split(",")])
    ctx.probe, ctx.py = a.probe, [sys.executable]
    ctx.stubdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs")
    only = set(a.only.split(",")) if a.only else None
    print("# m19_oracle candidate: %s" % " ".join(cmd), flush=True)
    core_pass = core_n = adv_ok = adv_n = 0
    for fn in CORE + ([] if a.core_only else ADV):
        tag = fn.__name__.split("_")[0]
        if only and tag not in only:
            continue
        t0 = time.time()
        try:
            if fn in CORE:
                core_n += 1
                msg = fn(ctx)
                core_pass += 1
                print("PASS %s (%.1fs): %s" % (fn.__name__, time.time() - t0, msg), flush=True)
            else:
                adv_n += 1
                ok, msg = fn(ctx)
                adv_ok += bool(ok)
                print("%s %s: %s" % ("OK" if ok else "FINDING", fn.__name__, msg), flush=True)
        except Fail as e:
            print("FAIL %s (%.1fs): %s" % (fn.__name__, time.time() - t0, e), flush=True)
        except Exception as e:
            print("FAIL %s (%.1fs): harness error %s: %s" % (fn.__name__, time.time() - t0, type(e).__name__, str(e)[:300]), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    verdict = "ACCEPTS" if core_pass == core_n else "REJECTS"
    print("SUMMARY core %d/%d pass; oracle %s candidate; adversarial %d/%d rejected the attack (%d findings)" % (
        core_pass, core_n, verdict, adv_ok, adv_n, adv_n - adv_ok), flush=True)
    return 0 if core_pass == core_n else 1


if __name__ == "__main__":
    sys.exit(main())
