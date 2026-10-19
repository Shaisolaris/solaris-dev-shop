# M16 r2: recheck of the G16 rework r2 "Grounded answers with citations"

**Kind:** Grok self-validation (same bot as the G16 builder). Not independent review. An independent reviewer is
still required by the QA2 contract.

**Verdict: FAIL** against rework commit `df25d6aa531e6fde1d0c8706595bb9a6410cbb69` (parent `1f2d0b9`, base
`02ba9c5`). One P2, one P3 and three P4 findings (R1 to R5 below). Every original r1 reproduction of N1 to N11 is
now handled correctly, but two N1 variants still reverse meaning and are graded `correct_supported` (P2), and the N5
guard can be bypassed by a case-variant path on the default macOS filesystem (P3).
- The manifest verified 28/28. Its file set equals the diff file set 02ba9c5..df25d6a, and `G16-r2.patch` equals
  the 1f2d0b9..df25d6a diff byte for byte (`raw/manifest-verify.txt`).
- The full suite is 106 OK (22 G16 + 84 other) on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (`raw/pyversions-matrix.txt`).
- The M16 oracle is core 10/10, and adversarial 17/17 attacks are rejected, with 0 findings on all four interpreters
  (`raw/oracle-candidate-<v>.txt`). The builder oracle is 14/14.
- The answers are byte-identical across the four interpreters (`raw/cross-interpreter-answers.txt`).

Runs were on host macOS (arm64, case-insensitive APFS) on 2026-10-18, between 16:52 and 17:25 PT. An unrelated
builder job ran on the same host at the same time.

## Isolation
- The commit was fetched read-only into the programme repo, and FETCH_HEAD equals the full SHA. Then
  `git worktree add --detach /tmp/m16r2-eval df25d6a...` (`raw/fetch.txt`, `raw/worktree-add.txt`). Nothing was
  cloned onto another machine.
- The builder's worktree was not written. Branch, HEAD, index hash and status hash are identical before (16:52:30 PT)
  and after (17:24:10 PT), and the status listing is byte-identical (`raw/weekgrok-before.txt`, `raw/weekgrok-after.txt`).
- Mutants and the proposed fix ran in scratch copies, and the fix ran in a separate detached worktree. The candidate
  worktree's `git status` was empty.

## r1 findings N1 to N11
| r1 | r2 result | Evidence |
|---|---|---|
| N1 (P2) | Original repros n1a to n1d are now unsupported. **Residual: R1** | `raw/finding-repros-r1-script.txt`, x1 to x4, a01 to a03 |
| N2 (P3) | Fixed (n2a unsupported, n2b incorrect; x5 and x6 rejected) | same |
| N3 (P2) | Fixed: abstains on every phrasing tried (x9) | same |
| N4 (P3) | Fixed: the near-miss question abstains (x10). a09 is a pre-existing over-abstain, also in r1, and not counted | same, a09 |
| N5 (P3) | The original repro is refused (x11). **Bypass: R2** | x11, a05 to a07 |
| N6 (P3) | Fixed: `answered_unanswerable` (x8) | repro script |
| N7 (P4) | The original repro is invalid (x7). **Bypass: R3** | x7, a04 |
| N8 (P3) | Fixed: an edited journal is refused (x12, x13). A journal with a deleted middle entry is refused (a10) | x12, x13, a10 |
| N9 (P4) | Fixed: fault values 100 → exit 3; 101, "2", 2.0 and {} → exit 2; no traceback (x14, x15, a11) | a11 |
| N10 (P4) | Fixed: producer claims are no longer echoed as facts (x17) | x17 |
| N11 (P4) | Instruction text is filtered (x16). **Over-filter regression: R4** | x16, a08 |

The r1 repro script (`oracle/m16_finding_repros.py`, unchanged) prints correct verdicts for N1 to N7. It then stops
at N8 with a FileNotFoundError, because the hand-edited journal is now refused, which is the intended r2 behaviour.
N8 is covered by x12, x13 and a10 instead.
The published run is on /usr/bin/python3 3.9.6. An earlier 3.12.14 run printed the same verdicts, but it was not published
because its traceback showed a local interpreter path.

## Findings (r2)
### R1 (P2): N1 residual. A moved or added negator still reverses meaning and is graded `correct_supported`
- a01: the source says "Plot holders must not light bonfires between April and September." The answer is "Plot
  holders must light bonfires between April and September, not later." It is graded `correct_supported`
  (coverage 0.875).
- a02: the source says "Hosepipes are not allowed on the Eastside site." The answer is "Hosepipes are allowed on the
  Eastside site, nothing else is." It is graded `correct_supported`.
- Cause: `_support` compares only whether any negator is present on each side, not what it negates. The a03 control
  (a correct "aren't") stays supported.
- The builder's documented limit ("antonyms and reordered clauses can still pass") does not cover these. They are
  plain negators that the check claims to handle. The same result holds on 3.9.6 and 3.12.14.
- **Proposed fix:** `proposed-fix-r2.patch`, 14 added lines, never applied to the candidate. It binds each negator
  to the next content word and rejects an answer that negates something the source does not, or that asserts a word
  the source negates. A leading answer-particle "No," is ignored.
- Positive control (`raw/proposed-fix-positive-control.txt`, 3.12.14 and 3.9.6): `git apply --check` succeeds on a
  clean df25d6a. The builder tests are 22 OK and the full suite 106 OK. The builder oracle is 14/14. The M16 oracle
  is 10/10, with 17/17 attacks rejected. a01 and a02 now hold, and every other adversarial case is unchanged.
- v1 of the fix broke builder test case `f` ("No, the Heron K13 is not rated..."). It is kept as
  `raw/proposed-fix-r2-v1-superseded.patch`.

### R2 (P3): N5 bypass. A case-variant path overwrites a snapshot source document
- a05: `evaluate --out SNAP/plots.md`, where the snapshot folder is `snap`, exits 0 and overwrites the source
  document `plots.md`. This works because APFS, the macOS default, is case-insensitive.
- a06: `answer --out Snap/new-answers.jsonl` writes a new file into the snapshot folder.
- a07 control: a symlink to the snapshot is refused.
- Cause: the guard compares path strings, not file identity. A fix would compare `os.path.samefile` or
  (st_dev, st_ino) of the resolved parent against the snapshot directory, and of the target against each document.
- No patch is required at P3, so none was written.

### R3 (P4): N7 bypass. A self-declared `meta.corpus_sha256` makes a fabricated quote `stale_citation`
- a04: a fabricated quote with a made-up `doc_sha256`, plus an answers-file meta that declares a different corpus
  hash, is reported as `stale_citation`, not invalid.
- The producer controls the meta, so "made for another snapshot" is self-asserted. The builder documents that a
  forger can recompute the hash chain. This is the narrower point that one free field is enough.

### R4 (P4): N11 over-filter regression. A legitimate rule is discarded as instruction-like
- a08: the source sentence "Model boats may be sailed on the pond at weekends; the warden will answer any
  questions." is filtered, so the answer abstains. A control without "answer" is answered, and so is one with "Toy
  boats".
- r1 answered this correctly. The failure is closed (abstain, not wrong), hence P4.

### R5 (P4): the builder's equivalence claim for `identifiers_not_exact` is wrong. The mutant survives every scorer
- REWORK.md lists `identifiers_not_exact` as an equivalent survivor. It is not equivalent. For "When does the K99
  bus to Heron leave?", the candidate correctly abstains, but the mutant answers "Bus K241 to Heron leaves at 23:10
  on weekdays." (`raw/equivalence-probes-3.12.14.txt`).
- The M16 oracle, the builder oracle and the builder tests all accept this mutant. The guard is real but untested,
  and the evidence claim is false. A test with a missing identifier that is a substring of a present one would kill it.

## Mutation teeth (3.12.14, `--scale-docs 300`)
Subjects: the candidate, the r1 tool (1f2d0b9), 3 M16 stubs, 2 builder stubs and 28 M16 mutants. 22 mutants use
their r1 anchors unchanged, and 6 were re-pointed using the builder's MOVED list and checked by hand
(`oracle/make_mutants_r2.py`, `raw/mutant-generation.txt`).

| Subject | M16 oracle core | Builder oracle | Builder tests |
|---|---|---|---|
| candidate | 10/10, ACCEPT | 14/14 | 22 OK |
| r1 tool | ACCEPT (core does not target the r2 fixes) | 11/14 (o12, o13, o14) | 7 failures |
| 5 stubs | all rejected | all rejected | n/a |
| 28 mutants, killed | 24 | 24 | 24 |

- The union of the three scorers kills 24/28. The survivors are `identifiers_not_exact` (not equivalent, R5),
  `invalid_input_writes` (equivalent on the probe: exit 2, journal kept, nothing written), `numbers_not_checked`
  (same verdict; only the problem text differs) and `symlink_doc_followed` (equivalent: O_NOFOLLOW, per the r1
  analysis).
- **Harness correction:** my r1 anchor for `stale_reported_invalid` still matched exactly once in r2. It now hits
  the new N7 fallback branch, which returns invalid anyway, so as generated that mutant is equivalent, and all three
  scorers "survived" it (`raw/teeth-3.12.14.tsv`). The mutant that keeps the original intent, with the builder's
  re-pointed anchor, is killed by all three scorers (`raw/teeth-repointed-3.12.14.tsv`). The counts above use the
  re-pointed version. Counted as generated, it would be 23/28.

## Fresh caller and adversarial runs
- Fresh caller (env -i, a new HOME, a python3 shim, documented commands only) passes on 3.12.14 and 3.9.6. The
  outputs are identical except for the interpreter line: 8 answered and 4 abstained, evaluate passes, 4 answers are
  stale on v2, re-answering passes, the fault exits 3, resume is byte-identical, and the hand span is 77 to 140
  (`raw/fresh-caller-*.txt`).
- The r2 adversarial cases a01 to a11 hold 4/11 on the candidate, identical on 3.9.6 and 3.12.14 (r1 tool: 2/11).
  a09 is pre-existing and is not counted as a finding.

## Limits
- Teeth ran on 3.12.14 only, at `--scale-docs 300`. Every other check ran on at least 3.9.6 and 3.12.14, and the
  matrix and oracle ran on all four interpreters.
- No Linux or Windows runs, and Python 3.10 is not installed on the host. The case-insensitivity finding (R2) is
  specific to case-insensitive filesystems.
- The equivalence probes ran on 3.12.14 only.
- Same-bot validation: shared blind spots with the builder are possible.
