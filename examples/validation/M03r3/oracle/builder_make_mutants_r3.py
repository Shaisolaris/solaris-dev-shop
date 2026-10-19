#!/usr/bin/env python3
"""G03 r3 mutants: the 15 M03 mutants + 8 builder r2 mutants (both read from the M03 evidence, never edited)
+ r3 mutants for R-A/R-B. Usage: make_mutants_r3.py <tool> <out> <m03 make_mutants.py> <m03r2 builder_make_mutants_r2.py>"""
import importlib.util, sys
from pathlib import Path

def load(p, n):
    spec = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

# anchors moved by the r3 edit (same intent as the original mutant)
MOVED = {
    "health_ignores_journal": [('    mid_swap = _lkind(dataset / JOURNAL) != "missing"\n', '    mid_swap = False\n')],
}
R3 = {
    "r3_health_opens_mid_swap": [("        if mid_swap:\n            continue  # mid-swap", "        if False:\n            continue  # mid-swap")],
    "r3_no_fallback_guard": [('        if _lkind(path.parent / JOURNAL) != "missing":\n            raise sqlite3.OperationalError(',
                              '        if False:\n            raise sqlite3.OperationalError(')],
    "r3_mkdir_before_lock": [("        return _locked(dataset, lambda: _snapshot_with_parent(dataset, out, names, lock_timeout, make_parent))",
                              "        if make_parent:\n            os.mkdir(out.parent, 0o755)\n"
                              "        return _locked(dataset, lambda: _snapshot_with_parent(dataset, out, names, lock_timeout, False))")],
    "r3_no_rmdir_on_failure": [("    except BaseException:\n        if make_parent:\n            try:\n                os.rmdir(out.parent)\n            except OSError:\n                pass\n        raise",
                                "    except BaseException:\n        raise")],
    "r3_snapshot_ignores_journal": [('        if _lkind(dataset / JOURNAL) != "missing":  # before the lock file is touched', '        if False:  # before the lock file is touched'),
                                    ('    if _lkind(dataset / JOURNAL) != "missing":  # re-checked under the lock', '    if False:  # re-checked under the lock')],
}

def main(src, out, m03, r2):
    a = load(m03, "m03mut"); b = load(r2, "m03r2mut")
    allm = dict(a.M); allm.update(b.R2); allm.update(MOVED); allm.update(R3)
    text = Path(src).read_text()
    for name, reps in allm.items():
        t = text
        for old, new in reps:
            n = t.count(old)
            if n != 1:
                raise SystemExit(f"{name}: pattern found {n} times: {old[:70]!r}")
            t = t.replace(old, new)
        assert t != text, name
        d = Path(out) / name; d.mkdir(parents=True, exist_ok=True)
        (d / "sqlite_recovery.py").write_text(t)
        print(name)

if __name__ == "__main__":
    main(*sys.argv[1:5])
