#!/usr/bin/env python3
"""M22 h2 probe (Grok self-validation, not independent review). Black-box checks of the G22 h2 resolve command, with
cases written for this pass: the shipped september fixture plus events this probe signs itself with the fixture test
secret. Usage: PY m22h2_probe.py SRC OUT.json [--old-tool PATH_TO_8bc3553_payment_ledger.py]"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile
from pathlib import Path
SRC = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]; ROWS = []
OLD = Path(sys.argv[sys.argv.index("--old-tool") + 1]).resolve() if "--old-tool" in sys.argv else None
TOOL = SRC / "employees/specialized/payments-specialist/payment_ledger.py"
G14 = SRC / "employees/leadership/cfo/cash_revenue_reconcile.py"
FIX = SRC / "examples/capabilities/G22/fixtures"; SECRET = FIX / "test-secret.txt"
LINES = [l for l in (FIX / "september.jsonl").read_text().splitlines() if l.strip()]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
NOW = "1790000200"
SEP = ("--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z")
NOV = ("--period-start", "2026-11-01T00:00:00Z", "--period-end", "2026-12-01T00:00:00Z")
def eid(l): return json.loads(json.loads(l)["body"])["id"]
def run(*a, tool=TOOL):
    p = subprocess.run([sys.executable, str(tool)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=300)
    return p.returncode, p.stdout, p.stderr
def js(s):
    try: return json.loads(s)
    except ValueError: return None
class L:
    def __init__(self, tool=TOOL):
        self.d = Path(tempfile.mkdtemp(prefix="m22h2-")); self.db = self.d / "l.db"; self.n = 0
        assert run("init", "--db", self.db, "--catalog", FIX / "catalog.json", tool=tool)[0] == 0
    def sign(self, body):
        self.n += 1; b = self.d / ("body%d.json" % self.n); b.write_text(json.dumps(body, sort_keys=True, separators=(",", ":")))
        rc, o, e = run("sign", "--secret-file", SECRET, "--body-file", b, "--t", NOW); assert rc == 0, e
        return o.strip()
    def ingest(self, lines, tool=TOOL):
        self.n += 1; p = self.d / ("b%d.jsonl" % self.n); p.write_text("\n".join(lines) + "\n")
        return run("ingest", "--db", self.db, "--secret-file", SECRET, "--events", p, "--now", NOW, tool=tool)[0]
    def resolve(self, ev, action, *extra, by="Probe Operator", note="probe note"):
        rc, o, e = run("resolve", "--db", self.db, "--event", ev, "--action", action, "--by", by, "--note", note, "--now", "1790001000", *extra)
        return rc, js(o), e
    def export(self, name, period=SEP):
        out = self.d / name; rc, o, e = run("export-g14", "--db", self.db, "--out", out, *period)
        return rc, out, js(o), e
    def report(self):
        rc, o, e = run("report", "--db", self.db, "--json"); return rc, js(o) or {}
    def check(self):
        rc, o, e = run("check", "--db", self.db); return rc, o + e
    def q(self, sql, args=()):
        c = sqlite3.connect(str(self.db))
        try:
            r = c.execute(sql, args).fetchall(); c.commit(); return r
        finally: c.close()
    def state(self, ev): return (self.q("SELECT state FROM events WHERE id = ?", (ev,)) or [[None]])[0][0]
    def nres(self):
        try: return self.q("SELECT COUNT(*) FROM resolutions")[0][0]
        except sqlite3.OperationalError: return None
    def close(self): shutil.rmtree(self.d, ignore_errors=True)
def row(rid, desc, ok, detail):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "detail": detail})
    print("%s %s %s %s" % (rid, "PASS" if ok else "FAIL", desc, json.dumps(detail, default=str)[:300]))
def g14(out):
    g = run("reconcile", out / "package.json", "--json", tool=G14)
    return g[0], (json.loads(g[1])["currencies"]["USD"] if g[0] == 0 else {})
def guard(rid, desc, fn):
    try: fn()
    except Exception as e: row(rid, desc, False, {"error": "%s: %s" % (type(e).__name__, e)})

def r1():
    l = L(); l.ingest(LINES)
    a = l.resolve("evt_008", "close", note="customer told, order dropped")
    b = l.resolve("evt_007", "close", "--reference", "provider case 77", note="refund paid by the provider outside the store")
    rn, outn, jn, en = l.export("nov", NOV)
    rs, outs, jsep, es = l.export("sep", SEP)
    gc, c = g14(outs) if rs == 0 else (None, {})
    rr, rep = l.report()
    closed = (rep.get("money") or {}).get("closed_unapplied_refunds"); res = rep.get("resolutions") or []
    listed = json.dumps(jsep or {}).count("40.00") > 0 if jsep else ("40.00" in str(jsep))
    row("R1", "close evt_008 (note) and evt_007 (reference): November and September export exit 0, G14 32.69, closed 40.00 refund reported and listed at export, 2 audit rows with who/why",
        a[0] == 0 and b[0] == 0 and rn == 0 and rs == 0 and gc == 0 and c.get("net_cash") == "32.69" and closed == "40.00" and rep.get("net_cash") == "32.69" and len(res) == 2
        and all(x.get("resolved_by") == "Probe Operator" for x in res) and "provider case 77" in json.dumps(res) and listed and l.check()[0] == 0,
        {"close": [a[0], b[0]], "rc_nov": rn, "rc_sep": rs, "g14": gc, "net_cash": c.get("net_cash"), "closed": closed, "report_net_cash": rep.get("net_cash"), "res": res, "export_stdout": jsep})
    # R2 second resolve of the same event is refused and adds no audit row
    d = l.resolve("evt_007", "close", "--reference", "again"); e = l.resolve("evt_007", "retry")
    row("R2", "double resolve (close again, then retry) of a resolved event: exit 2 both, still 2 audit rows, state resolved",
        d[0] == 2 and e[0] == 2 and l.nres() == 2 and l.state("evt_007") == "resolved", {"rc": [d[0], e[0]], "n": l.nres(), "state": l.state("evt_007")})
    # R8 re-delivery of a closed event stays a duplicate and the books stay exportable
    ri = l.ingest([x for x in LINES if eid(x) == "evt_007"]); r2, _, _, _ = l.export("sep2", SEP)
    row("R8", "re-delivering closed evt_007: ingest exit 0 (duplicate), state stays resolved, export still exit 0",
        ri == 0 and l.state("evt_007") == "resolved" and r2 == 0, {"ingest": ri, "state": l.state("evt_007"), "export": r2})
    # R6 tampering after resolve
    snap = l.d / "snap.db"; shutil.copy(l.db, snap)
    t = {}
    l.q("DELETE FROM resolutions WHERE event_id = 'evt_007'"); t["record_deleted"] = l.check(); shutil.copy(snap, l.db)
    l.q("UPDATE resolutions SET money_cents = 100 WHERE event_id = 'evt_007'"); t["amount_changed"] = l.check(); shutil.copy(snap, l.db)
    l.q("UPDATE resolutions SET reference = NULL, superseded_by = NULL WHERE event_id = 'evt_007'"); t["reference_dropped"] = l.check(); shutil.copy(snap, l.db)
    l.q("UPDATE events SET state = 'resolved' WHERE id = 'evt_002'"); t["applied_marked_resolved"] = l.check(); shutil.copy(snap, l.db)
    l.q("UPDATE events SET state = 'exception' WHERE id = 'evt_008'"); t["record_state_mismatch"] = l.check(); shutil.copy(snap, l.db)
    ok = all(v[0] != 0 for v in t.values())
    row("R6", "tampering after resolve is reported by check (record deleted, amount changed, reference dropped, applied event marked resolved, state reopened)",
        ok and l.check()[0] == 0, {k: [v[0], v[1][:140]] for k, v in t.items()})
    l.close()

def r3():
    l = L(); l.ingest(LINES)
    a = l.resolve("evt_007", "close")
    rs, out, j, _ = l.export("sep", SEP)
    b = l.resolve("evt_007", "close", "--reference", "   ")
    c = l.resolve("evt_002", "close", "--reference", "x")
    d = l.resolve("evt_404", "close")
    e = l.resolve("evt_008", "close", by="", note="x"); f = l.resolve("evt_008", "close", note="  ")
    g = l.resolve("evt_007", "close", "--reference", "x", "--superseded-by", "evt_006")
    row("R3", "refusals: money close without reference, blank reference, applied event, unknown id, blank --by or --note, both reference and superseded-by: exit 2, nothing recorded, export still refused",
        a[0] == 2 and b[0] == 2 and c[0] == 2 and d[0] == 2 and e[0] == 2 and f[0] == 2 and g[0] == 2 and l.state("evt_007") == "exception" and l.state("evt_008") == "exception"
        and (l.nres() in (0, None)) and rs == 1 and not out.exists(),
        {"rc": [a[0], b[0], c[0], d[0], e[0], f[0], g[0]], "n": l.nres(), "export": rs, "err_example": a[2][:160]})
    l.close()

def r4():
    l = L(); l.ingest(LINES)
    other = l.sign({"created": 1790000400, "data": {"amount": "0.20", "order_id": "ord_2", "refund_id": "re_2b", "restock": []}, "id": "evt_201", "type": "refund.succeeded"})
    same = l.sign({"created": 1790000410, "data": {"amount": "20.00", "order_id": "ord_1", "refund_id": "re_1c", "restock": []}, "id": "evt_202", "type": "refund.succeeded"})
    held = l.sign({"created": 1790000420, "data": {"amount": "1.00", "order_id": "ord_77", "refund_id": "re_77", "restock": []}, "id": "evt_203", "type": "refund.succeeded"})
    l.ingest([other, same, held])
    st = {k: l.state(k) for k in ("evt_201", "evt_202", "evt_203")}
    a = l.resolve("evt_007", "close", "--superseded-by", "evt_201")
    b = l.resolve("evt_007", "close", "--superseded-by", "evt_203")
    c = l.resolve("evt_007", "close", "--superseded-by", "evt_999")
    d = l.resolve("evt_007", "close", "--superseded-by", "evt_007")
    e = l.resolve("evt_007", "close", "--superseded-by", "evt_202")
    rr, rep = l.report(); res = [x for x in rep.get("resolutions") or [] if x.get("event_id") == "evt_007"]
    row("R4", "superseded-by: another order's applied event, a held event, an unknown id and itself are refused (exit 2); an applied re-delivered refund of the same order is accepted and recorded",
        st == {"evt_201": "applied", "evt_202": "applied", "evt_203": "held"} and [a[0], b[0], c[0], d[0]] == [2, 2, 2, 2] and e[0] == 0
        and l.state("evt_007") == "resolved" and len(res) == 1 and res[0].get("superseded_by") == "evt_202",
        {"states": st, "rc": [a[0], b[0], c[0], d[0], e[0]], "res": res})
    l.close()

def r5():
    l = L()
    ev = [l.sign({"created": 1790000100, "data": {"currency": "USD", "lines": [{"qty": 1, "sku": "tee-m"}], "order_id": "ord_8"}, "id": "evt_301", "type": "order.placed"}),
          l.sign({"created": 1790000110, "data": {"amount": "19.99", "order_id": "ord_8", "payment_id": "pay_8"}, "id": "evt_302", "type": "payment.captured"}),
          l.sign({"created": 1790000120, "data": {"currency": "USD", "lines": [{"qty": 4, "sku": "tee-m"}], "order_id": "ord_9"}, "id": "evt_303", "type": "order.placed"}),
          l.sign({"created": 1790000130, "data": {"amount": "79.96", "order_id": "ord_9", "payment_id": "pay_9"}, "id": "evt_304", "type": "payment.captured"})]
    l.ingest(ev)
    before = {k: l.state(k) for k in ("evt_303", "evt_304")}
    a = l.resolve("evt_303", "retry")  # still out of stock
    after_fail = {k: l.state(k) for k in ("evt_303", "evt_304")}; n_fail = l.nres()
    l.ingest([l.sign({"created": 1790000140, "data": {"amount": "19.99", "order_id": "ord_8", "refund_id": "re_8", "restock": [{"qty": 1, "sku": "tee-m"}]}, "id": "evt_305", "type": "refund.succeeded"})])
    b = l.resolve("evt_303", "retry", note="restocked by return re_8")
    after = {k: l.state(k) for k in ("evt_303", "evt_304")}
    rs, out, j, _ = l.export("sep", SEP)
    gc, c = g14(out) if rs == 0 else (None, {})
    rr, rep = l.report()
    row("R5", "retry: out-of-stock order still blocked gives exit 1 with nothing changed; after a restocking return the retry applies it and its held capture follows; export exit 0 and G14 reconciles; audit row action retry",
        before.get("evt_303") == "exception" and before.get("evt_304") == "held" and a[0] == 1 and after_fail == before and n_fail in (0, None)
        and b[0] == 0 and after == {"evt_303": "applied", "evt_304": "applied"} and rs == 0 and gc == 0
        and any(x.get("event_id") == "evt_303" and x.get("action") == "retry" for x in rep.get("resolutions") or []),
        {"before": before, "retry_fail": [a[0], a[1]], "after_fail": after_fail, "retry_ok": b[0], "after": after, "export": rs, "g14": gc, "net_cash": c.get("net_cash")})
    l.close()

def r7():
    l = L(); l.ingest([x for x in LINES if eid(x) == "evt_004"])  # refund before its order: held
    a = l.resolve("evt_004", "retry")
    l.ingest([x for x in LINES if eid(x) != "evt_004"])
    b = l.resolve("evt_004", "retry")
    row("R7", "held refund: retry before its order arrives exits 1 and stays held; after the order arrives it is applied by ingest, and resolving it then is refused (exit 2)",
        a[0] == 1 and b[0] == 2 and l.state("evt_004") == "applied", {"rc": [a[0], b[0]], "state": l.state("evt_004")})
    l.close()

def r9():
    if not OLD:
        row("R9", "ledger made by the h1 tool can be resolved by h2 (skipped: no --old-tool)", False, {}); return
    l = L(tool=OLD); l.ingest(LINES, tool=OLD)
    pre = l.nres()
    a = l.resolve("evt_007", "close", "--reference", "case 9"); b = l.resolve("evt_008", "close")
    rs, out, j, _ = l.export("sep", SEP); ck = l.check()
    row("R9", "ledger made by the h1 tool (no resolutions table): resolve works, table created, export exit 0, check 0",
        pre is None and a[0] == 0 and b[0] == 0 and l.nres() == 2 and rs == 0 and ck[0] == 0, {"pre_table": pre, "rc": [a[0], b[0]], "export": rs, "check": ck[0]})
    l.close()

guard("R1", "close path, export, audit", r1)
guard("R3", "refusals", r3)
guard("R4", "superseded-by rules", r4)
guard("R5", "retry and held release", r5)
guard("R7", "held retry", r7)
guard("R9", "old ledger", r9)
json.dump({"python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M22H2 PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
