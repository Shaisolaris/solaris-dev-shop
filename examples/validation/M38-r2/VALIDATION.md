# M38 r2 validation of G38 r2 authority consistency (Grok self-validation, not independent review)

Candidate: G38 r2 `01c9afbfc9066d844be0e0a7ee9b90c1a3859491` (branch review/grok-g38-authority-consistency),
direct parent G38 r1 `41ad34461d0924b34d1d725012825f736ee548a3`, on G05 `8b38a72f2183ad7427594d6557d7e308baf0469b`.
Tools: `employees/quality-security/security-auditor/provenance_check.py` and
`employees/engineering/blockchain-developer/event_chain.py`. Validator: Grok, the same agent family that built G38.
This is self-validation, not independent review, and not a legal opinion. Pass started 10:24 PT, Mon Oct 19 2026.

## Verdict

**FAIL (self-validation): one P2, three P4 and OBS notes.** A proposed fix for the P2 is in `proposed-fix.patch`. It is
positive-controlled and was not applied.

Every M38 finding the handback claims is repaired, and my M38 rows all pass:
- P2-1, header-only Apache and MIT with appended terms: both are now unrecognised.
- P2-2: append after a lost trailing newline no longer merges events.
- P3-1: root-level plugin.json is checked.
- P3-2: the "GPL, see LICENSE." section is read.
- P3-3: the subject holds only matching digests.
- P4-1: a missing --out folder exits 2.

The FAIL comes from probing past my own M38 oracle. The new whole-text match still skips the text it lets through
unchecked: the lines it treats as copyright lines, and the Apache appendix. A license with added restrictions there is
still called MIT or Apache-2.0.

## Own-patch disclosure (important)

The r2 fixes for both M38 P2s come from my own M38 proposed patch (examples/validation/M38/proposed-fix.patch on
994cb3d), generalized by the builder, and the r2 docs say so. A validator checking a fix it proposed tends to test what
it expected, so this pass adds R10 and O11, which use inputs my M38 oracle never used:
- small word edits to the whole MIT and Apache texts;
- terms placed in copyright-style lines and inside the Apache appendix;
- a filled-in appendix;
- CRLF license texts and CRLF event logs, a CR-only tail, and two lost newlines in a row;
- `--out` on an existing folder;
- the pyproject `file =`, single-quote and table forms, and README bold and parenthesis forms;
- a plugin.json in node_modules and in a fixture folder.

The builder also ran a copy of my M38 oracle in its handback (11/11). That is a builder re-run, not this validation.
The builder's own oracle case "apache everywhere but LICENSE" was changed to "apache header only" in r2. That follows
the fix, and I did not rely on it.

## Prerequisite chain

- The diff sha equals the patch file (`cddcff74...dc66d`). The manifest has 6/6 entries, 0 mismatches, and its set
  equals the diff set. 41ad344 is the direct parent and its parent is G05 8b38a72 (raw/binding-verify.txt).
- The remote heads of G38 and G05 are still 01c9afb and 8b38a72, so nothing in the chain is superseded. G38 r1 was
  validated by M38 (994cb3d, FAIL with P2-1 and P2-2) and G05 by M05 (177a42f, PASS with residuals).

## Method

- Oracle `oracle/m38r2_oracle.py`: the M38 v2 oracle (own synthetic repositories and hash chains, own sha256, an audit
  hook that allows no process, network or mail use) unchanged in P01-S08, plus:
  - R10 (scored): the probes listed above, each with the result the docs give.
  - O11 (OBS, not scored): an SPDX header line, a BOM, copyright before the title, a wrapped copyright, an Apache text
    with a copyright line on top, the "Licence" spelling, Apache without its appendix, pyproject forms, README forms
    and plugin.json in skipped or fixture folders.
- Negative control: the same oracle on the r1 tool (results/r1-tool-oracle-3.9.6.json) scores 7/12. It fails the M38
  rows that r2 repairs and 18 R10 subs, so the new row tells r1 from r2.
- Four interpreters; mutation tests on 3.13.15 and 3.9.6 with the builder's 63 r2 mutants copied unchanged; a fresh
  caller. All runs were on rsync copies or the detached eval worktree, and the candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g38: Ran 16 tests in 20.686s  OK  | full: Ran 171 tests in 43.436s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38r2-oracle: M38 R2 ORACLE 11/12 core FAIL | m38-naive: M38 R2 ORACLE 1/12 core FAIL | m38-noop: M38 R2 ORACLE 2/12 core FAIL
== 3.11.16 | g38: Ran 16 tests in 12.950s  OK  | full: Ran 171 tests in 34.019s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38r2-oracle: M38 R2 ORACLE 11/12 core FAIL | m38-naive: M38 R2 ORACLE 1/12 core FAIL | m38-noop: M38 R2 ORACLE 2/12 core FAIL
== 3.12.14 | g38: Ran 16 tests in 21.543s  OK  | full: Ran 171 tests in 40.302s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38r2-oracle: M38 R2 ORACLE 11/12 core FAIL | m38-naive: M38 R2 ORACLE 1/12 core FAIL | m38-noop: M38 R2 ORACLE 2/12 core FAIL
== 3.13.15 | g38: Ran 16 tests in 23.299s  OK  | full: Ran 171 tests in 47.623s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38r2-oracle: M38 R2 ORACLE 11/12 core FAIL | m38-naive: M38 R2 ORACLE 1/12 core FAIL | m38-noop: M38 R2 ORACLE 2/12 core FAIL
pycache in copy: 0
candidate status lines: 0
```

The oracle scores 11/12 on every interpreter, with the same failing subs on all four. My naive and no-op runs
score 1/12 and 2/12. P01-S08 pass; R10 fails three subs for P2-1 (MIT), two for P2-1
(Apache), `readme_bold_gpl_mismatch_found` (P4-3) and `provenance_out_existing_folder_exit_2` (P4-1).

Mutation tests (results/teeth-*.log): **56/63 killed on 3.13.15 and 55/63 on 3.9.6**. Survivors, each checked with
the builder's G38 tests:

- teeth-3.13.15.log: pc_escape_allowed SURVIVED
- teeth-3.13.15.log: pc_dup_manifest_ok SURVIVED
- teeth-3.13.15.log: pc_out_not_atomic SURVIVED
- teeth-3.13.15.log: ec_empty_ok SURVIVED
- teeth-3.13.15.log: ec_long_line_ok SURVIVED
- teeth-3.13.15.log: ec_claimed_unstripped SURVIVED
- teeth-3.13.15.log: ec_recover_in_place SURVIVED
- teeth-3.9.6.log: pc_escape_allowed SURVIVED
- teeth-3.9.6.log: pc_dup_manifest_ok SURVIVED
- teeth-3.9.6.log: pc_out_not_atomic SURVIVED
- teeth-3.9.6.log: ec_empty_ok SURVIVED
- teeth-3.9.6.log: ec_long_line_ok SURVIVED
- teeth-3.9.6.log: ec_claimed_unstripped SURVIVED
- teeth-3.9.6.log: ec_recover_in_place SURVIVED
- teeth-3.9.6.log: pc_g05_cache_written SURVIVED
- builder tests: (3.13.15) pc_escape_allowed builder tests: KILL FAILED (failures=1) FAIL: test_oracle_and_controls (tests.test_g38_capability.G38Wiring.test_oracle_and_controls)
- builder tests: (3.13.15) pc_dup_manifest_ok builder tests: KILL FAILED (failures=1) FAIL: test_manifest_cases (tests.test_g38_capability.G38Provenance.test_manifest_cases)
- builder tests: (3.13.15) pc_out_not_atomic builder tests: KILL FAILED (failures=1) FAIL: test_manifest_cases (tests.test_g38_capability.G38Provenance.test_manifest_cases)
- builder tests: (3.13.15) ec_empty_ok builder tests: KILL FAILED (failures=1) FAIL: test_tamper_kinds (tests.test_g38_capability.G38EventChain.test_tamper_kinds)
- builder tests: (3.13.15) ec_long_line_ok builder tests: KILL FAILED (failures=1) FAIL: test_tamper_kinds (tests.test_g38_capability.G38EventChain.test_tamper_kinds)
- builder tests: (3.13.15) ec_claimed_unstripped builder tests: KILL FAILED (failures=1) FAIL: test_append_rules (tests.test_g38_capability.G38EventChain.test_append_rules)
- builder tests: (3.13.15) ec_recover_in_place builder tests: KILL FAILED (failures=1) FAIL: test_recover (tests.test_g38_capability.G38EventChain.test_recover)
- builder tests: (3.9.6) pc_g05_cache_written builder tests: no kill OK

- The seven survivors on both interpreters are the same seven my M38 oracle missed in r1 (path escape, duplicate
  manifest lines, --out atomicity, empty log, long line, unstripped claimed_by, recover in place). The builder's
  tests kill each one, so the union of my oracle and the builder's tests kills them. R10 was aimed at the r2
  changes, not these.
- pc_g05_cache_written survives on 3.9.6 only, because the Apple 3.9.6 never writes bytecode. It is killed on
  3.13.15. On handback question 1, a teeth-local subprocess without PYTHONDONTWRITEBYTECODE, run on an interpreter
  that writes bytecode, would kill it. The existing copy-based test does not, under this harness.

Fresh caller (results/fresh-caller.txt): every line of the README block, verbatim under `env -i` with a new HOME, on 3.9.6 and
3.13.15, gives its documented result: exits 0, 0, 1 and 0, the builder oracle ACCEPTED 8/8, and the naive and no-op
controls REJECTED 1/8. No __pycache__ was written and the tree is unchanged. The 3.9 HOME entry is the Apple
interpreter's own cache folder.

## Findings

- **P2-1: restrictions placed in a "copyright" line or in the Apache appendix are still accepted as MIT or
  Apache-2.0.** This is the M38 P2-1 class, narrowed but not closed.
  - MIT: identify() drops every leading line that starts with "copyright" or "(c)" before comparing the body. Each of
    these gives license MIT, result **consistent, exit 0**:
    - "Copyright (c) 2026 Oracle Test Holdings (synthetic). Commercial use of the Software is prohibited.";
    - an extra line "(c) The Software may not be used for commercial purposes.";
    - an extra line "Copyright holders forbid any commercial use of the Software.".
  - Apache: after the hashed terms, the tail only has to start with the appendix title and end with "limitations
    under the License.". "NOTWITHSTANDING THE ABOVE, NO COMMERCIAL USE IS PERMITTED." inside the appendix, or an
    "Additional term: no commercial use." paragraph before the final sentence, is still Apache-2.0.
  - The doc promises the whole text, with MIT allowed only its title and copyright lines and Apache only "its
    standard appendix".
  - Proposed fix: a copyright line must have the form "copyright [(c)] YEAR[S] HOLDER[.] [all rights reserved.]",
    so a line that adds a sentence is not dropped. The Apache appendix is matched exactly by sha256 of its fixed
    parts, except the one boilerplate copyright line, which may be the placeholder or a year and holder.
  - Small edits stay unrecognised, as they should: "AUTHOR" for "AUTHORS", or a removed "merge", "sublicense",
    "NONINFRINGEMENT" or Apache "non-exclusive".
- **P4-1 (residual of M38 P4-1): `--out` naming an existing folder gives a traceback with exit 1**
  (IsADirectoryError from os.replace) in provenance_check. A missing folder is fixed, and event_chain recover refuses
  an existing path cleanly.
- **P4-2 (carried from M38 P4, not in the r2 scope): pyproject forms other than `license = "X"` and
  `license = { text = "X" }` are reported as license_undeclared.**
  - The forms are `license = { file = "LICENSE" }`, `license = 'MIT'` and a `[project.license]` table.
  - The file form is a valid declaration that points at the LICENSE being checked, so this is a false finding.
- **P4-3 (residual of M38 P3-2): a bold README section `**GPL-3.0**` is not read**, so with an MIT LICENSE no
  mismatch is reported. A parenthesis form ("GPL-3.0 (see LICENSE)") is read.
- OBS:
  - These are unrecognised (the safe direction, but noisy): an SPDX header line, a UTF-8 BOM, copyright before the
    title, a copyright line that wraps onto a second line, an Apache text with a copyright line on top, and the
    "MIT Licence" spelling.
  - Apache without its appendix is Apache.
  - "MIT OR Apache-2.0" in pyproject is a mismatch.
  - A plugin.json in node_modules is skipped, but one in a fixture folder is checked unless `--exclude` names it, as
    documented.
  - CRLF event logs verify and accept appends, which then use LF line endings (mixed endings in one file). A CR-only
    tail after a lost newline also recovers.
  - Handback question 1 (pc_g05_cache_written): see the survivor note above.

## Proposed fix (not applied)

`proposed-fix.patch` changes only provenance_check.py (COPYRIGHT_RE, FILL_RE and the appendix check).

Positive control on an rsync copy with the patch applied:
- my oracle passes every P2-1 sub, and R10 then fails only the two P4 subs the patch does not touch
  (results/fix-positive-control-oracle-3.9.6.json);
- O05, O06, O11, P03 and R09 details are unchanged apart from temp paths and times;
- tests.test_g38_capability 16 OK, the full suite 171 OK and the builder oracle ACCEPTED 8/8 on 3.13.15;
- the repository's own LICENSE is still MIT (results/fix-positive-control.txt).

## Disclosures

- Own-patch origin of both P2 fixes, as described above.
- Oracle authoring fixes after the first run (kept as results/kept/oracle-first-run-3.9.6.json and
  results/kept/m38r2_oracle_first.py):
  1. I expected an unrecognised text to report license null. It reports "unrecognized", so I accept both.
  2. My Apache word-edit probe targeted a phrase that wraps across lines in the real text, so the edit never
     happened. It now edits "worldwide, non-exclusive, no-charge".
  3. My filled-in appendix probe used square brackets, but the real placeholder uses braces, so it also tested
     nothing. It now uses braces.

  After these fixes, no expectation was changed to match the candidate. The P2-1 subs failed in both runs.
  I added the two README GPL subs after the first run.
- Scripts are copies of the M38 ones with paths changed to M38-r2 (scripts/).
- Publication safety: the first publish run stopped at the safety scan, which found local interpreter paths in the
  crash tracebacks of the no-op control runs (results/oracle-noop-*.json, one per interpreter). I trimmed each to
  its last line, marked as trimmed, as in M38. I did not loosen the scanner.
- Collision check (raw/collision-check.txt): my temp folders use m38r2 prefixes. The builder's G38, G39 r2 and G40
  folders were present and untouched; /tmp/m38-peek is not mine and was left alone. Nothing was started on G39 or G40.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there, and its branch, index and status are unchanged.
