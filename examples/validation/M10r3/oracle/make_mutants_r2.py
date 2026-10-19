#!/usr/bin/env python3
"""M10 r2 mutants of the G10 r3 netdiag.py: the 15 M10 mutants (13 unchanged anchors, 2 ported to the r3
code with the same meaning) plus 7 fix-revert mutants (rv_*) that each undo one r3 fix.
Usage: python make_mutants_r2.py <netdiag.py> <out-dir> <M10 make_mutants.py>. Each replacement must apply exactly once."""
import ast, sys
from pathlib import Path

src, out, m10 = sys.argv[1:4]
tree = ast.parse(Path(m10).read_text())
M = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "M")
PORTED = {
    "prefix_strip3": [('kind, value = ("dns" if m.group(1).lower().startswith("dns") else "ip"), raw[m.end():].strip()',
                       'kind, value = ("dns" if m.group(1).lower().startswith("dns") else "ip"), raw[3:].strip()')],
    "wildcard_any_depth": [("    return bool(head) and rest == base", "    return host.endswith(name[1:])")],
}
REVERT = {
    "rv_f1_unknown_bare": [('        return "unknown", raw.strip()\n    else:', '        kind, value = None, raw.strip()\n    else:')],
    "rv_f1_no_list_split": [('if "," in raw else [raw]', 'if False else [raw]')],
    "rv_f2_public_suffix": [(' or base in PUBLIC_SUFFIXES:', ':')],
    "rv_f2_one_label": [('if "*" in base or "." not in base or', 'if "*" in base or')],
    "rv_f3_fold": [('    if not raw.isascii():\n        return "invalid", raw\n', '')],
    "rv_f4_sni": [('if o["sni"] and not is_ip and o["sni"] != host:', 'if False:')],
    "rv_f5_recursion": [('    except RecursionError:\n        raise Invalid(f"{path.name}: JSON nested too deeply") from None',
                         '    except ZeroDivisionError:\n        raise Invalid(f"{path.name}: JSON nested too deeply") from None')],
    "rv_f7_fromisoformat": [('    m = RFC3339_RE.match(s)\n    if not m:\n        raise ValueError(s)\n',
                             '    return dt.datetime.fromisoformat(s[:-1] + "+00:00" if s[-1:] in "Zz" else s)\n    m = RFC3339_RE.match(s)\n    if not m:\n        raise ValueError(s)\n')],
}
M.update(PORTED)
M.update(REVERT)
text = Path(src).read_text()
for name, reps in M.items():
    t = text
    for old, new in reps:
        n = t.count(old)
        if n != 1:
            raise SystemExit(f"{name}: pattern found {n} times: {old[:70]!r}")
        t = t.replace(old, new)
    compile(t, name, "exec")
    d = Path(out) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "netdiag.py").write_text(t)
print(f"{len(M)} mutants ({len(PORTED)} ported, {len(REVERT)} fix-revert) in {out}")
