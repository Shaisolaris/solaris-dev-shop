"""M03 r3 extra mutants (Grok self-validation): split the two journal checks in snapshot.
Usage: python make_mutants_m03r3.py <sqlite_recovery.py> <out-dir>. Each replacement applies exactly once."""
import sys
from pathlib import Path
M = {
    "m03r3_no_prelock_journal_check": [('        if _lkind(dataset / JOURNAL) != "missing":  # before the lock file is touched, so nothing changes\n            raise Refused("refused", _SNAPSHOT_MID_SWAP.format(JOURNAL))\n', '')],
    "m03r3_no_underlock_journal_check": [('    if _lkind(dataset / JOURNAL) != "missing":  # re-checked under the lock\n        raise Refused("refused", _SNAPSHOT_MID_SWAP.format(JOURNAL))\n', '')],
}
src, out = sys.argv[1], sys.argv[2]
text = Path(src).read_text()
for name, reps in M.items():
    t = text
    for old, new in reps:
        assert t.count(old) == 1, (name, t.count(old)); t = t.replace(old, new)
    d = Path(out) / name; d.mkdir(parents=True, exist_ok=True); (d / "sqlite_recovery.py").write_text(t); print(name)
