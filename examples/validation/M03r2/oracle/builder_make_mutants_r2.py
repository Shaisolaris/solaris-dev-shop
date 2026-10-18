#!/usr/bin/env python3
"""G03 r2 mutants: the 15 M03 mutants (grok-output/M03/oracle/make_mutants.py, applied unchanged) plus one
per r2 fix. Usage: make_mutants_r2.py <sqlite_recovery.py> <out-dir> <m03 make_mutants.py>."""
import importlib.util
import sys
from pathlib import Path

R2 = {
    "r2_f1_like_unescaped": [("NOT LIKE 'sqlite\\\\_%' ESCAPE '\\\\'", "NOT LIKE 'sqlite_%'")],
    "r2_f2_no_header": [('    schema.append(("header", "user_version"', '    0 and schema.append(("header", "user_version"')],
    "r2_f3_no_ro_fallback": [('        if "unable to open" not in str(exc) or _lkind(shm) != "missing" or not _wal_header(path):\n            raise',
                              '        raise')],
    "r2_f3_copy_keeps_sidecars": [("                _drop_copy_sidecars(tmp, n)\n", "")],
    "r2_f4_empty_db_healthy": [('        if not got["tables"] and not (manifest and n in manifest["databases"]):', '        if False:'),
                               ('        if (dataset / n).stat().st_size == 0:', '        if False:')],
    "r2_f5_no_entry_check": [('                or not isinstance(tables, dict)\n', '                and False\n')],
    "r2_f7_nan_accepted": [("    if not math.isfinite(lt) or lt <= 0 or lt > 600:", "    if lt <= 0 or lt > 600:")],
    "r2_journal_temps_kept": [("    if temps and not dry_run:\n        for n in temps:\n            os.unlink(dataset / n)",
                               "    if False:\n        for n in temps:\n            os.unlink(dataset / n)")],
}


def main(src, out, m03):
    spec = importlib.util.spec_from_file_location("m03mut", m03)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = Path(src).read_text()
    for name, reps in list(mod.M.items()) + list(R2.items()):
        t = text
        for old, new in reps:
            n = t.count(old)
            if n != 1:
                raise SystemExit(f"{name}: pattern found {n} times: {old[:70]!r}")
            t = t.replace(old, new)
        d = Path(out) / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "sqlite_recovery.py").write_text(t)
        print(name)


if __name__ == "__main__":
    main(*sys.argv[1:4])
