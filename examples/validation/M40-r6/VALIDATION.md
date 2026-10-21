# M40 r6 validation of G40 r6 32d2176

- Verdict: PASS. M40 r5 P4-2 is closed: `skill-copy` without `--dest` removes its temp copy before it returns, also when the copy fails. No P1 to P4 open on G40. One OBS.
- This is Grok checking a Grok build, built in the same run by the same agent. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M40 r5 validated G40 r5 99b49c6 and left P4-2: `skill-copy` without `--dest` left a `g40-skill-*` folder in TMPDIR on every run (the `report` command too, since it runs skill-copy without a destination).
- Since then on review/grok-g40-fresh-install: 32d2176 G40 r6, a plain fast-forward over 99b49c6 (raw/binding-verify.txt). Without `--dest` the copy goes to a temp folder that is removed in a `finally` before returning; the JSON then has `dest: null` and a `temp_copy` note. `--dest DIR` keeps the copy as before. host-portability.md says so.

## Probe (oracle/m40r6_probe.py)
Written for this pass from the P4-2 row and the r6 doc. Inputs chosen here, not copied from the G40 r6 test. CLI rows point TMPDIR at an empty folder made by the probe.
- R01: skill-copy without `--dest` still reports `broken` (rc 1) and TMPDIR is empty afterwards.
- R02: the JSON says the copy is gone (`dest` null, `temp_copy` names `--dest`).
- R03: five back-to-back runs leave nothing.
- R04: `--dest DIR` keeps the copy, reports its path, no `temp_copy` key.
- R05: findings (missing, resolved, copied_files) are the same with and without `--dest`.
- R06: a bad ROLE exits 2 and creates nothing.
- R07: an error injected after the copy still removes the temp folder, and the error is raised, not swallowed.
- R08: the doc states both rules.
- R09 (OBS): see Residuals.

## Results
- G40 r5 99b49c6 on 3.9.6: 3/8 (R01, R02, R03, R07, R08 fail) (results/probe-at-99b49c6-3.9.6.txt).
- G40 r6 32d2176: 8/8 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r6-*.txt).
- Existing reproducer, the M40 r5 probe, with a local setuptools 79.0.1 wheelhouse: all rows PASS on 3.11.16, 3.12.14 and 3.13.15; on 3.9.6 the build rows are skipped by the probe (wheel needs 3.10+) and C3 to C6 PASS (results/m40r5-probe-*.txt).
- Builder portability_oracle: ACCEPTED 8/8 with the wheelhouse and with the index on 3.11.16, 3.12.14, 3.13.15; naive REJECTED 4/8, no-op REJECTED 2/8 (results/builder-oracle-matrix.txt). The offline-without-wheelhouse row of r5 was not rerun here (the network was not cut for this pass); M40 r5 probe C2 covers that refusal offline via PIP_NO_INDEX.
- New builder test fails on 99b49c6 (results/new-test-at-99b49c6.txt).
- Full suite on fresh clones: 333 OK on all four Pythons (3.9.6 skips 7, 3.12.14 and 3.13.15 skip 1). Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1 (new):** `report` has no `--dest`, so its skill-copy part can only be inspected by rerunning `skill-copy --dest`.
- **Carried OBS from M40 r5:** without G40_WHEELHOUSE the offline-build test skips on 3.12 and 3.13; backend detection reads pip's wording.
- **Host note, not in the repo:** runs before r6 left their `g40-skill-*` folders in this host's TMPDIR. They were counted, not removed.

Browser launches for this pass: 0.
