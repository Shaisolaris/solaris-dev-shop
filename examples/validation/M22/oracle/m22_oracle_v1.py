#!/usr/bin/env python3
"""M22 oracle (Grok self-validation, not independent review).

Written from M22.md, G22.md and payment_ledger's webhook-ledger.md, before reading the builder's
oracle. It signs its own envelopes with HMAC-SHA256 over "<t>.<body>", keeps its own money and stock
model in integer cents, and drives the real CLI (or --tool) in fresh temp dirs.

Usage: m22_oracle.py SRC OUT.json [--tool PATH] [--quick]
Rows: B01 clean, B02 signature/time, B03 replay, B04 out of order, B05 oversell under concurrent
processes (and the 'database is locked' race), B06 over-refund, B07 over-restock, B08 exact cents,
B09 crash drill and rerun, B10 export reconciles with G14, B11 cancel, B12 seeded soak.

Authoring fixes after the first run on the real tool (first run kept in results/kept, 9/12), disclosed:
- B07: the ingest after an over-restock exception exits 1 because that exception stays open (exit 1
  means held or exceptions are open in the ledger, not only in this batch). Expectation corrected.
- B08: the doc refuses a JSON float, and says "0.300" is not an amount without naming refuse or
  exception. Either is accepted if nothing is applied and the reason names the amount; an open
  exception then keeps later ingests at exit 1.
- B10: G14 JSON has no top-level status; reconciliation is read as every currencies.*.checks.*.ok
  true and every exceptions list empty.
"""
import hashlib, hmac, json, os, random, shutil, subprocess, sys, tempfile

SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/specialized/payments-specialist/payment_ledger.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
QUICK = "--quick" in sys.argv
G14 = os.path.join(SRC, "employees/leadership/cfo/cash_revenue_reconcile.py")
FIX = os.path.join(SRC, "examples/capabilities/G22/fixtures")
SECRET = "m22-oracle-local-test-value-grants-nothing"
PY = sys.executable
NOW = 1790000200
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
CAT = {"schema": "solaris.store-catalog/1", "currency": "USD",
       "skus": [{"sku": "mug-blue", "price": "12.50", "on_hand": 10},
                {"sku": "tee-m", "price": "19.99", "on_hand": 4},
                {"sku": "poster", "price": "0.10", "on_hand": 3}]}
PRICE = {"mug-blue": 1250, "tee-m": 1999, "poster": 10}


def body(i, typ, data, created=1790000000):
    return json.dumps({"id": i, "type": typ, "created": created, "data": data}, sort_keys=True)


def env(b, t=NOW - 100, secret=SECRET):
    sig = hmac.new(secret.encode(), ("%d.%s" % (t, b)).encode(), hashlib.sha256).hexdigest()
    return {"signature": "t=%d,v1=%s" % (t, sig), "body": b}


def order(i, oid, lines, c=1790000000):
    return body(i, "order.placed", {"order_id": oid, "currency": "USD",
                                    "lines": [{"sku": s, "qty": q} for s, q in lines]}, c)


def cap(i, oid, pid, amt, c=1790000010):
    return body(i, "payment.captured", {"order_id": oid, "payment_id": pid, "amount": amt}, c)


def ref(i, oid, rid, amt, restock=(), c=1790000020):
    return body(i, "refund.succeeded", {"order_id": oid, "refund_id": rid, "amount": amt,
                                        "restock": [{"sku": s, "qty": q} for s, q in restock]}, c)


def cancel(i, oid, c=1790000030):
    return body(i, "order.cancelled", {"order_id": oid}, c)


def run(args, cwd, timeout=120):
    p = subprocess.run([PY, TOOL] + args, cwd=cwd, env=ENV, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout, p.stderr


class L:
    def __init__(self, catalog=None):
        self.d = tempfile.mkdtemp(prefix="m22o-")
        with open(os.path.join(self.d, "secret.txt"), "w") as f: f.write(SECRET + "\n")
        with open(os.path.join(self.d, "cat.json"), "w") as f: json.dump(catalog or CAT, f)
        self.db = os.path.join(self.d, "l.db"); self.n = 0
        self.init = run(["init", "--db", self.db, "--catalog", "cat.json"], self.d)

    def write(self, envs):
        self.n += 1; p = os.path.join(self.d, "s%d.jsonl" % self.n)
        with open(p, "w") as f:
            for e in envs: f.write((e if isinstance(e, str) else json.dumps(e)) + "\n")
        return p

    def ingest(self, envs, now=NOW, extra=()):
        return run(["ingest", "--db", self.db, "--secret-file", "secret.txt", "--events",
                    self.write(envs), "--now", str(now)] + list(extra), self.d)

    def report(self):
        rc, o, e = run(["report", "--db", self.db, "--json"], self.d)
        try: return json.loads(o)
        except Exception: return {"_bad": (rc, o[-300:], e[-300:])}

    def check(self):
        return run(["check", "--db", self.db], self.d)[0]

    def close(self): shutil.rmtree(self.d, ignore_errors=True)


def cents(s):
    try:
        a, _, b = str(s).partition("."); return int(a) * 100 + int((b + "00")[:2]) * (1 if not a.startswith("-") else -1)
    except Exception: return None


def summary(r):
    if "_bad" in r: return r
    m = r.get("money", {})
    st = {s["sku"]: (s.get("on_hand"), s.get("reserved"), s.get("shipped"), s.get("restocked"))
          for s in r.get("stock", [])}
    return {"captured": cents(m.get("captured")), "refunded": cents(m.get("refunded")),
            "ucap": cents(m.get("unapplied_captures")), "uref": cents(m.get("unapplied_refunds")),
            "net": cents(r.get("net_cash")), "stock": st, "open": len(r.get("open") or [])}


ROWS = []


def row(name):
    def deco(fn):
        def wrap():
            try: ok, det = fn()
            except Exception as ex: ok, det = False, "crash %s: %s" % (type(ex).__name__, ex)
            ROWS.append({"row": name, "pass": bool(ok), "detail": det})
            print("%s %s %s" % ("PASS" if ok else "FAIL", name, str(det)[:400]), flush=True)
        ROWS_FN.append(wrap); return wrap
    return deco


ROWS_FN = []
BASE = [order("e1", "o1", [("mug-blue", 2), ("tee-m", 1)]), cap("e2", "o1", "p1", "44.99"),
        ref("e3", "o1", "r1", "12.50", [("mug-blue", 1)])]
BASE_EXPECT = {"captured": 4499, "refunded": 1250, "ucap": 0, "uref": 0, "net": 3249,
               "stock": {"mug-blue": (9, 0, 2, 1), "tee-m": (3, 0, 1, 0), "poster": (3, 0, 0, 0)},
               "open": 0}


@row("B01 clean stream: exact money, stock identity, exit 0, check consistent")
def b01():
    l = L(); rc = l.ingest([env(b) for b in BASE])[0]; s = summary(l.report()); ck = l.check(); l.close()
    return rc == 0 and s == BASE_EXPECT and ck == 0, {"rc": rc, "check": ck, "s": s}


@row("B02 signature and time: tampered, wrong secret, stale, future, malformed refused and nothing stored; 300 s boundary accepted")
def b02():
    det = {}; ok = True
    o = order("e1", "o1", [("mug-blue", 1)])
    good = env(o)
    tam = dict(good, body=good["body"].replace('"qty": 1', '"qty": 2'))
    cases = {"tampered": tam, "wrong_secret": env(o, secret="other"),
             "stale_301": env(o, t=NOW - 301), "future_301": env(o, t=NOW + 301),
             "no_t": {"signature": "v1=" + good["signature"].split("v1=")[1], "body": o},
             "sig_over_other_t": {"signature": "t=%d,v1=%s" % (NOW - 5, good["signature"].split("v1=")[1]), "body": o}}
    for k, e in cases.items():
        l = L(); rc = l.ingest([e])[0]; s = summary(l.report()); r = l.report(); l.close()
        good_case = rc == 3 and s["stock"]["mug-blue"] == (10, 0, 0, 0) and not r.get("events")
        det[k] = (rc, s["stock"].get("mug-blue"), r.get("events")); ok &= good_case
    l = L(); rc = l.ingest([env(o, t=NOW - 300)])[0]; s = summary(l.report()); l.close()
    det["boundary_300"] = (rc, s["stock"].get("mug-blue")); ok &= rc == 0 and s["stock"]["mug-blue"] == (10, 1, 0, 0)
    l = L(); rc = l.ingest([good, env(cap("e2", "o1", "p1", "12.50"), secret="other")])[0]
    s = summary(l.report()); l.close()
    det["mixed_batch"] = (rc, s["captured"], s["stock"].get("mug-blue"))
    ok &= rc == 3 and s["captured"] == 0 and s["stock"]["mug-blue"] == (10, 1, 0, 0)
    return ok, det


@row("B03 replay: same id and body once (in batch, across runs, re-signed); other body conflicting_replay; reused payment id is an exception")
def b03():
    det = {}; ok = True
    l = L(); e = [env(b) for b in BASE]
    r1 = l.ingest(e + e)[0]; r2 = l.ingest(e)[0]
    r3 = l.ingest([env(b, t=NOW - 7) for b in BASE])[0]
    s = summary(l.report()); det["dups"] = (r1, r2, r3, s); ok &= (r1, r2, r3) == (0, 0, 0) and s == BASE_EXPECT
    r4, out4, _ = l.ingest([env(cap("e2", "o1", "p1", "44.98"))]); s4 = summary(l.report())
    det["conflicting"] = (r4, "conflicting_replay" in out4, s4 == BASE_EXPECT)
    ok &= r4 == 3 and "conflicting_replay" in out4 and s4 == BASE_EXPECT
    l.close()
    l = L(); l.ingest([env(BASE[0]), env(BASE[1])])
    r5 = l.ingest([env(cap("e9", "o1", "p1", "44.99"))])[0]; s5 = summary(l.report()); ck = l.check(); l.close()
    det["reused_payment_id"] = (r5, s5["captured"], ck)
    ok &= r5 == 1 and s5["captured"] == 4499 and ck == 0
    return ok, det


@row("B04 out of order: reversed stream equals in-order; held events listed (exit 1), then applied when the order arrives")
def b04():
    det = {}; ok = True
    l = L(); rc = l.ingest([env(b) for b in reversed(BASE)])[0]; s = summary(l.report()); ck = l.check(); l.close()
    det["reversed"] = (rc, ck, s); ok &= rc == 0 and ck == 0 and s == BASE_EXPECT
    l = L(); r1 = l.ingest([env(BASE[2]), env(BASE[1])])[0]; s1 = summary(l.report())
    r2 = l.ingest([env(BASE[0])])[0]; s2 = summary(l.report()); ck = l.check(); l.close()
    det["split"] = (r1, s1["open"], s1["captured"], r2, s2, ck)
    ok &= r1 == 1 and s1["open"] == 2 and s1["captured"] == 0 and r2 == 0 and s2 == BASE_EXPECT and ck == 0
    l = L(); r1 = l.ingest([env(BASE[0]), env(BASE[2])])[0]; s1 = summary(l.report())
    r2 = l.ingest([env(BASE[1])])[0]; s2 = summary(l.report()); l.close()
    det["refund_before_capture"] = (r1, s1["open"], s1["refunded"], r2, s2 == BASE_EXPECT)
    ok &= r1 == 1 and s1["open"] == 1 and s1["refunded"] == 0 and r2 == 0 and s2 == BASE_EXPECT
    return ok, det


@row("B05 oversell under concurrency: 10 processes race for 4 tee-m; exactly 4 reserved, no 'database is locked', check consistent; concurrent replays capture once")
def b05():
    det = []; ok = True
    for trial in range(2 if QUICK else 5):
        l = L(); procs = []
        files = [l.write([env(order("c%d" % i, "oc%d" % i, [("tee-m", 1)]))]) for i in range(10)]
        for f in files:
            procs.append(subprocess.Popen([PY, TOOL, "ingest", "--db", l.db, "--secret-file", "secret.txt",
                                           "--events", f, "--now", str(NOW)], cwd=l.d, env=ENV,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        res = [(p.wait(timeout=120), p.stdout.read(), p.stderr.read()) for p in procs]
        s = summary(l.report()); ck = l.check()
        locked = sum("locked" in (o + e).lower() for _, o, e in res)
        oos = sum("out_of_stock" in o for _, o, _ in res)
        rcs = sorted(r for r, _, _ in res)
        good = s["stock"]["tee-m"] == (4, 4, 0, 0) and ck == 0 and locked == 0 and oos == 6 and set(rcs) <= {0, 1}
        # replay race: 6 processes deliver the same capture of one placed order
        l2 = L(); l2.ingest([env(order("x1", "ox", [("mug-blue", 1)]))])
        f2 = l2.write([env(cap("x2", "ox", "px", "12.50"))])
        ps = [subprocess.Popen([PY, TOOL, "ingest", "--db", l2.db, "--secret-file", "secret.txt", "--events", f2,
                                "--now", str(NOW)], cwd=l2.d, env=ENV, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True) for _ in range(6)]
        r2 = [(p.wait(timeout=120), p.stdout.read() + p.stderr.read()) for p in ps]
        s2 = summary(l2.report()); ck2 = l2.check()
        good2 = s2["captured"] == 1250 and ck2 == 0 and all(r == 0 for r, _ in r2) and not any("locked" in t.lower() for _, t in r2)
        det.append({"trial": trial, "tee": s["stock"]["tee-m"], "oos": oos, "locked": locked, "rcs": rcs, "check": ck,
                    "replay_captured": s2["captured"], "replay_rcs": [r for r, _ in r2], "check2": ck2})
        ok &= good and good2; l.close(); l2.close()
    return ok, det


@row("B06 over-refund refused as refund_exceeds_captured, kept as unapplied money; exact remainder accepted")
def b06():
    l = L(); l.ingest([env(b) for b in BASE])
    r1, o1, _ = l.ingest([env(ref("e4", "o1", "r2", "32.50"))]); s1 = summary(l.report())
    r2 = l.ingest([env(ref("e5", "o1", "r3", "32.49"))])[0]; s2 = summary(l.report())
    r3, o3, _ = l.ingest([env(ref("e6", "o1", "r4", "0.01"))]); s3 = summary(l.report()); ck = l.check(); l.close()
    ok = (r1 == 1 and "refund_exceeds_captured" in o1 and s1["refunded"] == 1250 and s1["uref"] == 3250
          and s1["net"] == 3249 and s2["refunded"] == 4499 and s2["net"] == 0 and s2["uref"] == 3250
          and r3 == 1 and "refund_exceeds_captured" in o3 and s3["refunded"] == 4499 and s3["uref"] == 3251 and ck == 0)
    return ok, {"r": (r1, r2, r3), "s1": s1, "s2": s2, "s3": s3, "check": ck}


@row("B07 over-restock refused as restock_exceeds_shipped: stock and money unchanged, refund money unapplied")
def b07():
    det = {}; ok = True
    l = L(); l.ingest([env(b) for b in BASE])
    r1, o1, _ = l.ingest([env(ref("e4", "o1", "r2", "1.00", [("mug-blue", 2)]))]); s1 = summary(l.report())
    det["mug_2_after_1"] = (r1, "restock_exceeds_shipped" in o1, s1["stock"]["mug-blue"], s1["refunded"], s1["uref"])
    ok &= r1 == 1 and "restock_exceeds_shipped" in o1 and s1["stock"]["mug-blue"] == (9, 0, 2, 1) and s1["refunded"] == 1250 and s1["uref"] == 100
    r2 = l.ingest([env(ref("e5", "o1", "r3", "1.00", [("mug-blue", 1)]))])[0]; s2 = summary(l.report())
    det["mug_last_one"] = (r2, s2["stock"]["mug-blue"]); ok &= r2 == 1 and s2["stock"]["mug-blue"] == (10, 0, 2, 2)
    r3, o3, _ = l.ingest([env(ref("e6", "o1", "r4", "1.00", [("poster", 1)]))]); s3 = summary(l.report())
    det["sku_not_in_order"] = (r3, "restock_exceeds_shipped" in o3, s3["stock"]["poster"])
    ok &= r3 == 1 and "restock_exceeds_shipped" in o3 and s3["stock"]["poster"] == (3, 0, 0, 0)
    ck = l.check(); det["check"] = ck; ok &= ck == 0; l.close()
    return ok, det


@row("B08 exact cents: 3 x 0.10 = 0.30 captured, refunds of 0.10 sum exactly, float and 0.300 refused, 0.29 is capture_amount_mismatch")
def b08():
    det = {}; ok = True
    l = L(); po = order("p0", "op", [("poster", 3)])
    r = l.ingest([env(po), env(cap("p1", "op", "pp", "0.30"))] + [env(ref("p%d" % (i + 2), "op", "rp%d" % i, "0.10")) for i in range(3)])[0]
    s = summary(l.report()); det["poster"] = (r, s["captured"], s["refunded"], s["net"])
    ok &= r == 0 and s["captured"] == 30 and s["refunded"] == 30 and s["net"] == 0
    r2, o2, _ = l.ingest([env(ref("p9", "op", "rp9", "0.01"))]); det["one_cent_over"] = (r2, "refund_exceeds_captured" in o2)
    ok &= r2 == 1 and "refund_exceeds_captured" in o2; l.close()
    l = L(); l.ingest([env(order("t0", "ot", [("tee-m", 3)]))])
    fl = json.dumps({"id": "t1", "type": "payment.captured", "created": 1790000010,
                     "data": {"order_id": "ot", "payment_id": "pt", "amount": 59.97}}, sort_keys=True)
    rf = l.ingest([env(fl)])[0]; rz, oz, _ = l.ingest([env(cap("t2", "ot", "pt", "59.970"))])
    fc = json.dumps({"id": "t3", "type": "payment.captured", "created": 1790000010.5,
                     "data": {"order_id": "ot", "payment_id": "pt", "amount": "59.97"}}, sort_keys=True)
    rc_ = l.ingest([env(fc)])[0]
    s = summary(l.report()); det["refused"] = (rf, rz, rc_, s["captured"], s["ucap"])
    ok &= rf == 3 and (rz == 3 or (rz == 1 and "amount" in oz)) and rc_ == 3 and s["captured"] == 0 and s["ucap"] == 0
    r3 = l.ingest([env(cap("t4", "ot", "pt", "59.97"))])[0]; s3 = summary(l.report())
    det["tee_3"] = (r3, s3["captured"]); ok &= r3 == (0 if rz == 3 else 1) and s3["captured"] == 5997; l.close()
    l = L(); l.ingest([env(po)]); r4, o4, _ = l.ingest([env(cap("p1", "op", "pp", "0.29"))]); s4 = summary(l.report())
    det["mismatch"] = (r4, "capture_amount_mismatch" in o4, s4["captured"], s4["ucap"], s4["stock"]["poster"])
    ok &= r4 == 1 and "capture_amount_mismatch" in o4 and s4["captured"] == 0 and s4["ucap"] == 29 and s4["stock"]["poster"] == (3, 3, 0, 0)
    ck = l.check(); ok &= ck == 0; l.close()
    return ok, det


CRASH_STREAM = [BASE[2], BASE[0], BASE[0], BASE[1], order("e7", "o2", [("tee-m", 2)]), cancel("e8", "o2"),
                ref("e9", "o1", "r9", "40.00")]


@row("B09 crash drill: --crash-after N exits 70, rerunning the whole batch reaches the clean end state")
def b09():
    l = L(); rc0 = l.ingest([env(b) for b in CRASH_STREAM])[0]; clean = summary(l.report()); l.close()
    det = {"clean": (rc0, clean)}; ok = rc0 == 1 and clean["net"] == 3249 and clean["uref"] == 4000 and clean["stock"]["tee-m"] == (3, 0, 1, 0)
    for n in range(1, len(CRASH_STREAM)):
        l = L(); e = [env(b) for b in CRASH_STREAM]
        rc = l.ingest(e, extra=["--crash-after", str(n)])[0]; ck1 = l.check()
        rr = l.ingest(e)[0]; s = summary(l.report()); ck = l.check(); l.close()
        det[n] = (rc, ck1, rr, ck, s == clean); ok &= rc == 70 and ck1 == 0 and rr == 1 and ck == 0 and s == clean
    return ok, det


def g14(l, start="2026-09-01T00:00:00Z", end="2026-10-01T00:00:00Z"):
    books = os.path.join(l.d, "books")
    rc = run(["export-g14", "--db", l.db, "--out", books, "--period-start", start, "--period-end", end], l.d)[0]
    p = subprocess.run([PY, G14, "reconcile", os.path.join(books, "package.json"), "--json"], cwd=l.d, env=ENV,
                       capture_output=True, text=True, timeout=120)
    try: j = json.loads(p.stdout)
    except Exception: j = {"_bad": p.stdout[-300:] + p.stderr[-300:]}
    return rc, p.returncode, j


def find_num(j, keys):
    out = {}
    def walk(x, path=""):
        if isinstance(x, dict):
            for k, v in x.items(): walk(v, path + "." + k)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, path + "[%d]" % i)
        else:
            for k in keys:
                if path.endswith(k): out[path] = x
    walk(j); return out


@row("B10 export-g14 reconciles in G14 with recognized revenue and net cash equal to the ledger net cash (september fixture and own streams)")
def b10():
    det = {}; ok = True
    for name, envs in (("september", None), ("base", [env(b) for b in BASE]), ("crash_stream", [env(b) for b in CRASH_STREAM])):
        l = L(json.load(open(os.path.join(FIX, "catalog.json"))) if envs is None else None)
        if envs is None:
            shutil.copy(os.path.join(FIX, "test-secret.txt"), os.path.join(l.d, "secret.txt"))
            run(["ingest", "--db", l.db, "--secret-file", "secret.txt", "--events", os.path.join(FIX, "september.jsonl"),
                 "--now", "1790000200"], l.d)
        else:
            l.ingest(envs)
        net = summary(l.report())["net"]
        erc, grc, j = g14(l)
        nums = find_num(j, ("recognized_revenue", "net_cash", "status", "reconciles", "reconciled"))
        vals = [cents(v) for k, v in nums.items() if k.endswith(("recognized_revenue", "net_cash")) and isinstance(v, str)]
        oks = [v for k, v in find_num(j, (".ok",)).items() if ".checks." in k]
        exc = j.get("exceptions") if isinstance(j, dict) else None
        clean = isinstance(exc, dict) and all(not v for v in exc.values())
        good = erc == 0 and grc == 0 and len(vals) >= 2 and all(v == net for v in vals) and oks and all(v is True for v in oks) and clean
        det[name] = {"net": net, "export_rc": erc, "g14_rc": grc, "nums": nums, "checks_ok": oks, "exceptions_empty": clean}; ok &= bool(good); l.close()
    if not QUICK:
        l = L(); l.ingest([env(b) for b in BASE]); erc, grc, j = g14(l, "2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z")
        det["outside_period"] = {"export_rc": erc, "g14_rc": grc, "nums": find_num(j, ("recognized_revenue", "net_cash"))}; l.close()
    return ok, det


@row("B11 cancel releases the reservation; capture after cancel and cancel after capture are named anomalies")
def b11():
    det = {}; ok = True
    l = L(); r1 = l.ingest([env(order("k1", "ok", [("tee-m", 3)])), env(cancel("k2", "ok"))])[0]; s1 = summary(l.report())
    r2, o2, _ = l.ingest([env(cap("k3", "ok", "pk", "59.97"))]); s2 = summary(l.report())
    det["cancel_then_capture"] = (r1, s1["stock"]["tee-m"], r2, "capture_on_cancelled_order" in o2, s2["captured"], s2["ucap"])
    ok &= r1 == 0 and s1["stock"]["tee-m"] == (4, 0, 0, 0) and r2 == 1 and "capture_on_cancelled_order" in o2 and s2["captured"] == 0 and s2["ucap"] == 5997
    l.close()
    l = L(); l.ingest([env(b) for b in BASE[:2]]); r3, o3, _ = l.ingest([env(cancel("e9", "o1"))]); s3 = summary(l.report()); ck = l.check(); l.close()
    det["capture_then_cancel"] = (r3, "cannot_cancel_captured_order" in o3, s3["stock"]["tee-m"], ck)
    ok &= r3 == 1 and "cannot_cancel_captured_order" in o3 and s3["stock"]["tee-m"] == (3, 0, 1, 0) and ck == 0
    return ok, det


@row("B12 seeded soak: shuffled captures/refunds, duplicates, crash restarts on an ample catalog equal an independent cents model")
def b12():
    det = []; ok = True
    for seed in range(2 if QUICK else 4):
        rnd = random.Random(2200 + seed)
        cat = {"schema": "solaris.store-catalog/1", "currency": "USD",
               "skus": [{"sku": k, "price": "%d.%02d" % divmod(v, 100), "on_hand": 500} for k, v in PRICE.items()]}
        store, money = [], []; cap_c = ref_c = 0; ship = {k: 0 for k in PRICE}; rest = {k: 0 for k in PRICE}; res = {k: 0 for k in PRICE}
        for o in range(14):
            lines = [(k, rnd.randint(1, 4)) for k in rnd.sample(sorted(PRICE), rnd.randint(1, 3))]
            tot = sum(PRICE[k] * q for k, q in lines); oid = "o%d" % o
            store.append(order("s%d-o" % o, oid, lines, 1790000000 + o))
            fate = rnd.random()
            if fate < 0.2:
                store.append(cancel("s%d-c" % o, oid, 1790000100 + o))
            elif fate < 0.35:
                for k, q in lines: res[k] += q
            else:
                money.append(cap("s%d-p" % o, oid, "p%d" % o, "%d.%02d" % divmod(tot, 100), 1790000200 + o)); cap_c += tot
                for k, q in lines: ship[k] += q
                left = tot; shipped = dict(lines)
                for r in range(rnd.randint(0, 3)):
                    a = rnd.randint(1, max(1, left // 2)) if left > 0 else 0
                    if a == 0: break
                    rs = [(k, 1) for k in shipped if shipped[k] > 0 and rnd.random() < 0.4]
                    for k, _ in rs: shipped[k] -= 1; rest[k] += 1
                    money.append(ref("s%d-r%d" % (o, r), oid, "r%d-%d" % (o, r), "%d.%02d" % divmod(a, 100), rs, 1790000300 + o * 10 + r))
                    left -= a; ref_c += a
        stream = list(store)
        for m in money: stream.insert(rnd.randint(0, len(stream)), m)
        stream += [rnd.choice(stream) for _ in range(5)]
        l = L(cat); e = [env(b) for b in stream]
        cut = rnd.randint(1, len(e) - 1); rc70 = l.ingest(e, extra=["--crash-after", str(cut)])[0]
        rc = l.ingest(e)[0]; s = summary(l.report()); ck = l.check(); l.close()
        exp_stock = {k: (500 - ship[k] + rest[k], res[k], ship[k], rest[k]) for k in PRICE}
        good = rc70 == 70 and rc == 0 and ck == 0 and s["captured"] == cap_c and s["refunded"] == ref_c and s["net"] == cap_c - ref_c and s["ucap"] == 0 and s["uref"] == 0 and s["stock"] == exp_stock and s["open"] == 0
        det.append({"seed": seed, "n": len(e), "ok": good, "rc": (rc70, rc, ck), "got": s, "exp": {"cap": cap_c, "ref": ref_c, "stock": exp_stock}} if not good else {"seed": seed, "n": len(e), "ok": True})
        ok &= good
    return ok, det


if __name__ == "__main__":
    for fn in ROWS_FN: fn()
    n = sum(r["pass"] for r in ROWS)
    with open(OUT, "w") as f: json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, f, indent=1, default=str)
    print("M22 ORACLE %d/%d core %s" % (n, len(ROWS), "PASS" if n == len(ROWS) else "FAIL"))
