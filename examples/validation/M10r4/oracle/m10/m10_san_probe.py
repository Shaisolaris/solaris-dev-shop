#!/usr/bin/env python3
"""SAN coverage probe: for each (target host, san list, expected covered?) build a trace whose DNS is
verified (expected_addresses) and whose TLS ended in a bad_certificate alert, run the candidate, and
report whether it raised TLS_NAME_MISMATCH. Usage: m10_san_probe.py -- <candidate prefix...>"""
import json, subprocess, sys, tempfile, os

ADDR = "198.51.100.77"
# (label, target host, sni or None for same, san entries, expected: True = names cover the target)
CASES = [
    ("bare exact", "api.shop.example", None, ["api.shop.example"], True),
    ("DNS: upper", "api.shop.example", None, ["DNS:api.shop.example"], True),
    ("dns: lower", "api.shop.example", None, ["dns:api.shop.example"], True),
    ("Dns : spaced", "api.shop.example", None, ["Dns : api.shop.example"], True),
    ("DNS: wildcard", "api.shop.example", None, ["DNS:*.shop.example"], True),
    ("upper value", "api.shop.example", None, ["DNS:API.SHOP.EXAMPLE"], True),
    ("san trailing dot", "api.shop.example", None, ["DNS:api.shop.example."], True),
    ("host trailing dot", "api.shop.example.", None, ["DNS:api.shop.example"], True),
    ("punycode A-label both", "xn--bcher-kva.example", None, ["DNS:xn--bcher-kva.example"], True),
    ("punycode wildcard", "api.xn--bcher-kva.example", None, ["DNS:*.xn--bcher-kva.example"], True),
    ("IP target, IP:", "198.51.100.77", None, ["IP:198.51.100.77"], True),
    ("IP target, IP Address:", "198.51.100.77", None, ["IP Address:198.51.100.77"], True),
    ("IP target, bare ip", "198.51.100.77", None, ["198.51.100.77"], True),
    ("IPv6 target, openssl long form", "2001:db8::1", None, ["IP Address:2001:DB8:0:0:0:0:0:1"], True),
    # must NOT cover
    ("other name", "api.shop.example", None, ["DNS:other.example"], False),
    ("wildcard two labels deep", "a.api.shop.example", None, ["DNS:*.shop.example"], False),
    ("wildcard does not cover apex", "shop.example", None, ["DNS:*.shop.example"], False),
    ("partial-label w*", "web.shop.example", None, ["DNS:w*.shop.example"], False),
    ("partial-label *eb", "web.shop.example", None, ["DNS:*eb.shop.example"], False),
    ("partial-label xn--*", "xn--bcher-kva.example", None, ["DNS:xn--*.example"], False),
    ("double wildcard", "a.b.shop.example", None, ["DNS:*.*.shop.example"], False),
    ("wildcard over TLD *.example", "web.example", None, ["DNS:*.example"], False),
    ("wildcard over TLD *.com", "shop.com", None, ["DNS:*.com"], False),
    ("wildcard over public suffix *.co.uk", "shop.co.uk", None, ["DNS:*.co.uk"], False),
    ("bare * only", "web.example", None, ["*"], False),
    ("DNS:<ip> for IP target", "198.51.100.77", None, ["DNS:198.51.100.77"], False),
    ("IP: entry for a name", "api.shop.example", None, ["IP:api.shop.example"], False),
    ("IPv4-mapped v6 vs v4", "198.51.100.77", None, ["IP:::ffff:198.51.100.77"], False),
    ("U-label SAN vs A-label host", "xn--bcher-kva.example", None, ["DNS:b\u00fccher.example"], False),
    ("KELVIN SIGN homoglyph SAN", "kelvin.example", None, ["DNS:\u212aelvin.example"], False),
    ("CN only (san empty) wrong name", "api.shop.example", None, [], None),
    ("double trailing dot SAN", "api.shop.example", None, ["DNS:api.shop.example.."], False),
    ("SNI differs from target, SAN covers SNI only", "api.shop.example", "www.other.example", ["DNS:www.other.example"], False),
    # other real-world spellings of a typed entry
    ("keytool DNSName:", "api.shop.example", None, ["DNSName: api.shop.example"], True),
    ("keytool IPAddress:", "198.51.100.77", None, ["IPAddress: 198.51.100.77"], True),
    ("Windows 'DNS Name='", "api.shop.example", None, ["DNS Name=api.shop.example"], True),
    ("openssl one-line list", "api.shop.example", None, ["DNS:a.example, DNS:api.shop.example"], True),
]


def trace(host, sni, san, cn=None):
    cert = {"san": san, "not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z", "chain_trusted": True}
    if cn:
        cert["subject_cn"] = cn
    obs = []
    is_ip = ":" in host or host.replace(".", "").isdigit()
    if not is_ip:
        obs.append({"stage": "dns", "qname": host, "resolver": "10.20.0.2", "rcode": "NOERROR", "answers": [ADDR]})
    dst = host if is_ip else ADDR
    obs += [{"stage": "tcp", "dst": dst, "port": 443, "result": "connected"},
            {"stage": "tls", "dst": dst, "sni": sni or (None if is_ip else host), "result": "alert", "alert": "bad_certificate", "cert": cert}]
    return {"schema": "solaris.net-trace/1", "captured_at": "2026-10-18T16:00:00Z",
            "target": {"host": host, "scheme": "https", "port": 443, "path": "/"},
            "config": {"resolvers": ["10.20.0.2"], "addresses": [{"dev": "eth0", "cidr": "10.20.0.15/24"}],
                       "routes": [{"dst": "default", "via": "10.20.0.1", "dev": "eth0"}], "expected_addresses": [ADDR]},
            "observations": obs}


def run(cmd, doc):
    d = tempfile.mkdtemp(prefix="m10san-")
    p = os.path.join(d, "t.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    r = subprocess.run(cmd + ["diagnose", p, "--json"], capture_output=True, text=True)
    os.unlink(p); os.rmdir(d)
    try:
        rep = json.loads(r.stdout)
    except ValueError:
        return r.returncode, None, (r.stdout + r.stderr).strip().splitlines()[-1][:120] if (r.stdout + r.stderr).strip() else ""
    return r.returncode, rep, ""


def main(argv):
    cmd = argv[argv.index("--") + 1:]
    wrong = 0
    for label, host, sni, san, covered in CASES:
        rc, rep, err = run(cmd, trace(host, sni, san))
        if rep is None:
            print(f"INVALID  {label:48s} rc={rc} {err}")
            continue
        mism = any(f["code"] == "TLS_NAME_MISMATCH" for f in rep.get("findings", []))
        if covered is None:
            print(f"INFO     {label:48s} mismatch={mism} verdict={rep.get('verdict')} layer={rep.get('layer')}")
            continue
        ok = (mism != covered)
        wrong += not ok
        print(f"{'OK' if ok else 'WRONG':8s} {label:48s} expected {'covered' if covered else 'NOT covered'}; mismatch={mism} verdict={rep.get('verdict')}")
    # CN fallback: SAN present but not matching, CN matching -> must still be a mismatch
    rc, rep, _ = run(cmd, trace("api.shop.example", None, ["DNS:other.example"], cn="api.shop.example"))
    mism = rep is not None and any(f["code"] == "TLS_NAME_MISMATCH" for f in rep["findings"])
    print(f"{'OK' if mism else 'WRONG':8s} {'CN matches, SAN does not (no CN fallback)':48s} mismatch={mism} rc={rc}")
    wrong += not mism
    print(f"SUMMARY wrong={wrong}")


if __name__ == "__main__":
    main(sys.argv[1:])
