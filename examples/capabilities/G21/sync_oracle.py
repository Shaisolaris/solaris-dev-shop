#!/usr/bin/env python3
"""G21 oracle: offline client sync against the real G19 ledger API, judged from the server's side.

It drives a sync tool only through its documented CLI (init, enqueue, sync, status --json, resolve,
apply-snapshot, check) and judges the result from the server: the invoices and payments the server
actually holds, `ledger_api.py check`, and an intent model the oracle keeps itself. It brings its own
synthetic principals (four keys, two tenants) and its own fault plans.

    sync_oracle.py [--tool PATH] [--seed N] [--quick]

Prints one PASS/FAIL line per check (13 checks) and a last line `PASSED n/m` or `REJECTED n/m`; exit 0 only if all pass.
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
API = ROOT / "employees" / "engineering" / "backend-developer" / "ledger_api.py"
DEFAULT_TOOL = ROOT / "employees" / "engineering" / "mobile-developer" / "offline_sync.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
KEYS = {"ed1": ("orc-acme-editor-71a2", "acme", "editor"), "ed2": ("orc-acme-editor2-5c3e", "acme", "editor"),
        "view": ("orc-acme-viewer-9b04", "acme", "viewer"), "other": ("orc-zenith-editor-33d8", "zenith", "editor")}


class Server:
    def __init__(self, tmp, db=None, plan=None):
        self.tmp, self.db = tmp, db or tmp / ("ledger-%d.db" % time.time_ns())
        self.start(plan)

    def start(self, plan=None):
        ready = self.tmp / ("ready-%d.json" % time.time_ns())
        cmd = [sys.executable, str(API), "serve", "--db", str(self.db), "--principals", str(self.tmp / "principals.json"),
               "--ready-file", str(ready)]
        if plan:
            pf = self.tmp / ("plan-%d.json" % time.time_ns())
            pf.write_text(json.dumps(dict(plan, schema="solaris.ledger-fault-plan/1")))
            cmd += ["--fault-plan", str(pf)]
        self.p = subprocess.Popen(cmd, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(300):
            if ready.exists() and ready.stat().st_size:
                self.url = "http://127.0.0.1:%d" % json.loads(ready.read_text())["port"]
                return
            time.sleep(0.02)
        raise RuntimeError("ledger server did not start")

    def restart(self, plan=None):
        self.stop()
        self.start(plan)

    def stop(self):
        if self.p.poll() is None:
            self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()

    def invoices(self, who="ed1"):
        out, after = [], None
        while True:
            q = "/api/v1/invoices?limit=100" + ("&after=" + after if after else "")
            req = urllib.request.Request(self.url + q, headers={"Authorization": "Bearer " + KEYS[who][0]})
            page = json.loads(urllib.request.urlopen(req, timeout=10).read())
            out += page["data"]
            after = page["next_after"]
            if not after:
                return out

    def post(self, path, body, idem, who="ed1"):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + KEYS[who][0], "Idempotency-Key": idem})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=10).read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read())

    def consistent(self):
        r = subprocess.run([sys.executable, str(API), "check", "--db", str(self.db)], env=ENV, capture_output=True, text=True)
        return r.returncode == 0


class Device:
    def __init__(self, tool, tmp, name, who="ed1"):
        self.tool, self.db, self.who = tool, tmp / ("%s-%d.db" % (name, time.time_ns())), who
        self.keyfile = tmp / ("key-%s-%s.txt" % (name, who))
        self.keyfile.write_text(KEYS[who][0] + "\n")
        r = self.run("init", "--db", self.db, "--device", name)
        if r.returncode != 0:
            raise AssertionError("init failed: %s" % r.stderr.strip()[:200])

    def run(self, *args, timeout=120):
        return subprocess.run([sys.executable, str(self.tool)] + [str(a) for a in args], env=ENV, capture_output=True,
                              text=True, timeout=timeout)

    def enq(self, kind, ref, **kw):
        args = ["enqueue", "--db", self.db, kind, "--ref", ref]
        for k, v in kw.items():
            args += ["--" + k, v]
        r = self.run(*args)
        if r.returncode != 0:
            raise AssertionError("enqueue %s %s failed: %s" % (kind, ref, r.stderr.strip()[:200]))

    def sync(self, srv, *extra):
        return self.run("sync", "--db", self.db, "--base-url", srv.url, "--key-file", self.keyfile, *extra).returncode

    def status(self):
        r = self.run("status", "--db", self.db, "--json")
        return json.loads(r.stdout)

    def check(self):
        return self.run("check", "--db", self.db).returncode == 0

    def ops(self):
        return self.status()["ops"]


def tagged(srv, tag, who="ed1"):
    return [i for i in srv.invoices(who) if i["customer"].startswith(tag)]


def standard_batch(dev, tag):
    dev.enq("create", "r1", customer=tag + "-one", amount="1000", currency="USD")
    dev.enq("create", "r2", customer=tag + "-two", amount="2500", currency="EUR")
    dev.enq("pay", "r1", amount="400")
    dev.enq("pay", "r1", amount="600")
    dev.enq("void", "r2")


def standard_ok(srv, tag):
    inv = {i["customer"]: i for i in tagged(srv, tag)}
    want = {tag + "-one": (1000, 1000, "paid"), tag + "-two": (2500, 0, "void")}
    got = {c: (i["amount_cents"], i["paid_cents"], i["status"]) for c, i in inv.items()}
    n = len(tagged(srv, tag))
    return (got == want and n == 2), "server holds %d invoices %s, want %s" % (n, got, want)


class Oracle:
    def __init__(self, tool, seed, quick):
        self.tool, self.seed, self.quick = Path(tool), seed, quick
        self.results = []
        self.tmp = Path(tempfile.mkdtemp(prefix="g21-oracle-"))
        (self.tmp / "principals.json").write_text(json.dumps({"schema": "solaris.ledger-principals/1", "principals": [
            {"key": k, "tenant": t, "user": n, "role": r} for n, (k, t, r) in KEYS.items()]}))
        self.servers = []

    def server(self, **kw):
        s = Server(self.tmp, **kw)
        self.servers.append(s)
        return s

    def record(self, name, ok, why):
        self.results.append(ok)
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else ": " + why))

    def check(self, name, fn):
        try:
            ok, why = fn()
        except Exception as e:  # a broken tool fails the check, it does not stop the oracle
            ok, why = False, "%s: %s" % (type(e).__name__, str(e)[:300])
        self.record(name, ok, why)

    # -- checks ---------------------------------------------------------------------------------
    def o1_clean(self):
        srv, d = self.server(), Device(self.tool, self.tmp, "o1")
        standard_batch(d, "o1")
        rc = d.sync(srv)
        ok, why = standard_ok(srv, "o1")
        st = d.status()
        acked = [o for o in st["ops"] if o["state"] == "acked"]
        r1 = [e for e in st["invoices"] if e["ref"] == "r1"]
        good = rc == 0 and ok and len(acked) == 5 and srv.consistent() and d.check() and r1 and r1[0]["balance_cents"] == 0
        return good, "rc=%s; %s; acked %d/5; local r1 %s" % (rc, why, len(acked), r1)

    def o2_client_crash(self, flag):
        def run():
            fails = []
            for k in range(1, 6):
                srv, d = self.server(), Device(self.tool, self.tmp, "o2%s%d" % (flag[8], k))
                tag = "o2-%s-%d" % (flag, k)
                standard_batch(d, tag)
                rc1 = d.sync(srv, flag, str(k))
                rc2 = d.sync(srv)
                ok, why = standard_ok(srv, tag)
                replays = sum(o["replayed"] for o in d.ops())
                if rc1 != 70 or rc2 != 0 or not ok or not d.check() or not srv.consistent() or \
                        (flag == "--crash-after-send" and replays < 1):
                    fails.append("k=%d rc=%s/%s %s replayed=%d" % (k, rc1, rc2, why, replays))
                srv.stop()
            return not fails, "; ".join(fails)
        return run

    def o3_server_crash(self):
        fails = []
        for k, mode in ((1, "crash_after_commit"), (3, "crash_after_commit"), (2, "crash_before_commit"), (5, "crash_before_commit")):
            d = Device(self.tool, self.tmp, "o3%d" % k)
            tag = "o3-%s-%d" % (mode, k)
            standard_batch(d, tag)
            key = [o for o in d.ops() if o["seq"] == k][0]["idempotency_key"]
            srv = self.server(plan={mode: [key]})
            rc1 = d.sync(srv)
            pend = d.status()["counts"]["pending"]
            srv.restart()
            rc2 = d.sync(srv)
            ok, why = standard_ok(srv, tag)
            if rc1 != 4 or pend < 1 or rc2 != 0 or not ok or not srv.consistent() or not d.check():
                fails.append("%s op%d rc=%s/%s pending-after-crash=%s %s" % (mode, k, rc1, rc2, pend, why))
            srv.stop()
        return not fails, "; ".join(fails)

    def o4_transient_and_order(self):
        d = Device(self.tool, self.tmp, "o4")
        d.enq("create", "a", customer="o4-a", amount="900", currency="GBP")
        d.enq("pay", "a", amount="900")
        key = d.ops()[0]["idempotency_key"]
        srv = self.server(plan={"fail_before_commit": {key: 2}})
        rc1, rc2 = d.sync(srv), d.sync(srv)
        mid = d.ops()
        before = tagged(srv, "o4")
        rc3 = d.sync(srv)
        after = tagged(srv, "o4")
        ok = (rc1 == 4 and rc2 == 4 and not before and all(o["state"] == "pending" for o in mid)
              and mid[1]["attempts"] == 0 and rc3 == 0 and len(after) == 1 and after[0]["status"] == "paid"
              and srv.consistent() and d.check())
        return ok, "rc=%s/%s/%s before=%d pay attempts while create failing=%s after=%s" % (
            rc1, rc2, rc3, len(before), mid[1].get("attempts"), [(i["paid_cents"], i["status"]) for i in after])

    def o5_conflict_void_vs_pay(self):
        srv = self.server()
        a, b = Device(self.tool, self.tmp, "o5a"), Device(self.tool, self.tmp, "o5b", who="ed2")
        a.enq("create", "x", customer="o5-x", amount="1000", currency="USD")
        a.sync(srv)
        b.sync(srv)
        sid = tagged(srv, "o5")[0]["id"]
        b.enq("pay", sid, amount="300")
        b.enq("pay", sid, amount="200")
        a.enq("void", "x")
        rca = a.sync(srv)
        rcb = b.sync(srv)
        ops = b.ops()
        inv = tagged(srv, "o5")[0]
        first_ok = (ops[0]["state"] == "conflict" and ops[0]["reason"] == "invoice_not_open"
                    and ops[1]["state"] == "pending" and ops[1].get("waiting"))
        r = b.run("resolve", "--db", b.db, "--op", ops[0]["seq"], "--action", "discard")
        rcb2 = b.sync(srv)
        ops2 = b.ops()
        ok = (rca == 0 and rcb == 1 and first_ok and inv["paid_cents"] == 0 and inv["status"] == "void"
              and r.returncode == 0 and rcb2 == 1 and ops2[0]["state"] == "discarded"
              and ops2[1]["state"] == "conflict" and srv.consistent() and b.check())
        return ok, "rc a=%s b=%s/%s first=%s then=%s server=%s" % (
            rca, rcb, rcb2, [(o["state"], o["reason"], o.get("waiting")) for o in ops],
            [(o["state"], o["reason"]) for o in ops2], (inv["paid_cents"], inv["status"]))

    def o6_overpay_two_devices(self):
        srv = self.server()
        a, b = Device(self.tool, self.tmp, "o6a"), Device(self.tool, self.tmp, "o6b", who="ed2")
        a.enq("create", "x", customer="o6-x", amount="1000", currency="USD")
        a.sync(srv)
        b.sync(srv)
        sid = tagged(srv, "o6")[0]["id"]
        a.enq("pay", "x", amount="600")
        b.enq("pay", sid, amount="600")
        rca, rcb = a.sync(srv), b.sync(srv)
        c1 = b.ops()[-1]
        r = b.run("resolve", "--db", b.db, "--op", c1["seq"], "--action", "retry")
        rcb2 = b.sync(srv)
        ops = b.ops()
        inv = tagged(srv, "o6")[0]
        retry = [o for o in ops if o.get("retry_of") == c1["seq"]]
        ok = (rca == 0 and rcb == 1 and c1["state"] == "conflict" and c1["reason"] == "exceeds_balance"
              and r.returncode == 0 and rcb2 == 1 and len(retry) == 1 and retry[0]["state"] == "conflict"
              and retry[0]["idempotency_key"] != c1["idempotency_key"] and inv["paid_cents"] == 600
              and srv.consistent() and b.check())
        return ok, "rc=%s/%s/%s conflict=%s retry=%s server paid=%s" % (
            rca, rcb, rcb2, (c1["state"], c1["reason"]), [(o["state"], o["reason"]) for o in retry], inv["paid_cents"])

    def o7_out_of_order_snapshots(self):
        srv = self.server()
        d = Device(self.tool, self.tmp, "o7")
        d.enq("create", "x", customer="o7-x", amount="1000", currency="USD")
        d.sync(srv)
        old = {"data": tagged(srv, "o7")}
        sid = old["data"][0]["id"]
        srv.post("/api/v1/invoices/%s/payments" % sid, {"amount_cents": 250}, "o7-direct-1")
        srv.post("/api/v1/invoices/%s/payments" % sid, {"amount_cents": 250}, "o7-direct-2")
        new = {"data": tagged(srv, "o7")}
        fo, fn = self.tmp / "o7-old.json", self.tmp / "o7-new.json"
        fo.write_text(json.dumps(old))
        fn.write_text(json.dumps(new))
        r1 = d.run("apply-snapshot", "--db", d.db, fn)
        r2 = d.run("apply-snapshot", "--db", d.db, fo)
        e = [x for x in d.status()["invoices"] if x["ref"] == "x"]
        ok = r1.returncode == 0 and r2.returncode == 0 and e and e[0]["balance_cents"] == 500 and d.check()
        return ok, "after new-then-old snapshots local view %s (want balance 500)" % (
            [(x["balance_cents"], x["status"]) for x in e])

    def o8_auth_refused(self):
        srv = self.server()
        d = Device(self.tool, self.tmp, "o8", who="view")
        standard_batch(d, "o8")
        rc = d.sync(srv)
        st = d.status()
        ok = rc == 3 and st["counts"]["pending"] == 5 and not tagged(srv, "o8") and d.check()
        return ok, "rc=%s pending=%s server=%d" % (rc, st["counts"].get("pending"), len(tagged(srv, "o8")))

    def o9_concurrent_syncs(self):
        srv = self.server()
        d = Device(self.tool, self.tmp, "o9")
        standard_batch(d, "o9")
        for i in range(6):
            d.enq("create", "c%d" % i, customer="o9-c%d" % i, amount=str(100 + i), currency="USD")
        with ThreadPoolExecutor(4) as ex:
            rcs = list(ex.map(lambda _: d.sync(srv), range(4)))
        final = d.sync(srv)
        inv = tagged(srv, "o9")
        names = sorted(i["customer"] for i in inv)
        ok = (all(rc in (0, 5) for rc in rcs) and final == 0 and len(inv) == 8 and len(set(names)) == 8
              and srv.consistent() and d.check())
        return ok, "rcs=%s final=%s server invoices=%d distinct=%d" % (rcs, final, len(inv), len(set(names)))

    def o10_tenant_pull(self):
        srv = self.server()
        a = Device(self.tool, self.tmp, "o10a")
        a.enq("create", "x", customer="o10-x", amount="700", currency="USD")
        a.sync(srv)
        z = Device(self.tool, self.tmp, "o10z", who="other")
        z.enq("create", "y", customer="o10-y", amount="800", currency="USD")
        rc = z.sync(srv)
        inv = z.status()["invoices"]
        custs = sorted(((e.get("server") or {}).get("customer")) for e in inv)
        ok = rc == 0 and custs == ["o10-y"] and z.check()
        return ok, "zenith device sees %s" % custs

    def o11_soak(self):
        rnd = random.Random(self.seed)
        srv = self.server()
        devs = [Device(self.tool, self.tmp, "o11d%d" % i, who=("ed1", "ed2")[i % 2]) for i in range(3)]
        intents = 0
        for d in devs:
            d.sync(srv)
        rounds = 3 if self.quick else 6
        for rnd_i in range(rounds):
            for i, d in enumerate(devs):
                refs = [e["ref"] for e in d.status()["invoices"]]
                for j in range(rnd.randint(2, 5)):
                    pick = rnd.random()
                    if pick < 0.35 or not refs:
                        ref = "n%d-%d-%d" % (i, rnd_i, j)
                        d.enq("create", ref, customer="o11-%s-%d" % (ref, self.seed), amount=str(rnd.randint(1, 50) * 100),
                              currency="USD")
                        refs.append(ref)
                    elif pick < 0.85:
                        d.enq("pay", rnd.choice(refs), amount=str(rnd.randint(1, 30) * 100))
                    else:
                        d.enq("void", rnd.choice(refs))
                    intents += 1
            for d in devs:
                for _ in range(12):
                    pend = [o for o in d.ops() if o["state"] == "pending"]
                    if not pend:
                        break
                    roll = rnd.random()
                    if roll < 0.3:
                        d.sync(srv, "--crash-after-send", str(rnd.randint(1, 3)))
                    elif roll < 0.45:
                        d.sync(srv, "--crash-before-send", str(rnd.randint(1, 3)))
                    elif roll < 0.6:
                        k = rnd.choice(pend)["idempotency_key"]
                        srv.restart(plan={rnd.choice(("crash_after_commit", "crash_before_commit")): [k]})
                        d.sync(srv)
                        srv.restart()
                    else:
                        rc = d.sync(srv)
                        if rc == 1:
                            for o in d.ops():
                                if o["state"] in ("conflict", "rejected"):
                                    d.run("resolve", "--db", d.db, "--op", o["seq"], "--action", "discard")
            for d in devs:
                for _ in range(8):
                    if d.sync(srv) == 0:
                        break
                    for o in d.ops():
                        if o["state"] in ("conflict", "rejected"):
                            d.run("resolve", "--db", d.db, "--op", o["seq"], "--action", "discard")
        # judge from the server against the oracle's own reading of every device's settled intents
        server = {i["id"]: i for i in tagged(srv, "o11")}
        paid, voided, created, unsettled, total_ops = {}, set(), 0, 0, 0
        for d in devs:
            st = d.status()
            ref_to_id = {e["ref"]: e.get("server_id") for e in st["invoices"]}
            for o in st["ops"]:
                total_ops += 1
                if o["state"] not in ("acked", "discarded"):
                    unsettled += 1
                if o["state"] != "acked":
                    continue
                sid = ref_to_id.get(o["ref"]) or o["ref"]
                if o["kind"] == "create":
                    created += 1
                elif o["kind"] == "pay":
                    paid[sid] = paid.get(sid, 0) + o["body"]["amount_cents"]
                else:
                    voided.add(sid)
        bad = [sid for sid, inv in server.items() if inv["paid_cents"] != paid.get(sid, 0)
               or (inv["status"] == "void") != (sid in voided)]
        ok = (not bad and created == len(server) and unsettled == 0 and total_ops == intents
              and srv.consistent() and all(d.check() for d in devs))
        return ok, "intents=%d ops=%d unsettled=%d acked creates=%d server invoices=%d mismatched=%s" % (
            intents, total_ops, unsettled, created, len(server), bad[:3])

    def o12_local_contract(self):
        srv = self.server()
        d = Device(self.tool, self.tmp, "o12")
        bad = []
        for args in (("create", "x", {"customer": "o12-x", "amount": "10.5", "currency": "USD"}),
                     ("create", "x", {"customer": "o12-x", "amount": "100", "currency": "XYZ"}),
                     ("pay", "never-made", {"amount": "100"})):
            r = d.run("enqueue", "--db", d.db, args[0], "--ref", args[1], *sum((["--" + k, v] for k, v in args[2].items()), []))
            if r.returncode != 2:
                bad.append("enqueue %s accepted (rc %s)" % (args, r.returncode))
        d.enq("create", "x", customer="o12-x", amount="1000", currency="USD")
        r = d.run("enqueue", "--db", d.db, "create", "--ref", "x", "--customer", "o12-dup", "--amount", "5", "--currency", "USD")
        if r.returncode != 2:
            bad.append("second create on the same ref accepted")
        if d.run("init", "--db", d.db, "--device", "o12").returncode != 2:
            bad.append("init over an existing outbox accepted")
        d.enq("pay", "x", amount="300")
        st = d.status()
        x = [e for e in st["invoices"] if e["ref"] == "x"]
        if st["counts"]["pending"] != 2 or not x or x[0]["balance_cents"] != 700:
            bad.append("projection with pending pay: %s pending=%s" % (x, st["counts"].get("pending")))
        r = d.run("sync", "--db", d.db, "--base-url", "http://192.0.2.10:9", "--key-file", d.keyfile, "--timeout", "1")
        if r.returncode != 2:
            bad.append("non-loopback base URL not refused (rc %s)" % r.returncode)
        if d.sync(srv) != 0:
            bad.append("sync failed")
        twin = Device(self.tool, self.tmp, "o12")
        twin.enq("create", "y", customer="o12-twin", amount="100", currency="USD")
        if set(o["idempotency_key"] for o in twin.ops()) & set(o["idempotency_key"] for o in d.ops()):
            bad.append("two installs with one device name share idempotency keys")
        ghost = dict(tagged(srv, "o12")[0], id="inv_00000000000000ab", version=1)
        f = self.tmp / "o12-ghost.json"
        f.write_text(json.dumps({"data": [ghost]}))
        d.run("apply-snapshot", "--db", d.db, f)
        d.enq("pay", ghost["id"], amount="100")
        d.enq("void", ghost["id"])
        rc = d.sync(srv, "--no-pull")
        ops = d.ops()
        if rc != 1 or ops[-2]["state"] != "conflict" or ops[-1]["state"] != "pending":
            bad.append("pay to an invoice the server does not know: rc=%s %s" % (rc, [(o["state"], o["reason"]) for o in ops[-2:]]))
        r = d.run("resolve", "--db", d.db, "--op", ops[0]["seq"], "--action", "discard")
        if r.returncode != 2:
            bad.append("resolving an acked change accepted")
        return not bad, "; ".join(bad)

    def run(self):
        if not self.tool.is_file():
            print("FAIL tool: %s does not exist" % self.tool)
            print("REJECTED 0/1")
            return 1
        try:
            self.check("o1 clean control: offline batch syncs once, server and local view agree", self.o1_clean)
            self.check("o2a client crash after each send, restart: one effect each", self.o2_client_crash("--crash-after-send"))
            self.check("o2b client crash before each send, restart: one effect each", self.o2_client_crash("--crash-before-send"))
            self.check("o3 server crash before/after commit, restart: one effect each", self.o3_server_crash)
            self.check("o4 transient failure keeps order: no dependent change sent early", self.o4_transient_and_order)
            self.check("o5 pay on an invoice voided elsewhere: explicit conflict, later change held", self.o5_conflict_void_vs_pay)
            self.check("o6 two devices overpay: one conflict, retry is a new key, never overpaid", self.o6_overpay_two_devices)
            self.check("o7 out-of-order server snapshots never roll the local view back", self.o7_out_of_order_snapshots)
            self.check("o8 refused key: nothing sent, nothing lost", self.o8_auth_refused)
            self.check("o9 four concurrent syncs of one outbox: one effect each", self.o9_concurrent_syncs)
            self.check("o10 pull is tenant-scoped", self.o10_tenant_pull)
            self.check("o12 local contract: refusals record nothing, projection, 404 conflict, per-install keys", self.o12_local_contract)
            self.check("o11 seeded soak (3 devices, crashes, faults, conflicts): server equals settled intent", self.o11_soak)
        finally:
            for s in self.servers:
                s.stop()
            shutil.rmtree(self.tmp, ignore_errors=True)
        n, m = sum(self.results), len(self.results)
        print("%s %d/%d" % ("PASSED" if n == m else "REJECTED", n, m))
        return 0 if n == m else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(DEFAULT_TOOL))
    ap.add_argument("--seed", type=int, default=2121)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    sys.exit(Oracle(a.tool, a.seed, a.quick).run())
