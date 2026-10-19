#!/usr/bin/env python3
"""M13 r3 fix-revert mutants (Grok self-validation) of the G13 r3 csv_reconcile.py. Each undoes or bends one part of the
RT or RD fix. Usage: python make_mutants_r3.py <csv_reconcile.py> <out-dir>. Each edit must apply exactly once."""
import sys
from pathlib import Path

src, out = sys.argv[1:3]
s = Path(src).read_text()
OFF = r'r"([Zz]| ?[+-][0-9]{2}(?::?[0-9]{2})?)?)?$")'
M = {
    "rv_rt_colon_offset_only": (OFF, r'r"([Zz]| ?[+-][0-9]{2}:[0-9]{2})?)?$")'),            # r2's +HH:MM only (space kept)
    "rv_rt_six_fraction_digits": (r"(?:\.([0-9]{1,9}))?)?", r"(?:\.([0-9]{1,6}))?)?"),        # r2's 6-digit cap
    "rv_rt_no_space_before_offset": (OFF, r'r"([Zz]|[+-][0-9]{2}(?::?[0-9]{2})?)?)?$")'),
    "rt_fraction_rounded": ('int((frac or "0")[:6].ljust(6, "0"))', 'min(999999, round(int((frac or "0").ljust(9, "0")[:9]) / 1000))'),
    "rt_space_not_stripped": ('        off = off.lstrip(" ") if off else off\n', ''),
    "rt_offset_minutes_unchecked": ("            if om > 59:\n", "            if False:\n"),
    "rt_hour_offset_minutes_misread": ("int(off[-2:]) if len(off) > 3 else 0", "int(off[-2:])"),
    "rv_rd_date_only_refused": ("        if a.utcoffset() != b.utcoffset() and hh is None:\n", "        if False:\n"),
    "rd_date_only_second_fold": ("            return a.astimezone(dt.timezone.utc), None\n", "            return b.astimezone(dt.timezone.utc), None\n"),
    "rd_any_clock_time": ("        if a.utcoffset() != b.utcoffset() and hh is None:\n", "        if a.utcoffset() != b.utcoffset():\n"),
}
for name, (a, b) in M.items():
    n = s.count(a)
    if n != 1:
        sys.exit(f"{name}: anchor found {n} times")
    d = Path(out, name); d.mkdir(parents=True)
    (d / "csv_reconcile.py").write_text(s.replace(a, b))
    print(f"{name}: ok")
