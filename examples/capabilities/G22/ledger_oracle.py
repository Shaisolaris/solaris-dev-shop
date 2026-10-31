#!/usr/bin/env python3
"""G22 oracle: signed webhooks, exact money and conserved stock, judged against its own reference model.

Drives a ledger tool only through its CLI (init, ingest, report --json, check, export-g14). The oracle
signs its own envelopes (HMAC-SHA256 over "<t>.<body>") with its own secret, keeps its own in-order
reference model of every seeded scenario, and checks the export with the G14 reconciliation.

    ledger_oracle.py [--tool PATH] [--seeds N]
Last line `PASSED n/m` or `REJECTED n/m`; exit 0 only if every check passes.
"""
import argparse
import hashlib
import hmac
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_TOOL = ROOT / "employees" / "specialized" / "payments-specialist" / "payment_ledger.py"
G14 = ROOT / "employees" / "leadership" / "cfo" / "cash_revenue_reconcile.py"
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
SECRET = b"oracle-only-signing-secret-7f3a91c2"
T0 = 1791000000


def c2s(c):
    return "%d.%02d" % (c // 100, c % 100)


def envelope(ev, t=None, secret=SECRET, body=None):
    body = body or json.dumps(ev, sort_keys=True)
    t = ev["created"] if t is None else t
    return json.dumps({"signature": "t=%d,v1=%s" % (t, hmac.new(secret, ("%d." % t).encode() + body.encode(), hashlib.sha256).hexdigest()),
                       "body": body})


class Ledger:
    def __init__(self, tool, tmp, catalog, name):
        self.tool, self.tmp = tool, tmp
        self.db = tmp / (name + ".db")
        (tmp / (name + "-cat.json")).write_text(json.dumps(catalog))
        (tmp / "secret.txt").write_text(SECRET.decode() + "\n")
        r = self.run("init", "--db", self.db, "--catalog", tmp / (name + "-cat.json"))
        if r.returncode != 0:
            raise AssertionError("init failed: %s" % r.stderr[:200])
        self.n = 0

    def run(self, *a):
        return subprocess.run([sys.executable, str(self.tool)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=300)

    def ingest(self, lines, now=T0 + 1000, *extra):
        f = self.tmp / ("%s-batch-%s.jsonl" % (self.db.stem, uuid.uuid4().hex))
        f.write_text("\n".join(lines) + "\n")
        r = self.run("ingest", "--db", self.db, "--secret-file", self.tmp / "secret.txt", "--events", f, "--now", now, "--tolerance", "100000", *extra)
        out = json.loads(r.stdout) if r.stdout.strip().startswith("{") else None
        return r.returncode, out

    def report(self):
        return json.loads(self.run("report", "--db", self.db, "--json").stdout)

    def consistent(self):
        return self.run("check", "--db", self.db).returncode == 0


def ev(eid, typ, t, **data):
    return {"id": eid, "type": typ, "created": T0 + t, "data": data}


def scenario(seed, n_orders=24):
    """A seeded store day and the oracle's own expected outcome, computed in event-time order."""
    rnd = random.Random(seed)
    skus = [{"sku": "s%d" % i, "price": c2s(rnd.randint(1, 9999)), "on_hand": 400} for i in range(5)]
    price = {s["sku"]: int(s["price"].replace(".", "")) for s in skus}
    events, want_orders, stock = [], {}, {s["sku"]: [400, 0, 0] for s in skus}  # on_hand, shipped, restocked
    t = 0
    for i in range(n_orders):
        oid = "o%d_%d" % (seed, i)
        lines = {s: rnd.randint(1, 4) for s in rnd.sample(sorted(price), rnd.randint(1, 3))}
        total = sum(price[s] * q for s, q in lines.items())
        t += rnd.randint(1, 30)
        events.append(ev("e%s_p" % oid, "order.placed", t, order_id=oid, currency="USD",
                         lines=[{"sku": s, "qty": q} for s, q in sorted(lines.items())]))
        fate = rnd.random()
        if fate < 0.2:
            t += 5
            events.append(ev("e%s_c" % oid, "order.cancelled", t, order_id=oid))
            want_orders[oid] = ("cancelled", total, 0, 0)
            continue
        if fate < 0.3:
            want_orders[oid] = ("placed", total, 0, 0)
            continue
        t += rnd.randint(1, 20)
        events.append(ev("e%s_cap" % oid, "payment.captured", t, order_id=oid, payment_id="pay_" + oid, amount=c2s(total)))
        for s, q in lines.items():
            stock[s][0] -= q
            stock[s][1] += q
        refunded, k = 0, 0
        left = dict(lines)
        while rnd.random() < 0.45 and refunded < total:
            k += 1
            amt = rnd.randint(1, total - refunded)
            rs = {s: rnd.randint(1, q) for s, q in left.items() if q and rnd.random() < 0.5}
            t += rnd.randint(1, 20)
            events.append(ev("e%s_r%d" % (oid, k), "refund.succeeded", t, order_id=oid, refund_id="re_%s_%d" % (oid, k),
                             amount=c2s(amt), restock=[{"sku": s, "qty": q} for s, q in sorted(rs.items())]))
            refunded += amt
            for s, q in rs.items():
                left[s] -= q
                stock[s][0] += q
                stock[s][2] += q
        want_orders[oid] = ("refunded" if refunded == total else "captured", total, total, refunded)
    cat = {"schema": "solaris.store-catalog/1", "currency": "USD", "skus": skus}
    return cat, events, want_orders, stock


def matches(rep, want_orders, stock):
    got = {o["id"]: (o["status"], o["total"], o["captured"], o["refunded"]) for o in rep["orders"]}
    want = {k: (s, c2s(t), c2s(c), c2s(r)) for k, (s, t, c, r) in want_orders.items()}
    gs = {s["sku"]: [s["on_hand"], s["shipped"], s["restocked"]] for s in rep["stock"]}
    cap = sum(v[2] for v in want_orders.values())
    ref = sum(v[3] for v in want_orders.values())
    bad = [k for k in want if got.get(k) != want[k]][:3] + [s for s in stock if gs.get(s) != stock[s]][:3]
    if rep["money"]["captured"] != c2s(cap) or rep["money"]["refunded"] != c2s(ref) or rep["net_cash"] != c2s(cap - ref):
        bad.append("money %s net %s want %s/%s" % (rep["money"], rep["net_cash"], c2s(cap), c2s(ref)))
    if set(got) != set(want):
        bad.append("order set differs (%d vs %d)" % (len(got), len(want)))
    return bad


class Oracle:
    def __init__(self, tool, seeds):
        self.tool, self.seeds, self.results = Path(tool), seeds, []
        self.tmp = Path(tempfile.mkdtemp(prefix="g22-oracle-"))

    def check(self, name, fn):
        try:
            ok, why = fn()
        except Exception as e:
            ok, why = False, "%s: %s" % (type(e).__name__, str(e)[:300])
        self.results.append(ok)
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else ": " + why))

    def ledger(self, cat, name):
        return Ledger(self.tool, self.tmp, cat, name)

    def p1_clean(self):
        cat, events, wo, st = scenario(11, 12)
        L = self.ledger(cat, "p1")
        rc, out = L.ingest([envelope(e) for e in events])
        rep = L.report()
        bad = matches(rep, wo, st)
        return rc == 0 and not bad and L.consistent() and rep["money"]["unapplied_captures"] == "0.00", "rc=%s %s" % (rc, bad)

    def p2_shuffled_replayed(self):
        fails = []
        for seed in range(1, self.seeds + 1):
            cat, events, wo, st = scenario(100 + seed)
            rnd = random.Random(seed)
            lines = [envelope(e) for e in events]
            lines += [rnd.choice(lines) for _ in range(len(lines) // 4)]
            rnd.shuffle(lines)
            L = self.ledger(cat, "p2s%d" % seed)
            half = len(lines) // 2
            L.ingest(lines[:half])
            rc, _ = L.ingest(lines[half:])
            rc2, out2 = L.ingest(lines)
            bad = matches(L.report(), wo, st)
            dup_ok = out2 and all(e["result"] == "duplicate" for e in out2["events"])
            if bad or not L.consistent() or rc != 0 or rc2 != 0 or not dup_ok:
                fails.append("seed %d rc=%s/%s dup_ok=%s %s" % (seed, rc, rc2, dup_ok, bad))
        return not fails, "; ".join(fails)

    def p3_forged_tampered_stale(self):
        cat, events, wo, st = scenario(12, 6)
        L = self.ledger(cat, "p3")
        good = [envelope(e) for e in events]
        e0 = events[0]
        tampered = json.loads(good[0]); tampered["body"] = tampered["body"].replace('"qty": ', '"qty": 1')
        wrong_key = envelope(e0, secret=b"another-secret-entirely-000000")
        rc, out = L.ingest([json.dumps(tampered), wrong_key, "not json", envelope(dict(e0, id="stale1"), t=T0 - 500000)])
        rep = L.report()
        nothing = not rep["orders"] and not rep["events"]
        ok = rc == 3 and out and out["refused"] == 4 and nothing and L.consistent()
        rc2, _ = L.ingest(good)
        return ok and rc2 == 0 and not matches(L.report(), wo, st), "rc=%s refused=%s stored=%s" % (rc, out and out["refused"], rep["events"])

    def p4_conflicting_replay(self):
        cat, events, wo, st = scenario(13, 6)
        L = self.ledger(cat, "p4")
        L.ingest([envelope(e) for e in events])
        cap = [e for e in events if e["type"] == "payment.captured"][0]
        forged = dict(cap, data=dict(cap["data"], amount="0.01"))
        rc, out = L.ingest([envelope(forged)])
        return rc == 3 and not matches(L.report(), wo, st) and L.consistent(), "rc=%s %s" % (rc, out and out["events"])

    def p5_crash_resume(self):
        cat, events, wo, st = scenario(14, 10)
        lines = [envelope(e) for e in events]
        random.Random(5).shuffle(lines)
        fails = []
        for k in (1, 3, len(lines) // 2, len(lines) - 1):
            L = self.ledger(cat, "p5k%d" % k)
            rc1, _ = L.ingest(lines, T0 + 1000, "--crash-after", str(k))
            rc2, _ = L.ingest(lines)
            bad = matches(L.report(), wo, st)
            if rc1 != 70 or rc2 != 0 or bad or not L.consistent():
                fails.append("k=%d rc=%s/%s %s" % (k, rc1, rc2, bad))
        return not fails, "; ".join(fails)

    def p6_concurrent_no_oversell(self):
        cat = {"schema": "solaris.store-catalog/1", "currency": "USD", "skus": [{"sku": "rare", "price": "5.00", "on_hand": 5}]}
        L = self.ledger(cat, "p6")
        batches = [[envelope(ev("e6_%d_%d" % (b, i), "order.placed", i, order_id="o6_%d_%d" % (b, i), currency="USD",
                                lines=[{"sku": "rare", "qty": 1}])) for i in range(6)] for b in range(3)]
        with ThreadPoolExecutor(3) as ex:
            rcs = list(ex.map(L.ingest, batches))
        rep = L.report()
        s = rep["stock"][0]
        placed = [o for o in rep["orders"] if o["status"] == "placed"]
        oos = [o for o in rep["open"] if "out_of_stock" in (o["reason"] or "")]
        ok = len(placed) == 5 and len(oos) == 13 and s["reserved"] == 5 and s["available"] == 0 and L.consistent()
        return ok, "placed=%d out_of_stock=%d stock=%s rcs=%s" % (len(placed), len(oos), s, [r[0] for r in rcs])

    def p7_exact_decimals_and_floats(self):
        cat = {"schema": "solaris.store-catalog/1", "currency": "USD", "skus": [{"sku": "dime", "price": "0.10", "on_hand": 9}]}
        L = self.ledger(cat, "p7")
        o = ev("e7p", "order.placed", 1, order_id="o7", currency="USD", lines=[{"sku": "dime", "qty": 3}])
        flt = envelope(None, t=T0 + 2, body='{"created": %d, "data": {"amount": 0.3, "order_id": "o7", "payment_id": "p7f"}, "id": "e7f", "type": "payment.captured"}' % (T0 + 2))
        three = envelope(ev("e7x", "payment.captured", 3, order_id="o7", payment_id="p7x", amount="0.300"))
        good = envelope(ev("e7c", "payment.captured", 4, order_id="o7", payment_id="p7", amount="0.30"))
        rc, out = L.ingest([envelope(o), flt, three, good])
        rep = L.report()
        res = [e["result"] for e in out["events"]] if out else None
        ok = res and res[0] == "applied" and res[1] == "refused" and res[2] in ("refused", "exception") and res[3] == "applied" \
            and rep["orders"][0]["captured"] == "0.30" and rep["money"]["unapplied_captures"] == "0.00"
        return bool(ok), "results=%s order=%s money=%s" % (res, rep["orders"], rep["money"])

    def p8_refund_limits(self):
        cat = {"schema": "solaris.store-catalog/1", "currency": "USD", "skus": [{"sku": "kit", "price": "30.00", "on_hand": 4}]}
        L = self.ledger(cat, "p8")
        E = [ev("e8p", "order.placed", 1, order_id="o8", currency="USD", lines=[{"sku": "kit", "qty": 2}]),
             ev("e8c", "payment.captured", 2, order_id="o8", payment_id="p8", amount="60.00"),
             ev("e8r1", "refund.succeeded", 3, order_id="o8", refund_id="r8a", amount="30.00", restock=[{"sku": "kit", "qty": 1}]),
             ev("e8r2", "refund.succeeded", 4, order_id="o8", refund_id="r8b", amount="30.01", restock=[]),
             ev("e8r3", "refund.succeeded", 5, order_id="o8", refund_id="r8c", amount="1.00", restock=[{"sku": "kit", "qty": 2}]),
             ev("e8r4", "refund.succeeded", 6, order_id="o8", refund_id="r8d", amount="30.00", restock=[{"sku": "kit", "qty": 1}])]
        rc, out = L.ingest([envelope(e) for e in E])
        rep = L.report()
        s = rep["stock"][0]
        res = [e["result"] for e in out["events"]]
        ok = (rc == 1 and res == ["applied", "applied", "applied", "exception", "exception", "applied"] and rep["orders"][0]["refunded"] == "60.00"
              and rep["orders"][0]["status"] == "refunded" and (s["on_hand"], s["shipped"], s["restocked"]) == (4, 2, 2)
              and rep["money"]["unapplied_refunds"] == "31.01" and L.consistent())
        return ok, "rc=%s results=%s order=%s stock=%s money=%s" % (rc, res, rep["orders"], s, rep["money"])

    def p9_held_until_ready(self):
        cat = {"schema": "solaris.store-catalog/1", "currency": "USD", "skus": [{"sku": "box", "price": "7.25", "on_hand": 3}]}
        L = self.ledger(cat, "p9")
        p = ev("e9p", "order.placed", 1, order_id="o9", currency="USD", lines=[{"sku": "box", "qty": 2}])
        c = ev("e9c", "payment.captured", 2, order_id="o9", payment_id="p9", amount="14.50")
        r = ev("e9r", "refund.succeeded", 3, order_id="o9", refund_id="r9", amount="7.25", restock=[{"sku": "box", "qty": 1}])
        rc1, o1 = L.ingest([envelope(r)])
        rc2, o2 = L.ingest([envelope(c)])
        mid = L.report()
        rc3, o3 = L.ingest([envelope(p)])
        rep = L.report()
        s = rep["stock"][0]
        ok = (rc1 == 1 and rc2 == 1 and not mid["orders"] and rc3 == 0 and rep["orders"][0]["refunded"] == "7.25"
              and (s["on_hand"], s["shipped"], s["restocked"], s["reserved"]) == (2, 2, 1, 0) and not rep["open"] and L.consistent())
        return ok, "rc=%s/%s/%s final=%s stock=%s open=%s" % (rc1, rc2, rc3, rep["orders"], s, rep["open"])

    def p10_g14_reconciles(self):
        fails = []
        for seed in (21, 22):
            cat, events, wo, st = scenario(seed)
            L = self.ledger(cat, "p10s%d" % seed)
            L.ingest([envelope(e) for e in events])
            out = self.tmp / ("g14-%d" % seed)
            r = L.run("export-g14", "--db", L.db, "--out", out, "--period-start", "2026-10-01T00:00:00Z", "--period-end", "2026-11-01T00:00:00Z")
            g = subprocess.run([sys.executable, str(G14), "reconcile", str(out / "package.json"), "--json"], capture_output=True, text=True, env=ENV)
            cap = sum(v[2] for v in wo.values()); ref = sum(v[3] for v in wo.values())
            try:
                c = json.loads(g.stdout)["currencies"]["USD"]
            except Exception:
                c = {}
            if r.returncode != 0 or g.returncode != 0 or c.get("net_cash") != c2s(cap - ref) or c.get("recognized_revenue") != c2s(cap - ref):
                fails.append("seed %d export rc=%s g14 rc=%s net=%s rev=%s want %s" % (seed, r.returncode, g.returncode, c.get("net_cash"),
                                                                                     c.get("recognized_revenue"), c2s(cap - ref)))
        return not fails, "; ".join(fails)

    def run(self):
        if not self.tool.is_file():
            print("FAIL tool: %s does not exist" % self.tool)
            print("REJECTED 0/1")
            return 1
        try:
            self.check("p1 clean control: in-order day matches the reference model", self.p1_clean)
            self.check("p2 shuffled, replayed, split deliveries: same outcome, replays are duplicates", self.p2_shuffled_replayed)
            self.check("p3 tampered, wrong-key, malformed and stale envelopes store nothing", self.p3_forged_tampered_stale)
            self.check("p4 same id with a different body is refused, original kept", self.p4_conflicting_replay)
            self.check("p5 crash after k events, rerun the whole batch: same outcome", self.p5_crash_resume)
            self.check("p6 three concurrent ingests never oversell", self.p6_concurrent_no_oversell)
            self.check("p7 exact decimals; floats and 3-place amounts never applied", self.p7_exact_decimals_and_floats)
            self.check("p8 partial refunds to the cent; over-refund and over-restock are exceptions", self.p8_refund_limits)
            self.check("p9 refund and capture before their order are held, then applied", self.p9_held_until_ready)
            self.check("p10 export reconciles in G14 to the ledger's net cash", self.p10_g14_reconciles)
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)
        n, m = sum(self.results), len(self.results)
        print("%s %d/%d" % ("PASSED" if n == m else "REJECTED", n, m))
        return 0 if n == m else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(DEFAULT_TOOL))
    ap.add_argument("--seeds", type=int, default=4)
    a = ap.parse_args()
    sys.exit(Oracle(a.tool, a.seeds).run())
