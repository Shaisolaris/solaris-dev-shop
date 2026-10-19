#!/usr/bin/env python3
"""M21 oracle (Grok self-validation, not independent review; black box). Written from M21.md and offline-sync.md.
It runs the real G19 ledger server on loopback and puts its own fault proxy between the tool and the server, so
faults are chosen here, not by the tool: 503 answers, connections dropped before forwarding, and lost acks (the
server commits, the proxy drops the answer). Expectations come from the doc's six rules and exit table, judged
from the server side (the invoices the ledger holds, ledger_api.py check) against an intent model kept here.
Authoring fixes before scoring against the controls (disclosed; first run kept in results/kept): A05 and A06b voided
an invoice that already had a payment, which G19 refuses (409 cannot_void), so my expected end state was wrong; they now
void an unpaid invoice and hold a fitting payment. A13 looked for the column name in status output ("idempotency_key")
while the outbox column is "idem", so it tampered nothing; it now finds either and adds a foreign-key tamper.
Usage: PY m21_oracle.py REPO OUT.json [--tool TOOL.py]. Core rows score; OBS rows record only."""
import http.client, http.server, json, os, random, re, shutil, socket, sqlite3, subprocess, sys, tempfile, threading, time
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = Path(sys.argv[sys.argv.index("--tool") + 1]).resolve() if "--tool" in sys.argv else REPO / "employees/engineering/mobile-developer/offline_sync.py"
API = REPO / "employees/engineering/backend-developer/ledger_api.py"; PR = REPO / "examples/capabilities/G19/fixtures/principals.json"
TOP = Path(tempfile.mkdtemp(prefix="m21o-", dir="/tmp")).resolve(); ROWS = []; PY = sys.executable
ENV = {"PATH": "/usr/bin:/bin", "HOME": str(TOP), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
ADA, BEN, CY = "local-demo-northwind-ada-0001", "local-demo-northwind-ben-0002", "local-demo-harbor-cy-0003"
def row(rid, ok, det, obs=False): ROWS.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": det})
class Server:
    def __init__(s, d):
        s.d = d; s.p = subprocess.Popen([PY, str(API), "serve", "--db", str(d / "ledger.db"), "--principals", str(PR), "--ready-file", str(d / "ready.json")], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            if (d / "ready.json").exists() and (d / "ready.json").stat().st_size: break
            time.sleep(0.05)
        s.port = json.loads((d / "ready.json").read_text())["port"]
    def req(s, method, path, key=ADA, body=None, ikey=None):
        c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10); h = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
        if ikey: h["Idempotency-Key"] = ikey
        c.request(method, path, body=None if body is None else json.dumps(body), headers=h); r = c.getresponse(); out = (r.status, json.loads(r.read() or b"{}")); c.close(); return out
    def invoices(s, key=ADA):
        out, after = [], None
        while True:
            st, b = s.req("GET", "/api/v1/invoices?limit=100" + ("&after=" + after if after else ""), key)
            out += b.get("data", []); after = b.get("next_after")
            if not after: return out
    def stop(s):
        s.p.terminate(); s.p.wait(10)
        cp = subprocess.run([PY, str(API), "check", "--db", str(s.d / "ledger.db")], env=ENV, capture_output=True, text=True); return cp.returncode, cp.stdout.strip()[-200:]
class Proxy:
    """Forwards to the server. plan: list of modes consumed by POSTs in order: ok, 503, drop (close before forwarding),
    lost (forward, then close without answering), slow (sleep 1.5 s then forward)."""
    def __init__(s, up):
        s.up = up; s.plan = []; s.log = []; s.lock = threading.Lock(); px = s
        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"
            def log_message(self, *a): pass
            def fwd(self):
                n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
                mode = "ok"
                if self.command == "POST":
                    with px.lock: mode = px.plan.pop(0) if px.plan else "ok"; px.log.append((self.path, self.headers.get("Idempotency-Key"), mode, body))
                if mode == "drop": self.connection.close(); return
                if mode == "503":
                    b = b'{"error": {"code": "transient_failure", "message": "proxy"}}'; self.send_response(503); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
                if mode == "slow": time.sleep(1.5)
                c = http.client.HTTPConnection("127.0.0.1", px.up, timeout=20); hd = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")}
                c.request(self.command, self.path, body=body, headers=hd); r = c.getresponse(); data = r.read(); hs = r.getheaders(); c.close()
                if mode == "lost": self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
                self.send_response(r.status)
                for k, v in hs:
                    if k.lower() not in ("content-length", "connection", "date", "server"): self.send_header(k, v)
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            do_GET = do_POST = fwd
        s.h = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); s.port = s.h.server_address[1]; threading.Thread(target=s.h.serve_forever, daemon=True).start()
    def stop(s): s.h.shutdown(); s.h.server_close()
class World:
    def __init__(s, name):
        s.d = TOP / name; s.d.mkdir(); s.srv = Server(s.d); s.px = Proxy(s.srv.port); s.url = "http://127.0.0.1:%d" % s.px.port
        for nm, k in (("ada", ADA), ("ben", BEN), ("cy", CY), ("bad", "local-demo-nobody-9999")): (s.d / (nm + ".key")).write_text(k + "\n")
    def t(s, *a, timeout=60):
        cp = subprocess.run([PY, str(TOOL)] + [str(x) for x in a], cwd=str(s.d), env=ENV, capture_output=True, text=True, timeout=timeout); return cp.returncode, cp.stdout, cp.stderr
    def dev(s, name):
        db = s.d / (name + ".db"); s.t("init", "--db", db, "--device", name); return db
    def sync(s, db, key="ada", *extra): return s.t("sync", "--db", db, "--base-url", s.url, "--key-file", s.d / (key + ".key"), *extra)
    def status(s, db):
        rc, out, _ = s.t("status", "--db", db, "--json")
        try: return json.loads(out)
        except Exception: return {}
    def check(s, db): return s.t("check", "--db", db)[0]
    def close(s):
        s.px.stop(); r = s.srv.stop(); shutil.rmtree(s.d, ignore_errors=True); return r
def server_view(w, key=ADA): return sorted((i["customer"], i["amount_cents"], i["paid_cents"], i["status"]) for i in w.srv.invoices(key))
def enq(w, db, *a): return w.t("enqueue", "--db", db, *a)[0]
def until_done(w, db, n=12, key="ada"):
    rcs = []
    for _ in range(n):
        rc = w.sync(db, key)[0]; rcs.append(rc)
        if rc in (0, 1, 3): break
    return rcs
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + "_crash", False, "harness or tool crash: %r" % (e,))
    return g
@safe
def a01():  # clean batch: create, two payments, void on a second invoice: server holds exactly the intent; exits 0
    w = World("a01"); db = w.dev("phone")
    rcs = [enq(w, db, "create", "--ref", "r1", "--customer", "Blue Fern", "--amount", 1000, "--currency", "USD"), enq(w, db, "pay", "--ref", "r1", "--amount", 400), enq(w, db, "pay", "--ref", "r1", "--amount", 600),
           enq(w, db, "create", "--ref", "r2", "--customer", "Oak", "--amount", 500, "--currency", "EUR"), enq(w, db, "void", "--ref", "r2", "--reason", "dup")]
    rc = w.sync(db)[0]; st = w.status(db); sv = server_view(w); order = [p for p, k, m, b in w.px.log]; chk = w.check(db); lc = w.close()
    want = sorted([("Blue Fern", 1000, 1000, "paid"), ("Oak", 500, 0, "void")])
    ok = rcs == [0] * 5 and rc == 0 and sv == want and st.get("pending") == 0 and chk == 0 and lc[0] == 0 and len(order) == 5 and order[0] == "/api/v1/invoices" and order[3] == "/api/v1/invoices"
    row("A01_clean_batch", ok, {"enqueue_rcs": rcs, "sync_rc": rc, "server": sv, "post_order": order, "check": chk, "ledger_check": lc})
@safe
def a02():  # lost ack on each request in turn: the change stays pending (exit 4), the rerun replays its key, effect once
    res = {}; ok_all = True
    for n in range(1, 4):
        w = World("a02-%d" % n); db = w.dev("phone"); enq(w, db, "create", "--ref", "r1", "--customer", "Fern", "--amount", 1000, "--currency", "USD"); enq(w, db, "pay", "--ref", "r1", "--amount", 300); enq(w, db, "pay", "--ref", "r1", "--amount", 700)
        w.px.plan = ["ok"] * (n - 1) + ["lost"]; rc1 = w.sync(db)[0]; rcs = until_done(w, db); st = w.status(db); sv = server_view(w); keys = [k for p, k, m, b in w.px.log]; lc = w.close()
        lost_key = keys[n - 1]; replays = keys.count(lost_key); rp = [o.get("replayed") for o in st.get("ops", []) if o.get("idempotency_key") == lost_key]
        ok = rc1 == 4 and rcs[-1] == 0 and sv == [("Fern", 1000, 1000, "paid")] and replays == 2 and rp == [True] and lc[0] == 0
        res["lost_ack_on_%d" % n] = {"first_rc": rc1, "then": rcs, "server": sv, "sends_of_lost_key": replays, "replayed": rp, "ledger_check": lc[0]}; ok_all &= ok
    row("A02_lost_ack_replayed_once", ok_all, res)
@safe
def a03():  # 503 and dropped connection before forwarding: exit 4, nothing lost, same key and body on the retry
    res = {}; ok_all = True
    for mode in ("503", "drop"):
        w = World("a03-" + mode); db = w.dev("phone"); enq(w, db, "create", "--ref", "r1", "--customer", "Fern", "--amount", 1000, "--currency", "USD"); enq(w, db, "pay", "--ref", "r1", "--amount", 250)
        w.px.plan = ["ok", mode]; rc1 = w.sync(db)[0]; st1 = w.status(db); rcs = until_done(w, db); sv = server_view(w); log = [(k, b) for p, k, m, b in w.px.log]; lc = w.close()
        same = log[1] == log[2] if len(log) > 2 else False
        ok = rc1 == 4 and st1.get("pending") == 1 and rcs[-1] == 0 and sv == [("Fern", 1000, 250, "open")] and same and lc[0] == 0
        res[mode] = {"first_rc": rc1, "pending_after": st1.get("pending"), "then": rcs, "server": sv, "same_key_and_body": same}; ok_all &= ok
    row("A03_transient_stops_and_resumes", ok_all, res)
@safe
def a04():  # client crash drills before and after each send: after reruns the server holds the intent exactly once
    res = {}; ok_all = True
    for flag in ("--crash-before-send", "--crash-after-send"):
        for n in (1, 2, 3, 4):
            w = World("a04"); db = w.dev("phone"); enq(w, db, "create", "--ref", "r1", "--customer", "Fern", "--amount", 900, "--currency", "GBP")
            for a in (200, 300, 400): enq(w, db, "pay", "--ref", "r1", "--amount", a)
            rc1 = w.sync(db, "ada", flag, n)[0]; rcs = until_done(w, db); sv = server_view(w); chk = w.check(db); lc = w.close()
            ok = rc1 == 70 and rcs[-1] == 0 and sv == [("Fern", 900, 900, "paid")] and chk == 0 and lc[0] == 0
            res["%s %d" % (flag, n)] = {"rc": rc1, "then": rcs, "server": sv, "check": chk}; ok_all &= ok
    row("A04_crash_drills_effect_once", ok_all, res)
@safe
def a05():  # ordering: changes go in the order of intent across invoices; a change to an offline-created invoice waits for its create
    w = World("a05"); db = w.dev("phone"); enq(w, db, "create", "--ref", "a", "--customer", "A", "--amount", 100, "--currency", "USD"); enq(w, db, "create", "--ref", "b", "--customer", "B", "--amount", 200, "--currency", "USD")
    enq(w, db, "pay", "--ref", "a", "--amount", 40); enq(w, db, "pay", "--ref", "a", "--amount", 60); enq(w, db, "void", "--ref", "b")
    w.px.plan = ["503"]; rc1 = w.sync(db)[0]; st1 = w.status(db); rc2 = w.sync(db)[0]; log = [(p, json.loads(b or b"{}")) for p, k, m, b in w.px.log]; sv = server_view(w); w.close()
    kinds = [("create" if p == "/api/v1/invoices" else p.rsplit("/", 1)[1]) for p, b in log[1:]]
    ok = rc1 == 4 and st1.get("pending") == 5 and rc2 == 0 and kinds == ["create", "create", "payments", "payments", "void"] and sv == sorted([("A", 100, 100, "paid"), ("B", 200, 0, "void")])
    row("A05_order_of_intent", ok, {"first_rc": rc1, "pending": st1.get("pending"), "rc2": rc2, "sent": kinds, "server": sv})
def two_devices(name):
    w = World(name); a = w.dev("tablet"); enq(w, a, "create", "--ref", "r", "--customer", "Shared", "--amount", 1000, "--currency", "USD"); w.sync(a)
    sid = [i for i in w.srv.invoices() if i["customer"] == "Shared"][0]["id"]; b = w.dev("phone"); w.sync(b); return w, a, b, sid
@safe
def a06():  # overpay conflict between devices: 409 kept as conflict (exit 1), later change on that invoice held, other invoice still sent
    w, a, b, sid = two_devices("a06"); enq(w, a, "pay", "--ref", sid, "--amount", 700); w.sync(a)
    enq(w, b, "pay", "--ref", sid, "--amount", 600); enq(w, b, "pay", "--ref", sid, "--amount", 300); enq(w, b, "create", "--ref", "n", "--customer", "Other", "--amount", 10, "--currency", "USD")
    rc = w.sync(b)[0]; st = w.status(b); ops = {o["seq"]: o for o in st.get("ops", [])}; sv = server_view(w)
    pay = [o for o in ops.values() if o["kind"] == "pay"]; vd = pay[1:]; cr = [o for o in ops.values() if o["kind"] == "create" and o["ref"] == "n"]
    ok1 = rc == 1 and pay and pay[0]["state"] == "conflict" and pay[0]["http_status"] == 409 and vd and vd[0]["state"] == "pending" and vd[0].get("waiting") and cr and cr[0]["state"] == "acked" and ("Shared", 1000, 700, "open") in sv
    row("A06_overpay_conflict_held_not_dropped", ok1, {"rc": rc, "pay": pay[:1], "void": vd[:1], "other_create": cr[:1], "server": sv})
    # recovery: discard the conflicting pay; the held 300 then goes (exit 0); the server invoice ends paid at 1000
    rr = w.t("resolve", "--db", b, "--op", pay[0]["seq"], "--action", "discard")[0] if pay else None; rc2 = w.sync(b)[0]; sv2 = server_view(w); st2 = w.status(b); w.close()
    row("A06b_discard_then_held_change_sent", rr == 0 and rc2 == 0 and ("Shared", 1000, 1000, "paid") in sv2 and any(o["state"] == "discarded" for o in st2.get("ops", [])), {"resolve_rc": rr, "rc": rc2, "server": sv2})
@safe
def a07():  # void versus pay: the pay after a remote void is a conflict; retry makes a new key at the back; the server refuses it again
    w, a, b, sid = two_devices("a07"); enq(w, a, "void", "--ref", sid); w.sync(a)
    enq(w, b, "pay", "--ref", sid, "--amount", 100); rc = w.sync(b)[0]; st = w.status(b); pay = [o for o in st.get("ops", []) if o["kind"] == "pay"]
    rr = w.t("resolve", "--db", b, "--op", pay[0]["seq"], "--action", "retry")[0] if pay else None; st2 = w.status(b); ops2 = [o for o in st2.get("ops", []) if o["kind"] == "pay"]
    keys = [o["idempotency_key"] for o in ops2]; link = [o.get("retry_of") for o in ops2]; rc2 = w.sync(b)[0]; sv = server_view(w); w.close()
    ok = rc == 1 and pay and pay[0]["state"] == "conflict" and rr == 0 and len(ops2) == 2 and len(set(keys)) == 2 and pay[0]["seq"] in link and rc2 == 1 and sv == [("Shared", 1000, 0, "void")]
    row("A07_void_vs_pay_conflict_and_retry_new_key", ok, {"rc": rc, "resolve_rc": rr, "keys": keys, "retry_of": link, "rc2": rc2, "server": sv})
@safe
def a08():  # stale overwrite: an older snapshot never replaces a newer local copy; a newer one does
    w, a, b, sid = two_devices("a08"); st0, old = w.srv.req("GET", "/api/v1/invoices")
    enq(w, a, "pay", "--ref", sid, "--amount", 100); w.sync(a); w.sync(b); st1, new = w.srv.req("GET", "/api/v1/invoices")
    (w.d / "old.json").write_text(json.dumps(old)); (w.d / "new.json").write_text(json.dumps(new))
    ra = w.t("apply-snapshot", "--db", b, w.d / "old.json")[0]; v1 = [i for i in w.status(b).get("invoices", []) if i.get("server_id") == sid]
    enq(w, a, "pay", "--ref", sid, "--amount", 200); w.sync(a); st2, newer = w.srv.req("GET", "/api/v1/invoices"); (w.d / "newer.json").write_text(json.dumps(newer))
    rb = w.t("apply-snapshot", "--db", b, w.d / "newer.json")[0]; v2 = [i for i in w.status(b).get("invoices", []) if i.get("server_id") == sid]; w.close()
    g = lambda v: ((v[0].get("server") or {}).get("version"), (v[0].get("server") or {}).get("paid_cents")) if v else None
    ok = ra == 0 and g(v1) == (2, 100) and rb == 0 and g(v2) == (3, 300)
    row("A08_stale_snapshot_never_rolls_back", ok, {"apply_old_rc": ra, "after_old": g(v1), "apply_newer_rc": rb, "after_newer": g(v2)})
@safe
def a09():  # four concurrent syncs of one outbox (slow proxy): one runs, the others exit 5 at once; effects once
    w = World("a09"); db = w.dev("phone"); enq(w, db, "create", "--ref", "r", "--customer", "C", "--amount", 800, "--currency", "USD")
    for _ in range(4): enq(w, db, "pay", "--ref", "r", "--amount", 100)
    w.px.plan = ["slow"] * 5; ps = [subprocess.Popen([PY, str(TOOL), "sync", "--db", str(db), "--base-url", w.url, "--key-file", str(w.d / "ada.key")], cwd=str(w.d), env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(4)]
    t0 = time.time(); rcs = []; quick = []
    for p in ps: p.wait(60); rcs.append(p.returncode)
    rest = until_done(w, db); sv = server_view(w); n_posts = len(w.px.log); lc = w.close()
    ok = sorted(rcs) == [0, 5, 5, 5] and sv == [("C", 800, 400, "open")] and n_posts == 5 and lc[0] == 0
    row("A09_concurrent_syncs_one_runs", ok, {"rcs": sorted(rcs), "then": rest, "server": sv, "posts": n_posts})
@safe
def a10():  # refused keys: unknown key and viewer key exit 3, nothing changed, changes stay pending with their keys
    res = {}; ok_all = True
    for k in ("bad", "ben"):
        w = World("a10" + k); db = w.dev("phone"); enq(w, db, "create", "--ref", "r", "--customer", "C", "--amount", 800, "--currency", "USD"); enq(w, db, "pay", "--ref", "r", "--amount", 100)
        k0 = [o["idempotency_key"] for o in w.status(db).get("ops", [])]; rc = w.sync(db, k)[0]; st = w.status(db); k1 = [o["idempotency_key"] for o in st.get("ops", [])]
        rc2 = w.sync(db)[0]; sv = server_view(w); w.close()
        ok = rc == 3 and st.get("pending") == 2 and k0 == k1 and rc2 == 0 and sv == [("C", 800, 100, "open")]; res[k] = {"rc": rc, "pending": st.get("pending"), "keys_kept": k0 == k1, "then": rc2, "server": sv}; ok_all &= ok
    row("A10_refused_key_stops_nothing_changed", ok_all, res)
@safe
def a11():  # invalid input: exit 2 and nothing recorded
    w = World("a11"); db = w.dev("phone"); enq(w, db, "create", "--ref", "r", "--customer", "C", "--amount", 800, "--currency", "USD")
    bad = {"amount_zero": ("pay", "--ref", "r", "--amount", 0), "amount_float": ("pay", "--ref", "r", "--amount", "1.5"), "currency": ("create", "--ref", "q", "--customer", "C", "--amount", 5, "--currency", "JPY"),
           "unknown_ref": ("pay", "--ref", "nope", "--amount", 5), "dup_ref": ("create", "--ref", "r", "--customer", "C", "--amount", 5, "--currency", "USD"), "customer_long": ("create", "--ref", "z", "--customer", "x" * 81, "--amount", 5, "--currency", "USD")}
    res = {k: enq(w, db, *v) for k, v in bad.items()}; n = len(w.status(db).get("ops", [])); w.close()
    row("A11_invalid_input_exit2_nothing_recorded", all(v == 2 for v in res.values()) and n == 1, {"rcs": res, "ops_after": n})
@safe
def a12():  # keys: fixed at enqueue, '<install>:<seq>', install = device + 8 hex; two installs with one device name differ
    w = World("a12"); d1 = w.dev("phone"); enq(w, d1, "create", "--ref", "r", "--customer", "C", "--amount", 8, "--currency", "USD"); k1 = w.status(d1).get("ops", [{}])[0].get("idempotency_key")
    shutil.copy(d1, w.d / "copy.db"); (w.d / "phone.db").unlink(); d2 = w.dev("phone"); enq(w, d2, "create", "--ref", "r", "--customer", "C", "--amount", 8, "--currency", "USD"); k2 = w.status(d2).get("ops", [{}])[0].get("idempotency_key")
    w.close(); pat = re.compile(r"^phone-[0-9a-f]{8}:\d+$")
    row("A12_key_format_and_unique_install", bool(k1 and k2 and pat.match(k1) and pat.match(k2) and k1.split(":")[0] != k2.split(":")[0]), {"k1": k1, "k2": k2})
@safe
def a13():  # check detects a tampered outbox (an acked change without an answer, a foreign key); read-only
    w = World("a13"); db = w.dev("phone"); enq(w, db, "create", "--ref", "r", "--customer", "C", "--amount", 8, "--currency", "USD"); w.sync(db)
    enq(w, db, "pay", "--ref", "r", "--amount", 2); c0 = w.check(db); con = sqlite3.connect(str(db)); tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    cols = {t: [r[1] for r in con.execute("pragma table_info(%s)" % t)] for t in tabs}; t = next((t for t, c in cols.items() if ("idempotency_key" in c or "idem" in c) and "state" in c), None); changed = None
    if t:
        con.execute("update %s set state='acked' where state='pending'" % t); con.commit(); changed = "pending->acked"
    con.close(); h = (db.read_bytes()); c1 = w.check(db); same = h == db.read_bytes()
    shutil.copy(db, w.d / "t2.db"); con = sqlite3.connect(str(w.d / "t2.db")); kc = next((c for c in cols.get(t, []) if c in ("idem", "idempotency_key")), None)
    if kc: con.execute("update %s set %s='other-12345678:000009', state='acked' where seq=1" % (t, kc)); con.commit()
    con.close(); c2 = w.check(w.d / "t2.db"); w.close()
    row("A13_check_names_tampered_outbox", c0 == 0 and c1 == 1 and c2 == 1 and same, {"before": c0, "tamper": changed, "after_ack_without_answer": c1, "after_foreign_key": c2, "read_only": same})
@safe
def a14():  # property soak: 3 devices, random changes and random proxy faults; loop until settled; server equals the model
    rnd = random.Random(2121); w = World("a14"); devs = [w.dev("d%d" % i) for i in range(3)]; model = {}; n = 0
    for dv, db in enumerate(devs):
        for j in range(3):
            ref = "i%d%d" % (dv, j); amt = rnd.randint(5, 20) * 100; enq(w, db, "create", "--ref", ref, "--customer", ref, "--amount", amt, "--currency", "USD"); model[ref] = [amt, 0, "open"]
            for _ in range(rnd.randint(0, 3)):
                p = rnd.randint(1, 4) * 100
                if model[ref][1] + p <= amt: enq(w, db, "pay", "--ref", ref, "--amount", p); model[ref][1] += p
            if rnd.random() < 0.2 and model[ref][1] == 0: enq(w, db, "void", "--ref", ref); model[ref][2] = "void"
            if model[ref][1] == amt: model[ref][2] = "paid"
    w.px.plan = [rnd.choice(["ok", "ok", "ok", "503", "drop", "lost"]) for _ in range(60)]
    rcs = {}
    for k, db in enumerate(devs): rcs[k] = until_done(w, db, 40)
    sv = server_view(w); want = sorted((r, a, p, s) for r, (a, p, s) in model.items()); lc = w.close()
    row("A14_seeded_soak_with_faults", sv == want and all(v[-1] == 0 for v in rcs.values()) and lc[0] == 0, {"syncs": rcs, "match": sv == want, "server_n": len(sv), "want_n": len(want), "ledger_check": lc})
@safe
def o15():  # OBS: retried change lands after later changes (doc limit); what the user sees in status
    w, a, b, sid = two_devices("o15"); enq(w, a, "pay", "--ref", sid, "--amount", 900); w.sync(a)
    enq(w, b, "pay", "--ref", sid, "--amount", 200); enq(w, b, "pay", "--ref", sid, "--amount", 100); rc = w.sync(b)[0]; st = w.status(b); w.close()
    row("O15_held_behind_conflict_view", True, {"rc": rc, "ops": [{k: o.get(k) for k in ("seq", "kind", "state", "http_status", "waiting", "reason")} for o in st.get("ops", []) if o["kind"] == "pay"]}, obs=True)
for f in (a01, a02, a03, a04, a05, a06, a07, a08, a09, a10, a11, a12, a13, a14, o15): f()
shutil.rmtree(TOP, ignore_errors=True)
json.dump(ROWS, open(OUT, "w"), indent=1, default=str)
for x in ROWS: print(x["id"], x["result"], json.dumps(x["detail"], default=str)[:500])
c = [x for x in ROWS if x["kind"] == "core"]; print("M21 ORACLE %d/%d core PASS" % (sum(x["result"] == "PASS" for x in c), len(c)))
