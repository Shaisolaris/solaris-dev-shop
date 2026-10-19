# M01 r3: Grok self-validation of G01 r2 (fixture runner)

Label: Grok self-validation by the same bot that built and validates the programme. This is not independent review and not manager acceptance.

- Candidate: G01 r2 at 1621c8207ccd85970cdcf2b8c841146dcf33ae89 on review/grok-g01-fixture-runner (parent deb06f6), fetched 21:15:39 PT and checked out detached in a /tmp worktree. Not modified.
- Binding (raw/binding-verify.txt): the deb06f6..1621c82 diff is byte-identical to G01-r2.patch (sha256 a730fc33...); MANIFEST.sha256 checks 4/4, and its file set equals the 02ba9c5..1621c82 diff set. Scope: ASSURANCE.md, quality_os.py (+27/-7 incl. comments), tests/test_fixture_runner.py (+74).
- Scope: the M01 r2 residuals S1 (P3) and S2 (P4), the F3 owner decision, and regressions.
- week-grok: before 21:15:37 PT and after 21:34:06 PT are identical (branch programme/grok-week-20261018, HEAD 02ba9c5, index c28a2f586b3e3001, status af8386300eb96552, 80 lines; full listing byte-identical).

## Verdict: FAIL

S1 and S2 are fixed on their reproductions and F3 is kept. The S1 fix introduces a P2 regression: valid G05 packets that carry `requested_actions` or `sources` are now refused. A positive-controlled proposed fix is attached (proposed-fix-r3.patch). It is not applied.

Disclosure: the field list that causes the regression is the one my own M01 r2 validation suggested ("the legal fields text, requested_actions, sources, freshness_days"). The builder implemented that suggestion as written. The suggestion was wrong for requested_actions and sources.

## Results (identical on 3.9.6, 3.11.16, 3.12.14, 3.13.15)
| Instrument | Result |
|---|---|
| M01 oracle (r1, unchanged) | core 12/12, gaps open 0/14 |
| M01 r2 probes y01 to y09 | 7/7 hold (y08 and y09 observations) |
| M01 r3 probes z01 to z14 (new) | 9/13 hold; GAP z01, z02, z13, z14; z04 INFO |
| Same r3 probes on deb06f6 (direction) | 8/13; z01 and z02 HOLD there, z05, z06, z11, z13, z14 GAP there |
| Builder fixture-runner tests | 18 OK |
| Builder suite | 102 OK |
| Fresh caller (env -i, new HOME, offline guard, doc commands), 3.9.6 and 3.13.15 | all documented commands as expected; plus the z01 packet through `run packet.json`: rc 1 INVALID_PACKET; network blocked |

## Residual fixes confirmed
- S1: y01, y03 and the synonym variants are INVALID_PACKET. Also z05 (`fixture_type: "LEGAL"`), z06 (`category: legal`) and z07 (`fixture_type: planted_defect`) are refused. z05 and z06 were false passes on deb06f6.
- S2: an unreadable subfolder is a failing INVALID_PACKET entry with the OS reason (y07). It is also named two levels down (z11, a false pass on deb06f6). An unreadable root (z10) and an unreadable fixture file (z12) are not ok, with no traceback.
- F3: a legal fixture without expectations is still read as fail_gate.

## Findings by severity
- P2, regression (z01, z02, z04, fresh caller). `requested_actions` and `sources` are G05 packet fields: evaluate_packet validates them (quality_os.py 907 to 913) and passes them to the legal check (1030), and ASSURANCE.md documents source dating and LEGAL_SOURCE_STALE for packets. r2 adds them to NON_PACKET_FIXTURE_KEYS, so any unwrapped packet carrying them is refused with INVALID_PACKET "packet fixture has non-packet fields requested_actions, sources; set fixture_kind". `run packet.json` is the documented main command. Effects:
  - A benign legal packet with dated sources (z01) or only requested_actions (z02) now fails, rc 1. On deb06f6 it passed, rc 0.
  - A negative legal packet (blocked legal_text plus requested_actions, fail_gate expectation, z04) used to meet its expectation with LEGAL_BINDING_PROHIBITED and LEGAL_DISCLAIMER_MISSING. Now it is INVALID_PACKET, so the legal gate codes are never reported.
  - It fails closed (no false pass). Wrapping the packet as `{"fixture_kind": "packet", "packet": ...}` works (z03). But the doc's `run packet.json` does not say to wrap, and a CI gate on such packets fails on every run.
  - The builder tests pin `requested_actions only` and `sources only` (bare objects) as INVALID, which is right. No test covers these fields on a real packet.
- Proposed fix (proposed-fix-r3.patch, not applied): count requested_actions and sources as stray only when the object has no G05 packet key (legal_text, risk_level, dimensions, completed_gates, evidence, planted_defects). `git apply --check` passes on 1621c82. Positive control on a scratch copy, all 4 interpreters (results/positive-control/):
  - z01 and z02 HOLD, and z04 meets fail_gate with the legal codes again.
  - Oracle 12/12 with 0/14 gaps, r2 probes 7/7, fixture tests and suite 102 OK (the builder's bare-field cases still INVALID).
  - Fresh caller: z01 rc 0.
  - r3 probes 11/13: the remaining 2 are z13 and z14 below, unchanged by the fix.
  - Residual of the fix: an object with a kind under a non kind/type name (for example `category`), packet keys and `requested_actions` but no legal_text is evaluated as a packet. The legal check then does not run on requested_actions alone. Contrived; noted.
- P4, S1 variant, pre-existing (open on deb06f6 too): a bare planted defect whose kind is lost to a value case variant (`fixture_type: "Planted_Defect"`, z13) or a non kind/type key (`category: planted_defect`, z14), and that has no `evidence` list, passes as an empty packet (rc 0, ok true, no gates). The fixture_kind form yields SELF_APPROVAL_FORBIDDEN. The alias check compares values case-sensitively. With an `evidence` list the object is refused, but only because packet `evidence` must be an object (z08, z09).
- P4, test gap: the non-equivalent mutant r3_alias_contract_off (the alias check also scans `kind` and the other contract keys) survives every instrument, including the builder tests. Distinguishing input (results/distinguish-r3_alias_contract_off.txt): `{"fixture_kind": "packet", "kind": "closure", ...passing packet}`. The candidate follows the documented "fixture_kind wins, kind is ignored" (rc 0, ok); the mutant refuses it (INVALID_PACKET).
- Observations kept: y08 (a symlinked fixture file is counted) and y09; unknown packet fields are still ignored (documented).

## Teeth (results/teeth-tally-3.9.6.txt)
39 mutants: the M01 r2 set unchanged (32, all anchors unique on 1621c82) plus 7 r3 mutants on the G01 r2 guards, plus a no-op control (killed by nothing). 4 shards on 3.9.6, 0 errors.
- Kills: builder fixture tests 37, suite 37, M01 oracle 17, M01 r2 probes 4, M01 r3 probes 5. Union 37/39.
- Survivors: f4_outer_recursion_off_EQUIV (expected equivalent, as M01 r2 named it) and r3_alias_contract_off (non-equivalent, above). Non-equivalent union 37/38.

## Harness disclosures
- First r3 probe run: z08 and z09 were refused only because `evidence` was a list (packet evidence must be an object). I added z13 and z14 without evidence; the first run output was overwritten by the final one, and the rows are otherwise unchanged.
- run_teeth_r3.py runs the r2 probes twice per mutant (a leftover line). Only the second result is used; this costs time and does not change the result.

## Not done
- Teeth ran on 3.9.6 only (time budget); the other instruments ran on all 4 interpreters. 3.10 is not installed.
