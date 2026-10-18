# M16: validation of G16 "Grounded-answer evals, offline"

**Kind:** Grok self-validation (same bot as the G16 builder). Not independent review. It was done adversarially:
- with an M16 oracle written for this pass on unseen snapshots (`oracle/m16_world.py`, "Brackwater allotments" plus seeded bus worlds), not derived from the builder's oracle or tests;
- with 28 single-site mutants and 5 stubs.

An independent reviewer is still required by the QA2 contract.

**Verdict: FAIL** against candidate commit `1f2d0b91e18690b577b64eff1c6ccb2ea4e9ad77` (branch `review/grok-g16-grounded-evals`, parent and base `02ba9c571b10ad1dba792d2ac5534bcad3171e67`). The candidate manifest verified 28/28, and its file set equals the diff file set (`raw/manifest-verify.txt`).

The core behaviour holds:
- The M16 core checks pass 10/10 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15.
- The suite passes (16 G16, 84 other, 100 total) on all four interpreters.
- Answers are byte-identical across interpreters.
- A fresh caller succeeds on 3.9.6 and 3.12.14.

The fail comes from two P2 defects in what the grader is for:
- **N1:** answers whose meaning contradicts the cited source, or that just dump whole documents, are graded `correct_supported`.
- **N3:** two sources that disagree on a number are answered, not abstained, unless the question is phrased how-much or how-many. The doc says it abstains "when two sources disagree on a number".

Eight more findings are P3 or P4, plus one observation (N11).

Runs were on host macOS (arm64) on 2026-10-18 between 13:32 and 14:10 PT. Python 3.12.14 was used unless stated.

## Isolation
- `git fetch origin review/grok-g16-grounded-evals` (read-only); FETCH_HEAD equals the full SHA (`raw/fetch.txt`). Then `git worktree add --detach /tmp/m16-eval 1f2d0b9...` (`raw/worktree-add.txt`). Nothing was cloned onto any other machine.
- The builder's worktree was not written. Branch, HEAD (`02ba9c5`), index hash (`c28a2f586b3e3001`) and status hash (`3c1f646dbc8025fc`, 61 lines) are identical before (13:32:58 PT) and after (14:08:31 PT), with an empty status diff (`raw/weekgrok-before.txt`, `raw/weekgrok-after.txt`).
- Mutants ran in scratch copies, not in the candidate worktree. Candidate `git status` is 0 lines after every matrix run (`raw/pyversions-matrix.txt`).
- No model was called. Everything is offline and deterministic.

## Acceptance items (M16 oracle, `raw/oracle-candidate-<version>.txt`)
| Check | Result | What it covers |
|---|---|---|
| k1 clean control | PASS | 8 cited answers with doc sha and code-point spans checked independently; 4 traps abstained; evaluate 12/12; baseline reproduced |
| k2 unseen seeds | PASS | Seeds 11, 2026 and 90210, 160 questions each, with sibling-route and wrong-stop traps |
| k3 forgeries | PASS | 16 hand-forged records (f01 to f16) get the exact verdict and citation status |
| k4 conflict and traps | PASS | how-much conflict abstains; unknown site and no-key-term questions abstain; a how-often question with no number abstains (but see N3) |
| k5 source change | PASS | changed sentence and deleted doc give stale_citation; moved lines are relocated; re-answer passes |
| k6 provenance | PASS | genuine baseline reproduced; edited or other-snapshot baseline unverified; imported claims labelled not executed or verified |
| k7 resume | PASS | faults x1 and x2 at 1 and 4 workers: exit 3 with no answers file; resume byte-identical with each step done once; torn tail recovered; corrupt journal, changed snapshot and changed questions refused |
| k8 invalid inputs | PASS | 7 invalid inputs exit 2 with nothing written and inputs unchanged (but see N5, N9) |
| k9 determinism and scale | PASS | 1500 docs by 6000 questions; 1 vs 4 workers identical; question order invariant; parallel evaluates identical |
| k10 abstain edges | PASS | abstain must be boolean true; an empty cited answer is not supported; missing records are counted |

Core is 10/10 and the oracle ACCEPTS on all four interpreters. Adversarial checks x1 to x17 are reported as findings and are never used to score.

## Findings (repros: `oracle/m16_finding_repros.py`, output `raw/finding-repros.txt`; identical on 3.9.6 in `raw/finding-repros-py39.txt`)
### N1 (P2): meaning-reversing or dumped citations are graded `correct_supported` (x1 to x4)
- **Negation flip.** An answer that reverses a "must not" rule, while quoting the exact full source sentence, is `correct_supported` with coverage 1.0.
- **Fragment quotes.** Quotes that skip the word "not" also pass. "not" and "no" are stopwords, so they never count against coverage.
- **Whole-document quote.** Quoting the whole document in full passes.
- **Cross-sentence swap.** One quote spanning two sentences, with the numbers swapped between subjects, passes.

The grader checks only that the answer's words and numbers occur somewhere in the quotes. It does not check that the claim is what the quote says, so a grounded-accuracy score can certify contradictions.

### N3 (P2): conflicting sources are answered unless the question says how-much or how-many (x9)
The doc says it "abstains ... when two sources disagree on a number". shed-2025.md says 15 pounds and shed-2026.md says 20 pounds. These questions all answer "A shed permit costs 15 pounds a year." from shed-2025.md, which wins on the alphabetical tie-break:
- "What does a shed permit cost?"
- "Shed permit cost per year?"
- "A shed permit costs how much?"

The conflict check only runs when `need_num` is set by the question's phrasing.

### N2 (P3): numbers are pooled across quotes and facts match as substrings (x5, x6)
- A number taken from an unrelated second quote passes ("12 troughs" makes "12 months" supported).
- The fact "22 pounds" is satisfied by the answer "122 pounds".

### N4 (P3): a near-miss question is answered (x10)
"How much does a quarter plot cost per season?" is answered with "A full plot costs 64 pounds per season." at coverage 0.75. It should abstain.

### N5 (P3): `evaluate --out` can overwrite a snapshot source document (x11)
`evaluate --out <snapshot>/plots.md` exits 0 and replaces the source document with the JSON report. The evaluate protect list does not include corpus documents. This contradicts the doc ("inputs are never overwritten") and README o9.

### N6 (P3): `abstain: true` with an asserted, cited answer counts as `correct_abstain` (x8)

### N8 (P3): journal integrity and concurrency (x12, x13)
- **Tampered record.** A hand-edited journal `done` record is resumed silently into the output. It exits 0 under producer `deterministic_baseline` with `executed_here` true. A later evaluate does mark the file unverified.
- **Concurrent resumes.** 4 concurrent `--resume` runs exit [0, 0, 2, 2] on 3.9.6 and 3.13.15, [0, 0, 0, 2] on 3.12.14 and [0, 0, 0, 0] on 3.11.16. The journal then has 3 ids done twice, and every later resume is refused ("duplicate or malformed done entry"). There is no lock, and the journal is left permanently unusable.

### N7 (P4): a fabricated quote with a made-up `doc_sha256` is reported as `stale_citation`, not invalid (x7)
A forger can turn "fabricated" into the softer "the source changed".

### N9 (P4): fault plan and path edge cases (x14, x15)
- Fault plan value `1e400` gives an OverflowError traceback with exit 1, not exit 2.
- `-1` is accepted, and `true` is treated as 1.
- `--out` equal to `--journal` (a new file) is accepted, and the journal is replaced by the answers file.

### N10 (P4): the report echoes producer claims (x17)
- `provenance.producer` echoes the file's own `verified: true` and `executed_here: true`.
- The producer kind string is interpolated into the evidence. The evidence can therefore contain "re-run here and matched", with the qualifier "(claimed by the file; not executed or verified by this evaluator)" appended.
- `baseline_reproduced` stays null. The qualifier is present, but the echoed fields can mislead a skim-reader.

### N11 (P4, observation): instruction text in a source (x16)
A source line with instruction text makes the baseline abstain (`conflicting_sources`) on an answerable question. This fails closed (a denial), with no wrong answer.

## Oracle teeth (`raw/oracle-teeth.txt`, `raw/builder-oracle-vs-teeth.txt`, `raw/builder-tests-vs-mutants.txt`, 3.12.14, `--scale-docs 300`)
| Subject | M16 oracle (core of 10) | Builder oracle (of 11) | Builder tests (16) |
|---|---|---|---|
| candidate | 10/10 ACCEPT | 11/11 | OK |
| noop stub (M16) | 0/10 reject | 0/11 | n/a |
| always-abstain stub | 2/10 reject | 1/11 | n/a |
| copy-question stub | 2/10 reject | 2/11 | n/a |
| builder noop_stub | 0/10 reject | 0/11 | n/a |
| builder naive_stub | 1/10 reject | 1/11 | n/a |
| 28 mutants | 27 killed, 1 survivor | 18 killed, 10 accepted | 23 killed, 5 accepted |

- **M16 oracle survivor:** `symlink_doc_followed`, judged equivalent. It removes the symlink guard, but the later `O_NOFOLLOW` open still refuses symlinked docs.
- **Builder oracle accepts:** abstain_truthy, cite_corpus_sha, conflict_check_off, coverage_not_checked, facts_not_in_quote_ok, invalid_input_writes, missing_record_ignored, need_number_ignored, order_dependent_output, symlink_doc_followed.
- **Builder tests accept:** abstain_truthy, coverage_not_checked, facts_not_in_quote_ok, invalid_input_writes, symlink_doc_followed.
- **Evidence claim.** The builder's handoff reported its mutations as 14/14 killed on its own set. Against this independent set of 28, its oracle misses 10 and its tests miss 5. Four of those are not equivalent and are missed by both: abstain_truthy, coverage_not_checked, facts_not_in_quote_ok and invalid_input_writes. Notably, `conflict_check_off` (turning off all conflict abstention) passes the builder oracle.

## Fresh caller (`oracle/m16_fresh_caller.sh`; `raw/fresh-caller.txt` on 3.12.14, `raw/fresh-caller-py39.txt` on 3.9.6)
The setup:
- a copy of the tree without .git;
- `env -i` with a new HOME (7 env vars);
- a PATH shim mapping python3 to the chosen interpreter;
- only the commands printed in `grounded-answer-evals.md`, run on the unseen allotment snapshots.

The results:
- Answer gives 8 answered and 4 abstained.
- Evaluate passes 12/12.
- Old answers against v2 name 4 stale citations exactly (exit 1). Re-answer and evaluate on v2 pass.
- The fault drill exits 3 with no answers file. Resume is byte-identical to the unbroken run.
- A hand-computed span for b07 equals the tool's span (77 to 140).

Both interpreters give the same output. The only difference is a trailing `[exit 0]` line that the 3.12 run's outer wrapper appended.

## Interpreter matrix (`raw/pyversions-matrix.txt`, `raw/cross-interpreter-answers.txt`)
- The suite passes on /usr/bin/python3 3.9.6, uv 3.11.16, 3.12.14 and uv 3.13.15: `test_g16_capability.py` 16 OK, `test_[!g]*.py` 84 OK, `test*.py` 100 OK.
- v1 answers, bus answers and the v1 report are byte-identical across all four (hashes bfbdb7a3bd027ae9, 772b1a3ef718a11e, bb9a5e68af1291d6).
- The M16 oracle v2 gives core 10/10 with 17 findings on each interpreter.

## Rejected and superseded runs (kept)
- `raw/oracle-candidate-run1-harness.txt` is rejected. My first k3 had wrong expectations: b06 is `incorrect`, not wrong_source, and an unknown doc with a sha is `stale`. k3 was rewritten with ids f01 to f16.
- `raw/*-v1-superseded.txt` are superseded. After teeth run 1, M16 oracle v1 left 5 mutant survivors. v2 adds checks that kill 4 of them (coverage, facts-in-quote, need-number, question order). All final numbers above are v2.

## Limitations
- This is self-validation by the same bot that built G16. It is not independent review.
- Mutant teeth were run on 3.12.14 only, with `--scale-docs 300` for speed. The candidate itself ran at the default 1500 docs.
- The builder oracle's o10 default of 3000 docs was not re-run at full size against mutants.
- Severity is my judgement. No fix was applied to the candidate, and no positive-control patch was written for M16.
- Matching is lexical by design (the doc says so). N1 and N2 are judged against the grader's stated purpose of certifying supported answers, not against a semantic standard.

## Files
- `oracle/`: m16_world.py, m16_oracle.py (v2), make_mutants.py, run_teeth.sh, run_pyversions.sh, m16_fresh_caller.sh, m16_finding_repros.py, stubs/
- `raw/`: fetch, worktree-add, manifest-verify, week-grok before and after, per-interpreter oracle runs, teeth (3 files), matrix, cross-interpreter answers, fresh caller (2), finding repros (2), plus rejected and superseded runs
- `MANIFEST.sha256`: sha256 of every file here except itself
