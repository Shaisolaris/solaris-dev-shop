# Offline trace diagnosis (netdiag.py)

Localizes a failed connection to one layer (dns, route, tls or application) from evidence
someone already captured. It reads a JSON trace and never opens a socket, resolves a name
or changes a route, firewall or certificate. Stdlib Python 3.12.

```bash
T=employees/infrastructure/network-engineer/netdiag.py
python3 $T diagnose examples/capabilities/G10/fixtures/06-tls-expired.json
python3 $T diagnose trace.json --json --out report.json    # report written atomically
python3 $T batch traces/ --workers 4                         # every *.json in the folder
```
Exit 0 healthy, 1 a fault or an undetermined result, 2 invalid input (nothing written).

## Trace format (`solaris.net-trace/1`)
`target` {host, scheme http|https, port, path}; `captured_at` (ISO time with zone; used to
judge certificate dates, never the wall clock); optional `config` {resolvers, addresses
[{dev, cidr}], routes [{dst or "default", via, dev, type unicast|blackhole|unreachable|
prohibit}], expected_addresses}; `observations`, each with a `stage`:
- `dns` {qname, resolver, rcode NOERROR|NXDOMAIN|SERVFAIL|REFUSED|TIMEOUT, answers}
- `route` {dst, hops [{ttl, addr or null}], reached}
- `tcp` {dst, port, result connected|refused|timeout|unreachable|reset}
- `tls` {dst, sni, result ok|alert|timeout|reset|eof, alert, version, cert {san, not_before, not_after, chain_trusted}}
- `http` {status or result timeout|reset, headers (only names are read), via_proxy}

Duplicate keys, NaN, symlinks, files over 8 MiB, more than 10000 observations and malformed
fields are refused. Observation order does not matter; the same trace gives the same bytes.

## How to read the result
- `healthy`: every applicable layer has positive evidence.
- `localized` at a layer: that layer failed and every earlier layer has positive evidence.
- `probable` at a layer: it failed, but an earlier layer has no evidence or another layer
  could explain the same symptom (a name mismatch can be DNS pointing at the wrong server;
  a handshake reset can be a middlebox). `candidates` lists every layer still in play.
- `undetermined`: nothing failed but some layers have no evidence.
- `missing_evidence` names the observation that would settle each open layer;
  `next_actions` are read-only commands for a human to run. Nothing is run for you.
- Layer states: ok, failed, intermittent (both), unknown, not_reached, not_applicable.

## Limits
- Judges only what the trace holds; a forged or partial capture gives a bounded answer, not truth.
- A TCP timeout cannot separate a routing hole from a silent firewall drop; both are `route`.
- Header values and bodies are never echoed; anything else in the trace may appear in evidence lines.
- Any change it suggests (route, firewall, certificate) still goes through a change window with rollback.
