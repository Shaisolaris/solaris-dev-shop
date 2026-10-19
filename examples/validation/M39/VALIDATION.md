# M39 validation of G39 cross-employee delivery and recovery drill (Grok self-validation, not independent review)

Candidate: G39 `f04d34dbf41364b6dcdb03104a647c2e499bccac` (branch review/grok-g39-delivery-drill), one commit on the
integration base `fabed6adf227e936dcd5690b26697e0fadf667d1`. Tool
`employees/product-project/delivery-lead/delivery_evidence.py`, doc `delivery-evidence.md`, drill
`examples/capabilities/G39`. Validator: Grok, the same agent family that built G39. This is self-validation, not
independent review. Pass started 09:38 PT, Mon Oct 19 2026.

## Verdict

**FAIL (self-validation): two P2 findings, three P3, two P4 and OBS notes.** A proposed fix for both P2s is in
`proposed-fix.patch`. It is positive-controlled and was not applied.

The drill itself works: crashes at several points recover safely, edits to the head and tail of the ledger are
caught, duplicate deliveries are suppressed, and eight concurrent recorders keep one intact chain. The FAIL comes
from the part the M39 goal names first: "change one upstream artifact after review and test that downstream
readiness responds honestly". An upstream input change after review still gives GO.

## Prerequisite chain

- G39's only parent is fabed6a. The diff sha equals the patch file and the handback (`c79cf299...56b1bd2`). The
  manifest has 17/17 entries, 0 mismatches, and its set equals the diff set (raw/binding-verify.txt).
- fabed6a is built the way the handback says. Its first-parent line is G05 8b38a72, then three no-ff merges with
  second parents G03 r3 d4d98f2 (2369b1a), G13 r3 5666e7b (804f3a3) and G19 5606672 (fabed6a). I recomputed each merge
  with `git merge-tree --write-tree`, and all three trees equal the committed trees, so no merge carries a hand edit.
  G05 stacks G04 314b4db and G02 r2 bbe682b.
- The remote heads of G02, G03, G04, G05, G13 and G19 still equal those commits, so nothing in the chain is
  superseded. Each has a Grok self-validation branch (M02 r2 8aee4df, M03 r3 1020f11, M04 1628e6d, M05 177a42f, M13 r3
  db6028e, M19 f2e52da), none is independently accepted, and the handback says so.
- pilot/integrate-capabilities (b61a201) is not the base and was not used.

## Method

- Oracle `oracle/m39_oracle.py`, written from M39.md, G39.md and delivery-evidence.md before reading the builder's
  drill_oracle.py. It builds its own delivery folders: a G04 work order from the G39 fixture, a G13 reconciliation, a G03
  snapshot of a SQLite folder it creates and a ROOT-local script. It drives the real CLIs, reads the ledger and files
  itself, and recomputes every sha256. Rows D01-D09 are scored; O09 is OBS.
  - D01 clean control: GO, true output, tool and log digests, real exits, chain and head, one delivery.
  - D02 crashes at other points: G04 crash after activate and after brief, then a resume by another worker; a recorder
    SIGKILLed mid-command; a crash between the line write and the head write (head one behind, then repaired by the
    next append); a cut-short last line (ignored, then dropped); a stray head temp file.
  - D03 stale and forged records: a later failed run supersedes an earlier ok one; an edited output (stale, naming the
    file and the command); a changed or removed ROOT tool; a file added to or removed from an output folder; a record
    copied in from another delivery.
  - D04 log head and tail: edited, re-serialised, removed, reordered or duplicated records (first and last); a seq gap
    with the chain and head rewritten to match; a complete last line without a newline (with the head current and
    one behind); a removed, unreadable, ahead or two-behind head. Each must give NO_GO with every contribution
    unevidenced and make record refuse with exit 3 before it runs anything.
  - D05 duplicate-delivery suppression: a crash after delivery resumed twice by other workers leaves one delivery and
    GO; a duplicated delivery line is NO_GO; a new revision is NO_GO until it is delivered once.
  - D06 default exits: a dirty month (exit 1), invalid input (exit 2) and exit 0 without the named output all block.
  - D07 upstream input changed after review: a source CSV row added, the data contract's timezone changed.
  - D08 fresh-caller input errors: unknown and non-canonical roles (`..`, upper case, `//`), a credential-shaped
    argument, outputs inside .delivery, outside ROOT or absolute, a role claimed twice, an order outside ROOT, a missing
    claims file. Also: no bytecode in the repo without PYTHONDONTWRITEBYTECODE, and `--out` writes only that file.
  - D09 concurrency and timeouts: eight concurrent recorders; `--no-wait` with the lock held (exit 4, nothing
    appended); a timeout kills and records not ok; out-of-range timeouts.
  - O09 (OBS): accepted non-zero exits, claims without an order, intake changed after delivery, a forged single
    append, a failed record removed with the head rewritten, a deleted ledger, an output restored byte for byte, the
    database changed after its snapshot, and a full consistent rewrite.
- The 3.12 one-off failure: 8 full-suite runs on 3.12.14, 4 at a time in separate rsync copies while other mutant and
  oracle runs loaded the machine (scripts/flake312.sh, results/flake/), plus a minimal reproduction of the suspected
  cause (scripts/zombie_killpg_repro.py).
- Four interpreters; mutation tests on 3.13.15 and 3.9.6 with the builder's 40 mutants copied unchanged; a fresh
  caller of the README "Run it" block. All runs were on rsync copies or the detached eval worktree, and the
  candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt, full suite logs in results/full-suite-*.txt):

```
== 3.9.6 | g39: Ran 30 tests in 14.356s  OK  | full: Ran 289 tests in 151.242s  OK   | drill: DRILL PASSED | builder-oracle: ACCEPTED 14/14 | builder-naive: REJECTED 9/14 | builder-noop: REJECTED 0/14 | m39-oracle: M39 ORACLE 7/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
== 3.11.16 | g39: Ran 30 tests in 11.212s  OK  | full: Ran 289 tests in 122.682s  OK   | drill: DRILL PASSED | builder-oracle: ACCEPTED 14/14 | builder-naive: REJECTED 9/14 | builder-noop: REJECTED 0/14 | m39-oracle: M39 ORACLE 7/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
== 3.12.14 | g39: Ran 30 tests in 8.781s  OK  | full: Ran 289 tests in 114.042s  OK   | drill: DRILL PASSED | builder-oracle: ACCEPTED 14/14 | builder-naive: REJECTED 9/14 | builder-noop: REJECTED 0/14 | m39-oracle: M39 ORACLE 7/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
== 3.13.15 | g39: Ran 30 tests in 8.932s  OK  | full: Ran 289 tests in 116.185s  OK   | drill: DRILL PASSED | builder-oracle: ACCEPTED 14/14 | builder-naive: REJECTED 9/14 | builder-noop: REJECTED 0/14 | m39-oracle: M39 ORACLE 7/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
pycache in copy: 0
candidate status lines: 0
```

The oracle scores 7/9 scored rows on every interpreter (O09 is OBS and not counted). The full suite (289) passed on
all four interpreters in this matrix run, including 3.12.14. D03 fails one sub (P2-2) and D07 fails
both subs (P2-1). Every other sub passes. The builder's naive tool scores 4/9 and its no-op tool 0/10 (the no-op run adds a crash row).

Mutation tests (results/teeth-*.log): **39/40 killed on 3.13.15 and 38/40 on 3.9.6** with oracle v3 (v2 killed
25/40 on 3.13.15, see Disclosures). Survivors, each checked with the builder's G39 tests:

- teeth-3.13.15.log: broken_chain_trusted SURVIVED
- teeth-3.9.6.log: broken_chain_trusted SURVIVED
- teeth-3.9.6.log: bytecode_written SURVIVED
- builder tests: 3.13.15 broken_chain_trusted builder tests: KILL FAILED (failures=1) FAIL: test_broken_ledger_refuses_before_running_the_command (tests.test_g39_capability.Direct.test_broken_ledger_refuses_before_running_the_command)
- builder tests: 3.9.6 bytecode_written builder tests: KILL FAILED (failures=1) FAIL: test_engine_load_leaves_no_bytecode (tests.test_g39_capability.Direct)
- builder tests: 3.9.6 broken_chain_trusted builder tests: KILL FAILED (failures=1) FAIL: test_broken_ledger_refuses_before_running_the_command (tests.test_g39_capability.Direct)

- broken_chain_trusted only changes the action wording on a broken ledger. The contributions are already
  unevidenced, because a broken ledger yields no records, and my oracle checks states, not wording. The builder's
  test_broken_ledger_refuses_before_running_the_command kills it.
- bytecode_written survives on 3.9.6 only, because the Apple 3.9.6 never writes bytecode. My oracle kills it on
  3.13.15, and the builder's test_engine_load_leaves_no_bytecode kills it on 3.9.6.

Fresh caller (results/fresh-caller.txt): every line of the README "Run it" block, verbatim under `env -i` with a new
HOME, on 3.9.6 and 3.13.15. Each line gives its documented result (DRILL PASSED, ACCEPTED 14/14, REJECTED 9/14, REJECTED 0/14).
No __pycache__ was written and the tree is unchanged. The 3.9 HOME entry is the Apple interpreter's own cache folder.

## Findings

- **P2-1: upstream inputs are not bound, so a changed input after review still gives GO.** A record digests its
  outputs and the `.py` files in its command, and nothing it reads. Shown in oracle D07 and, on the builder's own
  drill folder, in results/probe-findings.txt (scripts/probe_findings.sh).
  - After a clean GO, I appended a 5000.00 USD order to `data/orders.csv`. verify stays GO with data-engineer
    evidenced. Re-running the same reconciliation now exits 1 (control MISMATCH) with a different report.
  - Changing the contract's timezone (America/Los_Angeles to UTC), which is named in the command itself, also stays GO.
  - This is the M39 acceptance case ("change one upstream artifact after review and test that downstream readiness
    responds honestly"). The G39 drill only edits the output report, which is caught.
  - Proposed fix (part 1): record digests every existing file named in the command that is not an output or a tool,
    plus `--inputs PATH...` for files a tool reads indirectly (the CSVs named inside a contract). verify marks the
    contribution stale with `inputs_changed` when any of them differs. The drill and doc would need `--inputs data`.
- **P2-2: a file removed from a claimed output folder goes unnoticed.** The database administrator's output is
  `snapshots/s1` (ledger.db and manifest.json). After I delete `snapshots/s1/ledger.db`, verify is GO with the
  contribution evidenced. `_contribution` compares only the files that exist now (`{p: recorded[p] for p in current}`),
  so a recorded file that disappeared is never compared. An added file is caught (not_covered).
  Shown in oracle D03 and on the builder's drill folder in results/probe-findings.txt.
  - Proposed fix (part 2): any recorded file under a claimed path that is missing now makes the contribution stale with
    `removed`.
- **P3-1: accepted non-zero exits count toward GO silently (handback question 1).** With `--ok-exit 0,1`, a
  reconciliation with disclosed gaps is GO and "evidenced", and the text verdict does not mention exit 1. `--ok-exit`
  takes any integers: with `0,1,2`, an invalid-input run (exit 2, no report written for this run) is GO. My answer to
  question 1: an exit-1 reconciliation should not count toward a plain GO. The acceptance is chosen by whoever
  records, not by the person reading the verdict. I suggest:
  - a separate state (for example `evidenced_with_gaps`) that gives GO only when the claim itself lists the accepted
    exit for that role;
  - the exit shown in the text verdict;
  - `--ok-exit` limited to 0 and 1, since exit 2 means invalid input for these tools.
- **P3-2: a single forged record passes without touching the head, and the log is never checked (handback question
  2).** Because the head may lag by one record, appending one hand-written record with the right `prev` and `seq` (no
  command run, `argv` ["true"], a log file that does not exist, log_sha256 all zeros) gives GO for a new claimed
  role. The doc's limit says someone who rewrites every record and the head is not caught, but this case needs
  neither. verify could:
  - check that the log exists and matches log_sha256;
  - report a lagging head, and give NO_GO for a claim whose only evidence is the unconfirmed last record, until the
    next append confirms it.
  The lag tolerance itself is needed (D02 shows a crash between the two writes recovers), so I would keep it but stop
  it from vouching for that record.
- **P3-3: GO without a work order.** The doc says GO needs the G04 order to have every step done with exactly one
  delivery. A claims file without `order` gives GO with no work-order check, even with the outbox removed. Also, after
  delivery the intake can change (the order still names its old sha256) and verify stays GO: G04 `status` does not
  re-hash inputs (G04 `run` does). Requiring `order` (or stating that its absence is not a delivery GO) and checking
  the order's input hashes in verify would close both.
- **P4-1: the open 3.12 one-off failure is named and root-caused, and it is inherited G19 test code.**
  - Reproduced 3 times in 8 loaded full-suite runs on 3.12.14 (results/flake/py312-r1-1, r2-3, r2-4).
  - The failing test every time is
    `test_g19_capability.ProbeAndOracle.test_oracle_accepts_real_api_and_rejects_stubs`. Its G19 boundary oracle check
    o8 (crash after commit, then restart) reports "oracle saw PermissionError: [Errno 1] Operation not permitted".
  - Cause: `Server.stop()` in `examples/capabilities/G19/boundary_oracle.py` checks `poll()`, then calls
    `os.killpg(pid, SIGTERM)`. In o8 the server exits by design (crash_after_commit). If it exits between the two calls
    and is not yet reaped, macOS returns EPERM for killpg on that group. `stop()` catches only ProcessLookupError and
    TimeoutExpired.
  - scripts/zombie_killpg_repro.py shows this directly: killpg on an exited, unreaped session leader raised
    PermissionError 20/20 on 3.9.6 and 3.12.14 (results/flake/zombie-killpg-repro.txt). It explains the M22 P4-1 flake
    on 3.9.6 as well.
  - Not a G39 or product defect. Catching PermissionError there, or reaping before signalling, would fix the test.
- **P4-2: deleting the ledger file is a silent fresh start.** With `contributions.jsonl` removed and `head.json` kept,
  verify is NO_GO (good), but the next record starts again from genesis and overwrites the head with no warning. The
  history of failed runs is gone. A head with no ledger could be treated as a broken ledger.
- OBS:
  - Removing a failed latest record and rewriting the head to match makes the earlier ok record count again. A full
    consistent rewrite is also GO. Both are inside the doc's stated limit.
  - An output restored byte for byte is GO again (correct).
  - The database changing after its snapshot stays GO. A snapshot is a point-in-time copy, so this is arguably right.
  - A complete last line without a newline, or a head two behind, blocks until a person repairs the ledger
    (documented).

## Proposed fix (not applied)

`proposed-fix.patch` changes only delivery_evidence.py:
- `--inputs`, plus inputs taken from the command, digested before the run;
- `inputs_changed` and `removed` stale states in verify.

Positive control on an rsync copy with the patch applied:
- my oracle 9/9 scored rows (results/fix-positive-control-oracle-3.9.6.log; the oracle passes `--inputs data` only when
  the tool offers it);
- the builder's drill DRILL PASSED, drill_oracle ACCEPTED 14/14, tests.test_g39_capability 30 OK on 3.13.15
  (results/fix-positive-control-builder.txt).

The patch does not address the P3s.

## Disclosures

- Oracle authoring fixes after the first run (kept as results/kept/oracle-first-run-3.9.6.json and .log):
  - D02's torn-tail case re-ran the G03 snapshot into an existing folder, which G03 refuses; it now removes the folder
    first.
  - D07 first also expected a database change after its snapshot to block. I moved that to OBS, because a snapshot is
    a point-in-time copy.
  - O09's intake observation shared a folder whose outbox an earlier observation had removed. It now uses its own
    folder (the result changed from NO_GO to GO, now reported in P3-3).
- Oracle v2 to v3 after the first teeth run (disclosed; v2 and its 3.13.15 teeth log, 25/40, are kept in
  results/kept/v2). v2 had no scored row for an edited output, a removed tool, exact not_covered, the head and seq
  rewrites, an early broken-ledger refusal, a missing output, non-canonical roles, a duplicate claim, an order outside
  ROOT, bytecode, `--out` atomicity or `--no-wait`. I added those subs from the doc, stopped the v2 3.9.6 teeth run and the
  matrix, discarded their partial results, and reran both teeth runs and the matrix on v3. No v2 result is used.
- Collision check (raw/collision-check.txt): my temp folders all use m35r2 and m39 prefixes. The builder's G38 r2 and
  G40 folders were present and untouched; /tmp/m38-peek is not mine and was left alone.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there, and its branch, index and status are unchanged.
