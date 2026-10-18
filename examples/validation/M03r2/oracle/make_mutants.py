#!/usr/bin/env python3
"""Build deliberately broken copies of the candidate sqlite_recovery.py.
Usage: python make_mutants.py <sqlite_recovery.py> <out-dir>. Each replacement must apply exactly once."""
import sys
from pathlib import Path

M = {
    "skip_snapshot_verify": [("    problems = _verify_loaded(snap, manifest, None)\n    if problems:\n        raise Refused(\"refused\", \"snapshot failed",
                              "    problems = []\n    if problems:\n        raise Refused(\"refused\", \"snapshot failed")],
    "no_confirm_needed": [("        if confirm != manifest[\"snapshot_id\"]:\n            raise Refused(\"refused\", f\"restore needs explicit intent",
                           "        if False:\n            raise Refused(\"refused\", f\"restore needs explicit intent")],
    "dry_run_restores_when_confirmed": [("        if dry_run:\n            if _lock_held(dataset):\n                raise Refused(\"busy\", _lock_message(dataset))\n            plan = _plan(",
                                         "        if dry_run and confirm != manifest[\"snapshot_id\"]:\n            if _lock_held(dataset):\n                raise Refused(\"busy\", _lock_message(dataset))\n            plan = _plan(")],
    "delete_recoverable_copies": [("    os.unlink(dataset / JOURNAL)\n    _fsync_dir(dataset)\n    kept = [s[\"to\"] for s in journal[\"steps\"] if s[\"kind\"] == \"set_aside\"]\n",
                                   "    os.unlink(dataset / JOURNAL)\n    _fsync_dir(dataset)\n    kept = [s[\"to\"] for s in journal[\"steps\"] if s[\"kind\"] == \"set_aside\"]\n    for _k in kept:\n        os.unlink(dataset / _k)\n")],
    "recover_always_forward": [("    decision = \"roll_back\" if bad else \"roll_forward\"", "    bad = []\n    decision = \"roll_back\" if bad else \"roll_forward\"")],
    "recover_noop": [("    j = _load_journal(dataset)\n    if j is None:", "    j = None\n    if j is None:")],
    "no_dataset_flock": [("            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n", "            pass\n")],
    "no_dataset_lock_at_all": [("            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n", "            pass\n"),
                               ("        if _lock_held(dataset):\n            raise Refused(\"busy\", _lock_message(dataset))\n        plan = _plan(dataset, snap, manifest)  # read-only",
                                "        plan = _plan(dataset, snap, manifest)  # read-only")],
    "unbounded_lock_wait": [("        con = sqlite3.connect(path, timeout=lock_timeout, isolation_level=None)",
                             "        con = sqlite3.connect(path, timeout=3600, isolation_level=None)")],
    "health_ignores_journal": [("    if _lkind(dataset / JOURNAL) != \"missing\":\n        problems.append(", "    if False:\n        problems.append(")],
    "health_missing_ok": [("        if kind != \"file\":\n            problems.append(f\"{n}: expected database is {kind}\")\n            continue",
                           "        if kind != \"file\":\n            continue")],
    "follow_symlinks": [("        st = os.lstat(path)\n    except (FileNotFoundError, NotADirectoryError):\n        return \"missing\"",
                         "        st = os.stat(path)\n    except (FileNotFoundError, NotADirectoryError):\n        return \"missing\"")],
    "skip_when_counts_match": [("    identical = (not differing and not wal and cur[\"integrity\"] == \"ok\"",
                                "    identical = (all(cur[\"tables\"].get(t, {}).get(\"rows\") == v[\"rows\"] for t, v in info[\"tables\"].items()) and not wal and cur[\"integrity\"] == \"ok\"")],
    "no_extra_member_check": [("    if extra:\n        raise Refused(\"refused\", f\"snapshot contains entries", "    if False:\n        raise Refused(\"refused\", f\"snapshot contains entries")],
    "no_staging_journal": [("    journal = {\"schema\": JOURNAL_SCHEMA, \"state\": \"staging\"", "    journal = {\"schema\": JOURNAL_SCHEMA, \"state\": \"swapping\"")],
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
        (d / "sqlite_recovery.py").write_text(t)
        print(name)


if __name__ == "__main__":
    main(*sys.argv[1:3])
