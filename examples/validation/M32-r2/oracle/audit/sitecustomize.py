# M32 audit hook (Grok self-validation): records any network, process or mail attempt by the tool under test.
import os, sys
_LOG = os.environ.get("M32_AUDIT_LOG")
_BAD = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.bind", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn",
        "os.fork", "os.forkpty", "smtplib.connect", "smtplib.send", "urllib.Request", "http.client.connect", "http.client.send", "ftplib.connect", "webbrowser.open")
def _hook(ev, args):
    if _LOG and ev.startswith(_BAD):
        with open(_LOG, "a") as f: f.write("%s %r\n" % (ev, args[:2] if isinstance(args, tuple) else args))
if _LOG: sys.addaudithook(_hook)
