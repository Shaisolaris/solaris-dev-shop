#!/usr/bin/env python3
"""M10 r5 probes (Grok self-validation) on the G10 r6 rework (V1: _split_nonhost). v2, see the printed note. Derived from m10r4_probes.py; header of the original follows.
M10 r4 probes (Grok self-validation) on the G10 r5 rework (Q1 keytool/certutil non-host spellings, Q2 split of a
bare name after a typed one). Each case runs r5 (NEW) and r4 (OLD, 69c6081) on the same synthetic trace.
Usage: python m10r4_probes.py PY NEW OLD M10_ORACLE_DIR. Synthetic data only; offline (M10 env guard).
v2: the email and Principal Name values are plain strings (no address-shaped text) so the published output
carries none; the tool classifies these entries by their type prefix. v1 outputs are kept unpublished."""
import json, subprocess, sys, tempfile
from pathlib import Path
PY, NEW, OLD, ODIR = sys.argv[1:5]
sys.path.insert(0, ODIR)
import m10_oracle as M
from m10_oracle import trace, dns, tcp, tls, cert
tmp = Path(tempfile.mkdtemp(prefix="m10r5-pr-")); n = [0]; AT = "@"; H = "api.shop.example"
res = {"GAP": 0, "HOLDS": 0, "OBS": 0}


def run(tool, doc):
    n[0] += 1; f = tmp / ("t%03d.json" % n[0]); f.write_text(json.dumps(doc), encoding="utf-8")
    r = subprocess.run([PY, tool, "diagnose", "--json", str(f)], capture_output=True, text=True, env=M.env())
    if "Traceback" in r.stderr:
        return r.returncode, "TRACEBACK", [], []
    try:
        j = json.loads(r.stdout)
    except ValueError:
        return r.returncode, "NOJSON", [], []
    codes = sorted(x["code"] for x in j.get("findings", []))
    det = [x.get("detail", "") for x in j.get("findings", [])]
    return r.returncode, "%s/%s [%s]" % (j.get("verdict"), j.get("layer"), ",".join(codes)), j.get("notes", []), det


def alert(san):
    return trace([dns(qname=H), tcp(), tls("alert", cert(san=san), "bad_certificate", sni=H)], host=H)


mm = lambda r: "TLS_NAME_MISMATCH" in r[1]
no_mm = lambda r: "TLS_NAME_MISMATCH" not in r[1] and r[0] in (0, 1) and r[1] not in ("TRACEBACK", "NOJSON")


def case(tag, label, doc, want, obs=False):
    a, b = run(NEW, doc), run(OLD, doc)
    ok = want(a); k = "OBS" if obs else ("HOLDS" if ok else "GAP")
    res[k] += 1
    print("%s %s %s\n    r6 rc=%s %s\n    r5 rc=%s %s" % (k.ljust(5), tag, label, a[0], a[1], b[0], b[1]))
    return a


print("v2 (disclosed): mismatch controls carry DNS:other.example, because with no DNS/IP entry the tool abstains by design (no confident mismatch); u03 is an observation (a tab is rejected as invalid input).")
print("u01-u03,u07,u12: the covering name is its own entry after a non-host value (want: no mismatch)")
case("u01", "'URI:spiffe://x, %s, DNS:other.example'" % H, alert(["URI:spiffe://x, " + H + ", DNS:other.example"]), no_mm)
case("u02", "'URI:spiffe://x, other.example, %s'" % H, alert(["URI:spiffe://x, other.example, " + H]), no_mm)
case("u03", "tab after the comma 'URI:spiffe://x,<TAB>%s'" % H, alert(["URI:spiffe://x,\t" + H]), no_mm, obs=True)
case("u07", "wildcard after URI 'URI:spiffe://x, *.shop.example'", alert(["URI:spiffe://x, *.shop.example"]), no_mm)
case("u12", "dotted-OID RDN then the name 'DirName:CN=svc, 2.5.4.10=Shop, %s'" % H, alert(["DNS:other.example, DirName:CN=svc, 2.5.4.10=Shop, " + H]), no_mm)
print("u04-u06,u08,u13: the target appears only inside a non-host value or a too-broad wildcard (want: mismatch)")
case("u04", "DirName CN equals target 'DirName:/C=GB, O=Shop, CN=%s'" % H, alert(["DNS:other.example, DirName:/C=GB, O=Shop, CN=" + H]), mm)
case("u05", "keytool 'DirectoryName: CN=svc, O=Shop, CN=%s'" % H, alert(["DNSName: other.example, DirectoryName: CN=svc, O=Shop, CN=" + H]), mm)
case("u06", "URI host equals target 'DNS:other.example, URI:https://%s/, other2.example'" % H, alert(["DNS:other.example, URI:https://" + H + "/, other2.example"]), mm)
case("u08", "too-broad wildcard after URI 'DNS:other.example, URI:spiffe://x, *.example'", alert(["DNS:other.example, URI:spiffe://x, *.example"]), mm)
case("u13", "RDN-shaped chunk after URI 'DNS:other.example, URI:spiffe://x, CN=%s'" % H, alert(["DNS:other.example, URI:spiffe://x, CN=" + H]), mm)
case("u14", "type-prefixed chunk after URI 'URI:spiffe://x, OtherName:%s'" % H, alert(["DNS:other.example, URI:spiffe://x, OtherName:" + H]), mm)
print("u09-u11: documented limits and conservative forms (recorded)")
case("u09", "DirName RDN value without '=' equal to the target 'DirName:CN=svc, %s' (doc limit)" % H, alert(["DNS:other.example, DirName:CN=svc, " + H]), no_mm, obs=True)
case("u10", "comma without a space 'URI:spiffe://x,%s' (doc: never splits)" % H, alert(["DNS:other.example, URI:spiffe://x," + H]), mm, obs=True)
case("u11", "trailing dot 'URI:spiffe://x, %s.'" % H, alert(["URI:spiffe://x, " + H + "."]), no_mm, obs=True)
print("SUMMARY HOLDS=%d GAP=%d OBS=%d" % (res["HOLDS"], res["GAP"], res["OBS"]))
