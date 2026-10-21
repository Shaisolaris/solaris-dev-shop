"""Loopback API startup must not depend on reverse DNS or external networking."""
import http.client
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class NumericLoopbackStartup(unittest.TestCase):
    def test_real_and_control_servers_serve_without_reverse_dns(self):
        sources = [
            ("employees/engineering/backend-developer/ledger_api.py", "LoopbackServer", "Handler"),
            ("examples/capabilities/G19/noop_stub.py", "Server", "H"),
            ("examples/capabilities/G19/vulnerable_stub.py", "Server", "H"),
        ]
        for i, (source, server_name, handler_name) in enumerate(sources):
            with self.subTest(source=source):
                spec = importlib.util.spec_from_file_location("startup_" + str(i), ROOT / source)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with patch("socket.getfqdn", side_effect=AssertionError("reverse DNS is unavailable")) as dns:
                    server = getattr(module, server_name)(("127.0.0.1", 0), getattr(module, handler_name))
                    server.ledger = None  # health does not require a database or credentials
                    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
                    thread.start()
                    conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                    try:
                        conn.request("GET", "/api/v1/health")
                        response = conn.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertTrue(json.loads(response.read())["ok"])
                        self.assertEqual(server.server_name, "127.0.0.1")
                        self.assertEqual(server.server_port, server.server_address[1])
                        dns.assert_not_called()
                    finally:
                        conn.close()
                        server.shutdown()
                        thread.join(3)
                        server.server_close()
                    self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
