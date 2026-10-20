"""G22: signed-webhook order ledger (employees/specialized/payments-specialist/payment_ledger.py).
Real processes and SQLite files; the shipped september stream's figures are worked by hand in the README."""
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "employees" / "specialized" / "payments-specialist" / "payment_ledger.py"
G14 = ROOT / "employees" / "leadership" / "cfo" / "cash_revenue_reconcile.py"
EX = ROOT / "examples" / "capabilities" / "G22"
FIX = EX / "fixtures"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
SECRET = (FIX / "test-secret.txt").read_text().strip().encode()
NOW = 1790000200


def run(*a, timeout=300):
    return subprocess.run([sys.executable] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=timeout)


def env(ev, t=None, body=None):
    body = body or json.dumps(ev, sort_keys=True)
    t = ev["created"] if t is None else t
    return json.dumps({"signature": "t=%d,v1=%s" % (t, hmac.new(SECRET, ("%d." % t).encode() + body.encode(), hashlib.sha256).hexdigest()), "body": body})


def ev(eid, typ, dt, **data):
    return {"id": eid, "type": typ, "created": NOW + dt, "data": data}


class G22Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g22-test-"))
        self.db = self.tmp / "ledger.db"
        r = run(TOOL, "init", "--db", self.db, "--catalog", FIX / "catalog.json")
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ingest(self, path_or_lines, *extra, now=NOW):
        if isinstance(path_or_lines, list):
            p = self.tmp / ("batch-%d.jsonl" % len(list(self.tmp.iterdir())))
            p.write_text("\n".join(path_or_lines) + "\n")
        else:
            p = path_or_lines
        r = run(TOOL, "ingest", "--db", self.db, "--secret-file", FIX / "test-secret.txt", "--events", p, "--now", now, *extra)
        return r.returncode, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else None)

    def report(self):
        return json.loads(run(TOOL, "report", "--db", self.db, "--json").stdout)

    def check(self, db=None):
        return run(TOOL, "check", "--db", db or self.db)

    def test_september_stream_figures(self):
        rc, out = self.ingest(FIX / "september.jsonl")
        self.assertEqual(rc, 3)
        res = [(e.get("id"), e["result"]) for e in out["events"]]
        self.assertEqual(res[2], ("evt_002", "duplicate"))
        self.assertEqual([r for r in res if r[1] == "refused"], [(None, "refused"), (None, "refused")])
        self.assertEqual([e["reason"] for e in out["events"] if e["result"] == "refused"], ["bad_signature", "timestamp_outside_tolerance"])
        r = self.report()
        self.assertEqual(r["money"], {"captured": "45.29", "refunded": "12.60", "unapplied_captures": "0.00", "unapplied_refunds": "40.00",
                                      "closed_unapplied_captures": "0.00", "closed_unapplied_refunds": "0.00"})
        self.assertEqual(r["net_cash"], "32.69")
        st = {s["sku"]: (s["on_hand"], s["reserved"], s["shipped"], s["restocked"]) for s in r["stock"]}
        self.assertEqual(st, {"mug-blue": (9, 0, 2, 1), "poster": (1, 0, 3, 1), "tee-m": (3, 0, 1, 0)})
        self.assertEqual([(o["id"], o["state"], o["reason"].split()[0]) for o in r["open"]],
                         [("evt_007", "exception", "refund_exceeds_captured"), ("evt_008", "exception", "out_of_stock")])
        self.assertEqual({o["id"]: o["status"] for o in r["orders"]}, {"ord_1": "captured", "ord_2": "captured", "ord_4": "cancelled"})
        self.assertEqual(self.check().returncode, 0)

    def test_replay_of_the_whole_stream_changes_nothing(self):
        self.ingest(FIX / "september.jsonl")
        before = self.report()
        rc, out = self.ingest(FIX / "september.jsonl")
        self.assertEqual(rc, 3)
        self.assertTrue(all(e["result"] in ("duplicate", "refused") for e in out["events"]))
        self.assertEqual(self.report(), before)

    def test_signature_tamper_wrong_secret_and_tolerance(self):
        e = ev("t1", "order.placed", 0, order_id="o1", currency="USD", lines=[{"sku": "mug-blue", "qty": 1}])
        good = json.loads(env(e))
        tampered = dict(good, body=good["body"].replace('"qty": 1', '"qty": 9'))
        other = json.dumps({"signature": "t=%d,v1=%s" % (e["created"], hmac.new(b"some-other-secret-0000", ("%d." % e["created"]).encode()
                            + good["body"].encode(), hashlib.sha256).hexdigest()), "body": good["body"]})
        rc, out = self.ingest([json.dumps(tampered), other, env(e, t=NOW - 301)])
        self.assertEqual((rc, out["refused"]), (3, 3))
        self.assertEqual(self.report()["events"], {})
        rc, out = self.ingest([env(e, t=NOW - 300)])
        self.assertEqual((rc, out["events"][0]["result"]), (0, "applied"))
        rc, out = self.ingest([env(dict(e, data=dict(e["data"], lines=[{"sku": "mug-blue", "qty": 2}])))])
        self.assertEqual(rc, 3)
        self.assertIn("conflicting_replay", out["events"][0]["reason"])
        self.assertEqual(self.report()["stock"][0]["reserved"], 1)

    def test_exact_amounts_and_float_refusal(self):
        rc, out = self.ingest([env(ev("d1", "order.placed", 0, order_id="o1", currency="USD", lines=[{"sku": "poster", "qty": 3}])),
                               env(None, t=NOW + 1, body='{"created": %d, "data": {"amount": 0.3, "order_id": "o1", "payment_id": "pf"}, "id": "df", "type": "payment.captured"}' % (NOW + 1)),
                               env(ev("d2", "payment.captured", 2, order_id="o1", payment_id="p1", amount="0.29")),
                               env(ev("d3", "payment.captured", 3, order_id="o1", payment_id="p2", amount="0.30"))])
        res = [(e.get("id"), e["result"]) for e in out["events"]]
        self.assertEqual(res, [("d1", "applied"), (None, "refused"), ("d2", "exception"), ("d3", "applied")])
        r = self.report()
        self.assertEqual((r["money"]["captured"], r["money"]["unapplied_captures"]), ("0.30", "0.29"))
        self.assertIn("capture_amount_mismatch (order 0.30, captured 0.29)", r["open"][0]["reason"])
        self.assertEqual(self.check().returncode, 0)

    def test_out_of_order_events_are_held_then_applied(self):
        p = ev("h1", "order.placed", 0, order_id="o1", currency="USD", lines=[{"sku": "tee-m", "qty": 2}])
        c = ev("h2", "payment.captured", 1, order_id="o1", payment_id="p1", amount="39.98")
        r = ev("h3", "refund.succeeded", 2, order_id="o1", refund_id="r1", amount="19.99", restock=[{"sku": "tee-m", "qty": 1}])
        x = ev("h4", "order.cancelled", 3, order_id="o2")
        rc, out = self.ingest([env(r), env(c), env(x)])
        self.assertEqual(rc, 1)
        self.assertEqual([e["result"] for e in out["events"]], ["held", "held", "held"])
        rc, out = self.ingest([env(p)])
        self.assertEqual(rc, 1)  # the cancel for an order never placed stays held, named
        rep = self.report()
        self.assertEqual(rep["orders"], [{"id": "o1", "status": "captured", "total": "39.98", "captured": "39.98", "refunded": "19.99"}])
        self.assertEqual([(o["id"], o["state"]) for o in rep["open"]], [("h4", "held")])
        tee = [s for s in rep["stock"] if s["sku"] == "tee-m"][0]
        self.assertEqual((tee["on_hand"], tee["shipped"], tee["restocked"], tee["reserved"]), (3, 2, 1, 0))

    def test_refund_and_restock_limits(self):
        E = [ev("r0", "order.placed", 0, order_id="o1", currency="USD", lines=[{"sku": "mug-blue", "qty": 2}]),
             ev("r1", "payment.captured", 1, order_id="o1", payment_id="p1", amount="25.00"),
             ev("r2", "refund.succeeded", 2, order_id="o1", refund_id="x1", amount="10.00", restock=[{"sku": "mug-blue", "qty": 1}]),
             ev("r3", "refund.succeeded", 3, order_id="o1", refund_id="x2", amount="15.01", restock=[]),
             ev("r4", "refund.succeeded", 4, order_id="o1", refund_id="x3", amount="1.00", restock=[{"sku": "mug-blue", "qty": 2}]),
             ev("r5", "refund.succeeded", 5, order_id="o1", refund_id="x1", amount="1.00", restock=[]),
             ev("r6", "refund.succeeded", 6, order_id="o1", refund_id="x4", amount="15.00", restock=[{"sku": "mug-blue", "qty": 1}]),
             ev("r7", "order.cancelled", 7, order_id="o1"),
             ev("r8", "order.placed", 8, order_id="o2", currency="USD", lines=[{"sku": "poster", "qty": 1}]),
             ev("r9", "order.cancelled", 9, order_id="o2"),
             ev("r10", "payment.captured", 10, order_id="o2", payment_id="p2", amount="0.10")]
        rc, out = self.ingest([env(e) for e in E])
        self.assertEqual([e["result"] for e in out["events"]], ["applied", "applied", "applied", "exception", "exception", "exception", "applied", "exception",
                                                                 "applied", "applied", "exception"])
        self.assertEqual(out["events"][10]["reason"], "capture_on_cancelled_order")
        self.assertIn("refund_id_already_recorded", out["events"][5]["reason"])
        self.assertIn("cannot_cancel_refunded_order", out["events"][7]["reason"])
        rep = self.report()
        self.assertEqual(rep["orders"][0]["status"], "refunded")
        self.assertEqual((rep["net_cash"], rep["money"]["unapplied_refunds"], rep["money"]["unapplied_captures"]), ("0.00", "16.01", "0.10"))
        mug = [s for s in rep["stock"] if s["sku"] == "mug-blue"][0]
        self.assertEqual((mug["on_hand"], mug["shipped"], mug["restocked"]), (10, 2, 2))
        self.assertEqual(self.check().returncode, 0)

    def test_concurrent_ingests_never_oversell(self):
        batches = []
        for b in range(8):
            p = self.tmp / ("c%d.jsonl" % b)
            p.write_text("\n".join(env(ev("c%d_%d" % (b, i), "order.placed", i, order_id="oc%d_%d" % (b, i), currency="USD",
                                          lines=[{"sku": "tee-m", "qty": 1}])) for i in range(4)) + "\n")
            batches.append(p)
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(self.ingest, batches))
        rcs = [r[0] for r in res]
        self.assertTrue(all(r[1] is not None for r in res), "an ingest died: %s" % rcs)
        self.assertTrue(all(rc in (0, 1) for rc in rcs), rcs)
        rep = self.report()
        tee = [s for s in rep["stock"] if s["sku"] == "tee-m"][0]
        self.assertEqual((tee["reserved"], tee["available"]), (4, 0))
        self.assertEqual(rep["events"], {"applied": 4, "exception": 28})
        self.assertEqual(self.check().returncode, 0)

    def test_crash_mid_batch_then_rerun(self):
        rc, _ = self.ingest(FIX / "september.jsonl", "--crash-after", "6")
        self.assertEqual(rc, 70)
        self.ingest(FIX / "september.jsonl")
        self.assertEqual(self.report()["net_cash"], "32.69")
        self.assertEqual(self.check().returncode, 0)

    def test_export_refuses_open_exceptions(self):
        # G30 x2 finding (needs affected recheck): with evt_007 (unapplied 40.00 refund) and evt_008
        # (out-of-stock order) open, export-g14 exited 0 and G14 reconciled the rest as clean.
        self.ingest(FIX / "september.jsonl")
        out = self.tmp / "g14open"
        r = run(TOOL, "export-g14", "--db", self.db, "--out", out, "--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse(out.exists())
        doc = json.loads(r.stdout)
        self.assertEqual([e["id"] for e in doc["open"]], ["evt_007", "evt_008"])
        self.assertEqual(doc["unapplied_money"], [{"amount": "40.00", "event_id": "evt_007", "kind": "refund"}])
        self.assertIn("evt_007,evt_008", r.stderr)

    def test_export_refuses_unapplied_money_alone(self):
        # defence in depth: an unapplied money row blocks export even if no event is marked open
        self.ingest(FIX / "september.jsonl")
        con = sqlite3.connect(str(self.db))
        con.execute("UPDATE events SET state = 'applied' WHERE id IN ('evt_007', 'evt_008')")
        con.commit(); con.close()
        out = self.tmp / "g14money"
        r = run(TOOL, "export-g14", "--db", self.db, "--out", out, "--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["open"], [])
        self.assertFalse(out.exists())

    def test_export_refuses_held_events(self):
        lines = [l for l in (FIX / "september.jsonl").read_text().splitlines() if l.strip()]
        held = self.tmp / "held.jsonl"
        held.write_text("\n".join(l for l in lines if json.loads(json.loads(l)["body"])["type"] != "order.placed") + "\n")
        self.ingest(held)
        self.assertTrue(any(o["state"] == "held" for o in self.report()["open"]))
        out = self.tmp / "g14held"
        r = run(TOOL, "export-g14", "--db", self.db, "--out", out, "--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse(out.exists())

    def test_export_reconciles_in_g14(self):
        lines = (FIX / "september.jsonl").read_text().splitlines()
        clean = self.tmp / "clean.jsonl"
        clean.write_text("\n".join(l for l in lines if l.strip() and json.loads(json.loads(l)["body"])["id"] not in ("evt_007", "evt_008")) + "\n")
        self.ingest(clean)
        self.assertEqual(self.report()["open"], [])
        out = self.tmp / "g14"
        r = run(TOOL, "export-g14", "--db", self.db, "--out", out, "--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
        self.assertEqual(r.returncode, 0, r.stderr)
        g = run(G14, "reconcile", out / "package.json", "--json")
        self.assertEqual(g.returncode, 0, g.stdout[-800:])
        c = json.loads(g.stdout)["currencies"]["USD"]
        self.assertEqual((c["net_cash"], c["recognized_revenue"], c["closing"]["ar_net"]), ("32.69", "32.69", "0.00"))
        self.assertEqual(run(TOOL, "export-g14", "--db", self.db, "--out", out, "--period-start", "x", "--period-end", "y").returncode, 2)

    def test_check_names_tampering_and_bad_inputs(self):
        self.ingest(FIX / "september.jsonl")
        for sql, needle in (("UPDATE skus SET on_hand = on_hand + 1 WHERE sku = 'mug-blue'", "initial 10 != on_hand"),
                            ("UPDATE orders SET refunded_cents = 0 WHERE id = 'ord_1'", "differ from money rows"),
                            ("UPDATE skus SET reserved = 1, on_hand = on_hand + 1, initial = initial + 1 WHERE sku = 'poster'", "open order quantity"),
                            ("UPDATE money SET applied = 1 WHERE event_id = 'evt_007'", "does not match the event state")):
            with self.subTest(sql=sql):
                c = self.tmp / "copy.db"
                for ext in ("", "-wal", "-shm"):
                    if Path(str(self.db) + ext).exists():
                        shutil.copy(str(self.db) + ext, str(c) + ext)
                con = sqlite3.connect(str(c)); con.execute(sql); con.commit(); con.close()
                r = self.check(c)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(needle, r.stdout)
                for ext in ("", "-wal", "-shm"):
                    if Path(str(c) + ext).exists():
                        Path(str(c) + ext).unlink()
        bad_cat = self.tmp / "cat.json"
        for cat in ({"schema": "solaris.store-catalog/1", "currency": "USD", "skus": [{"sku": "a", "price": 1.5, "on_hand": 1}]},
                    {"schema": "solaris.store-catalog/1", "currency": "USD", "skus": [{"sku": "a", "price": "1.505", "on_hand": 1}]},
                    {"schema": "solaris.store-catalog/1", "currency": "JPY", "skus": [{"sku": "a", "price": "1.50", "on_hand": 1}]}):
            bad_cat.write_text(json.dumps(cat))
            self.assertEqual(run(TOOL, "init", "--db", self.tmp / "n.db", "--catalog", bad_cat).returncode, 2)
        self.assertEqual(run(TOOL, "init", "--db", self.db, "--catalog", FIX / "catalog.json").returncode, 2)

    # G22 h2: open events are resolved on the record (M22 h1 P3: an exception could never be cleared)
    def resolve(self, eid, action, *extra, by="Shai A", note="checked with the provider"):
        r = run(TOOL, "resolve", "--db", self.db, "--event", eid, "--action", action, "--by", by, "--note", note, "--now", NOW + 900, *extra)
        return r.returncode, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else None), r.stderr

    def export(self, name):
        out = self.tmp / name
        r = run(TOOL, "export-g14", "--db", self.db, "--out", out, "--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
        return r, out

    def test_close_resolves_exceptions_and_books_then_export(self):
        self.ingest(FIX / "september.jsonl")
        rc, doc, _ = self.resolve("evt_008", "close", note="out of stock, customer told, never charged")
        self.assertEqual((rc, doc["money_closed"], doc["open_now"]), (0, None, 1))
        r, out = self.export("still-open")
        self.assertEqual(r.returncode, 1)
        self.assertEqual([e["id"] for e in json.loads(r.stdout)["open"]], ["evt_007"])
        before = self.report()
        rc, _, err = self.resolve("evt_007", "close")
        self.assertEqual(rc, 2)
        self.assertIn("unapplied refund 40.00", err)
        self.assertEqual(self.report(), before)
        rc, doc, _ = self.resolve("evt_007", "close", "--reference", "provider case PC-1001", note="provider reversed the 40.00 refund")
        self.assertEqual((rc, doc["money_closed"], doc["open_now"], doc["unapplied_money_now"]), (0, {"amount": "40.00", "kind": "refund"}, 0, 0))
        rep = self.report()
        self.assertEqual((rep["net_cash"], rep["money"]["unapplied_refunds"], rep["money"]["closed_unapplied_refunds"]), ("32.69", "0.00", "40.00"))
        self.assertEqual(rep["open"], [])
        self.assertEqual([(x["event_id"], x["action"], x["prior_state"], x["resolved_by"], x["reference"], x["amount"]) for x in rep["resolutions"]],
                         [("evt_008", "close", "exception", "Shai A", None, None), ("evt_007", "close", "exception", "Shai A", "provider case PC-1001", "40.00")])
        self.assertTrue(rep["resolutions"][1]["prior_reason"].startswith("refund_exceeds_captured"))
        self.assertEqual(self.check().returncode, 0)
        r, out = self.export("books")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["closed_money_not_in_books"],
                         [{"amount": "40.00", "event_id": "evt_007", "money_kind": "refund", "reference": "provider case PC-1001", "superseded_by": None}])
        g = run(G14, "reconcile", out / "package.json", "--json")
        c = json.loads(g.stdout)["currencies"]["USD"]
        self.assertEqual((g.returncode, c["net_cash"], c["recognized_revenue"]), (0, "32.69", "32.69"))
        # re-delivering a closed event is a duplicate and does not reopen it
        rc, out2 = self.ingest(FIX / "september.jsonl")
        self.assertEqual(out2["open_held_or_exceptions"], 0)
        self.assertEqual([e["state"] for e in out2["events"] if e.get("id") == "evt_007"], ["resolved"])

    def test_retry_applies_once_the_block_is_gone(self):
        a = ev("r_1", "order.placed", 0, order_id="oa", currency="USD", lines=[{"sku": "tee-m", "qty": 3}])
        b = ev("r_2", "order.placed", 10, order_id="ob", currency="USD", lines=[{"sku": "tee-m", "qty": 2}])
        pay = ev("r_3", "payment.captured", 20, order_id="ob", payment_id="p_ob", amount="39.98")
        self.ingest([env(a), env(b), env(pay)])
        rep = self.report()
        self.assertEqual({o["id"]: o["state"] for o in rep["open"]}, {"r_2": "exception", "r_3": "held"})
        rc, doc, err = self.resolve("r_2", "retry")
        self.assertEqual((rc, doc["resolved"], doc["state"]), (1, False, "exception"))
        self.assertIn("nothing changed", err)
        self.assertEqual(self.report(), rep)
        self.ingest([env(ev("r_4", "order.cancelled", 30, order_id="oa"))])
        rc, doc, _ = self.resolve("r_2", "retry", note="stock released by the cancel of oa")
        self.assertEqual((rc, doc["open_now"]), (0, 0))
        rep = self.report()
        self.assertEqual({o["id"]: o["status"] for o in rep["orders"]}, {"oa": "cancelled", "ob": "captured"})
        self.assertEqual((rep["money"]["captured"], [s["shipped"] for s in rep["stock"] if s["sku"] == "tee-m"]), ("39.98", [2]))
        self.assertEqual([(x["event_id"], x["action"]) for x in rep["resolutions"]], [("r_2", "retry")])
        self.assertEqual(self.check().returncode, 0)

    def test_close_superseded_by_a_redelivered_event(self):
        o = ev("s_1", "order.placed", 0, order_id="os", currency="USD", lines=[{"sku": "mug-blue", "qty": 1}])
        bad = ev("s_2", "payment.captured", 10, order_id="os", payment_id="p_bad", amount="12.00")
        other = ev("s_9", "order.placed", 5, order_id="ot", currency="USD", lines=[{"sku": "poster", "qty": 1}])
        self.ingest([env(o), env(bad), env(other)])
        for sup in ("s_2", "s_404", "s_9"):
            rc, _, err = self.resolve("s_2", "close", "--superseded-by", sup)
            self.assertEqual(rc, 2, (sup, err))
        good = ev("s_3", "payment.captured", 20, order_id="os", payment_id="p_good", amount="12.50")
        self.ingest([env(good)])
        rc, doc, _ = self.resolve("s_2", "close", "--superseded-by", "s_3", note="provider re-delivered the capture with the right amount")
        self.assertEqual((rc, doc["money_closed"]), (0, {"amount": "12.00", "kind": "capture"}))
        rep = self.report()
        self.assertEqual((rep["money"]["captured"], rep["money"]["unapplied_captures"], rep["money"]["closed_unapplied_captures"]), ("12.50", "0.00", "12.00"))
        self.assertEqual(rep["resolutions"][0]["superseded_by"], "s_3")
        self.assertEqual(self.check().returncode, 0)

    def test_resolve_refusals_and_tampering(self):
        self.ingest(FIX / "september.jsonl")
        before = self.report()
        for args in (("evt_404", "close"), ("evt_001", "close"), ("evt_008", "retry", "--reference", "x"),
                     ("evt_007", "close", "--reference", "a", "--superseded-by", "evt_006"), ("evt_007", "close", "--reference", " ")):
            rc, _, err = self.resolve(*args)
            self.assertEqual(rc, 2, (args, err))
        rc, doc, _ = self.resolve("evt_007", "retry")
        self.assertEqual((rc, doc["state"]), (1, "exception"))
        self.assertTrue(doc["reason"].startswith("refund_exceeds_captured"), doc)
        self.assertEqual(self.resolve("evt_008", "close", by=" ")[0], 2)
        self.assertEqual(self.resolve("evt_008", "close", note="")[0], 2)
        self.assertEqual(self.report(), before)
        self.assertEqual(self.resolve("evt_008", "close")[0], 0)
        self.assertEqual(self.resolve("evt_008", "close")[0], 2)
        self.assertEqual(self.resolve("evt_007", "close", "--reference", "case 7")[0], 0)
        for sql, needle in (("DELETE FROM resolutions WHERE event_id = 'evt_008'", "resolved event evt_008 has no close record"),
                            ("UPDATE events SET state = 'exception' WHERE id = 'evt_008'", "resolution of evt_008 (close) does not match"),
                            ("UPDATE resolutions SET money_cents = 100 WHERE event_id = 'evt_007'", "closed money of evt_007 differs"),
                            ("UPDATE resolutions SET reference = NULL WHERE event_id = 'evt_007'", "closed money of evt_007 has no reference")):
            with self.subTest(sql=sql):
                c = self.tmp / "copy.db"
                for ext in ("", "-wal", "-shm"):
                    if Path(str(self.db) + ext).exists():
                        shutil.copy(str(self.db) + ext, str(c) + ext)
                con = sqlite3.connect(str(c)); con.execute(sql); con.commit(); con.close()
                r = self.check(c)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(needle, r.stdout)
                for ext in ("", "-wal", "-shm"):
                    if Path(str(c) + ext).exists():
                        Path(str(c) + ext).unlink()

    def test_ledger_made_before_resolve_still_works(self):
        self.ingest(FIX / "september.jsonl")
        con = sqlite3.connect(str(self.db)); con.execute("DROP TABLE resolutions"); con.commit(); con.close()
        self.assertEqual(self.report()["resolutions"], [])
        self.assertEqual(self.check().returncode, 0)
        self.assertEqual(self.resolve("evt_008", "close")[0], 0)
        self.assertEqual([x["event_id"] for x in self.report()["resolutions"]], ["evt_008"])

    def test_doc_and_contract_match(self):
        doc = (ROOT / "employees" / "specialized" / "payments-specialist" / "webhook-ledger.md").read_text()
        for cmd in ("init", "sign", "ingest", "report", "check", "export-g14", "resolve"):
            self.assertIn("payment_ledger.py %s" % cmd, doc)
        for code in ("0", "1", "2", "3", "70"):
            self.assertIn("| %s |" % code, doc)
        for word in ("--action retry", "--action close", "--reference", "--superseded-by", "closed_unapplied_refunds"):
            self.assertIn(word, doc)
        c = json.loads((ROOT / "employees" / "specialized" / "payments-specialist" / "capability.contract.json").read_text())
        self.assertIn("payment_ledger.py", c["dependencies"]["scripts"])
        self.assertIn("webhook-ledger.md", c["dependencies"]["references"])

    def test_oracle_passes_the_tool_and_rejects_the_controls(self):
        r = run(EX / "ledger_oracle.py", "--seeds", "2")
        self.assertEqual(r.stdout.strip().splitlines()[-1], "PASSED 10/10", r.stdout[-1500:])
        for ctl, want in (("naive_ledger.py", "REJECTED 5/10"), ("noop_ledger.py", "REJECTED 0/10")):
            r = run(EX / "ledger_oracle.py", "--seeds", "2", "--tool", EX / ctl)
            self.assertEqual((r.returncode, r.stdout.strip().splitlines()[-1]), (1, want))


if __name__ == "__main__":
    unittest.main()
