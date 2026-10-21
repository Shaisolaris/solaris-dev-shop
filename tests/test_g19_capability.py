"""G19: duplicate-safe API and tenant boundaries (ledger_api.py, boundary_probe.py, oracle).

Every test starts the real API on 127.0.0.1 with a free port and a temporary database, using the
synthetic keys in examples/capabilities/G19/fixtures/principals.json. Nothing leaves loopback.
"""
import concurrent.futures as cf
import http.client
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "employees/engineering/backend-developer/ledger_api.py"
DOC = ROOT / "employees/engineering/backend-developer/duplicate-safe-api.md"
PROBE = ROOT / "employees/quality-security/security-auditor/boundary_probe.py"
EX = ROOT / "examples/capabilities/G19"
PRINCIPALS = EX / "fixtures/principals.json"
ADA, BEN = "local-demo-northwind-ada-0001", "local-demo-northwind-ben-0002"
CY, DEE = "local-demo-harbor-cy-0003", "local-demo-harbor-dee-0004"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(*args, timeout=120):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=timeout, env=ENV)


class Server:
    def __init__(self, tmp, script=API, db=None, fault=None, principals=PRINCIPALS):
        self.tmp = Path(tmp)
        self.db = Path(db or self.tmp / "ledger.db")
        self.ready = self.tmp / f"ready-{time.time_ns()}.json"
        args = [sys.executable, str(script), "serve", "--db", str(self.db), "--principals", str(principals),
                "--ready-file", str(self.ready)]
        if fault is not None:
            fp = self.tmp / f"fault-{time.time_ns()}.json"
            fp.write_text(json.dumps(dict(fault, schema="solaris.ledger-fault-plan/1")))
            args += ["--fault-plan", str(fp)]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=ENV)
        end = time.time() + 20
        while time.time() < end:
            if self.proc.poll() is not None:
                raise AssertionError(f"server exited {self.proc.returncode}: {self.proc.stderr.read().decode()[:300]}")
            try:
                self.port = int(json.loads(self.ready.read_text())["port"])
                break
            except (OSError, ValueError, KeyError):
                time.sleep(0.05)
        else:
            self.stop()
            raise AssertionError("server did not become ready")

    def call(self, method, path, key=None, body=None, idem=None, headers=None, raw=None):
        h = dict(headers or {})
        if key:
            h["Authorization"] = "Bearer " + key
        if idem:
            h["Idempotency-Key"] = idem
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            payload = r.read()
            js = json.loads(payload.decode()) if payload else None
            return r.status, js, {k.lower(): v for k, v in r.getheaders()}
        except (OSError, http.client.HTTPException):
            return 0, None, {}
        finally:
            c.close()

    def create(self, key, customer, amount, idem, **extra):
        body = {"customer": customer, "amount_cents": amount, "currency": "USD"}
        body.update(extra)
        return self.call("POST", "/api/v1/invoices", key, body, idem)

    def pay(self, key, iid, amount, idem):
        return self.call("POST", f"/api/v1/invoices/{iid}/payments", key, {"amount_cents": amount}, idem)

    def listing(self, key):
        out, after = [], None
        while True:
            st, js, _ = self.call("GET", "/api/v1/invoices?limit=100" + (f"&after={after}" if after else ""), key)
            assert st == 200, (st, js)
            out += js["data"]
            after = js["next_after"]
            if not after:
                return out

    def wait_exit(self, timeout=10):
        return self.proc.wait(timeout)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        self.proc.stderr.close()
        return self.proc.returncode


def code(js):
    return (js or {}).get("error", {}).get("code")


def par(fn, n):
    with cf.ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(fn, range(n)))


def check(db):
    p = run(API, "check", "--db", db, "--json")
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None), p.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            s.stop()
        self._td.cleanup()

    def start(self, **kw):
        s = Server(self.tmp, **kw)
        self.servers.append(s)
        return s


class Contract(Base):
    def test_doc_endpoint_table_matches_routes(self):
        sys.path.insert(0, str(API.parent))
        try:
            import ledger_api
        finally:
            sys.path.pop(0)
        rows = re.findall(r"^\| (GET|POST) \| (/api/v1/\S*) \| [^|]+ \| (no|required) \|", DOC.read_text(), re.M)
        self.assertEqual(sorted((m, p, i == "required") for m, p, i in rows),
                         sorted((m, p, idem) for m, p, _n, idem, _w in ledger_api.ROUTES))
        doc_lines = re.findall(r"^\s+(GET|POST)\s+(/api/v1/\S*)", ledger_api.__doc__, re.M)
        self.assertEqual(sorted(doc_lines), sorted((m, p) for m, p, *_ in ledger_api.ROUTES))
        # the probe and the oracle only call real endpoints
        known = {p for _m, p, *_ in ledger_api.ROUTES}
        for src in (PROBE, EX / "boundary_oracle.py"):
            used = {re.sub(r"inv_$", "{id}", re.sub(r"\{[^}]*\}", "{id}", u.split("?")[0]))
                    for u in re.findall(r'"(/api/v1/[^"]*)"', src.read_text())}
            self.assertTrue(used, src)
            self.assertEqual(used - known, set(), src.name)

    def test_clean_control_create_read_list_pay_void_and_check(self):
        s = self.start()
        st, js, h = s.call("GET", "/api/v1/health")
        self.assertEqual((st, js["ok"]), (200, True))
        st, inv, h = s.create(ADA, "Lumen Supply", 4250, "c-1")
        self.assertEqual(st, 201)
        self.assertEqual((inv["tenant"], inv["status"], inv["balance_cents"]), ("northwind", "open", 4250))
        self.assertRegex(inv["id"], r"^inv_[0-9a-f]{16}$")
        self.assertEqual(h["location"], f"/api/v1/invoices/{inv['id']}")
        self.assertEqual(h["idempotent-replayed"], "false")
        self.assertEqual(s.call("GET", f"/api/v1/invoices/{inv['id']}", BEN)[1], inv)
        self.assertEqual(s.pay(ADA, inv["id"], 1000, "c-2")[0], 201)
        st, done, _ = s.pay(ADA, inv["id"], 3250, "c-3")
        self.assertEqual((st, done["status"], done["paid_cents"], done["version"]), (201, "paid", 4250, 3))
        st, js, _ = s.pay(ADA, inv["id"], 1, "c-4")
        self.assertEqual((st, code(js)), (409, "invoice_not_open"))
        _, v, _ = s.create(ADA, "Void Me", 100, "c-5")
        st, vv, _ = s.call("POST", f"/api/v1/invoices/{v['id']}/void", ADA, {"reason": "duplicate"}, "c-6")
        self.assertEqual((st, vv["status"]), (200, "void"))
        st, js, _ = s.call("POST", f"/api/v1/invoices/{inv['id']}/void", ADA, {}, "c-7")
        self.assertEqual((st, code(js)), (409, "cannot_void"))
        self.assertEqual([x["id"] for x in s.listing(ADA)], [inv["id"], v["id"]])
        self.assertEqual(s.listing(CY), [])
        self.assertEqual(s.stop(), 0)
        rc, rep, _ = check(s.db)
        self.assertEqual((rc, rep["ok"], rep["tenants"]["northwind"]["payments"]), (0, True, 2))

    def test_validation_errors_are_bounded_and_store_nothing(self):
        s = self.start()
        cases = [
            (dict(raw=b"{not json"), 400, "invalid_json"),
            (dict(raw=b'{"customer": "a", "customer": "b", "amount_cents": 1, "currency": "USD"}'), 400, "invalid_json"),
            (dict(body={"customer": "A", "amount_cents": 1.5, "currency": "USD"}), 422, "invalid_amount"),
            (dict(body={"customer": "A", "amount_cents": True, "currency": "USD"}), 422, "invalid_amount"),
            (dict(body={"customer": "A", "amount_cents": 1, "currency": "XYZ"}), 422, "invalid_currency"),
            (dict(body={"customer": "A", "amount_cents": 1, "currency": "USD", "note": 1}), 422, "unknown_field"),
            (dict(body={"customer": "A", "amount_cents": 1, "currency": "USD"}, idem="bad key"), 400, "invalid_idempotency_key"),
            (dict(raw=b"x" * 17000), 413, "body_too_large"),
        ]
        for kw, want_st, want_code in cases:
            kw.setdefault("idem", "v-1")
            st, js, _ = s.call("POST", "/api/v1/invoices", ADA, **kw)
            self.assertEqual((st, code(js)), (want_st, want_code), kw)
            self.assertNotIn("Traceback", json.dumps(js))
        st, js, _ = s.call("POST", "/api/v1/invoices", ADA, {"customer": "A", "amount_cents": 1, "currency": "USD"})
        self.assertEqual((st, code(js)), (400, "idempotency_key_required"))
        self.assertEqual(s.call("DELETE", "/api/v1/invoices", ADA)[0], 405)
        self.assertEqual(code(s.call("GET", "/api/v1/nope", ADA)[1]), "no_route")
        self.assertEqual(s.listing(ADA), [])
        st, inv, _ = s.create(ADA, "Fixed", 10, "v-1")  # the key stays usable once the request is fixed
        self.assertEqual(st, 201)
        self.assertEqual(code(s.call("GET", "/api/v1/invoices?limit=0", ADA)[1]), "invalid_limit")
        self.assertEqual(code(s.call("GET", "/api/v1/invoices?tenant=harbor", ADA)[1]), "unknown_parameter")


class DuplicateEffects(Base):
    def test_32_concurrent_replays_of_one_create_make_one_invoice(self):
        s = self.start()
        res = par(lambda i: s.create(ADA, "Replay Co", 777, "dup-create"), 32)
        self.assertEqual({r[0] for r in res}, {201})
        self.assertEqual(len({json.dumps(r[1], sort_keys=True) for r in res}), 1)
        self.assertEqual(sum(r[2]["idempotent-replayed"] == "true" for r in res), 31)
        self.assertEqual(len(s.listing(ADA)), 1)
        s.stop()
        rc, rep, _ = check(s.db)
        self.assertEqual((rc, rep["audit_rows"], rep["idempotency_records"]), (0, 1, 1))

    def test_concurrent_and_sequential_payment_replays_make_one_payment(self):
        s = self.start()
        _, inv, _ = s.create(ADA, "Pay Once", 1000, "p-create")
        res = par(lambda i: s.pay(ADA, inv["id"], 100, "p-same"), 24) + [s.pay(ADA, inv["id"], 100, "p-same") for _ in range(3)]
        self.assertEqual({r[0] for r in res}, {201})
        self.assertEqual(s.call("GET", f"/api/v1/invoices/{inv['id']}", ADA)[1]["paid_cents"], 100)

    def test_distinct_concurrent_payments_never_overspend(self):
        s = self.start()
        _, inv, _ = s.create(ADA, "Race", 1000, "r-create")
        res = par(lambda i: s.pay(ADA, inv["id"], 300, f"r-{i}"), 16)
        self.assertEqual(sorted(r[0] for r in res), [201] * 3 + [409] * 13)
        self.assertEqual(s.call("GET", f"/api/v1/invoices/{inv['id']}", ADA)[1]["paid_cents"], 900)
        refused = [i for i, r in enumerate(res) if r[0] == 409][0]
        st, js, h = s.pay(ADA, inv["id"], 300, f"r-{refused}")  # a stored conflict replays as the same conflict
        self.assertEqual((st, code(js), h["idempotent-replayed"]), (409, "exceeds_balance", "true"))
        st, js, _ = s.pay(ADA, inv["id"], 100, f"r-{refused}")  # and its key is spent
        self.assertEqual((st, code(js)), (422, "idempotency_key_reused"))
        s.stop()
        self.assertEqual(check(s.db)[0], 0)

    def test_key_reuse_for_a_different_request_is_refused_and_keys_are_per_tenant(self):
        s = self.start()
        st, a, _ = s.create(ADA, "First", 100, "shared-key")
        st2, js, _ = s.create(ADA, "Second", 200, "shared-key")
        self.assertEqual((st2, code(js)), (422, "idempotency_key_reused"))
        st3, b, _ = s.create(CY, "Harbor own", 300, "shared-key")
        self.assertEqual(st3, 201)
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual([x["customer"] for x in s.listing(ADA)], ["First"])
        self.assertEqual([x["customer"] for x in s.listing(CY)], ["Harbor own"])


class TenantBoundaries(Base):
    def test_other_tenant_reads_writes_and_cursors_look_like_missing_and_change_nothing(self):
        s = self.start()
        _, inv, _ = s.create(ADA, "Northwind only", 1000, "t-1")
        missing = "inv_" + "0" * 16
        own_missing = s.call("GET", f"/api/v1/invoices/{missing}", CY)
        cross = s.call("GET", f"/api/v1/invoices/{inv['id']}", CY)
        self.assertEqual((cross[0], cross[1]), (own_missing[0], own_missing[1]))
        self.assertEqual(cross[0], 404)
        for path, body in ((f"/api/v1/invoices/{inv['id']}/payments", {"amount_cents": 1000}),
                           (f"/api/v1/invoices/{inv['id']}/void", {})):
            st, js, _ = s.call("POST", path, CY, body, "t-x-" + path[-4:])
            self.assertEqual((st, code(js)), (404, "not_found"))
        self.assertEqual(code(s.call("GET", f"/api/v1/invoices?after={inv['id']}", CY)[1]), "invalid_cursor")
        self.assertEqual(code(s.call("GET", f"/api/v1/invoices?after={missing}", CY)[1]), "invalid_cursor")
        self.assertEqual(s.listing(CY), [])
        self.assertEqual(s.call("GET", f"/api/v1/invoices/{inv['id']}", ADA)[1], inv)

    def test_tenant_smuggling_auth_and_roles(self):
        s = self.start()
        st, js, _ = s.create(ADA, "Smuggle", 100, "s-1", tenant_id="harbor")
        self.assertEqual((st, code(js)), (422, "tenant_is_server_derived"))
        st, inv, _ = s.call("POST", "/api/v1/invoices", ADA, {"customer": "Hdr", "amount_cents": 5, "currency": "USD"}, "s-2",
                            headers={"X-Tenant-Id": "harbor", "X-Tenant": "harbor"})
        self.assertEqual((st, inv["tenant"]), (201, "northwind"))
        self.assertEqual(s.listing(CY), [])
        for key in (None, "local-demo-unknown-key-9999"):
            st, js, _ = s.create(key, "Anon", 5, "s-3")
            self.assertEqual((st, code(js)), (401, "unauthenticated"))
        st, js, _ = s.create(BEN, "Viewer write", 5, "s-4")
        self.assertEqual((st, code(js)), (403, "forbidden"))
        st, js, _ = s.pay(DEE, inv["id"], 1, "s-5")
        self.assertEqual(st, 403)
        self.assertEqual(s.call("GET", "/api/v1/invoices", BEN)[0], 200)
        self.assertEqual([x["customer"] for x in s.listing(ADA)], ["Hdr"])


class RetryRestartRecovery(Base):
    def test_transient_failure_rolls_back_and_retry_makes_one_effect(self):
        s = self.start(fault={"fail_before_commit": {"f-1": 2}})
        for _ in range(2):
            st, js, h = s.create(ADA, "Retry", 500, "f-1")
            self.assertEqual((st, code(js), h.get("retry-after")), (503, "transient_failure", "0"))
        self.assertEqual(s.listing(ADA), [])
        st, inv, h = s.create(ADA, "Retry", 500, "f-1")
        self.assertEqual((st, h["idempotent-replayed"]), (201, "false"))
        self.assertEqual(s.create(ADA, "Retry", 500, "f-1")[2]["idempotent-replayed"], "true")
        self.assertEqual(len(s.listing(ADA)), 1)

    def test_crash_before_and_after_commit_then_restart_and_retry(self):
        s = self.start(fault={"crash_before_commit": ["k-before"], "crash_after_commit": ["k-after"]})
        _, inv, _ = s.create(ADA, "Crash", 1000, "k-0")
        st, js, _ = s.pay(ADA, inv["id"], 400, "k-before")
        self.assertEqual(st, 0)
        self.assertEqual(s.wait_exit(), 70)
        s2 = self.start(db=s.db)
        self.assertEqual(s2.call("GET", f"/api/v1/invoices/{inv['id']}", ADA)[1]["paid_cents"], 0)
        st, after, h = s2.pay(ADA, inv["id"], 400, "k-before")
        self.assertEqual((st, after["paid_cents"], h["idempotent-replayed"]), (201, 400, "false"))
        s2.stop()
        s3 = self.start(db=s.db, fault={"crash_after_commit": ["k-after"]})
        st, _, _ = s3.pay(ADA, inv["id"], 600, "k-after")
        self.assertEqual(st, 0)
        self.assertEqual(s3.wait_exit(), 70)
        s4 = self.start(db=s.db)
        st, done, h = s4.pay(ADA, inv["id"], 600, "k-after")
        self.assertEqual((st, done["paid_cents"], done["status"], h["idempotent-replayed"]), (201, 1000, "paid", "true"))
        s4.stop()
        rc, rep, _ = check(s.db)
        self.assertEqual((rc, rep["tenants"]["northwind"]["payments"], rep["tenants"]["northwind"]["paid_cents"]), (0, 2, 1000))

    def test_check_names_tampering_and_audit_is_append_only(self):
        s = self.start()
        _, inv, _ = s.create(ADA, "Audit", 1000, "a-1")
        s.pay(ADA, inv["id"], 100, "a-2")
        s.stop()
        con = sqlite3.connect(s.db)
        for stmt in ("UPDATE audit SET amount_cents = 1", "DELETE FROM audit"):
            with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
                con.execute(stmt)
        con.execute("INSERT INTO payments (tenant, invoice_id, amount_cents, idem_key, actor) VALUES ('harbor', ?, 50, 'forged', 'x')",
                    (inv["id"],))
        con.commit()
        con.close()
        rc, rep, _ = check(s.db)
        self.assertEqual(rc, 1)
        text = " ".join(rep["violations"])
        self.assertIn("another tenant", text)
        self.assertIn("payments add to 150", text)

    def test_numeric_transport_fields_reject_unicode_and_oversized_digits(self):
        from urllib.parse import quote
        s = self.start()
        for value in ("²", "١", "９", "9" * 5000):
            with self.subTest(limit=value[:10]):
                status, body, _ = s.call("GET", "/api/v1/invoices?limit=" + quote(value), ADA)
                self.assertEqual(status, 422, body)
                self.assertEqual(code(body), "invalid_limit")
        for value, expected in (("²", 411), ("9" * 5000, 413)):
            with self.subTest(length=value[:10]):
                status, body, _ = s.call("POST", "/api/v1/invoices", ADA, raw=b"{}",
                                         headers={"Content-Length": value}, idem="synthetic-numeric")
                self.assertEqual(status, expected, body)
        # Ordinary requests still work after all malformed inputs; long leading zeroes
        # preserve the decimal value without asking int() to parse thousands of digits.
        self.assertEqual(s.call("GET", "/api/v1/invoices?limit=" + "0" * 5000 + "1", ADA)[0], 200)
        self.assertEqual(s.call("POST", "/api/v1/invoices", ADA, raw=b"{}",
                               headers={"Content-Length": "0" * 5000 + "2"}, idem="synthetic-zeroes")[0], 422)
        self.assertEqual(s.create(ADA, "Synthetic", 100, "numeric-clean")[0], 201)
        self.assertEqual(len(s.listing(ADA)), 1)

    def test_serve_and_check_refuse_bad_input_with_exit_2(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps({"schema": "solaris.ledger-principals/1", "principals": [{"key": "short", "tenant": "a", "user": "b", "role": "editor"}]}))
        fault = self.tmp / "fault.json"
        fault.write_text(json.dumps({"schema": "solaris.ledger-fault-plan/1", "explode": True}))
        db = self.tmp / "x.db"
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        busy = sock.getsockname()[1]
        try:
            for extra, needle in ((["--host", "0.0.0.0"], "not loopback"), (["--host", "example.com"], "only loopback"),
                                  (["--principals", bad], "16-200"), (["--fault-plan", fault], "unknown fields"),
                                  (["--port", str(busy)], "cannot listen"), (["--db", self.tmp / "no" / "x.db"], "does not exist")):
                args = ["serve", "--db", db, "--principals", PRINCIPALS] + extra
                p = run(API, *args, timeout=20)
                self.assertEqual(p.returncode, 2, (extra, p.stderr))
                self.assertIn(needle, p.stderr)
                self.assertNotIn("Traceback", p.stderr)
        finally:
            sock.close()
        (self.tmp / "junk.db").write_bytes(b"not sqlite" * 100)
        p = run(API, "check", "--db", self.tmp / "junk.db")
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)


class ProbeAndOracle(Base):
    def test_probe_refuses_non_loopback_before_any_request(self):
        for url in ("http://10.0.0.1:80", "http://example.com", "https://8.8.8.8:443", "ftp://127.0.0.1"):
            p = run(PROBE, "--base-url", url, "--principals", PRINCIPALS, timeout=20)
            self.assertEqual(p.returncode, 2, (url, p.stdout, p.stderr))

    def test_probe_clean_on_real_api_findings_on_vulnerable_inconclusive_on_noop(self):
        out = {}
        for name, script in (("real", API), ("vulnerable", EX / "vulnerable_stub.py"), ("noop", EX / "noop_stub.py")):
            s = self.start(script=script, db=self.tmp / f"{name}.db")
            p = run(PROBE, "--base-url", f"http://127.0.0.1:{s.port}", "--principals", PRINCIPALS, "--json")
            out[name] = (p.returncode, json.loads(p.stdout) if p.stdout.strip() else None)
            s.stop()
        rc, rep = out["real"]
        self.assertEqual((rc, rep["findings"]), (0, []))
        self.assertEqual(len(rep["checks"]), 10)
        rc, rep = out["vulnerable"]
        self.assertEqual(rc, 1)
        self.assertTrue({"B1", "B2", "B3", "B4", "B6", "B7"} <= {f["check"] for f in rep["findings"]}, rep["findings"])
        self.assertEqual(out["noop"][0], 3)

    def test_oracle_accepts_real_api_and_rejects_stubs(self):
        cmd = f"{sys.executable} {API}"
        p = run(EX / "boundary_oracle.py", "--server", cmd, "--scale", "300", timeout=300)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:])
        self.assertIn("10/10", p.stdout)
        for stub in ("vulnerable_stub.py", "noop_stub.py"):
            p = run(EX / "boundary_oracle.py", "--server", f"{sys.executable} {EX / stub}", "--scale", "300", timeout=300)
            self.assertNotEqual(p.returncode, 0, stub)



class OracleServerStop(unittest.TestCase):
    """The oracle's Server.stop() on a server that exited after poll() but before the group signal.

    o8 (crash after commit) makes the server exit by design. If it exits between stop()'s poll() and
    os.killpg(), the session leader is an unreaped zombie and macOS answers killpg with EPERM. Both tests pin
    that window deterministically: the child has exited, poll() reports it still running once, and stop()
    must treat it as stopped and reap it. Source: M39 P4-1 root cause (Grok self-validation)."""

    def _exited_unreaped(self):
        sys.path.insert(0, str(EX))
        try:
            import boundary_oracle
        finally:
            sys.path.pop(0)
        proc = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, start_new_session=True, env=ENV)
        # wait for exit without reaping, so the pid stays a zombie session leader (macOS has no os.waitid)
        end = time.time() + 20
        while subprocess.run(["ps", "-o", "stat=", "-p", str(proc.pid)], capture_output=True,
                             text=True).stdout.strip()[:1] != "Z":
            self.assertLess(time.time(), end, "child did not exit")
            time.sleep(0.02)
        real_poll, calls = proc.poll, []

        def racy_poll():
            calls.append(1)
            return None if len(calls) == 1 else real_poll()
        proc.poll = racy_poll
        srv = boundary_oracle.Server.__new__(boundary_oracle.Server)
        srv.proc = proc
        return boundary_oracle, srv

    def test_stop_after_exit_race_real_zombie(self):
        mod, srv = self._exited_unreaped()
        srv.stop()  # macOS: os.killpg on the zombie group raises PermissionError before the fix
        self.assertEqual(srv.proc.returncode, 0)

    def test_stop_after_exit_race_eperm_any_platform(self):
        mod, srv = self._exited_unreaped()
        real_killpg = mod.os.killpg

        def eperm(pid, sig):
            raise PermissionError(1, "Operation not permitted")
        mod.os.killpg = eperm
        try:
            srv.stop()
        finally:
            mod.os.killpg = real_killpg
        self.assertEqual(srv.proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
