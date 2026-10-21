# M32 r5 validation of G32 r5 807f1eb

- Verdict: PASS. M32 r3 P4 (suppression keyed by handle, while the doc implied any CRM merge keeps it) is closed by documentation; behaviour is unchanged.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing. Nothing is sent in any run; drafts only.

## What is being checked
- M32 r4 validated G32 r4 3346efa; the M32 r3 P4 stood.
- Since then on review/grok-g32-consent-followthrough: 807f1eb G32 r5 (raw/binding-verify.txt). The doc and the module docstring say the stored suppression follows the normalized handle, not the record id, and what to do when merging. One new test pins both sides.

## Probe (oracle/m32r5_probe.py)
Written for this pass. Inputs chosen here, not copied from the G32 r5 test.
- R01: followthrough.py equals G32 r4 once docstrings are removed (AST compare), so r5 changes no behaviour.
- R02: the doc and the module docstring both state the handle keying.
- R03 to R06: what the doc now says holds. A merged record keeping the handle (case, spaces, zero-width and fullwidth variants) stays suppressed; a new handle with the history dropped is a new person (welcome drafted); the opt-out put back on the merged record suppresses it.

## Results
- G32 r5 807f1eb: 6/6 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r5-four-python.txt).
- Existing reproducers: the M32 r3 probe 15/15 and the M32 r4 probe 15/15 on all four Pythons; Q14 (merge that changes the handle and drops the history) still drafts `welcome`, which the doc now states. Builder followthrough_oracle ACCEPTED 11/11 (results/reproducer-m32-and-oracle.txt).
- Full suite on fresh clones: 169 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS (by design, now documented):** a CRM merge that both changes the handle and drops the opt-out history cannot be linked by this tool; the person is drafted as new. The doc tells the operator to put the opt-out back on the merged record or keep the old handle.
- **OBS (from M32 r3, unchanged):** plus-addressing, dots, look-alikes and domain aliases are not matched (documented).

Browser launches for this pass: 0.
