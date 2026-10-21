# M30 r3 validation of G30 r4 f9794c2

- Verdict: PASS. M12 P4-1, carried onto the day 5 stack by the shared tool blob, is closed on G30: a plan text over 300 characters is named with its length and the limit. No P1 to P4. One OBS.
- This is Grok checking a Grok build, built in the same run by the same agent. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M30 r2 validated G30 r3 3285d35 (PASS, no findings). G30 r3 carries daily_integration.py blob 2a40a9d, the same blob M12 P4-1 found on G12 (a text over 300 characters refused as "expected a non-empty string").
- Since then on review/grok-g30-daily-integration: f9794c2 G30 r4, a plain fast-forward over 3285d35 (raw/binding-verify.txt). The tool and doc now equal G12 r3 a245f1f (blob aa21975); a G30 test is added. Plan and prerequisites are unchanged.

## Probe (oracle/m30r3_probe.py)
Written for this pass. Each CLI row runs `check --plan` on a copy of the shipped G30 plan with one field changed. Inputs chosen here, not copied from the G12 or G30 tests.
- R01: a 301-character overlap reason exits 2 and is named with its length and the limit.
- R02: the limit counts characters (301 x U+00E9), and a previous `--out` is kept.
- R03: exactly 300 characters is not refused for length.
- R04: empty, int, null and list reasons keep the old message (exit 2).
- R05: another text field (an external reply_url of 400 characters) gets the length message too.
- R06: the shipped plan still binds the stack (exit 0).
- R07 (OBS): see Residuals.

Harness repairs during this pass, disclosed: v1 read only the last stderr line (the VERDICT line) and failed R01, R02, R04 on r4; v2 reads the whole stderr. v2 used external id X1, which the id rule refuses before the URL is read; v3 uses X91 and an https URL. Scores below are v3.

## Results
- G30 r3 3285d35 on 3.9.6: 3/6 (R01, R02, R05 fail) (results/probe-at-3285d35-3.9.6.txt).
- G30 r4 f9794c2: 6/6 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r4-*.txt).
- Existing reproducers on all four Pythons: daily_integration_oracle ACCEPTED 13/13, no-op control REJECTED 0/13, cross_checks CLEAN, `check --plan` VERDICT INTEGRATED; `--run all` on 3.9.6 ran every prerequisite test, command, cross-check and gate with rc 0 (results/reproducers-oracle-crosschecks-runall.txt; that capture lists the runs, its VERDICT line was cut off by the capture).
- New builder test fails on 3285d35 (results/new-test-at-3285d35.txt).
- Full suite on fresh clones: 288 OK on all four Pythons (1 skipped each). Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1 (new):** the 300 limit is a fixed constant per field; the message names it but the plan cannot raise it.
- **Not on G30:** G06, G18, G24, G42 carry the same old blob. G24 and G42 are not touched by this pass; G06 and G18 are in the stronger lane.

Browser launches for this pass: 0.
