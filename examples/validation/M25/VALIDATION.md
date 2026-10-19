# M25: Grok self-validation of G25 (reliable device and event protocol, simulator only)

Grok self-validation. This is not independent review: the builder and the validator are the same
agent family. Use these results as input for the independent reviewer that G25 names as its final
validation dependency.

**Verdict: PASS with residuals.** The acceptance core holds on every interpreter run:
- out-of-order and duplicate messages never produce a duplicate effect claim;
- malformed data is bounded, quarantined and never echoed;
- the simulator scope is stated in every report;
- a clean control, failure cases and crash recovery all hold.

No P1 or P2 was found. Two P3 and two P4 findings remain, plus two test gaps.

## Candidate binding

- Branch `review/grok-g25-device-protocol`, head 822db7d08e044d7c17ea5b64103d69b85a21f4f3, parent
  02ba9c5 (v0.61). Fetched 19:09:55 PT.
- `raw/binding-verify.txt`:
  - The builder handback's MANIFEST.sha256 checks 17/17 at 822db7d, and its file set equals the
    02ba9c5..822db7d diff set.
  - G25.patch is not byte-identical to a plain `git diff`, but applied with `git apply --index` to 02ba9c5
    it gives tree 3e9a5493..., the 822db7d tree exactly. The difference is diff formatting only.
- The 84 original tests are untouched. The diff adds only tests/test_g25_capability.py (19 tests): 103
  in total.

## Method

- **`oracle/m25_oracle.py`:** a fresh black-box oracle.
  - Written from device-event-protocol.md before reading the builder's tests, oracle or fixtures. It
    drives `device_protocol.py ingest` and `simulate` through the CLI only, in temp dirs with a minimal
    environment.
  - Every history has a hand-derived expectation: the exact claim set, final device state and boot,
    anomaly classes and exit code.
  - 23 core checks (K01 to K23) and 17 adversarial checks (A01 to A16, plus A06b).
  - The report's JSON field names (`claims`, `devices`, `anomalies_found`, `counts`) are not specified in
    the doc. I learned them from one candidate run on a 3-line history before writing the checks.
- **Runs:**
  - Oracle on 3.9.6, 3.11.16, 3.12.14 and 3.13.15.
  - Builder suite (`python -m unittest discover -s tests`) on the same four.
  - Builder oracle (`protocol_oracle.py`) on the candidate and both builder stubs.
  - My oracle on the builder's no-op and naive stubs.
- **Fresh caller** (`oracle/m25_fresh_caller.sh`, 3.13.15 and 3.9.6):
  - Environment: env -i, a new HOME, a `python3` shim and a socket-blocking sitecustomize.
  - Commands: the doc's "## Commands", transcribed by hand, with cwd at the iot-engineer folder.
  - Pass 1 runs them verbatim. Pass 2 adds one deviation, `mkdir out`.
- **Teeth** (`oracle/make_mutants.py`, `oracle/run_teeth.sh`, 3.9.6):
  - 21 exact single-occurrence mutants of device_protocol.py, 2 of them expected-equivalent controls.
  - Plus the candidate and a no-op control.
  - Scorers: my core, tests/test_g25_capability.py, the builder oracle and the full suite.
  - Setup: a detached scratch worktree, restored and hash-checked after each mutant.

## Results

| | result |
|---|---|
| M25 core K01 to K23 | 23/23 on 3.9.6, 3.11.16, 3.12.14, 3.13.15 |
| M25 adversarial holding | 11/17 on each (identical) |
| builder suite | 103/103 OK on each |
| builder oracle | candidate 12/12, no-op 0/12, naive 1/12 (matches the handback) |
| M25 oracle on builder stubs | no-op 0/23, naive 0/23 (the naive stub also omits `devices`, so it fails on schema as well as on behaviour) |
| fresh caller, doc verbatim | all four commands exit 2 (S2) |
| fresh caller with `mkdir out` | simulate exit 0 (claims equal ground truth, 93); ingest exit 1 (anomalies from the injected faults); crash drill exit 3; resume exit 1; resumed report identical to the unbroken one (sha 8cff5789...); identical on 3.9.6 |

The core covers:
- the clean control;
- reorder inside the window;
- exact duplicates;
- re-acks at new seqs;
- reboot with re-ack;
- stale-boot replay claiming nothing;
- end-of-stream gap;
- window overflow;
- unknown and other-device commands;
- wrong-state and rejected acks;
- unexplained transitions;
- 12 kinds of malformed line (with a marker never echoed);
- invalid command logs;
- a 4-device interleaved history with reboots, exact, also fully duplicated and swapped;
- crash and resume equality;
- refusal of changed events or commands;
- lost acks;
- simulate on three seeds with heavy faults;
- the text scope line.

Adversarial checks that held:
- integral-float seq;
- the 2^31 and 2^53 bounds;
- the 10001st device;
- a lost ack recovered by a reboot re-ack;
- a reused seq;
- a ~45k-line stream in 1.7 s;
- a stale-boot done ack;
- the 200-entry list cap with an exact count;
- a late re-ack;
- CRLF;
- an infinite `flow_lpm`.

## Findings

### P3

**S1. The checkpoint body is trusted without any integrity or structure check.** (A06, A06b, A14)

`--state` refuses a checkpoint whose schema, command-log hash or events-prefix hash differs. The
controller state inside it (`claims`, `devices`, `counts`, `anomalies`) is loaded as-is, though.
- A06b: deleting the 22 claims from a valid checkpoint taken at line 70 makes the resume exit 0. It
  reports 38 effects claimed instead of 60, and nothing says the claims went missing.
- A06: editing one state value is accepted, and the report differs from the unbroken run.
- A14: `"devices": {"valve-000": 5}` crashes with `TypeError` and a traceback, exiting 1. Exit 1 is the
  documented code for "anomalies listed", so a caller cannot tell the crash from a normal run.
- Why P3: no duplicate claim results, because each device's `acked` list still blocks a re-claim, and the
  doc does not promise tamper detection. The doc does say a resume onto changed input is refused, and the
  checkpoint is the one input that is not bound.
- Suggested direction (not patched): store a sha256 of the snapshot body inside the checkpoint and check
  it on load, validate its structure, and map any load error to exit 2.

**S2. The doc's first command fails as written in a fresh folder.**
(`results/fresh-caller-3.13.15.txt`, pass 1)

- `simulate ... --record out/` exits 2 ("out is not a folder", nothing written), because `--record` needs
  an existing folder.
- The three following doc commands then exit 2 too, with no commands file.
- With `mkdir out` first, everything works.
- Suggested direction: create the folder, or add `mkdir -p out` to the doc.

### P4

**S3. The reorder window holds 31 records, not 32.** (A13)

- The check is `s - next < WINDOW` (32). With a hole at `next`, only seqs next+1..next+31 can wait.
- With 32 records waiting, a gap is declared even though the late record would have closed the hole.
- The doc says "Records ahead of the next expected number wait in a buffer of 32".
- This fails closed: an extra gap, no false claim.
- Either the doc or the comparison should change.

**S4. A trailing newline passes the documented id patterns.** (A15, A16)

- `DEVICE_RE.match` and `CMD_RE.match` use `$`, which in Python also matches before a final newline.
- A record from device `"v1\n"` is accepted as a second device beside `"v1"`.
- A command log entry `"c-1\n"` is accepted, where the doc's pattern makes it invalid (exit 2).
- No false claim was found: an ack from `"v1\n"` for `v1`'s command is `unknown_command`.
- Suggested direction: `fullmatch`.

### Test gaps (P4)

Teeth results, from `results/teeth-3.9.6.tsv`. There are 19 non-equivalent mutants, and both equivalent
controls survive everywhere, as expected.

| scorer | killed |
|---|---|
| M25 core | 15/19 |
| builder tests/test_g25_capability.py | 17/19 |
| builder oracle | 14/19 |
| union | 17/19 |

- **Survivors of every scorer** (`results/survivors-distinguish.txt`):
  - `acked_only_claimed`: dedupe through `claimed` only. A done ack that follows a rejected ack of the
    same command is then claimed, where the candidate claims nothing. This is non-equivalent.
  - `window_le`: the window comparison is `<=`, so 32 records ahead fit (the doc's reading). This is
    non-equivalent. S3 shows the boundary is not pinned anywhere.
- **Gaps in my core:**
  - `rejected_claims`: K13's rejected ack carries the closed state, so it also fails the target check.
  - `max_devices_off`: covered only by adversarial A03.

  The builder tests kill both.

## Harness disclosures

- **Two core checks were corrected after the first run** (`raw/m25_oracle-v1-as-first-run.py`,
  `raw/cand-v1-3.9.6.txt`):
  - K08 first required 32 records ahead to fit. The doc is ambiguous at that boundary, so K08 now uses 31,
    which fits under either reading, and the 32 case became adversarial A13 (S3).
  - K22 first passed a `--record` folder that did not exist. It now creates the folder. That harness error
    surfaced S2.
- A06b, A14, A15 and A16 were added after reading the checkpoint and pattern code, so they are
  source-informed rather than doc-only.
- week-grok, read-only (`raw/weekgrok-before.txt` 19:14:59 PT, `raw/weekgrok-after.txt` 19:26:10 PT):
  branch, HEAD 02ba9c5, the index hash and the status hash are identical.

## Not done

- Python 3.10, which CI lists, is not installed here. Linux and Windows were not run (macOS arm64 only).
- No hardware, serial or radio test, consistent with the simulator-only scope.
- Teeth ran on 3.9.6 only.
- No proposed-fix patch: there is no P1 or P2.
