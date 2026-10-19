#!/usr/bin/env python3
"""Naive control for the G21 oracle: the same CLI with the shortcuts offline clients usually take.

It loads the real offline_sync.py and swaps in four common habits: a fresh idempotency key on every
attempt, any non-auth answer counts as delivered (a 409 is quietly marked done), the last server
answer always wins whatever its version, and no lock around a sync. Not for use; it exists so the
oracle and tests can show they catch these habits.
"""
import importlib.util
import json
import secrets
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[3] / "employees" / "engineering" / "mobile-developer" / "offline_sync.py"
spec = importlib.util.spec_from_file_location("offline_sync_naive", str(TOOL))
m = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(m)

_request = m.request


def request(base, key, method, path, body, idem, timeout):
    return _request(base, key, method, path, body, idem and "naive-" + secrets.token_hex(8), timeout)


def apply_server_doc(con, doc):
    con.execute("INSERT OR REPLACE INTO server (id, version, doc) VALUES (?, ?, ?)",
                (doc["id"], doc["version"], json.dumps(doc, sort_keys=True)))
    return True


_error_code = m.error_code


def push(con, base, key, a):
    sent = 0
    for seq, kind, ref, idem, body in con.execute("SELECT seq, kind, ref, idem, body FROM ops WHERE state = 'pending' "
                                                  "ORDER BY seq").fetchall():
        path = m.API if kind == "create" else "%s/%s/%s" % (m.API, m.server_id(con, ref), "payments" if kind == "pay" else "void")
        sent += 1
        if a.crash_before_send == sent:
            m.os._exit(70)
        status, text, replayed = request(base, key, "POST", path, body, idem, a.timeout)
        if a.crash_after_send == sent:
            m.os._exit(70)
        if status in (401, 403):
            raise m.Stop(3, "auth")
        if status >= 500:
            raise m.Stop(4, "transient")
        if status in (200, 201):
            doc = json.loads(text)
            if kind == "create":
                con.execute("INSERT OR REPLACE INTO refs (ref, server_id, create_seq) VALUES (?, ?, ?)", (ref, doc["id"], seq))
            apply_server_doc(con, doc)
        con.execute("UPDATE ops SET state = 'acked', http_status = 201, response = ? WHERE seq = ?",
                    (text if status in (200, 201) else '{"id": null}', seq))
    return sent


class NoLock:
    LOCK_EX = LOCK_NB = LOCK_UN = 0

    @staticmethod
    def flock(*_a):
        return None


m.request, m.apply_server_doc, m.push, m.fcntl = request, apply_server_doc, push, NoLock
if __name__ == "__main__":
    sys.exit(m.main())
