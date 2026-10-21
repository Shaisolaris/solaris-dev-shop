# M07 r2 validation of G07 r2 f4776bd

- Verdict: PASS. M07 P4-1, P4-2 and P4-3 are closed. No P1, P2, P3 or P4 in r2.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M07 validated G07 0d6a78d: PASS with residuals (P4 only).
- Since then on review/grok-g07-fleet-registration: f4776bd G07 r2 (raw/binding-verify.txt). G07 still sits on G04 314b4db; it does not carry the later G04 r2 to r4 commits.
  - P4-1: handoff.py loads registry.py and activate.py with bytecode writing off.
  - P4-2: machine ids are compared without regard to case in register and claim checks.
  - P4-3: `.reg-*.tmp` files found on taking the registry lock are removed and noted.

## Probe (oracle/m07r2_probe.py)
Written for this pass from the three findings. Inputs chosen here, not copied from the G07 r2 tests.
- R01: 4 case variants of a registered id under new aliases are refused; one machine stays.
- R02: a claim with a case variant of the id is admitted; an id one letter off is refused as wrong machine.
- R03: control, two different ids register as two machines.
- R04: status removes 3 `.reg-*.tmp` leftovers and keeps 3 unrelated files (`reg-keep.tmp`, `.reg-keep.tmp.bak`, `notes.tmp`).
- R05: a refused transfer still clears a leftover, and status after is clean.
- R06: a fleet-bound G04 order run from a copied tree with bytecode writing on leaves no `__pycache__` in it.
- R07: the loader restores `sys.dont_write_bytecode` after the import.

## Results
- G07 r1 0d6a78d on 3.13.15: 1/7 (only the control R03 passes) (results/probe-r1-0d6a78d-3.13.15.txt).
- G07 r2 f4776bd: 7/7 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r2-four-python.txt). On 3.9.6 R06 is weak, since Apple's Python caches bytecode outside the tree anyway.
- Existing reproducer, the M07 oracle v3: 22/22 core on all four Pythons (it was 21/22 on 3.11+ for C21). OBS C06b now shows the upper-case claim admitted and the second alias refused; C11b shows no leftover temp file (results/m07-reproducer/).
- Builder registry_oracle: 17/17 on all four Pythons.
- New builder tests fail on 0d6a78d, 3 of 3 on 3.13.15 (results/new-tests-at-0d6a78d-py313.txt).
- Full suite on fresh clones: 158 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1:** a registry written before r2 can already hold two machines whose ids differ only in case. r2 does not merge them; `find` returns the first active one. The doc now says ids are case-blind.
- **OBS (from M07, unchanged):** a retired machine can be registered again under a new alias; a hand edit of FLEET.md is not detected (claims never read it); a transfer during delivery is not blocked.

Browser launches for this pass: 0.
