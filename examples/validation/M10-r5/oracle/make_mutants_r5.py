#!/usr/bin/env python3
"""M10 r5 mutants (Grok self-validation) of the G10 r6 netdiag.py: M10 r4 set with the two q2 mutants re-pointed at r6's split line (same meaning), plus v1_* for _split_nonhost. Original header: M10 r4 mutants of the G10 r5 netdiag.py: the 7 r3 mutants (rg1_split_every_comma re-pointed
at r5's split block with the same meaning: every comma splits) plus one per r5 change (Q1 types, Q2 split, note, detail).
Usage: python make_mutants_r4.py <netdiag.py> <out-dir>. Each edit must apply exactly once."""
import sys
from pathlib import Path
src, out = sys.argv[1:3]
s = Path(src).read_text()
M = {
    "rv_rg1_other_blocks": ('unknown = [n for k, n in entries if k == "unknown" or (k == "other" and not hostnames)]',
                            'unknown = [n for k, n in entries if k in ("unknown", "other")]'),
    "rg1_other_alone_mismatches": ('(k == "other" and not hostnames)]', 'False]'),
    "rg1_note_dropped": ("                if other:\n                    notes.append(", "                if False:\n                    notes.append("),
    "rg1_split_every_comma": ('    if not typed:\n        parts = raw.split(",")\n', '    if True:\n        parts = raw.split(",")\n'),
    "rv_rg3_six_digits": (r'(?:\.(\d+))?([Zz]|[+-]\d{2}:\d{2})$")', r'(?:\.(\d{1,6}))?([Zz]|[+-]\d{2}:\d{2})$")'),
    "rg3_rounded": ("(f\".{frac[:6].ljust(6, '0')}\" if frac else \"\")",
                    "(f\".{min(999999, round(int(frac.ljust(9, '0')[:9]) / 1000)):06d}\" if frac else \"\")"),
    "rg3_no_truncate": ("(f\".{frac[:6].ljust(6, '0')}\" if frac else \"\")", "(f\".{frac.ljust(6, '0')}\" if frac else \"\")"),
    # r5 (Q1, Q2)
    "q2_rv_bare_split": ('parts.extend(_split_nonhost(piece) if NON_HOST_TYPE_RE.match(piece) else piece.split(","))', 'parts.append(piece)'),
    "q2_split_nonhost_too": ('parts.extend(_split_nonhost(piece) if NON_HOST_TYPE_RE.match(piece) else piece.split(","))', 'parts.extend(piece.split(","))'),
    "q1_rv_types": ('NON_HOST_TYPES = (r"uri ?name|uri|url|email|rfc822 ?name|other[ -]?name|oid ?name|dir ?name|directory ?name|"',
                    'NON_HOST_TYPES = (r"uri|email|rfc822 ?name|other ?name|dir ?name|"'),
    "q1_no_url": ('r"uri ?name|uri|url|email|', 'r"uri ?name|uri|email|'),
    "q1_no_oidname": ('|oid ?name|', '|'),
    "q1_note_old": ('"URI, email and other non-host types never name a TLS server: do not rewrite them as DNS"', '""'),
    "detail_all_san": ("certificate host names {hostnames[:4]} do not cover", "certificate names {c['san'][:4]} do not cover"),
    # r6 (V1, _split_nonhost)
    "v1_rv_nonhost_whole": ('parts.extend(_split_nonhost(piece) if NON_HOST_TYPE_RE.match(piece)', 'parts.extend([piece] if NON_HOST_TYPE_RE.match(piece)'),
    "v1_eq_ignored": ('        if "=" in c or OTHER_TYPE_RE.match(c):\n', '        if OTHER_TYPE_RE.match(c):\n'),
    "v1_type_ignored": ('        if "=" in c or OTHER_TYPE_RE.match(c):\n', '        if "=" in c:\n'),
    "v1_split_any_comma": ('chunks = re.split(r",(?=\\s)", piece)', 'chunks = piece.split(",")'),
    "v1_glue_drops_comma": ('            out[-1] += "," + c\n', '            out[-1] += c\n'),
    "v1_never_split": ('        else:\n            out.append(c)\n    return out\n', '        else:\n            out[-1] += "," + c\n    return out\n'),
}
for name, (a, b) in M.items():
    k = s.count(a)
    if k != 1:
        sys.exit(f"{name}: anchor found {k} times")
    d = Path(out, name); d.mkdir(parents=True)
    (d / "netdiag.py").write_text(s.replace(a, b))
    print(f"{name}: ok")
