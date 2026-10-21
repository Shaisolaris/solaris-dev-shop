"""G21: offline client sync (employees/engineering/mobile-developer/offline_sync.py) against the real
G19 ledger API on loopback. Real processes, real SQLite files, synthetic keys from the G19 fixture."""
import fcntl
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "employees" / "engineering" / "mobile-developer" / "offline_sync.py"
API = ROOT / "employees" / "engineering" / "backend-developer" / "ledger_api.py"
EX = ROOT / "examples" / "capabilities" / "G21"
PRINCIPALS = ROOT / "examples" / "capabilities" / "G19" / "fixtures" / "principals.json"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
EDITOR, EDITOR_OTHER_TENANT, VIEWER = "local-demo-northwind-ada-0001", "local-demo-harbor-cy-0003", "local-demo-northwind-ben-0002"


def run(*args, timeout=120):
    return subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True, env=ENV, timeout=timeout)


class G21Capability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g21-test-"))
        self.procs = []
        self.keys = {}
        for name, k in (("ed", EDITOR), ("other", EDITOR_OTHER_TENANT), ("view", VIEWER)):
            p = self.tmp / ("key-%s.txt" % name)
            p.write_text(k + "\n")
            self.keys[name] = p

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                p.wait(10)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def serve(self, db=None, plan=None):
        db = db or self.tmp / "ledger.db"
        ready = self.tmp / ("ready-%d.json" % time.time_ns())
        cmd = [sys.executable, str(API), "serve", "--db", str(db), "--principals", str(PRINCIPALS), "--ready-file", str(ready)]
        if plan:
            pf = self.tmp / ("plan-%d.json" % time.time_ns())
            pf.write_text(json.dumps(dict(plan, schema="solaris.ledger-fault-plan/1")))
            cmd += ["--fault-plan", str(pf)]
        p = subprocess.Popen(cmd, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        for _ in range(300):
            if ready.exists() and ready.stat().st_size:
                return "http://127.0.0.1:%d" % json.loads(ready.read_text())["port"], db, p
            time.sleep(0.02)
        self.fail("server did not start")

    def stop(self, p):
        p.terminate()
        p.wait(10)

    def tool(self, *args):
        return run(TOOL, *args)

    def device(self, name):
        db = self.tmp / ("%s.db" % name)
        r = self.tool("init", "--db", db, "--device", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        return db

    def enq(self, db, *args, rc=0):
        r = self.tool("enqueue", "--db", db, *args)
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return r

    def sync(self, db, url, key="ed", *extra):
        r = self.tool("sync", "--db", db, "--base-url", url, "--key-file", self.keys[key], *extra)
        return r.returncode, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else None)

    def status(self, db):
        return json.loads(self.tool("status", "--db", db, "--json").stdout)

    def batch(self, db):
        self.enq(db, "create", "--ref", "r1", "--customer", "Blue Fern", "--amount", "1000", "--currency", "USD")
        self.enq(db, "create", "--ref", "r2", "--customer", "Kestrel", "--amount", "2500", "--currency", "EUR")
        self.enq(db, "pay", "--ref", "r1", "--amount", "400")
        self.enq(db, "pay", "--ref", "r1", "--amount", "600")
        self.enq(db, "void", "--ref", "r2")

    def server_rows(self, ledger):
        con = sqlite3.connect(str(ledger))
        try:
            return sorted(con.execute("SELECT customer, amount_cents, paid_cents, status FROM invoices").fetchall())
        finally:
            con.close()

    def assert_batch_once(self, ledger):
        self.assertEqual(self.server_rows(ledger), [("Blue Fern", 1000, 1000, "paid"), ("Kestrel", 2500, 0, "void")])
        self.assertEqual(run(API, "check", "--db", ledger).returncode, 0)

    def test_clean_control_offline_batch_then_one_sync(self):
        url, ledger, _p = self.serve()
        db = self.device("phone")
        self.batch(db)
        st = self.status(db)
        self.assertEqual(st["counts"]["pending"], 5)
        r1 = [e for e in st["invoices"] if e["ref"] == "r1"][0]
        self.assertEqual((r1["status"], r1["balance_cents"]), ("not_on_server", 0))
        rc, out = self.sync(db, url)
        self.assertEqual(rc, 0, out)
        self.assertEqual((out["sent"], out["counts"]["acked"]), (5, 5))
        self.assert_batch_once(ledger)
        st = self.status(db)
        r1 = [e for e in st["invoices"] if e["ref"] == "r1"][0]
        self.assertEqual((r1["status"], r1["balance_cents"], r1["pending_ops"]), ("paid", 0, []))
        self.assertTrue(r1["server_id"].startswith("inv_"))
        keys = [o["idempotency_key"] for o in st["ops"]]
        self.assertEqual(len(set(keys)), 5)
        self.assertTrue(all(k.startswith(st["install"] + ":") for k in keys))
        self.assertEqual(self.tool("check", "--db", db).returncode, 0)

    def test_client_crash_after_every_send_then_restart_makes_each_effect_once(self):
        for k in range(1, 6):
            with self.subTest(crash_after_send=k):
                url, ledger, p = self.serve(db=self.tmp / ("ledger-%d.db" % k))
                db = self.device("phone%d" % k)
                self.batch(db)
                self.assertEqual(self.sync(db, url, "ed", "--crash-after-send", str(k))[0], 70)
                st = self.status(db)
                self.assertEqual(st["counts"]["pending"], 5 - (k - 1))
                rc, _out = self.sync(db, url)
                self.assertEqual(rc, 0)
                self.assert_batch_once(ledger)
                replayed = [o["seq"] for o in self.status(db)["ops"] if o["replayed"]]
                self.assertEqual(replayed, [k])
                self.assertEqual(self.tool("check", "--db", db).returncode, 0)
                self.stop(p)

    def test_server_crash_after_commit_and_transient_failure_keep_one_effect_and_order(self):
        db = self.device("phone")
        self.batch(db)
        ops = self.status(db)["ops"]
        url, ledger, p = self.serve(plan={"crash_after_commit": [ops[0]["idempotency_key"]],
                                          "fail_before_commit": {ops[2]["idempotency_key"]: 1}})
        rc, out = self.sync(db, url)
        self.assertEqual(rc, 4, out)
        self.assertIn("unreachable", out["detail"])
        st = self.status(db)
        self.assertEqual(st["counts"]["pending"], 5)
        self.assertEqual([o["attempts"] for o in st["ops"]], [1, 0, 0, 0, 0])
        p.wait(10)
        url, ledger, p = self.serve(db=ledger, plan={"fail_before_commit": {ops[2]["idempotency_key"]: 1}})
        rc, out = self.sync(db, url)
        self.assertEqual(rc, 4)
        self.assertIn("503", out["detail"])
        st = self.status(db)
        self.assertEqual([o["state"] for o in st["ops"]], ["acked", "acked", "pending", "pending", "pending"])
        rc, out = self.sync(db, url)
        self.assertEqual(rc, 0, out)
        self.assert_batch_once(ledger)
        self.assertTrue(self.status(db)["ops"][0]["replayed"])

    def test_conflicts_are_explicit_held_and_resolved_by_the_user(self):
        url, ledger, _p = self.serve()
        a, b = self.device("a"), self.device("b")
        self.enq(a, "create", "--ref", "x", "--customer", "Orchard", "--amount", "1000", "--currency", "USD")
        self.assertEqual(self.sync(a, url)[0], 0)
        self.assertEqual(self.sync(b, url)[0], 0)
        sid = self.status(b)["invoices"][0]["server_id"]
        self.enq(b, "pay", "--ref", sid, "--amount", "700")
        self.enq(b, "void", "--ref", sid)
        self.enq(a, "pay", "--ref", "x", "--amount", "600")
        self.assertEqual(self.sync(a, url)[0], 0)
        rc, out = self.sync(b, url)
        self.assertEqual(rc, 1)
        self.assertEqual(out["result"], "needs_user")
        ops = self.status(b)["ops"]
        self.assertEqual((ops[0]["state"], ops[0]["reason"], ops[0]["http_status"]), ("conflict", "exceeds_balance", 409))
        self.assertEqual(ops[1]["state"], "pending")
        self.assertIn("held behind op 1", ops[1]["waiting"])
        self.assertEqual(self.server_rows(ledger), [("Orchard", 1000, 600, "open")])
        # resolving to retry gives a new key; the stored refusal of the old key is not replayed as success
        r = self.tool("resolve", "--db", b, "--op", "1", "--action", "retry")
        self.assertEqual(r.returncode, 0, r.stderr)
        rc, _out = self.sync(b, url)
        self.assertEqual(rc, 1)
        ops = self.status(b)["ops"]
        # the void now goes first and the server refuses it (part-paid); the retried pay waits behind it
        self.assertEqual([(o["seq"], o["state"]) for o in ops], [(1, "superseded"), (2, "conflict"), (3, "pending")])
        self.assertEqual((ops[1]["reason"], ops[2]["retry_of"]), ("cannot_void", 1))
        self.assertIn("held behind op 2", ops[2]["waiting"])
        self.assertNotEqual(ops[2]["idempotency_key"], ops[0]["idempotency_key"])
        self.assertEqual(self.tool("resolve", "--db", b, "--op", "3", "--action", "discard").returncode, 2)
        self.assertEqual(self.tool("resolve", "--db", b, "--op", "2", "--action", "discard").returncode, 0)
        rc, _out = self.sync(b, url)
        ops = self.status(b)["ops"]
        self.assertEqual((rc, ops[2]["state"], ops[2]["reason"]), (1, "conflict", "exceeds_balance"))
        self.assertEqual(self.server_rows(ledger), [("Orchard", 1000, 600, "open")])
        self.assertEqual(self.tool("resolve", "--db", b, "--op", "3", "--action", "discard").returncode, 0)
        self.assertEqual(self.sync(b, url)[0], 0)
        self.assertEqual(self.tool("check", "--db", b).returncode, 0)

    def test_out_of_order_server_state_never_rolls_back(self):
        url, ledger, _p = self.serve()
        db = self.device("phone")
        self.enq(db, "create", "--ref", "x", "--customer", "Lumen", "--amount", "1000", "--currency", "GBP")
        self.assertEqual(self.sync(db, url)[0], 0)
        doc = self.status(db)["invoices"][0]["server"]
        newer = dict(doc, paid_cents=400, balance_cents=600, version=doc["version"] + 1)
        older = dict(doc, version=doc["version"])
        (self.tmp / "new.json").write_text(json.dumps({"data": [newer]}))
        (self.tmp / "old.json").write_text(json.dumps({"data": [older]}))
        self.assertEqual(json.loads(self.tool("apply-snapshot", "--db", db, self.tmp / "new.json").stdout), {"applied": 1, "stale_ignored": 0})
        self.assertEqual(json.loads(self.tool("apply-snapshot", "--db", db, self.tmp / "old.json").stdout), {"applied": 0, "stale_ignored": 1})
        self.assertEqual(self.status(db)["invoices"][0]["balance_cents"], 600)
        # a change to an invoice the server no longer knows (404) is a conflict, and later changes wait
        ghost = dict(doc, id="inv_00000000000000aa")
        (self.tmp / "ghost.json").write_text(json.dumps({"data": [ghost]}))
        self.tool("apply-snapshot", "--db", db, self.tmp / "ghost.json")
        self.enq(db, "pay", "--ref", ghost["id"], "--amount", "100")
        self.enq(db, "void", "--ref", ghost["id"])
        rc, _out = self.sync(db, url, "ed", "--no-pull")
        ops = self.status(db)["ops"]
        self.assertEqual((rc, ops[1]["state"], ops[1]["reason"], ops[2]["state"]), (1, "conflict", "not_found", "pending"))
        (self.tmp / "bad.json").write_text(json.dumps({"data": [dict(doc, version=True)]}))
        self.assertEqual(self.tool("apply-snapshot", "--db", db, self.tmp / "bad.json").returncode, 2)

    def test_enqueue_validation_refuses_and_records_nothing(self):
        db = self.device("phone")
        bad = [("create", "--ref", "x", "--customer", "C", "--amount", "10.5", "--currency", "USD"),
               ("create", "--ref", "x", "--customer", "C", "--amount", "0", "--currency", "USD"),
               ("create", "--ref", "x", "--customer", "C", "--amount", "100", "--currency", "JPY"),
               ("create", "--ref", "x", "--customer", "", "--amount", "100", "--currency", "USD"),
               ("create", "--ref", "a b", "--customer", "C", "--amount", "100", "--currency", "USD"),
               ("create", "--ref", "inv_0123456789abcdef", "--customer", "C", "--amount", "100", "--currency", "USD"),
               ("pay", "--ref", "nobody", "--amount", "100"),
               ("void", "--ref", "nobody")]
        for args in bad:
            with self.subTest(args=args):
                self.enq(db, *args, rc=2)
        self.enq(db, "create", "--ref", "x", "--customer", "C", "--amount", "100", "--currency", "USD")
        self.enq(db, "create", "--ref", "x", "--customer", "C", "--amount", "100", "--currency", "USD", rc=2)
        self.assertEqual(self.status(db)["counts"]["pending"], 1)
        self.assertEqual(self.tool("init", "--db", db, "--device", "phone").returncode, 2)
        self.assertEqual(self.status(db)["counts"]["pending"], 1)
        # a reinstall with the same device name gets its own keys, so it can never collect another's answers
        again = self.tmp / "phone-reinstalled.db"
        self.assertEqual(self.tool("init", "--db", again, "--device", "phone").returncode, 0)
        self.assertNotEqual(self.status(again)["install"], self.status(db)["install"])

    def test_refused_key_and_non_loopback_url_send_nothing(self):
        url, ledger, _p = self.serve()
        db = self.device("phone")
        self.batch(db)
        rc, out = self.sync(db, url, "view")
        self.assertEqual(rc, 3, out)
        self.assertEqual(self.status(db)["counts"]["pending"], 5)
        self.assertEqual(self.server_rows(ledger), [])
        r = self.tool("sync", "--db", db, "--base-url", "http://192.0.2.10:8080", "--key-file", self.keys["ed"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("loopback", r.stderr)

    def test_second_sync_on_a_held_outbox_is_busy(self):
        url, ledger, _p = self.serve()
        db = self.device("phone")
        self.batch(db)
        with open(str(db) + ".lock", "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            rc, out = self.sync(db, url)
            fcntl.flock(fh, fcntl.LOCK_UN)
        self.assertEqual((rc, out["result"]), (5, "busy"))
        self.assertEqual(self.server_rows(ledger), [])
        self.assertEqual(self.sync(db, url)[0], 0)
        self.assert_batch_once(ledger)

    def test_pull_is_tenant_scoped_and_discarding_a_create_names_its_dependents(self):
        url, _ledger, _p = self.serve()
        a, z = self.device("north"), self.device("harbor")
        self.enq(a, "create", "--ref", "x", "--customer", "North", "--amount", "100", "--currency", "USD")
        self.assertEqual(self.sync(a, url)[0], 0)
        self.assertEqual(self.sync(z, url, "other")[0], 0)
        self.assertEqual(self.status(z)["invoices"], [])
        # a create the server rejects (here: forced by editing the stored body) holds its dependents by name
        self.enq(z, "create", "--ref", "y", "--customer", "Harbor", "--amount", "100", "--currency", "USD")
        self.enq(z, "pay", "--ref", "y", "--amount", "50")
        con = sqlite3.connect(str(z))
        con.execute("UPDATE ops SET body = ? WHERE seq = 1", ('{"amount_cents":100,"currency":"USD","customer":"H","tenant":"north"}',))
        con.commit(); con.close()
        rc, _out = self.sync(z, url, "other")
        self.assertEqual(rc, 1)
        ops = self.status(z)["ops"]
        self.assertEqual((ops[0]["state"], ops[0]["reason"]), ("rejected", "tenant_is_server_derived"))
        self.assertIn("waits for create op 1", ops[1]["waiting"])
        r = self.tool("resolve", "--db", z, "--op", "1", "--action", "discard")
        self.assertEqual(json.loads(r.stdout)["also_discarded"], [2])
        self.assertEqual(self.sync(z, url, "other")[0], 0)
        self.assertEqual(self.tool("check", "--db", z).returncode, 0)

    def test_check_names_tampering(self):
        url, _ledger, _p = self.serve()
        db = self.device("phone")
        self.batch(db)
        self.assertEqual(self.sync(db, url)[0], 0)
        for sql, needle in (("UPDATE ops SET response = NULL WHERE seq = 3", "acked without a 2xx"),
                            ("UPDATE ops SET idem = 'other:000002' WHERE seq = 2", "not this install's key"),
                            ("UPDATE refs SET server_id = 'inv_0000000000000000' WHERE ref = 'r1'", "not mapped"),
                            ("UPDATE ops SET state = 'pending' WHERE seq = 4", "pending but has a server answer")):
            with self.subTest(sql=sql):
                c = self.tmp / "copy.db"
                shutil.copy(str(db), str(c))
                for ext in ("-wal", "-shm"):
                    if Path(str(db) + ext).exists():
                        shutil.copy(str(db) + ext, str(c) + ext)
                con = sqlite3.connect(str(c)); con.execute(sql); con.commit(); con.close()
                r = self.tool("check", "--db", c)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(needle, r.stdout)
                for ext in ("", "-wal", "-shm"):
                    if Path(str(c) + ext).exists():
                        Path(str(c) + ext).unlink()
        self.assertEqual(self.tool("check", "--db", self.tmp / "missing.db").returncode, 2)

    def test_doc_commands_and_exit_codes_match_the_tool(self):
        doc = (ROOT / "employees" / "engineering" / "mobile-developer" / "offline-sync.md").read_text()
        for cmd in ("init", "enqueue", "sync", "status", "resolve", "apply-snapshot", "check"):
            self.assertIn("offline_sync.py %s" % cmd, doc)
        src = TOOL.read_text()
        for code in ("0", "1", "2", "3", "4", "5", "70"):
            self.assertIn("| %s |" % code, doc)
        self.assertIn("Exit codes: 0 done; 1 conflicts", src)
        contract = json.loads((ROOT / "employees" / "engineering" / "mobile-developer" / "capability.contract.json").read_text())
        self.assertIn("offline_sync.py", contract["dependencies"]["scripts"])
        self.assertIn("offline-sync.md", contract["dependencies"]["references"])

    def test_oracle_passes_the_tool_and_rejects_the_controls(self):
        r = run(EX / "sync_oracle.py", "--quick", timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])
        self.assertEqual(r.stdout.strip().splitlines()[-1], "PASSED 13/13")
        for ctl, want in (("naive_sync.py", "REJECTED 4/13"), ("noop_sync.py", "REJECTED 0/13")):
            r = run(EX / "sync_oracle.py", "--quick", "--tool", EX / ctl, timeout=600)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout.strip().splitlines()[-1], want)


    def test_redirects_never_contact_target_or_ack_pending_change(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        hits = []
        class Sink(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data": [], "next_after": null}')
            do_POST = do_GET
            def log_message(self, *args):
                pass
        sink = ThreadingHTTPServer(('127.0.0.1', 0), Sink)
        target = 'http://127.0.0.1:%d/capture' % sink.server_port
        class Redirect(Sink):
            code = 302
            def do_GET(self):
                self.send_response(self.code)
                self.send_header('Location', target)
                self.end_headers()
            do_POST = do_GET
        source = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (sink, source)]
        for t in threads:
            t.start()
        try:
            url = 'http://127.0.0.1:%d' % source.server_port
            for code in (301, 302, 303, 307, 308):
                Redirect.code = code
                for method in ('GET', 'POST'):
                    with self.subTest(code=code, method=method):
                        db = self.device('redir%d%s' % (code, method))
                        if method == 'POST':
                            self.enq(db, 'create', '--ref', 'r', '--customer', 'Synthetic', '--amount', '100', '--currency', 'USD')
                        rc, out = self.sync(db, url)
                        self.assertEqual(rc, 4, out)
                        self.assertIn('redirect refused', out['detail'])
                        self.assertEqual(out['counts']['acked'], 0)
                        self.assertEqual(out['pending'], int(method == 'POST'))
                        self.assertEqual(hits, [])
        finally:
            for s in (sink, source):
                s.shutdown()
                s.server_close()
            for t in threads:
                t.join(5)

    def test_concurrent_creates_and_resolutions_have_single_winner(self):
        db = self.device('race')
        con = sqlite3.connect(str(db), isolation_level=None)
        def race(args):
            con.execute('BEGIN IMMEDIATE')
            ps = [subprocess.Popen([sys.executable, str(TOOL)] + [str(x) for x in args],
                                   env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            try:
                time.sleep(0.4)
                self.assertTrue(all(p.poll() is None for p in ps))
            finally:
                con.execute('COMMIT')
            output = [p.communicate(timeout=30) for p in ps]
            self.assertEqual(sorted(p.returncode for p in ps), [0, 2, 2, 2], output)
        try:
            race(['enqueue', '--db', db, 'create', '--ref', 'same', '--customer', 'Synthetic', '--amount', '100', '--currency', 'USD'])
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ops').fetchone()[0], 1)
            con.execute("UPDATE ops SET state='rejected', http_status=422, response='{}'")
            race(['resolve', '--db', db, '--op', '1', '--action', 'retry'])
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ops').fetchone()[0], 2)
            self.assertEqual(self.tool('check', '--db', db).returncode, 0)
        finally:
            con.close()
        url, ledger, _ = self.serve()
        self.assertEqual(self.sync(db, url)[0], 0)
        self.assertEqual(len(self.server_rows(ledger)), 1)

    def test_retry_transaction_rolls_back_if_supersession_fails(self):
        db = self.device('atomic')
        self.enq(db, 'create', '--ref', 'r', '--customer', 'Synthetic', '--amount', '100', '--currency', 'USD')
        with sqlite3.connect(str(db)) as con:
            con.execute("UPDATE ops SET state='rejected', http_status=422, response='{}'")
            con.execute("CREATE TRIGGER fail_sup BEFORE UPDATE OF state ON ops WHEN NEW.state='superseded' BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        result = self.tool('resolve', '--db', db, '--op', '1', '--action', 'retry')
        self.assertNotEqual(result.returncode, 0)
        with sqlite3.connect(str(db)) as con:
            self.assertEqual(con.execute('SELECT seq,state FROM ops').fetchall(), [(1, 'rejected')])
        self.assertEqual(self.tool('check', '--db', db).returncode, 0)

    def test_loopback_sync_ignores_environment_proxy(self):
        url, ledger, _ = self.serve()
        db = self.device('proxy')
        self.enq(db, 'create', '--ref', 'r', '--customer', 'Synthetic', '--amount', '100', '--currency', 'USD')
        env = dict(ENV, http_proxy='http://127.0.0.1:1', HTTP_PROXY='http://127.0.0.1:1',
                   all_proxy='http://127.0.0.1:1', ALL_PROXY='http://127.0.0.1:1', no_proxy='', NO_PROXY='')
        result = subprocess.run([sys.executable, str(TOOL), 'sync', '--db', str(db), '--base-url', url,
                                 '--key-file', str(self.keys['ed'])], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.server_rows(ledger)), 1)

    def test_orphan_retry_cannot_bypass_duplicate_intent_check(self):
        db = self.device('orphan')
        self.enq(db, 'create', '--ref', 'same', '--customer', 'Synthetic', '--amount', '100', '--currency', 'USD')
        with sqlite3.connect(str(db)) as con:
            con.execute("INSERT INTO ops(seq,idem,kind,ref,body,created_at,state,retry_of) SELECT 2, substr(idem,1,length(idem)-6)||'000002',kind,ref,body,created_at,state,1 FROM ops WHERE seq=1")
        result = self.tool('check', '--db', db, '--json')
        self.assertEqual(result.returncode, 1)
        self.assertIn('matching superseded predecessor', result.stdout)
        url, ledger, _ = self.serve()
        self.assertEqual(self.sync(db, url)[0], 2)
        self.assertEqual(self.server_rows(ledger), [])

    def test_legacy_duplicate_outbox_is_rejected_before_network_effect(self):
        db = self.device('legacy')
        self.enq(db, 'create', '--ref', 'same', '--customer', 'Synthetic', '--amount', '100', '--currency', 'USD')
        with sqlite3.connect(str(db)) as con:
            con.execute("INSERT INTO ops(seq,idem,kind,ref,body,created_at,state) SELECT 2, substr(idem,1,length(idem)-6)||'000002',kind,ref,body,created_at,state FROM ops WHERE seq=1")
        result = self.tool('check', '--db', db, '--json')
        self.assertEqual(result.returncode, 1)
        self.assertIn('duplicate create roots', result.stdout)
        url, ledger, _ = self.serve()
        rc, out = self.sync(db, url)
        self.assertEqual(rc, 2, out)
        self.assertEqual(out['sent'], 0)
        self.assertEqual(self.server_rows(ledger), [])
        self.assertEqual(out['pending'], 2)


if __name__ == "__main__":
    unittest.main()
