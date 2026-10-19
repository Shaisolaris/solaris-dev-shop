#!/usr/bin/env python3
"""M10 r3 fix-revert mutants (Grok self-validation) of the G10 r4 netdiag.py: each undoes or bends one part of the RG1 or
RG3/RG4 fix. Usage: python make_mutants_r3.py <netdiag.py> <out-dir>. Each edit must apply exactly once."""
import sys
from pathlib import Path

src, out = sys.argv[1:3]
s = Path(src).read_text()
M = {
    "rv_rg1_other_blocks": ('unknown = [n for k, n in entries if k == "unknown" or (k == "other" and not hostnames)]',
                            'unknown = [n for k, n in entries if k in ("unknown", "other")]'),
    "rg1_other_alone_mismatches": ('(k == "other" and not hostnames)]', 'False]'),
    "rg1_note_dropped": ("                if other:\n                    notes.append(", "                if False:\n                    notes.append("),
    "rg1_split_every_comma": ('parts = TYPED_SPLIT_RE.split(raw) if typed else raw.split(",")', 'parts = raw.split(",")'),
    "rv_rg3_six_digits": (r'(?:\.(\d+))?([Zz]|[+-]\d{2}:\d{2})$")', r'(?:\.(\d{1,6}))?([Zz]|[+-]\d{2}:\d{2})$")'),
    "rg3_rounded": ("(f\".{frac[:6].ljust(6, '0')}\" if frac else \"\")",
                    "(f\".{min(999999, round(int(frac.ljust(9, '0')[:9]) / 1000)):06d}\" if frac else \"\")"),
    "rg3_no_truncate": ("(f\".{frac[:6].ljust(6, '0')}\" if frac else \"\")", "(f\".{frac.ljust(6, '0')}\" if frac else \"\")"),
}
for name, (a, b) in M.items():
    k = s.count(a)
    if k != 1:
        sys.exit(f"{name}: anchor found {k} times")
    d = Path(out, name); d.mkdir(parents=True)
    (d / "netdiag.py").write_text(s.replace(a, b))
    print(f"{name}: ok")
