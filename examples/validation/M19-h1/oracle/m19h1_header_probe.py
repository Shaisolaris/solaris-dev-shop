#!/usr/bin/env python3
"""M19 h1 header probe (Grok self-validation, not independent review). Starts ledger_api.py serve on loopback with
synthetic principals and checks the duplicate-safe-api.md "Boundaries of the demo" claims about repeated headers.
Uses raw sockets so header order is exact. Usage: PY m19h1_header_probe.py LEDGER_API OUT.json"""
import json, os, signal, socket, subprocess, sys, tempfile, time
API = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
w = tempfile.mkdtemp(prefix="m19h1-hdr-")
P = [{"key": "kA-synthetic-0001", "tenant": "aldane", "user": "ed", "role": "editor"},
     {"key": "kB-synthetic-0002", "tenant": "brisk", "user": "ed", "role": "editor"}]
json.dump({"schema": "solaris.ledger-principals/1", "principals": P}, open(w + "/p.json", "w"))
proc = subprocess.Popen([sys.executable, API, "serve", "--db", w + "/l.db", "--principals", w + "/p.json", "--port", "0",
                         "--ready-file", w + "/ready.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
for _ in range(300):
    try: port = json.load(open(w + "/ready.json"))["port"]; break
    except Exception: time.sleep(0.05)
def req(method, path, headers, body=b""):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    lines = ["%s %s HTTP/1.1" % (method, path), "Host: 127.0.0.1", "Connection: close", "Content-Length: %d" % len(body)]
    if body: lines.append("Content-Type: application/json")
    s.sendall(("\r\n".join(lines + ["%s: %s" % h for h in headers]) + "\r\n\r\n").encode() + body)
    data = b""
    while True:
        c = s.recv(65536)
        if not c: break
        data += c
    s.close(); head, _, b = data.partition(b"\r\n\r\n")
    return int(head.split()[1]), json.loads(b or b"null")
B = json.dumps({"customer": "c1", "amount_cents": 100, "currency": "USD"}).encode()
rows = []
def row(name, ok, detail): rows.append({"row": name, "pass": bool(ok), "detail": detail}); print(("PASS " if ok else "FAIL ") + name, detail)
try:
    time.sleep(0.2)
    st, inv = req("POST", "/api/v1/invoices", [("Authorization", "Bearer kA-synthetic-0001"), ("Authorization", "Bearer kB-synthetic-0002"), ("Idempotency-Key", "h1")], B)
    _, la = req("GET", "/api/v1/invoices", [("Authorization", "Bearer kA-synthetic-0001")])
    _, lb = req("GET", "/api/v1/invoices", [("Authorization", "Bearer kB-synthetic-0002")])
    ida = [x["id"] for x in la["data"]]; idb = [x["id"] for x in lb["data"]]
    row("two Authorization headers act as the first caller", st == 201 and inv["id"] in ida and inv["id"] not in idb, {"status": st, "in_first": inv["id"] in ida, "in_second": inv["id"] in idb})
    st1, i1 = req("POST", "/api/v1/invoices", [("Authorization", "Bearer kA-synthetic-0001"), ("Idempotency-Key", "k2"), ("Idempotency-Key", "k3")], B)
    st2, i2 = req("POST", "/api/v1/invoices", [("Authorization", "Bearer kA-synthetic-0001"), ("Idempotency-Key", "k3")], B)
    st3, i3 = req("POST", "/api/v1/invoices", [("Authorization", "Bearer kA-synthetic-0001"), ("Idempotency-Key", "k2")], B)
    row("two Idempotency-Key headers store under the first key only", st1 in (200, 201) and i3["id"] == i1["id"], {"replay_first_same": i3["id"] == i1["id"]})
    row("a retry with only the second key makes a second effect (documented, not refused)", i2["id"] != i1["id"], {"second_key_new_invoice": i2["id"] != i1["id"]})
    row("canonical single-header tenant split still holds", idb == [] and len(ida) == 1, {"brisk_list": len(idb), "aldane_list_before_k-tests": len(ida)})
finally:
    try: os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError): pass
    proc.wait(5)
json.dump({"rows": rows}, open(OUT, "w"), indent=1)
print("M19H1 HEADER PROBE %d/%d" % (sum(r["pass"] for r in rows), len(rows)))
