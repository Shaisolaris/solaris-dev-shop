#!/usr/bin/env python3
"""G19 oracle: does a candidate local API stop duplicate effects and cross-tenant access, and stay
correct across retries and a restart?

The oracle owns the truth. It writes its own synthetic principals (seeded, four tenants), starts the
candidate on loopback, drives it with its own HTTP client and compares every listing with what it
knows it asked for. It does not use the shipped probe. A candidate is any command with
    <cmd> serve --db FILE --principals FILE --port 0 --ready-file FILE [--fault-plan FILE]
serving the endpoints documented in duplicate-safe-api.md, with the solaris.ledger-fault-plan/1 drill.
No network beyond 127.0.0.1, no live target.

Usage: boundary_oracle.py --server "python3 path/to/ledger_api.py" [--seed N] [--scale N] [--json]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import http.client
import json
import os
import random
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TENANTS = ["aldane", "brisk", "corvo", "delmar"]


class Server:
    def __init__(self, cmd, work: Path, principals: Path, db: Path, fault: dict | None = None, extra=()):
        self.ready = work / f"ready-{time.time_ns()}.json"
        args = shlex.split(cmd) + ["serve", "--db", str(db), "--principals", str(principals),
                                   "--port", "0", "--ready-file", str(self.ready)] + list(extra)
        if fault is not None:
            fp = work / f"fault-{time.time_ns()}.json"
            fp.write_text(json.dumps(dict(fault, schema="solaris.ledger-fault-plan/1")))
            args += ["--fault-plan", str(fp)]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        self.port = None

    def wait(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                return False
            try:
                info = json.loads(self.ready.read_text())
                self.port = int(info["port"])
                c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
                c.request("GET", "/api/v1/health")
                c.getresponse().read()
                c.close()
                return True
            except (OSError, ValueError, KeyError, http.client.HTTPException):
                time.sleep(0.05)
        return False

    def stop(self):
        if self.proc.poll() is None:
            # The server may exit between poll() and killpg() (o8 crashes it by design). The group is then gone
            # (ProcessLookupError) or its leader is an unreaped zombie, which macOS answers with EPERM
            # (PermissionError). Either way it has stopped: reap it below instead of failing the check.
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                self.proc.wait(5)
        if self.proc.stderr:
            self.proc.stderr.close()


class Api:
    def __init__(self, port):
        self.port = port

    def call(self, method, path, key=None, body=None, idem=None, headers=None, raw=None):
        h = dict(headers or {})
        if key:
            h["Authorization"] = "Bearer " + key
        if idem:
            h["Idempotency-Key"] = idem
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None:
            h["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            payload = r.read()
            try:
                js = json.loads(payload.decode() or "null")
            except ValueError:
                js = None
            return r.status, js, {k.lower(): v for k, v in r.getheaders()}
        except (OSError, http.client.HTTPException):
            return 0, None, {}
        finally:
            c.close()

    def listing(self, key):
        out, after = [], None
        for _ in range(500):
            st, js, _ = self.call("GET", "/api/v1/invoices?limit=100" + (f"&after={after}" if after else ""), key)
            if st != 200 or not isinstance(js, dict) or not isinstance(js.get("data"), list):
                return None
            out.extend(js["data"])
            after = js.get("next_after")
            if not after:
                return out
        return None

    def create(self, key, customer, amount, idem, currency="USD", extra=None, headers=None):
        body = {"customer": customer, "amount_cents": amount, "currency": currency}
        body.update(extra or {})
        return self.call("POST", "/api/v1/invoices", key, body, idem, headers)

    def pay(self, key, iid, amount, idem):
        return self.call("POST", f"/api/v1/invoices/{iid}/payments", key, {"amount_cents": amount}, idem)


def code(js):
    return js.get("error", {}).get("code") if isinstance(js, dict) and isinstance(js.get("error"), dict) else None


def par(fn, n, workers=None):
    with cf.ThreadPoolExecutor(max_workers=workers or n) as ex:
        return list(ex.map(fn, range(n)))


class Oracle:
    def __init__(self, cmd, seed, scale):
        self.cmd, self.seed, self.scale = cmd, seed, scale
        self.rng = random.Random(seed)
        self.work = Path(tempfile.mkdtemp(prefix="g19-oracle-"))
        self.keys = {}
        principals = []
        for t in TENANTS:
            for user, role in (("ed", "editor"), ("vi", "viewer")):
                k = f"oracle-{seed}-{t}-{user}-{self.rng.getrandbits(48):012x}"
                self.keys[(t, role)] = k
                principals.append({"key": k, "tenant": t, "user": user, "role": role})
        self.principals = self.work / "principals.json"
        self.principals.write_text(json.dumps({"schema": "solaris.ledger-principals/1", "principals": principals}))
        self.results = []

    def ed(self, t):
        return self.keys[(t, "editor")]

    def fresh(self, name, fault=None, db=None):
        db = db or self.work / f"{name}.db"
        s = Server(self.cmd, self.work, self.principals, db, fault)
        if not s.wait():
            s.stop()
            return None, None, db
        return s, Api(s.port), db

    def check(self, cid, title, fn):
        t0 = time.time()
        problems, info = [], {}
        try:
            fn(problems, info)
        except Exception as e:  # a crash in the candidate path is a failed check, not an oracle crash
            problems.append(f"oracle saw {type(e).__name__}: {e}")
        self.results.append({"id": cid, "title": title, "pass": not problems, "problems": problems[:8],
                             "info": info, "seconds": round(time.time() - t0, 2)})

    # ------------------------------------------------------------------ checks
    def o1(self, P, info):
        s, api, _ = self.fresh("o1")
        if not api:
            return P.append("server did not start")
        try:
            A = self.ed("aldane")
            st, inv, h = api.create(A, "Lumen Supply", 4250, "o1-create")
            if st != 201 or not isinstance(inv, dict):
                return P.append(f"create answered {st}")
            want = {"customer": "Lumen Supply", "amount_cents": 4250, "currency": "USD", "paid_cents": 0, "status": "open"}
            for k, v in want.items():
                if inv.get(k) != v:
                    P.append(f"created invoice {k}={inv.get(k)!r}, expected {v!r}")
            if h.get("location") != f"/api/v1/invoices/{inv.get('id')}":
                P.append(f"Location header {h.get('location')!r}")
            if h.get("idempotent-replayed") != "false":
                P.append("first create not marked Idempotent-Replayed: false")
            st, got, _ = api.call("GET", f"/api/v1/invoices/{inv['id']}", A)
            if st != 200 or got != inv:
                P.append(f"read-back differs ({st})")
            lst = api.listing(A)
            if lst is None or [x.get("id") for x in lst] != [inv["id"]]:
                P.append(f"owner list should hold exactly the new invoice, got {None if lst is None else len(lst)}")
            st, p1, _ = api.pay(A, inv["id"], 1000, "o1-pay-1")
            st2, p2, _ = api.pay(A, inv["id"], 3250, "o1-pay-2")
            if st != 201 or st2 != 201 or not isinstance(p2, dict) or p2.get("status") != "paid" or p2.get("paid_cents") != 4250:
                P.append(f"payments 1000 + 3250 should make the invoice paid: {st} {st2} {p2}")
            st, over, _ = api.pay(A, inv["id"], 1, "o1-pay-3")
            if st != 409:
                P.append(f"paying a paid invoice answered {st}, expected 409")
            st, v, _ = api.create(A, "Void Me", 100, "o1-create-2")
            st2, vv, _ = api.call("POST", f"/api/v1/invoices/{v['id']}/void", A, {"reason": "duplicate"}, "o1-void")
            if st2 != 200 or not isinstance(vv, dict) or vv.get("status") != "void":
                P.append(f"void of an open unpaid invoice answered {st2} {vv}")
            info["invoices"] = 2
        finally:
            s.stop()

    def o2(self, P, info):
        s, api, _ = self.fresh("o2")
        if not api:
            return P.append("server did not start")
        try:
            A = self.ed("brisk")
            n = 32
            res = par(lambda i: api.create(A, "Replay Co", 777, "o2-same-key"), n)
            sts = [r[0] for r in res]
            bodies = {json.dumps(r[1], sort_keys=True) for r in res if r[0] == 201}
            lst = api.listing(A) or []
            made = [x for x in lst if x.get("customer") == "Replay Co"]
            replayed = sum(1 for r in res if r[2].get("idempotent-replayed") == "true")
            info.update(requests=n, statuses=sorted(set(sts)), distinct_bodies=len(bodies), invoices=len(made), replayed=replayed)
            if len(made) != 1:
                P.append(f"{n} concurrent replays made {len(made)} invoices, expected exactly 1")
            if set(sts) != {201} or len(bodies) != 1:
                P.append(f"every replay should get the same 201 body: statuses {sorted(set(sts))}, {len(bodies)} distinct bodies")
            if replayed != n - 1:
                P.append(f"{replayed} responses marked replayed, expected {n - 1}")
        finally:
            s.stop()

    def o3(self, P, info):
        s, api, _ = self.fresh("o3")
        if not api:
            return P.append("server did not start")
        try:
            A = self.ed("corvo")
            _, inv, _ = api.create(A, "Pay Once", 1000, "o3-create")
            res = par(lambda i: api.pay(A, inv["id"], 100, "o3-pay-same"), 24)
            res += [api.pay(A, inv["id"], 100, "o3-pay-same") for _ in range(3)]
            _, after, _ = api.call("GET", f"/api/v1/invoices/{inv['id']}", A)
            if not isinstance(after, dict) or after.get("paid_cents") != 100:
                P.append(f"27 replays of one payment left paid_cents={None if not isinstance(after, dict) else after.get('paid_cents')}, expected 100")
            _, inv2, _ = api.create(A, "Race", 1000, "o3-create-2")
            res = par(lambda i: api.pay(A, inv2["id"], 300, f"o3-race-{i}"), 16)
            ok = [r for r in res if r[0] == 201]
            refused = [r for r in res if r[0] == 409 and code(r[1]) == "exceeds_balance"]
            _, after2, _ = api.call("GET", f"/api/v1/invoices/{inv2['id']}", A)
            paid = after2.get("paid_cents") if isinstance(after2, dict) else None
            info.update(race_accepted=len(ok), race_refused=len(refused), race_paid=paid)
            if len(ok) != 3 or paid != 900 or len(refused) != 13:
                P.append(f"16 concurrent payments of 300 on 1000: accepted {len(ok)}, refused {len(refused)}, paid {paid}; expected 3, 13, 900")
            if refused:
                # a refused payment is a decided outcome: its replay is marked replayed and its key cannot be reused
                rk = f"o3-race-{res.index(refused[0])}"
                st, js, h = api.pay(A, inv2["id"], 300, rk)
                if st != 409 or h.get("idempotent-replayed") != "true":
                    P.append(f"replay of a refused payment answered {st}, Idempotent-Replayed {h.get('idempotent-replayed')!r}; expected 409, 'true'")
                st, js, _ = api.pay(A, inv2["id"], 100, rk)
                if st != 422 or code(js) != "idempotency_key_reused":
                    P.append(f"reusing a refused payment's key for another amount answered {st} {code(js)}, expected 422 idempotency_key_reused")
        finally:
            s.stop()

    def _attack_world(self, api):
        """Create a known world in tenants aldane and brisk; return truth."""
        truth = {}
        for t in ("aldane", "brisk"):
            ids = []
            for i in range(25):
                st, inv, _ = api.create(self.ed(t), f"{t}-cust-{i}", 100 + i, f"world-{t}-{i}")
                ids.append(inv["id"])
            truth[t] = ids
        return truth

    def o4(self, P, info):
        s, api, _ = self.fresh("o4")
        if not api:
            return P.append("server did not start")
        try:
            truth = self._attack_world(api)
            A, B = self.ed("aldane"), self.ed("brisk")
            missing = api.call("GET", "/api/v1/invoices/inv_" + "0" * 16, B)
            for iid in truth["aldane"][:10]:
                st, js, _ = api.call("GET", f"/api/v1/invoices/{iid}", B)
                if (st, code(js)) != (missing[0], code(missing[1])) or "aldane" in json.dumps(js):
                    P.append(f"brisk reading aldane {iid}: {st} {code(js)}; a missing id gives {missing[0]} {code(missing[1])}")
                    break
            lst = api.listing(B) or []
            seen = {x.get("id") for x in lst}
            if seen != set(truth["brisk"]):
                P.append(f"brisk list holds {len(seen & set(truth['aldane']))} aldane ids and {len(seen & set(truth['brisk']))}/25 own ids")
            st, js, _ = api.call("GET", f"/api/v1/invoices?limit=5&after={truth['aldane'][3]}", B)
            if st == 200 and isinstance(js, dict) and any(x.get("id") in truth["aldane"] for x in js.get("data", [])):
                P.append("an aldane id used as a brisk cursor exposed aldane rows")
            st2, js2, _ = api.call("GET", "/api/v1/invoices?limit=5&after=inv_" + "0" * 16, B)
            if (st, code(js)) != (st2, code(js2)):
                P.append(f"an aldane id as a brisk cursor answers {st} {code(js)}, a made-up id answers {st2} {code(js2)}: existence signal")
            pages, after = [], None
            while True:
                st, js, _ = api.call("GET", "/api/v1/invoices?limit=10" + (f"&after={after}" if after else ""), A)
                if st != 200:
                    P.append(f"page answered {st}")
                    break
                pages.append([x["id"] for x in js["data"]])
                after = js.get("next_after")
                if not after or len(pages) > 10:
                    break
            if [len(p) for p in pages] != [10, 10, 5] or sum(pages, []) != truth["aldane"]:
                P.append(f"limit=10 paging over 25 gave {[len(p) for p in pages]}, expected [10, 10, 5] in creation order")
            for bad in ("limit=0", "limit=101", "limit=x"):
                if api.call("GET", f"/api/v1/invoices?{bad}", A)[0] != 422:
                    P.append(f"?{bad} not refused with 422")
            info["pages"] = [len(p) for p in pages]
        finally:
            s.stop()

    def o5(self, P, info):
        s, api, _ = self.fresh("o5")
        if not api:
            return P.append("server did not start")
        try:
            truth = self._attack_world(api)
            A, B = self.ed("aldane"), self.ed("brisk")
            before = api.listing(A)
            attempts = 0
            for n, iid in enumerate(truth["aldane"]):
                for path, body in ((f"/api/v1/invoices/{iid}/payments", {"amount_cents": 1}), (f"/api/v1/invoices/{iid}/void", {})):
                    st, _, _ = api.call("POST", path, B, body, f"x-{n}-{len(path)}")
                    attempts += 1
                    if 200 <= st < 300:
                        P.append(f"brisk write to aldane {path} answered {st}")
            st1, j1, _ = api.create(B, "smuggle-body", 5, "smuggle-1", extra={"tenant_id": "aldane"})
            st2, j2, _ = api.create(B, "smuggle-header", 5, "smuggle-2", headers={"X-Tenant-Id": "aldane"})
            after = api.listing(A)
            if after != before:
                P.append("aldane's invoices changed after brisk's attacks")
            if 200 <= st1 < 300 and isinstance(j1, dict) and j1.get("tenant") == "aldane":
                P.append("a body tenant_id placed a record in aldane")
            if 200 <= st2 < 300 and isinstance(j2, dict) and j2.get("tenant") not in (None, "brisk"):
                P.append("an X-Tenant-Id header placed a record outside brisk")
            info.update(cross_tenant_writes=attempts, body_smuggle_status=st1, header_smuggle_status=st2)
        finally:
            s.stop()

    def o6(self, P, info):
        s, api, _ = self.fresh("o6")
        if not api:
            return P.append("server did not start")
        try:
            A, B = self.ed("corvo"), self.ed("delmar")
            _, ia, _ = api.create(A, "Shared Key", 500, "shared-key-1")
            st, ib, h = api.create(B, "Shared Key", 500, "shared-key-1")
            if st != 201 or not isinstance(ib, dict) or ib.get("id") == ia.get("id") or h.get("idempotent-replayed") == "true":
                P.append("delmar reusing corvo's key got corvo's cached response or no own record")
            n0 = len(api.listing(A))
            st, js, _ = api.create(A, "Shared Key", 501, "shared-key-1")
            if st != 422 or code(js) != "idempotency_key_reused":
                P.append(f"same key with a different body answered {st} {code(js)}, expected 422 idempotency_key_reused")
            st2, _, _ = api.create(A, "No Key", 5, None)
            st3, _, _ = api.create(A, "Bad Key", 5, "bad key with spaces")
            if not (400 <= st2 < 500) or not (400 <= st3 < 500):
                P.append(f"missing/invalid Idempotency-Key answered {st2}/{st3}")
            if len(api.listing(A)) != n0:
                P.append("refused requests made records")
            info.update(key_reuse=st, missing_key=st2, invalid_key=st3)
        finally:
            s.stop()

    def o7(self, P, info):
        s, api, _ = self.fresh("o7")
        if not api:
            return P.append("server did not start")
        try:
            A, V = self.ed("aldane"), self.keys[("aldane", "viewer")]
            _, inv, _ = api.create(A, "Authz", 300, "o7-create")
            before = api.listing(A)
            out = {"no_key": api.create(None, "x", 1, "o7-a")[0], "unknown_key": api.create("nobody-" + "z" * 20, "x", 1, "o7-b")[0],
                   "viewer_create": api.create(V, "x", 1, "o7-c")[0], "viewer_pay": api.pay(V, inv["id"], 1, "o7-d")[0],
                   "no_key_read": api.call("GET", f"/api/v1/invoices/{inv['id']}")[0],
                   "viewer_read": api.call("GET", f"/api/v1/invoices/{inv['id']}", V)[0]}
            want = {"no_key": 401, "unknown_key": 401, "viewer_create": 403, "viewer_pay": 403, "no_key_read": 401, "viewer_read": 200}
            for k, v in want.items():
                if out[k] != v:
                    P.append(f"{k} answered {out[k]}, expected {v}")
            if api.listing(A) != before:
                P.append("refused calls changed aldane's invoices")
            info.update(out)
        finally:
            s.stop()

    def o8(self, P, info):
        db = self.work / "o8.db"
        A = self.ed("brisk")
        s, api, _ = self.fresh("o8a", {"fail_before_commit": {"r-transient": 1}, "crash_after_commit": ["r-after"],
                                       "crash_before_commit": []}, db)
        if not api:
            return P.append("server did not start with a fault plan")
        try:
            body = ("Retry Ltd", 640, "r-transient")
            st1, js1, _ = api.create(A, *body)
            st2, js2, h2 = api.create(A, *body)
            if st1 != 503 or st2 != 201 or h2.get("idempotent-replayed") != "false":
                P.append(f"transient failure then retry: {st1} then {st2} (replayed {h2.get('idempotent-replayed')}); expected 503 then fresh 201")
            st3, _, _ = api.create(A, "After Commit", 900, "r-after")
            if st3 != 0:
                P.append(f"crash_after_commit request answered {st3}; the server should have died before replying")
        finally:
            s.stop()
        s, api, _ = self.fresh("o8b", None, db)
        if not api:
            return P.append("server did not restart on the same db")
        try:
            st4, js4, h4 = api.create(A, "After Commit", 900, "r-after")
            lst = api.listing(A) or []
            if st4 != 201 or h4.get("idempotent-replayed") != "true":
                P.append(f"retry after a crash past commit: {st4}, replayed {h4.get('idempotent-replayed')}; expected the stored 201")
            if [x.get("customer") for x in lst].count("After Commit") != 1 or [x.get("customer") for x in lst].count("Retry Ltd") != 1:
                P.append(f"after restart the list holds {[x.get('customer') for x in lst]}")
        finally:
            s.stop()
        s, api, _ = self.fresh("o8c", {"crash_before_commit": ["r-before"]}, db)
        if not api:
            return P.append("server did not start with crash_before_commit")
        try:
            st5, _, _ = api.create(A, "Before Commit", 120, "r-before")
            if st5 != 0:
                P.append(f"crash_before_commit request answered {st5}")
        finally:
            s.stop()
        s, api, _ = self.fresh("o8d", None, db)
        if not api:
            return P.append("server did not restart after crash_before_commit")
        try:
            st6, _, h6 = api.create(A, "Before Commit", 120, "r-before")
            names = [x.get("customer") for x in (api.listing(A) or [])]
            if st6 != 201 or h6.get("idempotent-replayed") != "false" or names.count("Before Commit") != 1:
                P.append(f"retry after a crash before commit: {st6}, replayed {h6.get('idempotent-replayed')}, count {names.count('Before Commit')}; expected one fresh effect")
            info.update(final_list=names)
        finally:
            s.stop()

    def o9(self, P, info):
        s, api, _ = self.fresh("o9")
        if not api:
            return P.append("server did not start")
        try:
            n = self.scale
            ops = []
            for i in range(n):
                t = TENANTS[i % 4]
                ops.append((t, f"s-{t}-{i}", f"scale-{i}", 100 + i % 97))
            work = ops + [ops[self.rng.randrange(n)] for _ in range(n // 4)]
            self.rng.shuffle(work)
            t0 = time.time()
            res = par(lambda j: api.create(self.ed(work[j][0]), work[j][1], work[j][3], work[j][2]), len(work), 16)
            secs = time.time() - t0
            bad = [r[0] for r in res if r[0] != 201]
            if bad:
                P.append(f"{len(bad)} of {len(work)} requests failed: {sorted(set(bad))}")
            for t in TENANTS:
                want = sorted(o[1] for o in ops if o[0] == t)
                got = sorted(x.get("customer") for x in (api.listing(self.ed(t)) or []))
                if got != want:
                    P.append(f"{t}: {len(got)} invoices, expected {len(want)} (duplicates or losses)")
            info.update(unique=n, requests=len(work), workers=16, seconds=round(secs, 2))
            if secs > 120:
                P.append(f"{len(work)} requests took {secs:.0f}s, over the 120 s budget")
        finally:
            s.stop()

    def _refuses(self, args):
        try:
            return subprocess.run(shlex.split(self.cmd) + args, capture_output=True, timeout=10).returncode
        except subprocess.TimeoutExpired:  # run() has killed it; it kept running instead of refusing
            return "still running after 10 s"

    def o10(self, P, info):
        db = self.work / "o10.db"
        for host in ("0.0.0.0", "192.0.2.10"):
            rc = self._refuses(["serve", "--db", str(db), "--principals", str(self.principals),
                                "--port", "0", "--host", host, "--ready-file", str(self.work / "o10r.json")])
            if rc != 2 or (self.work / "o10r.json").exists():
                P.append(f"--host {host} gave exit {rc}; expected 2 and no listener")
        broken = self.work / "broken.json"
        for content in ('{"schema": "solaris.ledger-principals/1", "principals": []}', "{not json",
                        '{"schema": "solaris.ledger-principals/1", "principals": [{"key": "short", "tenant": "a", "user": "u", "role": "editor"}]}'):
            broken.write_text(content)
            rc = self._refuses(["serve", "--db", str(db), "--principals", str(broken), "--port", "0"])
            if rc != 2:
                P.append(f"bad principals {content[:30]!r} gave exit {rc}, expected 2")
        s, api, _ = self.fresh("o10s")
        if not api:
            return P.append("server did not start")
        try:
            A = self.ed("delmar")
            cases = {
                "oversized": (api.call("POST", "/api/v1/invoices", A, idem="v1", raw=b'{"customer": "' + b"x" * 20000 + b'"}'), 413),
                "malformed": (api.call("POST", "/api/v1/invoices", A, idem="v2", raw=b"{nope"), 400),
                "unknown_field": (api.create(A, "x", 5, "v3", extra={"discount": 1}), 422),
                "bool_amount": (api.call("POST", "/api/v1/invoices", A, {"customer": "x", "amount_cents": True, "currency": "USD"}, "v4"), 422),
                "negative": (api.create(A, "x", -5, "v5"), 422),
                "float": (api.call("POST", "/api/v1/invoices", A, {"customer": "x", "amount_cents": 5.5, "currency": "USD"}, "v6"), 422),
                "currency": (api.create(A, "x", 5, "v7", currency="XXX"), 422),
                "dup_json_key": (api.call("POST", "/api/v1/invoices", A, idem="v8", raw=b'{"customer": "a", "customer": "b", "amount_cents": 5, "currency": "USD"}'), 400),
            }
            for k, (r, want) in cases.items():
                if r[0] != want:
                    P.append(f"{k} answered {r[0]}, expected {want}")
            if api.listing(A) != []:
                P.append("refused requests made records")
            st, _, _ = api.create(A, "x", 5, "v3")  # the key from a refused request stays usable
            if st != 201:
                P.append(f"a key whose first request was refused could not be used afterwards ({st})")
            info["refusals"] = {k: r[0] for k, (r, _) in cases.items()}
        finally:
            s.stop()

    def run(self):
        checks = [("o1", "clean control: create, read, list, pay in full, void, with exact values", self.o1),
                  ("o2", "32 concurrent replays of one create make one invoice and one shared answer", self.o2),
                  ("o3", "payment replays apply once; concurrent distinct payments never overspend", self.o3),
                  ("o4", "another tenant's records read like missing ones; lists, cursors and paging stay in tenant", self.o4),
                  ("o5", "cross-tenant pay/void and tenant smuggling change nothing", self.o5),
                  ("o6", "keys are per tenant; key reuse with a different body and missing keys are refused", self.o6),
                  ("o7", "401 and 403 are exact and change nothing", self.o7),
                  ("o8", "transient failure, crash after commit and crash before commit all retry to one effect across a restart", self.o8),
                  ("o9", "scale: shuffled duplicate-laden load over four tenants keeps exact per-tenant counts", self.o9),
                  ("o10", "invalid input refused: non-loopback host, bad principals, bad bodies; refusals make nothing", self.o10)]
        try:
            for cid, title, fn in checks:
                self.check(cid, title, fn)
        finally:
            shutil.rmtree(self.work, ignore_errors=True)
        return self.results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--seed", type=int, default=1919)
    ap.add_argument("--scale", type=int, default=2000)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = Oracle(a.server, a.seed, a.scale).run()
    passed = sum(r["pass"] for r in res)
    if a.json:
        print(json.dumps({"passed": passed, "total": len(res), "results": res}, indent=2))
    else:
        for r in res:
            print(f"{'PASS' if r['pass'] else 'FAIL'} {r['id']} {r['title']} ({r['seconds']}s)")
            for p in r["problems"]:
                print(f"     - {p}")
        for r in res:
            if r["id"] in ("o3", "o9") and r["info"]:
                print(f"{r['id']}: {r['info']}")
        print(f"{passed}/{len(res)} checks passed")
    return 0 if passed == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
