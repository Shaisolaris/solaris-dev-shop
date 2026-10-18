#!/usr/bin/env python3
"""Build single-edit mutants of csv_reconcile.py. Each edit must apply exactly once.
Usage: make_mutants.py SOURCE OUT_DIR"""
import sys
from pathlib import Path
M = {
 "no_exact_collapse": ('            if sig in distinct:\n                n["exact_copies"] += 1', '            if False:\n                n["exact_copies"] += 1'),
 "oldest_wins": ("                top = max(vals)", "                top = min(vals)"),
 "tie_picks_first": ("                best = winners[0] if len(winners) == 1 else None", "                best = winners[0]"),
 "status_ignored": ("        if stc and r.get(stc) in excl:", "        if False:"),
 "window_end_inclusive": ('C["window"]["start"] <= t < C["window"]["end"]', 'C["window"]["start"] <= t <= C["window"]["end"]'),
 "window_start_exclusive": ('C["window"]["start"] <= t < C["window"]["end"]', 'C["window"]["start"] < t < C["window"]["end"]'),
 "naive_as_utc": ("        t = t.replace(tzinfo=tz)", "        t = t.replace(tzinfo=dt.timezone.utc)"),
 "null_as_zero": ('                nulls += 1\n                continue', '                nulls += 1\n                v = Decimal(0)'),
 "ambiguous_as_unmatched": ("                elif k in ambiguous_keys:", "                elif False:"),
 "decimal_not_normalized": ('return format(v.normalize(), "f")', 'return format(v, "f")'),
 "uppercase_ignored": ('row[c] = v.upper() if c in t["upper"] else v', 'row[c] = v'),
 "late_boundary_inclusive": ('r[F["loaded_at"]] > C["as_of"]', 'r[F["loaded_at"]] >= C["as_of"]'),
 "late_ignored": ('if C["as_of"] is not None and r.get(F["loaded_at"]) is not None', 'if False and r.get(F["loaded_at"]) is not None'),
 "control_ignores_rejects": ("ok = ok and exp == act and not rejected", "ok = ok and exp == act"),
 "symlink_allowed": ('_need(not stat.S_ISLNK(st.st_mode), f"{where}', '_need(True or not stat.S_ISLNK(st.st_mode), f"{where}'),
 "out_over_input": ('_need(not (out.exists() and os.path.samefile(out, p))', '_need(True or not (out.exists() and os.path.samefile(out, p))'),
 "thousands_loose": ("if not (1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])):", "if False:"),
 "count_distinct_as_count": ("val = len({_canon(x) for x in vals})", "val = len(vals)"),
 "null_gap_dropped": ('("null_metric_values", any(m["null_values_skipped"] for m in metrics.values()))', '("null_metric_values", False)'),
 "digits_unbounded": (r'DEC_RE = re.compile(r"^[+-]?[0-9]{1,20}(\.[0-9]{1,10})?$")', r'DEC_RE = re.compile(r"^[+-]?[0-9]+(\.[0-9]+)?$")'),
 "no_atomic_tmp": ('    tmp = out.parent / f".{out.name}.{secrets.token_hex(6)}.tmp"\n    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL',
                   '    tmp = out\n    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC'),
 "dedup_after_status": ('            excluded.append({"file": F["file"], "line": r["_line"], "reason": "late_after_as_of", "detail": F["loaded_at"]})\n            continue\n        known.append(r)',
                        '            excluded.append({"file": F["file"], "line": r["_line"], "reason": "late_after_as_of", "detail": F["loaded_at"]})\n            continue\n        if F["status"][0] and r.get(F["status"][0]) in F["status"][1]:\n            cov["excluded_status"] += 1\n            excluded.append({"file": F["file"], "line": r["_line"], "reason": "excluded_status", "detail": ""})\n            continue\n        known.append(r)'),
 "dim_dupes_fan_out": ("                if k in dkept:\n                    state, src = \"matched\", dkept[k]\n                elif k in ambiguous_keys:\n                    state, src = AMBIGUOUS, None",
                       "                if k in dkept:\n                    state, src = \"matched\", dkept[k]\n                elif k in ambiguous_keys:\n                    state, src = \"matched\", next(d for d in ddropped if (_canon(d[Dm['key']]),) == k)"),
}
src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])
for name, (a, b) in sorted(M.items()):
    n = src.count(a)
    if n != 1:
        print(f"SKIP {name}: pattern found {n} times"); continue
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "csv_reconcile.py").write_text(src.replace(a, b))
    print(f"OK {name}")
