#!/usr/bin/env python3
"""Repros for the M13 findings (synthetic CSVs in a temp dir; candidate CLI only).
Usage: python m13_finding_repros.py PY_MAIN PY39 CSV_RECONCILE"""
import shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m13_oracle as M, m13_adversarial as A

PY, PY39, T = sys.argv[1:4]
M.CMD = [PY, T]
A.PYS = [PY39]
root = Path(tempfile.mkdtemp(prefix="m13r-"))
try:
    for fid, fn in (("N1 as_of with missing loaded_at", A.b07_as_of_missing_loaded_at),
                    ("N1 (oracle k5b)", M.k5b_as_of_missing_loaded_at),
                    ("N2 timestamp forms 3.12 vs 3.9", A.b02_timestamp_forms_by_interpreter),
                    ("N3 re-delivered identical record", A.b09_redelivered_identical_record),
                    ("N4 write failure after checks", A.b11_write_failure_after_checks),
                    ("N5 deep JSON contract", A.b10_deep_json_contract),
                    ("N6 DST local times", A.b03_dst_ambiguous_and_missing_local_times),
                    ("N7 Unicode digits in int", A.b04_unicode_digits_in_int),
                    ("N8 total spelling vs row order (oracle k6b)", M.k6b_value_spelling_stable)):
        w = M.Work(root / fn.__name__)
        try:
            r = fn(w)
            st, msg = r if isinstance(r, tuple) else ("PASS", r)
        except M.Fail as e:
            st, msg = "FAIL", str(e)
        print(f"{fid}\n  [{st}] {msg}\n")
finally:
    shutil.rmtree(root, ignore_errors=True)
