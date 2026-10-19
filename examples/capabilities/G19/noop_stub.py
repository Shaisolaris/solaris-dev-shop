#!/usr/bin/env python3
"""No-op stand-in for ledger_api.py (negative control). It answers every call with a plausible
status and stores nothing, so any acceptance check that only looks at status codes would pass it."""
import argparse
import json
import os
import secrets
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, st, body):
        data = json.dumps(body).encode()
        self.send_response(st)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def do_GET(self):
        if "/invoices/" in self.path:
            return self.send(404, {"error": {"code": "not_found", "message": "no such invoice"}})
        if self.path.startswith("/api/v1/invoices"):
            return self.send(200, {"data": [], "next_after": None})
        return self.send(200, {"ok": True})

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        return self.send(201, {"id": "inv_" + secrets.token_hex(8), "status": "open", "paid_cents": 0})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    for f in ("--db", "--principals", "--ready-file", "--fault-plan"):
        s.add_argument(f)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    srv = Server(("127.0.0.1", a.port), H)
    if a.ready_file:
        with open(a.ready_file, "w") as f:
            json.dump({"host": "127.0.0.1", "port": srv.server_address[1], "pid": os.getpid()}, f)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown).start())
    srv.serve_forever(poll_interval=0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
