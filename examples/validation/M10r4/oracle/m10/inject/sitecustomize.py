"""M10 offline guard: when M10_NET_LOG is set, every socket connect/sendto/bind, DNS lookup and
urllib open in the candidate process is refused and recorded in that file."""
import os
LOG = os.environ.get("M10_NET_LOG")
if LOG:
    import socket

    def _block(name):
        def f(*a, **k):
            with open(LOG, "a") as fh:
                fh.write(f"{os.getpid()} {name} {a[1:2] if len(a) > 1 else a[:1]}\n")
            raise OSError(f"M10 offline guard: {name} blocked")
        return f

    for n in ("connect", "connect_ex", "sendto", "bind"):
        setattr(socket.socket, n, _block("socket." + n))
    for n in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "create_connection"):
        setattr(socket, n, _block("socket." + n))
