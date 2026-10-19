# M38 validation of G38 repository and legal authority consistency (Grok self-validation, not independent review)

Candidate: G38 `41ad34461d0924b34d1d725012825f736ee548a3` (branch review/grok-g38-authority-consistency), direct parent
G05 `8b38a72f2183ad7427594d6557d7e308baf0469b`. Tools `employees/quality-security/security-auditor/provenance_check.py`
and `employees/engineering/blockchain-developer/event_chain.py`, docs `provenance-integrity.md` and
`immutable-event-validation.md`. Validator: Grok, the same agent family that built G38. This is self-validation, not
independent review, and it is not a legal opinion about any license. Pass started 08:57 PT, Mon Oct 19 2026.

## Verdict

FAIL (self-validation) on two P2 findings, with three P3 and four P4 findings. A proposed fix for both P2s is
included and positive-controlled, and it is not applied (`proposed-fix.patch`). The parts M38 was asked to stress
mostly hold: the tamper-evident chain names every tamper I tried at its line, it trusts nothing after the break,
and an anchor catches a full rewrite. No legal opinion, compliance claim, verified signature or authenticated
identity is claimed anywhere in the outputs or in the changed role text. Nothing contacts a network, starts a
process or touches a wallet. The license check, though, can report a wrong license as consistent, and append can
break a log that verified.

## Prerequisite chain

- The diff sha equals the patch file and the handback (`592a261e...4b0`). The manifest has 32/32 entries with 0
  mismatches and its set equals the diff set. 8b38a72 is the direct parent (raw/binding-verify.txt).
- G05 8b38a72 sits on G04 314b4db and G02 bbe682b. M05 validated it at 177a42f (PASS with P3 and P4 residuals). The
  remote G05 head is still 8b38a72, so nothing in the chain is superseded. provenance_check.py loads G05
  `artifact_digests` by path; M38 exercised it only through G38.

## Method

- Fresh oracle `oracle/m38_oracle.py` (v2), written from M38.md, G38.md and the two docs before I read the builder's
  oracle. It builds its own synthetic repositories (a full MIT text I typed, an Apache-2.0 text copied from a local
  pip licence file into `oracle/data/`) and its own seeded hash chains. It computes every expectation with hashlib
  and drives both CLIs. Every run goes through an audit hook, and no process, network or mail event is allowed at all.
- Rows:
  - P01 clean controls: my MIT repo is consistent with 4 declarations, and integrity.subject equals my own sha256 of
    all 8 listed files. The actual repository is consistent with the fixture folder excluded (the exclusion is
    disclosed) and names exactly the fixture's two license files without it.
  - P02 single-cause drifts: plugin, PEP 639 pyproject string, no pyproject license, badge, section, COPYING, LICENCE
    spelling, NOTICE naming a missing file, nested plugin without a license, unrecognised text, Apache text under MIT
    declarations, no LICENSE.
  - P03 unseen license cases: MIT plus an added restriction; MIT-0; Apache named in prose; NOTICE naming a longer
    path; no NOTICE; a symlink loop; malformed and non-string plugin licenses; "GPL, see LICENSE."; a plugin.json
    outside employees/; --out into a missing folder.
  - P04 manifest integrity: a symlink entry, a path through a symlinked folder leading outside ROOT, a .. escape, an
    absolute path, a folder, missing and changed files; the subject holds only matching files; a conflicting
    duplicate entry; a malformed manifest exits 2 and keeps the earlier --out report.
  - R09 (v2) documented forms (see Disclosures).
  - E01 clean chains: the fixture recomputes, the anchored verify passes, and my 60-event chain verifies as
    self-consistent only, with claimed_by counts equal to mine and reported as not authenticated.
  - E02 tamper evidence on seeded chains of 50 events: edit; edit with that event rehashed; deletion; swap; replay;
    torn tail; junk line; rehashed time regression; rehashed naive time; extra and missing fields; an unanchored
    rewrite (self-consistent only) caught by the original anchor; truncation before the anchor; a tamper after a
    good anchor; bad anchors; and a soak of 10 seeded chains of 40 to 300 events.
  - E03 append: from no file; refusals for a broken log, a naive --at, bad bodies and a blank claim; a last line
    without a newline; a lock I hold (exit 4); 8 concurrent appenders x 20.
  - E04 recovery: a byte-equal prefix in a new file that verifies and accepts an append; refusals for --out as the
    log, an existing file, a path alias of the log and a missing folder; an anchored rewrite keeps nothing; a torn
    tail recovers 9 of 10.
  - C07 claims: across every output of the run there is no positive legal-validity, compliance, certification,
    verified-signature or verified-identity wording; "authenticated" only ever appears negated; and the changed docs
    never say signatures or attestations are verified here.
  - S08 side effects: no process, network or mail event; no such imports; the candidate tree is byte-identical with
    no __pycache__.
- OBS rows O05 (license and manifest edge forms) and O06 (event edge forms) are recorded, not scored.
- Controls: the builder's naive and no-op tools (see the matrix). Four interpreters; mutation tests on 3.13.15 and
  3.9.6 with the builder's 55 mutants copied unchanged; a fresh caller. All runs were on rsync copies, and the
  candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g38: Ran 13 tests in 12.854s  OK  | full: Ran 168 tests in 28.070s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38-oracle: M38 ORACLE 7/11 core FAIL | m38-naive: M38 ORACLE 1/11 core FAIL | m38-noop: M38 ORACLE 2/11 core FAIL
== 3.11.16 | g38: Ran 13 tests in 10.986s  OK  | full: Ran 168 tests in 22.548s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38-oracle: M38 ORACLE 7/11 core FAIL | m38-naive: M38 ORACLE 1/11 core FAIL | m38-noop: M38 ORACLE 2/11 core FAIL
== 3.12.14 | g38: Ran 13 tests in 11.313s  OK  | full: Ran 168 tests in 25.146s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38-oracle: M38 ORACLE 7/11 core FAIL | m38-naive: M38 ORACLE 1/11 core FAIL | m38-noop: M38 ORACLE 2/11 core FAIL
== 3.13.15 | g38: Ran 13 tests in 11.556s  OK  | full: Ran 168 tests in 23.485s  OK  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 1/8 | builder-noop: REJECTED 1/8 | m38-oracle: M38 ORACLE 7/11 core FAIL | m38-naive: M38 ORACLE 1/11 core FAIL | m38-noop: M38 ORACLE 2/11 core FAIL
pycache in copy: 0
candidate status lines: 0
```

The M38 oracle scores 7/11 on every interpreter. The same 8 subs fail each time: P03 mit_plus_restriction (P2-1),
section_name_then_comma_read (P3-2), root_level_plugin and chief_of_staff (P3-1), out_missing_dir_exit2 (P4-1); P04
subject_only_matching (P3-3); E03 no_trailing_newline_never_merges (P2-2); E04 out_missing_dir (P4-1). The naive
control scores 1/11 and the no-op 2/11.

Mutation tests: **v2 oracle 48/55 killed on 3.13.15 and 47/55 on 3.9.6** (results/teeth-*.log). The v1 oracle
killed 36/55 on 3.13.15 (results/v1), and its survivors led to row R09. Each survivor applied to a copy and checked
with the builder's G38 tests (results/survivors-builder-tests.txt):

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

pc_g05_cache_written cannot show on this machine's system 3.9.6, which never writes bytecode
(`sys.flags.dont_write_bytecode` is 1 even under `env -i`). It is killed on 3.13.15, and the builder reports the
same limit.

Fresh caller (results/fresh-caller.txt): every line of the README "Run" block, verbatim under `env -i` with a new
HOME, on 3.9.6 and 3.13.15. Each line gave its documented exit or oracle result (0, 0, 1, 0, ACCEPTED 8/8,
REJECTED 1/8 twice), with no __pycache__ and the tree unchanged.

## Findings

Reproductions are in results/probe-findings.txt (scripts/probe_findings.sh) and in the oracle's row details.

- **P2-1: the license check reports a modified or partial license as that license.** `identify()` accepts a text
  when it contains three fingerprint phrases.
  - The MIT text with "The Software may not be used for commercial purposes without written permission." appended
    gives `consistent; LICENSE MIT`, exit 0.
  - A three-line Apache header with no terms is reported as `LICENSE Apache-2.0`. The builder's own test and oracle
    assert this (test_unrecognized_or_other_license_text, the oracle case "apache everywhere but LICENSE").
  - The doc promises "nothing is guessed", and the legal-advisor SKILL now takes "which license the LICENSE text is"
    from this tool. So a usage restriction can reach counsel as "MIT, consistent".
  - MIT-0 is correctly not called MIT.
- **P2-2: append can turn a verifying log into a broken one and lose a verified event.** When the last event is
  complete but its newline is missing (an interrupted write that stopped just before the newline, or an editor
  that strips the final newline), verify accepts the log and append re-verifies it. Append then writes the new
  event onto the same line. The result: "5 of 6 event(s) verified ... FINDING line_not_json at line 6". The
  verified seq 5 and the new event are both lost to recovery, and later appends are refused.
- **P3-1: plugin.json files outside `employees/` are not checked.** The doc says "a `plugin.json` `license`" and the
  handback counts "61 plugin.json files", but the repository has 62. Changing `chief-of-staff/plugin.json` to
  Apache-2.0 in a copy still gives `consistent; 64 declaration(s) MIT`, exit 0. The walk only covers employees/.
- **P3-2: a README License section whose license name is followed by a comma is silently not read.** "## License"
  followed by "GPL, see LICENSE." gives `consistent; 3 declaration(s)`, exit 0, with no finding and no note that
  the section was skipped. The regex allows only letters, digits, ".", "-" and spaces before a "." or newline.
  (Prose such as "This project is licensed under the Apache License 2.0." is caught.)
- **P3-3: integrity.subject includes digests of files that do not match the manifest.** The doc says "the matching
  digests are returned as `integrity.subject`". A changed `src/app.py` is reported as digest_mismatch, yet its
  current digest is in the subject that receipts are meant to be checked against. A caller that binds the subject
  without reading the findings binds the changed bytes.
- **P4-1: --out into a missing folder gives a Python traceback and exit 1** for both `check` and `recover`.
  Nothing is written. Exit 1 is documented as "findings" or "nothing to keep", so the code is misleading.
- **P4-2: NOTICE coverage only counts backticked, upper-case names.** A lowercase `lib/license.txt` is walked as a
  license file but can never be listed: naming it in NOTICE in backticks still reports it. A plain-text path in
  NOTICE does not count either. The doc says only "named in NOTICE.md".
- **P4-3: canonical JSON is UTF-8 (`ensure_ascii=False`), and the doc does not say so.** A writer that follows "sorted
  keys, no spaces" with Python's default ASCII escaping gets hash_mismatch on any non-ASCII body (O06). The tool's own
  non-ASCII appends verify.
- **P4-4 (doc and edge forms):**
  - `pyproject license = { file = "LICENSE" }` is reported as license_undeclared.
  - folders in SKIP_DIRS (`node_modules`, `.venv`, `venv`, `dist`, `build`) are skipped
    silently, so their license files are never reported. The doc does not say this.
  - The README Run line for verify ends in a duplicated "# exit 0   # exit 0".
  - Append silently moves an earlier `--at` to the previous event's time (handback open question 5). The doc does
    not say so.
- OBS:
  - A claimed_by that says "(authenticated, signed)" is still reported under "claimed in plain text, not
    authenticated".
  - Bool, string and float seq are refused as fields_wrong.
  - An uppercase stored hash is a hash_mismatch.
  - An empty log is `chain_empty` (exit 1).
  - An earlier --out inside ROOT is allowed.

## Proposed fix (P2-1 and P2-2 only; not applied)

`proposed-fix.patch` (diff -ru a/b over 6 files, 137 lines, sha256 in results/fix-positive-control.txt):
- `identify()` requires the whole text. For MIT, an optional title and copyright lines, then exactly the MIT body
  (whitespace and quote style aside). For Apache-2.0, the sha256 of the normalised terms through "END OF TERMS AND
  CONDITIONS", optionally followed by the standard appendix.
- `append` writes a newline first when the verified log does not end in one.
- The builder test and oracle expectations for the three-line Apache header change to license_unrecognized. A test
  for the restricted MIT and one for the lost newline are added. Both doc tables are updated.

Positive control (results/fix-positive-control.txt and -v2.txt), on a patched copy:
- Both P2 subs pass (mit_plus_restriction_not_called_mit, no_trailing_newline_never_merges). The M38 oracle goes from
  7/11 to 8/11; the remaining fails are the P3 and P4 items above.
- G38 tests: 14 OK. Full suite: 169 OK on 3.9.6 and 3.13.15. Builder oracle: ACCEPTED 8/8; naive and no-op REJECTED
  1/8.
- The full Apache text is still Apache-2.0, and the repository and fixture LICENSE files are still MIT.
- The same patched tests on the unpatched tools fail exactly the two new assertions.

## Disclosures

- **Oracle authoring fixes after the first run** (first run kept as results/kept/oracle-first-run-3.9.6.json, 3/10;
  the pre-fix file is oracle/m38_oracle_first.py):
  - notice_path_missing is reported at NOTICE.md with the missing path in its detail; the doc does not say which
    path, so either is accepted.
  - Refusing a conflicting duplicate manifest entry with exit 2 is accepted as safe.
  - A truncated last line that still ends in a newline may be torn_tail or line_not_json (the doc pairs them). A
    no-newline torn case was added, and R09 requires torn_tail there.
  - My clean-control README first used "MIT, see LICENSE.", which the tool does not read (that is P3-2). The clean
    control now uses "MIT. See LICENSE." and the comma form is its own P03 probe.
  - The Apache-under-MIT case counts mismatching paths rather than 4 findings.
  - The repository plugin count moved from P01 to the P03 chief-of-staff probe (P3-1).
- **Oracle v1 to v2:** R09 was added after the v1 mutation run (v1 kept as oracle/m38_oracle_v1.py, results in
  results/v1).
- **Harness incident:** the v1 mutation run on 3.9.6 was still running when I wrote v2 into the same oracle path. I
  stopped it and discarded its partial results (results/v1/teeth-3.9.6-not-run.txt), then reran both versions on v2
  from scratch.
- Publish-safety edit: the no-op control crashes the oracle's E03 row (it writes no log). The four
  results/oracle-noop-*.json files had that Python traceback, with local interpreter paths, cut to its exception
  type. The scores are unchanged, and the scanner was not loosened.
- PYTHONDONTWRITEBYTECODE was exported in my shell for part of the session. The oracle sets its own environment
  (and R09 runs once without it), and the matrix, teeth and fresh caller set theirs, so no recorded result depends
  on it.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there, and its branch, index and status are unchanged.
