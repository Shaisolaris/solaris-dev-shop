#!/usr/bin/env python3
"""M13 r2 mutants of the G13 r2 csv_reconcile.py: the 23 M13 mutants (20 unchanged anchors, 3 ported to the r2
code with the same meaning) plus 8 fix-revert mutants (rv_*) that each undo one r2 fix (N1 to N8; N9 is memory only).
Usage: python make_mutants_r2.py <csv_reconcile.py> <out-dir> <M13 make_mutants.py>. Each edit must apply exactly once."""
import ast, sys
from pathlib import Path

src, out, m13 = sys.argv[1:4]
tree = ast.parse(Path(m13).read_text())
M = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "M")
PORTED = {
    "late_ignored": ('if C["as_of"] is not None and r[F["loaded_at"]] > C["as_of"]:', 'if False and r[F["loaded_at"]] > C["as_of"]:'),
    "naive_as_utc": ("a, b = t.replace(tzinfo=tz, fold=0), t.replace(tzinfo=tz, fold=1)",
                     "a, b = t.replace(tzinfo=dt.timezone.utc, fold=0), t.replace(tzinfo=dt.timezone.utc, fold=1)"),
    "uppercase_ignored": ('row[c] = intern(v.upper() if c in t["upper"] else v)', "row[c] = intern(v)"),
}
REVERT = {
    "rv_n1_unknown_on_time": ('        if C["as_of"] is not None and r.get(F["loaded_at"]) is None:\n            cov["loaded_at_unknown"] += 1\n'
                              '            excluded.append({"file": F["file"], "line": r["_line"], "reason": "loaded_at_unknown", "detail": F["loaded_at"]})\n'
                              '            continue\n        if C["as_of"] is not None and r[F["loaded_at"]] > C["as_of"]:',
                              '        if C["as_of"] is not None and r.get(F["loaded_at"]) is not None and r[F["loaded_at"]] > C["as_of"]:'),
    "rv_n2_fromisoformat_fallback": ('    m = TIME_RE.match(s.strip())\n    if not m:\n        return None, "bad_timestamp"\n',
                                     '    m = TIME_RE.match(s.strip())\n    if not m:\n        try:\n            t = dt.datetime.fromisoformat(s.strip()[:-1] + "+00:00" if s.strip()[-1:] in "Zz" else s.strip())\n'
                                     '        except ValueError:\n            return None, "bad_timestamp"\n'
                                     '        return (t if t.tzinfo else t.replace(tzinfo=tz)).astimezone(dt.timezone.utc), None\n'),
    "rv_n3_loaded_at_in_content": ("    sig_cols = [c for c in cols if c != load_col]", "    sig_cols = list(cols)"),
    "rv_n4_write_each_now": ("            staged.append([out, _stage(out, data), None])", "            os.replace(_stage(out, data), out)\n            continue"),
    "rv_n5_recursion_uncaught": ('    except RecursionError:\n        raise Invalid(f"{p.name}: JSON nested too deeply") from None',
                                 '    except ZeroDivisionError:\n        raise Invalid(f"{p.name}: JSON nested too deeply") from None'),
    "rv_n6_dst_guess": ("        if a.utcoffset() != b.utcoffset():", "        if False:"),
    "rv_n7_unicode_int": ('INT_RE = re.compile(r"^[+-]?[0-9]{1,18}$")', 'INT_RE = re.compile(r"^[+-]?\\d{1,18}$")'),
    "rv_n8_line_order": ('return (la is None, la or _EARLIEST, tuple(_spelling(r.get(c)) for c in cols), r["_line"])',
                         'return (la is None, la or _EARLIEST, r["_line"])'),
}
M.update(PORTED)
M.update(REVERT)
text = Path(src).read_text()
for name, (old, new) in sorted(M.items()):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{name}: pattern found {n} times: {old[:70]!r}")
    t = text.replace(old, new)
    compile(t, name, "exec")
    d = Path(out) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "csv_reconcile.py").write_text(t)
print(f"{len(M)} mutants ({len(PORTED)} ported, {len(REVERT)} fix-revert) in {out}")
