# M25 r3: Grok self-validation of G25 r3 (device event protocol, device_protocol.py)

Grok self-validation by the same bot that built the programme. This is not independent review and not manager acceptance.

- Candidate: G25 r3, commit eb9c7c47384ec5d8ba951aca72240ed57ca7b383 on review/grok-g25-device-protocol (parent a902bc4, G25 r2). main stays at 02ba9c5.
- Window: 23:20 to 23:40 PT, 2026-10-18. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. The candidate was not modified.
- Disclosure: the r3 fixes are the builder's own code. M25 r2 had no P1 or P2, so I wrote no proposed-fix patch for it. The findings this round fixes (P3 lines, three P4s) came from my own M25 r2 pass, so I am scoring the fix for findings I raised.

## Verdict: PASS with residuals (no P1, P2 or P3)
The M25 r2 P3 is fixed: editing lines, offset, the prefix hash, tool_version or the schema gives exit 4 or 2 with or without a recomputed hash. All three r2 P4s are fixed. What is left is P4 and the documented limits.

## Binding (raw/binding-verify.txt)
- The diff a902bc4..eb9c7c4 is byte-identical to G25-r3.patch (sha256 0956adb4...).
- The manifest has 17 entries, all OK, and its file set equals the diff file set.

## Results (results/, matrix.txt)
| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| Builder suite | 113 OK | 113 OK | 113 OK | 113 OK |
| Builder oracle (noop 0/12, naive 1/12) | 12/12 | 12/12 | 12/12 | 12/12 |
| M25 oracle v2 core / adversarial | 23/23, 17/17 | same | same | same |
| M25 r2 probes (r2 tool 15/21) | 21/21 | 21/21 | 21/21 | 21/21 |
| New M25 r3 probes, graded (r2 tool 14/26) | 26/26 | 26/26 | 26/26 | 26/26 |

- **M25 r3 probes (oracle/m25r3_probes.py).** The expectations come from device-event-protocol.md at eb9c7c4.
  - H00 to H06: editing any checkpoint field gives exit 4.
  - H10, H11: lines plus or minus 1 with a recomputed hash gives exit 4.
  - H12, H17: a forged offset gives exit 2 ("events file no longer starts with the part already ingested").
  - H14 to H16: body_sha256 missing or a number, or lines as a string, gives exit 4.
  - H18: a schema /2 checkpoint gives exit 2.
  - N01 to N03, N05, N06: "1", "true", "[{}]", a BOM and invalid UTF-8 give exit 4. N07: a folder gives exit 2 with no traceback.
  - U01: an unterminated last line, crash before it and resume equals the unbroken run.
  - Q01, Q02, Q04, Q05: --record under a file three levels up, under a dangling symlink, or in a read-only folder gives exit 2, and nothing is written.
- **Direction:** the r2 tool fails H00 to H04, H18, N01 to N03, Q01, Q02 and Q05, so these rows are sensitive to the r3 change.
- **Observation rows (recorded, not graded):** N04, H13, U02, Q03, Q06; see the findings.
- **Disclosed reclassification:** N04 (`{}`) was graded in the first run and failed there (exit 2, not 4). I reclassified it to an observation before the scored run, because the doc can be read either way: `{}` is a JSON object, and "belongs to another command log or tool" is a defensible answer. It is listed as a P4 below, not hidden.
- **Fresh caller (results/fresh-caller-3.9.6.txt, fresh-caller-3.13.15.txt; the M25 r2 script):** env -i, a new HOME, a python3 shim, an offline guard, and only the doc commands.
  - Exits are 0, 1, 3 and 1, as documented.
  - The unbroken and resumed report hashes are identical (9d40473102857c30), and 3.13.15 output equals 3.9.6.
  - The hash differs from r2 (8e5d7b19). I believe the tool_version bump to 1.2.0 explains this, but I did not prove it.

## Teeth (3.9.6 only; results/teeth-3.9.6/, results/teeth-tally.txt)
- There are 45 single-anchor mutants: the M25 r2 set plus 10 new r3 mutants of my own (oracle/r3_extra.py) aimed at the r3 changes, plus 2 _EQUIV controls. The baseline holds core 23, r2 probes 21, builder tests OK and builder oracle 12/12.
- **Grok graded oracles kill 29/45. Builder tests kill 42/45. Builder oracle kills 23/45.**
- **Survivors of every instrument:** the 2 _EQUIV controls (expected) and my r3g_parent_no_symlink.
- **Non-equivalence (oracle/survivor_distinguish_r3.py, results/survivor-distinguish-3.9.6.json).**
  - r3g_parent_no_symlink: for `--record dang/sub` under a dangling symlink, the candidate gives "dang is not a folder, so dang/sub cannot be created", while the mutant falls through to "cannot write dang/sub: File exists". Both exit 2 and write nothing.
  - r3g_parent_walk_off and r3g_parent_first_only show the same pattern with a file three levels up. The builder tests kill both.
  - r3g_recount_no_tail: if a checkpoint is taken at an unterminated end and the writer then finishes the line, the candidate resumes rc 0 while the mutant gives exit 4 "lines does not match". The builder tests kill it; my probes did not.
- **Teeth gap in my own probes (oracle note, not a candidate finding):** the Q rows grade only the exit code and traceback. Because the late OSError catch also gives a clean exit 2, they cannot see whether the ancestor walk ran. I did not change the scored probes after the run.
- The 13 r2-era mutants that survive my graded oracles but die to the builder tests are the same mutant classes as in M25 r2 (ack, claim and counts guards that are only reachable through forged checkpoints).

## Findings by severity
- P1: none.
- P2: none.
- P3: none.
- P4 test gap: no builder test covers a dangling symlink above --record. r3g_parent_no_symlink survives all 113 tests. The behaviour is correct today (Q02 PASS) but unpinned. The handback's claim that the builder tests kill all 8 of its r3 mutants still holds; this mutant is mine, not one of those 8.
- P4 U02, pre-existing: if a checkpoint is written at an unterminated end and the file then grows, the resumed report differs from an unbroken run only in inputs.event_lines (393 against 392). The r2 tool behaves the same.
- P4 H13: an unknown top-level checkpoint key with a recomputed hash is accepted (rc 1, same report). This is consistent with the documented forged-recompute limit.
- P4 N04: `{}` gives exit 2 "belongs to another command log or tool", not exit 4 "not a checkpoint object". This is arguable either way; the doc could say which.
- P4 Q03, doc silent: a symlinked folder above --record is allowed and the run writes through it.
- Observation Q06: ingest rejects --record with an argparse error (exit 2), which is the expected behaviour.
- Open: L03 stays an owner decision as documented. A forger who recomputes the r3 hash with consistent fields is still accepted, which is a documented limit.

## week-grok hygiene (raw/weekgrok-before.txt, raw/weekgrok-after.txt)
- The branch (programme/grok-week-20261018), head 02ba9c5 and index c28a2f586b3e3001 are unchanged from 23:20:42 to 23:34:34 PT.
- The status went from 87 to 95 lines. All 8 new lines are G34 marketing files (content-marketer, cro-landing-designer, seo-aso-specialist, tests/test_g34_capability.py), with mtimes from 23:24:24 to 23:29:52 PT. The builder made them; I wrote none of them. The listings are kept outside this folder.

## Not done
- Teeth ran on 3.9.6 only.
- I did not prove why the fresh-caller hash changed from r2.
- No browser, network or install was used. No patch was proposed, because there is no P1 or P2.
