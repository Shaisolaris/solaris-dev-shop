#!/bin/zsh
# M10 r3 fresh caller (Grok self-validation): env -i, a new HOME, a python3 shim, the M10 offline guard, and only the three
# commands in offline-trace-diagnosis.md, run in a /tmp copy of the candidate tree, on 4 NEW traces that exercise the r4
# fixes (v2: the email SAN value is a plain string so the published output carries no address-shaped text;
# the tool treats any email: entry the same way) (built by M10's own trace helpers, not the candidate), with a hand answer written before running.
# Usage: zsh m10r3_fresh_caller.sh PYTHON CANDIDATE_TREE M10_ORACLE_DIR
PY=$1; C=$2; O=$3; F=/tmp/m10r3-fc
rm -rf $F; mkdir -p $F/home $F/bin $F/tree; rsync -a --exclude .git $C/ $F/tree/
printf '#!/bin/sh\nexec %s "$@"\n' "$PY" > $F/bin/python3; chmod +x $F/bin/python3
mkdir -p $F/tree/traces
/usr/bin/python3 - $O $F/tree/traces <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1]); from m10_oracle import trace, dns, tcp, tls, cert, http
H, AT, d = "pay.ledger.example", "@", sys.argv[2]
def w(name, doc): open(f"{d}/{name}", "w").write(json.dumps(doc, indent=1))
w("a-mtls-mismatch.json", trace([dns(qname=H), tcp(), tls("alert", cert(san=["DNS:ledger-old.example, URI:spiffe://ledger.example/ns/pay, email:security-team"]), "bad_certificate", sni=H)], host=H))
w("b-mtls-covering.json", trace([dns(qname=H), tcp(), tls("alert", cert(san=["DNS:" + H, "URI:spiffe://ledger.example/ns/pay"]), "bad_certificate", sni=H)], host=H))
w("c-ns-expired.json", trace([dns(qname=H), tcp(), tls("alert", cert(san=["DNS:" + H], na="2026-10-18T15:59:59.999999999Z"), "certificate_expired", sni=H)], host=H, captured="2026-10-18T16:00:00.000000001Z"))
w("d-ns-healthy.json", trace([dns(qname=H), tcp(), tls("ok", cert(san=["DNS:" + H]), sni=H), http(200)], host=H, captured="2026-10-18T16:00:00.123456789Z"))
PY
cat > $F/tree/hand-answer.txt <<'TXT'
Hand answer (written before running; M10 r3):
a-mtls-mismatch: one-line openssl list, DNS ledger-old.example does not cover pay.ledger.example; the URI and email entries are
  not host names and must not hide it -> TLS_NAME_MISMATCH, layer tls, exit 1, with an "ignored" note.
b-mtls-covering: DNS covers the host, URI beside it -> no TLS_NAME_MISMATCH; generic TLS_ALERT (bad_certificate), exit 1.
c-ns-expired: not_after 15:59:59.999999999Z before captured_at 16:00:00.000000001Z -> TLS_CERT_EXPIRED, exit 1.
d-ns-healthy: 9-digit captured_at parses -> healthy, exit 0.
batch: 4 traces, none invalid.
TXT
cat $F/tree/hand-answer.txt
(cd $F/tree && find . -type f | sort) > $F/before.txt
run() { echo "\$ $1"; env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$O/inject M10_NET_LOG=$F/net.log PYTHONDONTWRITEBYTECODE=1 \
  /bin/bash -c "cd $F/tree && T=employees/infrastructure/network-engineer/netdiag.py && $1"; echo "[exit $?]"; }
echo "# m10r3 fresh caller $(date '+%F %T %Z'); python3 shim -> $($PY -c 'import platform;print(platform.python_version())'); offline guard on (M10_NET_LOG)"
run 'python3 $T diagnose traces/a-mtls-mismatch.json'
for x in a-mtls-mismatch b-mtls-covering c-ns-expired d-ns-healthy; do
  run "python3 \$T diagnose traces/$x.json --json --out $x.report.json > /dev/null"
  echo "$x: $($PY -c 'import json,sys;j=json.load(open(sys.argv[1]));print(j["verdict"],j["layer"],sorted(f["code"] for f in j["findings"]),[n[:70] for n in j.get("notes",[]) if "ignored" in n])' $F/tree/$x.report.json)"
done
run 'python3 $T batch traces/ --workers 4'
/usr/bin/python3 - $F/tree <<'PY'
import json, sys
d = sys.argv[1]; g = lambda x: json.load(open(f"{d}/{x}.report.json"))
a, b, c, e = g("a-mtls-mismatch"), g("b-mtls-covering"), g("c-ns-expired"), g("d-ns-healthy")
codes = lambda j: sorted(f["code"] for f in j["findings"])
ok = ("TLS_NAME_MISMATCH" in codes(a) and a["layer"] == "tls" and any("ignored" in n for n in a.get("notes", []))
      and "TLS_NAME_MISMATCH" not in codes(b) and "TLS_ALERT" in codes(b)
      and "TLS_CERT_EXPIRED" in codes(c) and e["verdict"] == "healthy")
print("matches the hand answer:", ok)
PY
(cd $F/tree && find . -type f | sort) > $F/after.txt
echo "network attempts logged: $( [ -f $F/net.log ] && wc -l < $F/net.log | tr -d ' ' || echo 0)"
echo "stray files: $(comm -13 $F/before.txt $F/after.txt | grep -v '\.report\.json$' | tr '\n' ' ')"
echo "HOME after: $(find $F/home -mindepth 1 | wc -l | tr -d ' ') entries"
rm -rf $F
