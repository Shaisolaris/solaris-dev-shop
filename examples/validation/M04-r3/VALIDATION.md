# M04 r3 validation of G04 r4 7ed5f70

- Verdict: PASS. M04 P4-1 (carried in M04 r2) is closed. No P1, P2, P3 or P4 in r4. One observation.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M04 r2 validated G04 r3 e9fa278 and carried P4-1: an exit-2 refusal created an empty `.handoff/<order>/.worker.lock` in a new folder.
- Since then on review/grok-g04-handoff: 7ed5f70 G04 r4. On a refusal the run removes the empty lock and the folders it created, still under the lock, when nothing else was written (raw/binding-verify.txt).

## Probe (oracle/m04r3_probe.py)
Black-box CLI checks written for this pass. Inputs chosen here, not copied from the G04 r4 test.
- Q1: owner change after delivery into a brand new `--state` folder.
- Q2: the same into an existing `--state` folder that holds another order.
- Q3: the same into a deep new `--state` path (`a/b/c`).
- Q4: refusal in the existing order folder keeps its lock, journal and receipts unchanged.
- Q5: a held lock is not removed by a second worker (exit 4), and the holder can then run.
- Q6: an intake that is valid JSON but not an object (`[1, 2]`, sha256 updated) on a fresh order.
- Q7: control (run, rerun, one delivery).

## Results
- G04 r3 e9fa278: 3/7. Q1, Q2, Q3 and Q6 leave `WO-HARBOR-1/.worker.lock` behind (results/probe-r3-e9fa278.txt). This is P4-1.
- G04 r4 7ed5f70: 7/7 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r4-four-python.txt).
- Existing reproducer, the M04 r2 probe: 8/8 on all four Pythons (Q9 needs an r1 checkout and was not run) (results/m04r2-reproducer-r4-four-python.txt).
- Builder handoff oracle: 16/16 on all four Pythons (results/builder-oracle-r4.txt).
- Full suite on fresh clones: 147 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1:** with a deep new `--state` path, the tool still creates the missing parents with `mkdir(parents=True)`. A refusal removes the order folder and the innermost state folder, but the empty parents above it (`a/b` for `a/b/c`) stay. No lock or journal is left. Q3 records it.
- **OBS (from M04 r2, unchanged):** a receiver that wants the owner history reads revisions in order. By design.

Browser launches for this pass: 0.
