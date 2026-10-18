#!/usr/bin/env python3
"""M10 r2 regression hunt on the G10 r3 rework: each case runs the r3 tool and the r2 tool (6af7849)
on the same synthetic trace and prints both diagnoses, so a behaviour change is visible side by side.
Usage: python m10r2_regressions.py PY NETDIAG_NEW NETDIAG_OLD M10_ORACLE_DIR   (labels say r3 for NEW and r2 for OLD)"""
import json, subprocess, sys, tempfile
from pathlib import Path
PY, NEW, OLD, ODIR = sys.argv[1:5]
sys.path.insert(0, ODIR)
import m10_oracle as M
from m10_oracle import trace, dns, tcp, tls, cert, A

tmp = Path(tempfile.mkdtemp(prefix="m10r2-reg-"))
n = [0]


def run(tool, doc):
    n[0] += 1
    f = tmp / ("t%03d.json" % n[0])
    f.write_text(json.dumps(doc))
    r = subprocess.run([PY, tool, "diagnose", "--json", str(f)], capture_output=True, text=True, env=M.env())
    try:
        j = json.loads(r.stdout)
        return r.returncode, "%s/%s/%s [%s]" % (j.get("verdict"), j.get("layer"), j.get("confidence"),
                                                 ",".join(sorted(x["code"] for x in j.get("findings", []))))
    except ValueError:
        return r.returncode, (r.stderr.strip().splitlines() or [""])[-1][:140]


def case(group, label, doc, want=None):
    a, b = run(NEW, doc), run(OLD, doc)
    flag = ""
    if want is not None:
        flag = "  <-- REGRESSION (r2 right, r3 wrong)" if want(b) and not want(a) else ""
    print("[%s] %s\n    r3 rc=%s %s\n    r2 rc=%s %s%s" % (group, label, a[0], a[1], b[0], b[1], flag))


def alert(host, san, sni="same"):
    return trace([dns(qname=host), tcp(), tls("alert", cert(san=san), "bad_certificate", sni=host if sni == "same" else sni)], host=host)


mm = lambda r: "TLS_NAME_MISMATCH" in r[1]
print("RG1 real name mismatch on a certificate that also carries a URI, email, othername or DirName entry")
for label, extra in [("URI SPIFFE", "URI:spiffe://shop.example/ns/api"), ("email", "email:ops" + "@" + "shop.example"),
                     ("othername UPN", "othername:UPN::svc" + "@" + "shop.example"), ("DirName with comma", "DirName:/C=GB, O=Shop"),
                     ("Registered ID", "Registered ID:1.2.3.4")]:
    case("RG1", label + " + DNS:other.example (does not cover api.shop.example)", alert("api.shop.example", ["DNS:other.example", extra]), want=mm)
case("RG1", "control: DNS:other.example only", alert("api.shop.example", ["DNS:other.example"]), want=mm)
case("RG1", "covering DNS + URI (must not be a mismatch)", alert("api.shop.example", ["DNS:api.shop.example", "URI:spiffe://x/y"]))

print("RG2 SNI spelling variants that name the same host")
for label, sni in [("upper case", "API.Shop.Example"), ("trailing dot", "api.shop.example."), ("other name", "www.other.example")]:
    doc = trace([dns(), tcp(), tls("ok", cert(san=["DNS:api.shop.example", "DNS:www.other.example"]), sni=sni)])
    case("RG2", "sni=%s, handshake ok" % sni, doc)

print("RG3 RFC 3339 timestamps (captured_at)")
for ts in ("2026-10-18T16:00:00.123456789Z", "2026-10-18T16:00:00.1234567Z", "2026-10-18T16:00:00.123Z",
           "2026-10-18t16:00:00z", "2026-10-18 16:00:00Z", "2026-10-18T16:00:00-00:00", "2026-12-31T23:59:60Z",
           "2026-10-18T16:00:00+0000", "20261018T160000Z", "2026-10-18T16:00:00"):
    case("RG3", ts, trace(M.healthy_obs(), captured=ts))

print("RG4 certificate dates with nanosecond fractions (not_after), expired vs valid")
for na in ("2026-10-18T15:59:59.999999999Z", "2027-01-01T00:00:00.000000001Z"):
    case("RG4", "not_after " + na, trace([dns(), tcp(), tls("alert", cert(na=na), "certificate_expired")]))

print("RG5 wildcards and suffixes after the F2 fix")
for host, san in [("api.shop.github.io", "DNS:*.shop.github.io"), ("shop.github.io", "DNS:*.github.io"),
                  ("api.example.com", "DNS:*.example.com"), ("a.b.example.com", "DNS:*.example.com"),
                  ("api.shop.example", "DNS:*.shop.example"), ("shop.example", "DNS:*.example")]:
    case("RG5", "%s vs %s" % (host, san), alert(host, [san]))

print("RG6 SAN list forms")
for san in (["DNS:api.shop.example,DNS:www.shop.example"], ["api.shop.example, www.shop.example"],
            ["IP Address:198.51.100.77, DNS:www.shop.example"], ["DNS: api.shop.example"], ["dns:API.SHOP.EXAMPLE"]):
    case("RG6", repr(san), alert("api.shop.example", san))

print("RG7 nesting depth that real traces use (must still parse)")
doc = trace(M.healthy_obs())
doc["x_meta"] = {"a": {"b": {"c": {"d": {"e": {"f": [[[[1]]]]}}}}}}
case("RG7", "6-deep extra metadata", doc)
