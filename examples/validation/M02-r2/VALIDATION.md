# M02 r2: Grok self-validation of G02 r2 (bbe682b)

**Grok self-validation, not independent review.** The validator is the same bot (Backend Developer) that built G02. Written by Grok Bot on 2026-10-19, 01:11 to 01:35 PT. The candidate was not modified. Root records acceptance. Muse's relayed ACCEPT of bbe682b (grok-output/G02/MUSE-REVIEW-direct-r2.md) is prior reviewer evidence only; this pass does not rely on it.

## Verdict: PASS with residuals (no P1, no P2)
All eight M02 r1 findings (F1 to F8, found against 41132041) are fixed at bbe682b, each confirmed by fresh probes that differ from the M02 r1 repro script. The same probes fail on the pre-fix commit 41132041 (positive control). One P3 and four P4 residuals remain. The P3 is a set of unseen inputs that still end in an uncaught exception (the F4 class). It exists unchanged in 41132041 too, so it is not a regression; my M02 r1 pass missed it. Nothing is written in those cases. No acceptance item in M02.md fails.

My oracle grades the candidate 14/15 on all four interpreters. The only FAIL is C06, and that FAIL is the P3 below. I am reporting the strict oracle result as it came out, not adjusting it.

## Binding (raw/binding-verify.txt)
- Candidate bbe682b28e96296723826c1f113e138ccc39c530. It is the remote head of review/grok-g02-activation, so it has not been superseded. Its only parent is 41132041afeb2cce63a68554caf18cf6992a11ae (G02 r1, validated by M02 r1). The author is the noreply address.
- `git diff 41132041 bbe682b` has sha256 62614bb3..., which is byte-identical to grok-output/G02/G02-r2.patch (`DIFF_EQUALS_G02_R2_PATCH`). It changes 5 files, +331/-24.
- All 11 entries in grok-output/G02/MANIFEST.sha256 (sha256 1c6a4fe6...) match at bbe682b (OK x11). The manifest file set equals `git diff --name-only 02ba9c5 bbe682b`.
- main is still 02ba9c571b10ad1dba792d2ac5534bcad3171e67.

## F1 to F8 re-check (fresh probes; positive control 41132041 in results/control-r1-41132041-3.12.14.txt)
| Finding | bbe682b | 41132041 | Fresh evidence |
|---|---|---|---|
| F1 (P2) copied folder or journal inherits a live deploy model | FIXED | fails C04 | C04 covers five cases: a copied folder run twice (UNRESOLVED and not complete both times, no inherited credentials), the human report, resume in a copy (blocked, tree unchanged), a journal-only copy, and a journal with no project_root. Same-folder carry-over control: the report says "carried over". Operational: 30 parallel template copies, 0 leaks. Fresh caller step 1 |
| F2 (P3) invisible-only deploy answer | FIXED | fails C05 | ZW, BOM, WJ, MVS, soft hyphen, ideographic space + ZWJ, mixed: UNRESOLVED; invisible-only name refused |
| F3 (P3) literal UNRESOLVED | FIXED | fails C05 | `UNRESOLVED`, `unresolved`, `Unresolved, ask owner`, padded, `UNRESOLVED: main=live`: not complete. Controls: an answer mentioning "unresolved" mid-text is recorded verbatim and is complete |
| F4 (P3) tracebacks | FIXED for the four reported shapes; see P3-1 | fails C06 (17 unbounded) | files list, pending list, read-only root and 300-byte component are all bounded. Also bounded: project_root int, files null, intake list, top-level list, non-UTF-8 bytes, empty file, NUL bytes, garbage or non-UTF-8 lock, root over 900 bytes |
| F5 (P4) temp litter after SIGKILL | FIXED | fails C07 | SIGKILL before os.replace 1..9 in a changed intake: after the documented recovery, 0 temp files, docs consistent, second resume stable. Decoys are kept: a temp name in Development/, a non-hex name, the wrong folder, a non-target name, a temp-named dir, and a temp-named symlink to outside. Operational: 0 temps after recovery in 230 random-kill iterations |
| F6 (P4) empty lock not stale | FIXED | fails C08 | Empty lock and dead-pid lock are reported stale. A live holder is not called stale. pid 0, -1 and `true` never signal anyone (the sleeper survives) |
| F7 (P4) marker in name | FIXED | fails C09 | Marker refused in name, brief (`deploy_model:`, `Deploy-Model :`) and credential username/location (rc 2, nothing written). The first `DEPLOY-MODEL:` in STATUS is the anchored line for a parent folder named `DEPLOY-MODEL: main=live`, a bidi name and a fullwidth-colon name |
| F8 (P4) commit id refused | FIXED | fails C10 | `fork of`, `commit`, `sha` (64 hex), `rev:` (upper case) and `revision #` are accepted verbatim. Bare hex, a token after `commit`, `commit <hex> token=...`, and a commit id in a credential field are refused. See P4-3 |

## Findings
Reproductions: oracle/m02r2_finding_repros.sh. Output at bbe682b is in results/finding-repros-3.12.14.txt, and at 41132041 in results/finding-repros-r1-41132041.txt.

**P3-1 (pre-existing, F4 class, unseen): three inputs still raise instead of returning a result.** Nothing is written in any of them, and the run exits 1 with a traceback and no JSON.
- a. A deeply nested journal (`[` x 200000, or nested objects) raises RecursionError, on both `activate` and `resume`. `_read_journal` catches only OSError, ValueError and UnicodeDecodeError.
- b. The same applies to a deeply nested `.solaris-activation.lock` (`_acquire_lock`).
- c. A non-UTF-8 byte in an argument, such as `--name "$(printf 'Caf\351')"` (a Latin-1 paste), gives `UnicodeEncodeError: surrogates not allowed` while rendering. The project root is not created.

Impact on the stack: G04's handoff.py imports `activate()` and calls it in process. Through the API, a lone-surrogate name in a JSON intake (`"Bad\udcffName"` is valid JSON) and a deep journal both raise out of `activate()` (results/api-probe-3.12.14.txt). The docstring says it "never raises for expected failures". This is P3 because no data is lost and no authority is granted.

Suggested direction:
- Catch RecursionError where the journal and lock are parsed, and report `blocked`.
- Refuse lone surrogates in `_check_text` with `invalid`.

**P4-1: some visually blank deploy answers still count as resolved.** U+3164 Hangul filler, U+2800 braille blank and a lone combining acute U+0301 each give `complete`, with a visually empty `DEPLOY-MODEL:` line. `_visible` only excludes the Cf, Cc and Z* categories. These characters are Lo, So and Mn. This is the narrow tail of F2.

**P4-2: UNRESOLVED behind an invisible or fullwidth character is accepted as an answer.** `\u200bUNRESOLVED` and fullwidth `ＵＮＲＥＳＯＬＶＥＤ` give `complete`, while the STATUS line reads as UNRESOLVED. This is the tail of F3. Quoted `'UNRESOLVED'` and `TBD` are also recorded as answers, which I treat as owner words (a note, not a finding).

**P4-3: `sha256 <64 hex>` in the brief is refused as a secret.** `sha256` and `sha256:` give exit 2, because `\bsha\b` does not match `sha256`. The documented `sha <64 hex>` works. This is a usability issue only.

**P4-4: a moved project folder can no longer resume.** After `mv m m2`, `resume m2` is `blocked` ("written for another folder"). Activate there works, but the deploy model and credentials must be restated. This fails closed. SKILL.md covers copies, not moves.

Notes (not defects):
- In the same folder, an omitted deploy answer is carried over even when the name changes, and the 5-line report says "carried over". This is a documented design choice. The M02 r1 suggestion not to inherit across a name change was not taken.
- An `invalid` report still prints `Deploy model: UNRESOLVED` for a project that has a recorded answer. This is cosmetic and carried over from M02 r1.
- G04 accepts `partial` as a successful activation step, so a copied-journal project (now `partial`, UNRESOLVED) passes G04's activate step. This is G04's choice and M04's scope. Nothing deploys.

## Oracle (mine, written fresh for r2: oracle/m02r2_oracle.py, sha256 532b9cf9f15514cf)
The oracle is black box: it uses only the CLI from SKILL.md. Nothing from the candidate is imported, and no check can SKIP. A candidate that creates no files is ENTRY_ABSENT, which counts as a FAIL. The injector, oracle/inject/sitecustomize.py, is new: it SIGKILLs the process before the Nth os.replace.

Checks:
- C01 clean run twice plus resume, byte-identical
- C02 owner docs
- C03 Git (existing repo x3, unborn staged)
- C04 to C10: F1 to F8
- C11 escapes
- C12 EACCES failure and resume
- C13 concurrency: 5 rounds x 16 racers on one root, plus 40 parallel projects
- C14 scale: 4000 owner files
- C15 secrets

| Implementation | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| candidate bbe682b | 14/15 (C06 = P3-1) | 14/15 | 14/15 | 14/15 |
| no-op stub (prints a fake complete) | | | **0/15 REJECTS** | |
| echo stub (echoes intake as complete) | | | **0/15 REJECTS** | |
| pre-fix r1 41132041 | | | 8/15 REJECTS (fails exactly C04 to C10) | |

- Rejected evidence I kept, in results/rejected-oracle-v1/ and results/oracle-run1-3.12.txt:
  - The first oracle let the no-op and echo stubs pass C14 (1/15), because C14 did not check that any files were produced. I added the ENTRY_ABSENT check, and both stubs now score 0/15.
  - The first C06 stopped at the first failure. It now collects every failure.
  - The first C10 used an all-letter 64-hex, which proved nothing. It now uses a real sha256.
- Before publishing, I edited test literals so the published files hold no token-shaped or e-mail literals: the AKIA key is now built by concatenation, the Git test e-mail is `o@localhost`, the fresh caller's token is built at run time and redacted in logs, and the runner takes PY312 from the environment. I then re-ran the oracle on four interpreters plus the controls, the fresh caller and the teeth with that final oracle (sha256 532b9cf9...), and the results were unchanged. Earlier oracle versions: 5bc97dcd (results/oracle-run1-3.12.txt), 6bc8844e (results/rejected-oracle-v1/), and fdc8f401 (the pre-edit final, superseded by this re-run).

## Teeth (results/teeth/, results/teeth-tally.txt, 3.12.14)
I wrote 15 mutants of the bbe682b activate.py (oracle/make_mutants_r2v.py), each targeting one r2 fix or a core guard:
- bind_off, inherit_on_foreign, foreign_resume_allowed
- visible_is_strip, unresolved_off
- journal_entry_types_off, lock_oserror_uncaught, path_length_off
- temps_not_removed, temps_greedy
- empty_lock_not_stale
- marker_allowed
- commit_ids_everywhere, bare_hex_allowed
- no_lock

The candidate already fails C06, so a kill means a new failing check, or more C06 unbounded cases than the candidate's 6. On that rule, **my oracle kills 15/15**, and **the builder's G02 tests also kill 15/15**. The unmutated builder G02 tests pass (47 OK).

## Operational depth (oracle/m02r2_operational.py)
- 3.12.14, 150 iterations: Alpha completes, then Beta is SIGKILLed at a random 15 to 60 ms. 24 were killed mid-run, 6 stale locks were deleted per the message, and 3 had mixed docs and 3 had temp files right after the kill. All 150 recovered to `complete` and consistent, with 0 temps, 0 locks and the owner file kept, and a second resume was byte-identical. 144 converged on Beta and 6 on Alpha (killed before Beta's intent was journaled). There were 0 tracebacks.
- 3.9.6, 80 iterations: 58 killed mid-run, 0 bad.
- On both interpreters, 12 activate-vs-resume races left 0 inconsistent docs, locks or temps, and 30 parallel copies of a live template had 0 live-deploy leaks.

## Fresh-caller transfer (oracle/m02r2_fresh_caller.sh, results/fresh-caller-3.12.14.txt and -3.9.6.txt, identical)
This ran under `env -i` with an empty temp HOME, using only SKILL.md commands and the tool's messages:
- A live client folder is copied for a new client: `partial`, UNRESOLVED, and the gap names the other folder.
- The owner states the deploy model: `complete`.
- A killed-run lock and temp: the message says stale, and after deleting the lock, resume completes with 0 temps.
- A commit id in the brief is accepted, and a pasted token is refused (rc 2).

## Suites (results/full-suite-*.txt, results/downstream-g04-g05-3.12.14.txt)
- Full suite at bbe682b (`python -m unittest discover -s tests`): 131 OK on 3.12.14, 3.9.6, 3.11.16 and 3.13.15. The G02 module is 47 OK on all four.
- Downstream G05 8b38a72 (ancestry 8b38a72, 314b4db, bbe682b): 155 OK on 3.12.14. activate.py is identical to bbe682b, and no project-onboarding, G02 or test_g02 file changed after bbe682b. G04 handoff.py calls activate() in process (see P3-1 impact).

## Commands (all on Shais.local, from a detached temp worktree)
```
git worktree add --detach /tmp/m02r2-eval bbe682b...; git worktree add --detach /tmp/m02r2-r1 41132041...; git worktree add --detach /tmp/m02r2-g05 8b38a72...
zsh oracle/run_oracle_r2.sh <O> /tmp/m02r2-eval /tmp/m02r2-r1          # 4 interpreters + no-op, echo, r1 controls
zsh oracle/run_teeth_r2.sh <O> <PY312> /tmp/m02r2-mutants /tmp/m02r2-eval; python3 oracle/tally_teeth_r2.py results
python oracle/m02r2_operational.py 150 -- <PY312> employees/product-project/project-onboarding/activate.py   (80 on 3.9.6)
sh oracle/m02r2_fresh_caller.sh <PY>; sh oracle/m02r2_finding_repros.sh <PY312>; python oracle/m02r2_api_probe.py <activate.py>
<PY> -m unittest discover -s tests            # 4 interpreters at bbe682b; 3.12.14 at 8b38a72
```

## Hygiene
- The week-grok before and after records are identical: branch programme/grok-week-20261018, HEAD 02ba9c5, index c28a2f58..., status listing ab0ce788... with 95 lines (raw/weekgrok-before.txt, raw/weekgrok-after.txt).
- The shared .git only gained fetched objects and temporary worktree metadata, which was removed (raw/cleanup.txt).
- The three temp worktrees had 0 dirty entries and no pycache, and were removed. /tmp/g07, /tmp/g05, the other ID folders and WORK-QUEUE.json were not touched.
- No installs. There were no network calls beyond git fetch/ls-remote and GitHub API reads.

## Not done / limits
- This is self-validation by the same bot, so it is not independent.
- Everything ran on macOS only.
- Teeth, the operational run at 150 iterations, and the API probe ran on 3.12.14 only.
- Random-kill timing is probabilistic. The deterministic injector covers 9 os.replace points.
- I wrote no fix for P3-1 or the P4s.
