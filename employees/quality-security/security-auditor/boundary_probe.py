#!/usr/bin/env python3
"""Duplicate-effect and tenant-boundary probe for a LOCAL invoice API (loopback only).

Drives an API that follows the solaris ledger contract (the endpoints served by
employees/engineering/backend-developer/ledger_api.py) with the caller keys in a principals file,
and reports what it saw. It never probes a live target: any base URL that is not a loopback address
is refused before a single request is sent. It writes synthetic records into the target, so point
it only at a disposable local instance.

Checks
    B1  concurrent replay of one create (same Idempotency-Key) makes exactly one invoice
    B2  concurrent and sequential replay of one payment makes exactly one payment
    B3  concurrent distinct payments never overspend an invoice (no lost update)
    B4  another tenant's invoice reads exactly like a missing one (no data, no existence signal)
    B5  another tenant's list never contains the owner's invoices
    B6  another tenant's pay and void change nothing
    B7  tenant smuggling in the body or a header cannot create records in another tenant
    B8  idempotency keys are scoped per tenant (no cross-tenant replay of a cached response)
    B9  reusing a key for a different request is refused and makes nothing
    B10 missing or unknown key gets 401, a viewer write gets 403, and neither makes anything

Usage: boundary_probe.py --base-url http://127.0.0.1:PORT --principals FILE
                         [--concurrency 16] [--json] [--out REPORT]
Exit codes: 0 no findings, 1 findings, 2 invalid or refused input, 3 inconclusive (the target did
not behave like a working API, so boundary results cannot be trusted).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import http.client
import ipaddress
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

VERSION = "1.0.0"
CWE = {"dup": "CWE-837 Improper Enforcement of a Single, Unique Action",
       "race": "CWE-362 Race Condition",
       "idor": "CWE-639 Authorization Bypass Through User-Controlled Key",
       "authz": "CWE-285 Improper Authorization",
       "authn": "CWE-306 Missing Authentication for Critical Function"}


class Refused(Exception):
    pass


class Inconclusive(Exception):
    pass


def loopback_target(url: str):
    u = urlsplit(url)
    if u.scheme != "http" or not u.hostname or u.path not in ("", "/") or u.query or u.username:
        raise Refused("base URL must look like http://127.0.0.1:PORT with no path, query or credentials")
    host = u.hostname
    if host == "localhost":
        host = "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise Refused(f"{u.hostname} is not an IP address; only loopback targets are probed")
    if not ip.is_loopback:
        raise Refused(f"{host} is not loopback; this probe never touches a live target")
    return host, u.port or 80


def load_principals(path: str):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise Refused(f"principals: {path} is not a regular file")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise Refused(f"principals: not valid JSON ({e})")
    items = doc.get("principals") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        raise Refused("principals: needs a 'principals' list")
    editors, viewers = {}, {}
    for it in items:
        if not isinstance(it, dict) or not all(isinstance(it.get(k), str) for k in ("key", "tenant", "role")):
            raise Refused("principals: each entry needs key, tenant and role strings")
        (editors if it["role"] == "editor" else viewers).setdefault(it["tenant"], it["key"])
    tenants = sorted(editors)
    if len(tenants) < 2:
        raise Refused("principals: need editors in at least two tenants to test the boundary")
    return editors, viewers, tenants


class Client:
    def __init__(self, host: str, port: int):
        self.host, self.port = host, port

    def call(self, method, path, key=None, body=None, idem=None, headers=None):
        h = dict(headers or {})
        if key:
            h["Authorization"] = "Bearer " + key
        if idem:
            h["Idempotency-Key"] = idem
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        c = http.client.HTTPConnection(self.host, self.port, timeout=30)
        try:
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            raw = r.read()
            try:
                js = json.loads(raw.decode() or "null")
            except ValueError:
                js = None
            return r.status, js, {k.lower(): v for k, v in r.getheaders()}
        except (OSError, http.client.HTTPException) as e:
            return 0, {"transport_error": type(e).__name__}, {}
        finally:
            c.close()

    def all_invoices(self, key):
        out, after = [], None
        for _ in range(1000):
            q = "/api/v1/invoices?limit=100" + (f"&after={after}" if after else "")
            st, js, _ = self.call("GET", q, key)
            if st != 200 or not isinstance(js, dict) or not isinstance(js.get("data"), list):
                raise Inconclusive(f"list endpoint answered {st} {str(js)[:120]}")
            out.extend(js["data"])
            after = js.get("next_after")
            if not after:
                return out
        raise Inconclusive("list never ended after 1000 pages")


def _id(js):
    return js.get("id") if isinstance(js, dict) else None


def run(base_url: str, principals: str, concurrency: int = 16) -> dict:
    host, port = loopback_target(base_url)
    editors, viewers, tenants = load_principals(principals)
    ta, tb = tenants[0], tenants[1]
    A, B = editors[ta], editors[tb]
    api = Client(host, port)
    run_id = secrets.token_hex(4)
    checks, findings = [], []

    def record(cid, title, ok, kind, severity, evidence):
        checks.append({"id": cid, "title": title, "result": "pass" if ok else "finding", "evidence": evidence})
        if not ok:
            findings.append({"check": cid, "title": title, "severity": severity, "cwe": CWE[kind],
                             "confidence": "confirmed (reproduced against the local target in this run)",
                             "evidence": evidence})

    def par(fn, n):
        with cf.ThreadPoolExecutor(max_workers=n) as ex:
            return list(ex.map(lambda _: fn(), range(n)))

    def create(key, customer, amount=1000, idem=None, extra=None, headers=None):
        body = {"customer": customer, "amount_cents": amount, "currency": "USD"}
        body.update(extra or {})
        return api.call("POST", "/api/v1/invoices", key, body, idem or f"probe-{run_id}-{secrets.token_hex(6)}", headers)

    # sanity: a plain create must persist, otherwise nothing below means anything
    st, js, _ = create(A, f"probe-{run_id}-sanity")
    if st != 201 or not _id(js):
        raise Inconclusive(f"create answered {st} {str(js)[:120]}")
    st2, js2, _ = api.call("GET", f"/api/v1/invoices/{_id(js)}", A)
    if st2 != 200 or _id(js2) != _id(js):
        raise Inconclusive(f"a created invoice could not be read back by its owner ({st2})")
    before_a = api.all_invoices(A)

    # B1
    marker = f"probe-{run_id}-replay"
    key1 = f"probe-{run_id}-create"
    res = par(lambda: create(A, marker, 1234, key1), concurrency)
    ids = {_id(j) for s, j, _ in res if s == 201}
    made = [x for x in api.all_invoices(A) if x.get("customer") == marker]
    record("B1", "concurrent replay of one create makes exactly one invoice", len(made) == 1 and len(ids) == 1,
           "dup", "P1", {"requests": concurrency, "statuses": sorted({s for s, _, _ in res}),
                         "distinct_ids_returned": len(ids), "invoices_created": len(made)})
    inv_a = made[0]["id"] if made else _id(js)

    # B2
    st, j, _ = create(A, f"probe-{run_id}-pay", 1000)
    pay_id = _id(j)
    pay1 = lambda: api.call("POST", f"/api/v1/invoices/{pay_id}/payments", A, {"amount_cents": 100}, f"probe-{run_id}-pay1")
    res = par(pay1, concurrency)
    res += [pay1(), pay1()]  # sequential retries too: a lost update can hide a duplicate under concurrency
    _, after, _ = api.call("GET", f"/api/v1/invoices/{pay_id}", A)
    paid = after.get("paid_cents") if isinstance(after, dict) else None
    record("B2", "concurrent and sequential replay of one payment makes exactly one payment", paid == 100, "dup", "P1",
           {"requests": len(res), "statuses": sorted({s for s, _, _ in res}), "paid_cents_after": paid, "expected": 100})

    # B3
    st, j, _ = create(A, f"probe-{run_id}-race", 1000)
    race_id = _id(j)
    res = par(lambda: api.call("POST", f"/api/v1/invoices/{race_id}/payments", A, {"amount_cents": 300},
                               f"probe-{run_id}-race-{secrets.token_hex(6)}"), concurrency)
    ok_n = sum(1 for s, _, _ in res if s == 201)
    _, after, _ = api.call("GET", f"/api/v1/invoices/{race_id}", A)
    paid = after.get("paid_cents") if isinstance(after, dict) else None
    record("B3", "concurrent distinct payments never overspend an invoice", paid == 300 * ok_n and paid is not None and paid <= 1000,
           "race", "P1", {"requests": concurrency, "accepted": ok_n, "paid_cents_after": paid, "amount_cents": 1000})

    # B4
    snap_a = api.call("GET", f"/api/v1/invoices/{inv_a}", A)[1]
    s_other, j_other, _ = api.call("GET", f"/api/v1/invoices/{inv_a}", B)
    s_none, j_none, _ = api.call("GET", "/api/v1/invoices/inv_" + secrets.token_hex(8), B)
    leaked = marker in json.dumps(j_other)
    code = lambda j: (j or {}).get("error", {}).get("code") if isinstance(j, dict) else None
    record("B4", "another tenant's invoice reads exactly like a missing one",
           not leaked and s_other == s_none and s_other >= 400 and code(j_other) == code(j_none), "idor", "P1",
           {"other_tenant_status": s_other, "missing_status": s_none, "other_tenant_code": code(j_other),
            "missing_code": code(j_none), "owner_data_in_body": leaked})

    # B5
    b_ids = {x.get("id") for x in api.all_invoices(B)}
    a_ids = {x.get("id") for x in api.all_invoices(A)}
    overlap = sorted(b_ids & a_ids)
    record("B5", "another tenant's list never contains the owner's invoices", not overlap, "idor", "P1",
           {"owner_ids_visible_to_other_tenant": len(overlap)})

    # B6
    s_pay, _, _ = api.call("POST", f"/api/v1/invoices/{inv_a}/payments", B, {"amount_cents": 1}, f"probe-{run_id}-xpay")
    s_void, _, _ = api.call("POST", f"/api/v1/invoices/{inv_a}/void", B, {}, f"probe-{run_id}-xvoid")
    snap_a2 = api.call("GET", f"/api/v1/invoices/{inv_a}", A)[1]
    record("B6", "another tenant's pay and void change nothing", snap_a == snap_a2 and s_pay >= 400 and s_void >= 400,
           "idor", "P1", {"pay_status": s_pay, "void_status": s_void, "owner_record_unchanged": snap_a == snap_a2})

    # B7
    smug = f"probe-{run_id}-smuggle"
    s1, _, _ = create(B, smug, 10, extra={"tenant_id": ta})
    s2, _, _ = create(B, smug, 10, headers={"X-Tenant-Id": ta, "X-Tenant": ta})
    in_a = [x for x in api.all_invoices(A) if x.get("customer") == smug]
    record("B7", "tenant smuggling cannot create records in another tenant", not in_a, "idor", "P1",
           {"body_tenant_status": s1, "header_tenant_status": s2, "records_landed_in_owner_tenant": len(in_a)})

    # B8
    s8, j8, _ = create(B, marker, 1234, key1)
    a_after = [x for x in api.all_invoices(A) if x.get("customer") == marker]
    record("B8", "idempotency keys are scoped per tenant", _id(j8) != inv_a and len(a_after) == len(made),
           "idor", "P2", {"status": s8, "got_owner_invoice": _id(j8) == inv_a, "owner_records_with_marker": len(a_after)})

    # B9
    n_before = len(api.all_invoices(A))
    s9, j9, _ = create(A, marker, 999, key1)
    n_after = len(api.all_invoices(A))
    record("B9", "reusing a key for a different request is refused and makes nothing",
           s9 >= 400 and n_after == n_before, "dup", "P2", {"status": s9, "code": code(j9), "new_records": n_after - n_before})

    # B10
    n_before = len(api.all_invoices(A))
    s_none_key = create(None, f"probe-{run_id}-anon")[0]
    s_bad_key = create("not-a-real-key-" + secrets.token_hex(8), f"probe-{run_id}-anon")[0]
    s_view = create(viewers[ta], f"probe-{run_id}-viewer")[0] if ta in viewers else None
    n_after = len(api.all_invoices(A))
    ok = s_none_key == 401 and s_bad_key == 401 and s_view in (None, 403) and n_after == n_before
    record("B10", "unauthenticated and viewer writes are refused and make nothing", ok,
           "authn" if s_none_key != 401 or s_bad_key != 401 else "authz", "P1",
           {"no_key": s_none_key, "unknown_key": s_bad_key, "viewer_write": s_view, "new_records": n_after - n_before})

    return {"schema": "solaris.boundary-probe/1", "version": VERSION, "target": f"http://{host}:{port}",
            "scope": "loopback only; synthetic records were written to this target",
            "tenants_used": [ta, tb], "run_id": run_id, "status": "findings" if findings else "pass",
            "checks": checks, "findings": findings,
            "not_assessed": ["transport security", "rate limits", "session lifetime", "anything not reachable on this loopback target"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Duplicate-effect and tenant-boundary probe (loopback targets only).")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--principals", required=True)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if not 2 <= a.concurrency <= 64:
        print("invalid: --concurrency must be 2-64", file=sys.stderr)
        return 2
    try:
        rep = run(a.base_url, a.principals, a.concurrency)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except Inconclusive as e:
        print(f"inconclusive: {e}", file=sys.stderr)
        return 3
    text = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if a.out:
        d = os.path.dirname(os.path.abspath(a.out))
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".probe-", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, a.out)
    if a.json:
        sys.stdout.write(text)
    else:
        for c in rep["checks"]:
            print(f"{'PASS' if c['result'] == 'pass' else 'FINDING'} {c['id']} {c['title']}")
        print(f"{len(rep['findings'])} findings; target {rep['target']} ({rep['scope']})")
    return 1 if rep["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
