#!/usr/bin/env python3
"""Build deliberately broken copies of the candidate netdiag.py.
Usage: python make_mutants.py <netdiag.py> <out-dir>. Each replacement must apply exactly once."""
import sys
from pathlib import Path

M = {
    "prefix_strip3": [('return kind, raw[m.end():].strip().rstrip(".").lower()', 'return kind, raw[3:].strip().rstrip(".").lower()')],
    "ip_entry_covers_names": [("            continue  # an address entry never covers a host name", "            pass  # an address entry never covers a host name")],
    "dns_entry_covers_ip": [("            if kind == \"dns\":\n                continue", "            if False:\n                continue")],
    "wildcard_any_depth": [('if host.split(".", 1)[1] == name[2:] and host.split(".", 1)[0]:', 'if host.endswith(name[1:]):')],
    "ip_compared_as_text": [("if ipaddress.ip_address(name) == host_ip:", "if name == str(host_ip):")],
    "host_not_lowercased": [('    return s.rstrip(".").lower()\n\n\ndef _obj', '    return s.rstrip(".")\n\n\ndef _obj')],
    "expiry_ignored": [('if c["not_after"] and now > _iso(c["not_after"]):', 'if False:')],
    "wall_clock_dates": [('now = _iso(trace["captured_at"])', 'now = dt.datetime.now(dt.timezone.utc)')],
    "no_dns_ambiguity_on_mismatch": [('                        ambiguous.setdefault("tls", []).append("dns")\n', '                        pass\n')],
    "no_middlebox_ambiguity": [('ambiguous.setdefault("tls", []).append("route")  # middleboxes', 'pass  # middleboxes')],
    "chain_ignored": [('if c["chain_trusted"] is False:', 'if False:')],
    "refused_not_app": [('            find("APP_NOT_LISTENING", "application",', '            find("APP_NOT_LISTENING", "route",')],
    "probable_promoted": [('if len(cands) == 1 and states[first] == "failed":', 'if states[first] in ("failed", "intermittent"):')],
    "unknown_counts_healthy": [('if all(states[l] == "ok" for l in applicable):', 'if not any(states[l] in ("failed", "intermittent") for l in applicable):')],
    "answers_unsorted": [('answers = sorted({str(_ip(a, f"{w}.answers")) for a in _list(o.get("answers", []), f"{w}.answers")})',
                          'answers = list({str(_ip(a, f"{w}.answers")) for a in _list(o.get("answers", []), f"{w}.answers")})')],
}


def main(src, out):
    text = Path(src).read_text()
    for name, reps in M.items():
        t = text
        for old, new in reps:
            n = t.count(old)
            if n != 1:
                raise SystemExit(f"{name}: pattern found {n} times: {old[:70]!r}")
            t = t.replace(old, new)
        d = Path(out) / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "netdiag.py").write_text(t)
        print(name)


if __name__ == "__main__":
    main(*sys.argv[1:3])
