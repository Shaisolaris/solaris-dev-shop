#!/usr/bin/env python3
"""M19 mutants of ledger_api.py: each is one exact, single-occurrence edit (the script stops if an anchor
is missing or not unique). Usage: make_mutants.py CANDIDATE_TREE OUT_DIR
Each OUT_DIR/<name>/ is an APFS clone of the tree (no .git) with only ledger_api.py changed."""
import os, shutil, subprocess, sys

REL = "employees/engineering/backend-developer/ledger_api.py"
M = [
    # idempotency
    ("replay_ignored", "                if row:\n                    con.execute(\"ROLLBACK\")", "                if False:\n                    con.execute(\"ROLLBACK\")"),
    ("deferred_begin", 'con.execute("BEGIN IMMEDIATE")', 'con.execute("BEGIN")'),
    ("fingerprint_ignored", "if row[0] != fingerprint:", "if False:"),
    ("fingerprint_no_body", "json.dumps([method, name, iid, body], sort_keys=True)", "json.dumps([method, name, iid], sort_keys=True)"),
    ("fingerprint_no_iid", "json.dumps([method, name, iid, body], sort_keys=True)", "json.dumps([method, name, body], sort_keys=True)"),
    ("conflict_not_stored", "if e.status != 409:", "if True:"),
    ("errors_stored", "if e.status != 409:", "if e.status not in (409, 404, 422):"),
    ("key_global_scope", '"SELECT fingerprint, status, response FROM idempotency WHERE tenant = ? AND idem_key = ?",\n                                  (tenant, key)',
     '"SELECT fingerprint, status, response FROM idempotency WHERE idem_key = ?",\n                                  (key,)'),
    ("replay_status_200", "return row[1], json.loads(row[2]), True", "return 200, json.loads(row[2]), True"),
    ("replay_header_false", '"true" if replayed else "false"', '"false"'),
    ("location_missing", "hdr[\"Location\"] = f\"/api/v1/invoices/{resp['id']}\"", "pass"),
    ("key_optional", "if needs_key and key is None:", "if False:"),
    # tenant boundary
    ("find_any_tenant", '"SELECT {INVOICE_COLS} FROM invoices WHERE tenant = ? AND id = ?"', '"SELECT {INVOICE_COLS} FROM invoices WHERE (tenant = ? OR 1) AND id = ?"'),
    ("list_any_tenant", "FROM invoices WHERE tenant = ? AND seq > ? ORDER BY seq", "FROM invoices WHERE (tenant = ? OR 1) AND seq > ? ORDER BY seq"),
    ("cursor_any_tenant", 'row = find_invoice(con, who["tenant"], a[0]) if len(a) == 1 else None',
     'row = con.execute(f"SELECT {INVOICE_COLS} FROM invoices WHERE id = ?", (a[0],)).fetchone() if len(a) == 1 else None'),
    ("smuggle_code_lost", 'if any(k.lower().replace("-", "_") in ("tenant", "tenant_id", "owner", "created_by") for k in extra):', "if False:"),
    ("extra_fields_allowed", "    if extra:\n        raise ApiError(422, \"unknown_field\"", "    if False:\n        raise ApiError(422, \"unknown_field\""),
    ("tenant_header_trusted", 'who = led.authenticate(self.headers.get("Authorization"))',
     'who = led.authenticate(self.headers.get("Authorization"))\n            who = dict(who, tenant=self.headers.get("X-Tenant-Id") or who["tenant"])'),
    ("other_tenant_403", "        if row is None:\n            raise not_found()\n        return 200, invoice_view(row)",
     "        if row is None:\n            c2 = connect(self.db)\n            hit = c2.execute(\"SELECT 1 FROM invoices WHERE id = ?\", (iid,)).fetchone()\n            c2.close()\n            raise ApiError(403, \"forbidden\", \"not yours\") if hit else not_found()\n        return 200, invoice_view(row)"),
    ("sequential_ids", 'iid = "inv_" + secrets.token_hex(8)', 'iid = "inv_" + format(con.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] + 1, "016x")'),
    # auth
    ("viewer_can_write", 'if not ROLES[who["role"]]:', "if False:"),
    ("any_bearer", "            if hmac.compare_digest(known, d):", "            if True:"),
    # money rules
    ("overspend_allowed", 'if amount > inv["balance_cents"]:', 'if amount > inv["amount_cents"]:'),
    ("status_stays_open", '"paid" if paid == inv["amount_cents"] else "open"', '"open"'),
    ("void_paid_allowed", 'if inv["status"] != "open" or inv["paid_cents"]:', 'if inv["status"] == "void":'),
    ("pay_closed_allowed", 'if inv["status"] != "open":\n            raise ApiError(409, "invoice_not_open"', 'if inv["status"] == "never":\n            raise ApiError(409, "invoice_not_open"'),
    ("bool_amount_ok", "if isinstance(v, bool) or not isinstance(v, int)", "if not isinstance(v, int)"),
    ("body_limit_off", "if int(length) > MAX_BODY:", "if False:"),
    ("dup_json_keys_ok", 'body = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dup_keys)', 'body = json.loads(raw.decode("utf-8"))'),
    # crash drill and storage
    ("fault_after_commit_swapped", '                self._fault("before_commit", key)\n                con.execute("COMMIT")',
     '                con.execute("COMMIT")\n                self._fault("before_commit", key)'),
    ("pay_audit_dropped", "(who[\"tenant\"], who[\"user\"], iid, amount, key))\n        return 201, invoice_view(find_invoice(con, who[\"tenant\"], iid)), \"pay:\" + iid",
     "(who[\"tenant\"], who[\"user\"], iid, amount, key)) if False else None\n        return 201, invoice_view(find_invoice(con, who[\"tenant\"], iid)), \"pay:\" + iid"),
    ("non_loopback_bind", "if not ip.is_loopback:", "if False:"),
    # paging
    ("next_after_lost", "(who[\"tenant\"], after_seq, limit + 1)).fetchall()", "(who[\"tenant\"], after_seq, limit)).fetchall()"),
    ("cursor_inclusive", "FROM invoices WHERE tenant = ? AND seq > ? ORDER BY seq", "FROM invoices WHERE tenant = ? AND seq >= ? ORDER BY seq"),
    # check command
    ("check_paid_skipped", 'if paid_sum.get(iid, 0) != v["paid_cents"]:', "if False:"),
    ("check_audit_skipped", "if audit_keys.get(k) != [eff]:", "if False:"),
]


def main():
    tree, out = sys.argv[1], sys.argv[2]
    src = open(os.path.join(tree, REL), encoding="utf-8").read()
    names = [n for n, _, _ in M]
    assert len(set(names)) == len(names)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for name, a, b in M:
        n = src.count(a)
        if n != 1:
            sys.exit("anchor for %s occurs %d times" % (name, n))
        d = os.path.join(out, name)
        subprocess.run(["cp", "-cR", tree, d], check=True)
        g = os.path.join(d, ".git")
        if os.path.lexists(g):
            os.remove(g) if os.path.isfile(g) else shutil.rmtree(g)
        with open(os.path.join(d, REL), "w", encoding="utf-8") as f:
            f.write(src.replace(a, b))
        compile(src.replace(a, b), name, "exec")
    print("%d mutants in %s" % (len(M), out))


if __name__ == "__main__":
    main()
