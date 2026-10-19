"""Minimal Chrome DevTools Protocol client, Python standard library only (M20 prep, Grok self-validation).
Launches headless Google Chrome with a throwaway profile under /tmp/m20prep-chrome-*, background networking off,
and talks CDP over a hand-rolled websocket. Used to drive real keyboard events and read real DOM/focus state."""
import base64, json, os, socket, struct, subprocess, tempfile, time, urllib.request, shutil
from urllib.parse import urlparse

CHROME = os.environ.get("M20_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class WS:
    def __init__(self, url):
        u = urlparse(url)
        self.s = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket upgrade failed: " + buf[:120].decode("latin1"))
        self.rest = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _frame(self):
        """Parse one complete frame from the buffer, or return None without consuming anything."""
        r = self.rest
        if len(r) < 2:
            return None
        b0, b1 = r[0], r[1]
        n, off = b1 & 0x7F, 2
        if n == 126:
            if len(r) < 4:
                return None
            n, off = struct.unpack(">H", r[2:4])[0], 4
        elif n == 127:
            if len(r) < 10:
                return None
            n, off = struct.unpack(">Q", r[2:10])[0], 10
        if len(r) < off + n:
            return None
        self.rest = r[off + n:]
        return b0, r[off:off + n]

    def recv(self):
        """Return one complete text message. A socket timeout leaves partial data buffered (nothing is lost)."""
        while True:
            f = self._frame()
            if f is None:
                chunk = self.s.recv(1 << 20)
                if not chunk:
                    raise ConnectionError("websocket closed")
                self.rest += chunk
                continue
            b0, payload = f
            op = b0 & 0x0F
            if op == 8:
                raise ConnectionError("websocket close frame")
            if op in (0, 1, 2):
                self.partial = getattr(self, "partial", b"") + payload
                if b0 & 0x80:
                    msg, self.partial = self.partial, b""
                    return msg.decode("utf-8", "replace")


class Browser:
    """One headless Chrome, one page target. Events are queued; call() waits for its own reply."""

    def __init__(self, width=1280, height=800):
        self.prof = tempfile.mkdtemp(prefix="m20prep-chrome-")
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={self.prof}",
                                      "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
                                      "--disable-component-update", "--disable-sync", "--disable-default-apps",
                                      "--disable-extensions", "--use-mock-keychain", "--password-store=basic", "--metrics-recording-only", "--disable-features=Translate,OptimizationHints,MediaRouter",
                                      f"--window-size={width},{height}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = os.path.join(self.prof, "DevToolsActivePort")
        for _ in range(200):
            if os.path.exists(port_file) and open(port_file).read().strip():
                break
            time.sleep(0.05)
        port = int(open(port_file).read().split()[0])
        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10))
        page = next(t for t in tabs if t.get("type") == "page")
        self.ws = WS(page["webSocketDebuggerUrl"])
        self.n = 0
        self.events = []
        self.replies = {}
        self.hook = None
        self.version = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=10)).get("Browser")

    def _dispatch(self, m):
        if "id" in m:
            self.replies[m["id"]] = m
        else:
            self.events.append(m)
            if self.hook:
                self.hook(m)

    def call(self, method, **params):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while mid not in self.replies:
            self._dispatch(json.loads(self.ws.recv()))
        m = self.replies.pop(mid)
        if "error" in m:
            raise RuntimeError(f"{method}: {m['error']}")
        return m.get("result", {})

    def pump(self, seconds=0.0):
        """Read queued events for up to `seconds`."""
        end = time.time() + seconds
        while True:
            self.ws.s.settimeout(0.01)
            try:
                raw = self.ws.recv()
            except (socket.timeout, BlockingIOError):
                raw = None
            finally:
                self.ws.s.settimeout(30)
            if raw is not None:
                self._dispatch(json.loads(raw))
                continue
            if time.time() >= end:
                break

    def eval(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError("page JS error: " + json.dumps(r["exceptionDetails"])[:300])
        return r["result"].get("value")

    def key(self, key, shift=False):
        """Real key press. Enter and Space carry text so buttons activate; Backspace uses the editing command."""
        kc = {"Tab": 9, "Enter": 13, "Escape": 27, "ArrowDown": 40, "ArrowUp": 38, " ": 32, "Backspace": 8,
              "Home": 36, "End": 35, "PageDown": 34, "PageUp": 33}[key]  # M20: Home/End/PageUp/PageDown added for the combobox checks
        base = dict(key=key, code={" ": "Space"}.get(key, key), modifiers=8 if shift else 0, windowsVirtualKeyCode=kc)
        if key in ("Enter", " "):
            self.call("Input.dispatchKeyEvent", type="keyDown", text="\r" if key == "Enter" else " ", **base)
        elif key == "Backspace":
            self.call("Input.dispatchKeyEvent", type="rawKeyDown", commands=["deleteBackward"], **base)
        else:
            self.call("Input.dispatchKeyEvent", type="rawKeyDown", **base)
        self.call("Input.dispatchKeyEvent", type="keyUp", **base)

    def type(self, s):
        for ch in s:
            self.call("Input.dispatchKeyEvent", type="keyDown", key=ch, text=ch, unmodifiedText=ch)
            self.call("Input.dispatchKeyEvent", type="keyUp", key=ch)

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        for _ in range(20):
            shutil.rmtree(self.prof, ignore_errors=True)
            if not os.path.exists(self.prof):
                break
            time.sleep(0.25)
