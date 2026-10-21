# Delivery evidence across specialists (delivery_evidence.py)

The delivery lead orchestrates; specialists do the work with their own tools. This reference says how a
delivery claim is backed by evidence that the work actually ran, and when a claim stops counting.

## Record each specialist run

```bash
T=employees/product-project/delivery-lead/delivery_evidence.py
python3 $T record ROOT --role data/data-engineer --worker ana --inputs data --outputs reports/metrics.json \
  -- python3 employees/data/data-engineer/csv_reconcile.py reconcile data/contract.json --out reports/metrics.json
```

`record` runs the specialist command once in ROOT and appends, after it finishes, one line to
`ROOT/.delivery/contributions.jsonl`: role, worker (a plain-text claim), command, exit code, sha256 of every
`.py` tool in the command, of every output (G05 `artifact_digests`) and of every input, and the log digest.
Inputs are every existing file or folder named in the command that is not an output or a `.py` tool, in any of
these spellings: a plain argument, `--flag VALUE`, `--flag=VALUE`, an absolute path inside ROOT, or a relative path
with a `..` segment that resolves inside ROOT (both stored relative, resolved as the OS does);
a symlink named in the command is refused (exit 2) like one given to `--inputs`. An existing path named in the
command that lies outside ROOT cannot be re-checked later; it is listed in the record as `unbound_inputs`, and
`verify` repeats that list with a note on the contribution, so a reader can see what was not bound. Add `--inputs PATH...` for files
and folders the tool reads without naming them (the CSVs a data contract points to). Inputs
are digested after the run; every input that changed, appeared or disappeared during the run is listed in
`inputs_changed_during_run`. One that existed before the run and was changed or removed by it is also listed in
`inputs_rewritten_during_run` and is a gap at verify (below), because the record binds only its after-run bytes,
not what the tool read (r5). A file that appeared during the run was not there to be read, and a SQLite `-shm`
file next to a bound database is an index every reader updates with no data in it, so neither is a gap (a `-wal`
or `-journal` file holds data and is). A record written before r5 has no such list; its whole
`inputs_changed_during_run` list counts. Each
line carries the sha256 of the line before it. `--ok-exit` is 0 (default) or 0,1: a data reconciliation that
exits 1 for disclosed gaps is recorded as ok but counts only as `evidenced_with_gaps` (below). Any other exit
code, such as 2 for invalid input, never counts: `verify` also re-checks each record, so a record whose exit is not
in its `ok_exit`, or whose `ok_exit` is not 0 or 0,1, is `failed` whatever its `ok` flag says (r3).
The role must be an employee in this repository. Credential-shaped values in the command are refused.

## Verify the delivery claim

```json
{"schema": "solaris.delivery-claims/1", "order": "order.json",
 "contributions": [{"role": "data/data-engineer", "outputs": ["reports/metrics.json"], "accept_gaps": false}]}
```

`verify ROOT --claims CLAIMS.json [--json] [--out F] [--strict]` gives GO only when every claimed contribution is
`evidenced` and the G04 work order (`handoff.py status`) has every step done, exactly one delivery for its
revision and its intake still matching the sha256 in the order. The other verdicts:

- GO_WITH_GAPS: as GO, but at least one contribution is `evidenced_with_gaps` and its claim says
  `"accept_gaps": true`. The text verdict names each role and its gaps (exit 1, or the input files the run
  rewrote); the JSON has `gap_details` (role to `exit_1` and/or `input_rewritten_by_run`). Never a plain GO.
- EVIDENCED_NO_ORDER: every contribution counts but the claim names no work order, so nothing about the
  delivery itself was checked. This is not a delivery GO.
- NO_GO (exit 1), with the state and the action for each blocker:

| State | Meaning | Action |
|-------|---------|--------|
| evidenced | latest record ok (exit 0); outputs, inputs, tool scripts and run log hash as recorded | none |
| evidenced_with_gaps | as evidenced, but the run exited 1 under `--ok-exit 0,1` (`exit_1`), or it rewrote an input it read (`input_rewritten_by_run`, files in `inputs_rewritten_by_run`) | counts only if the claim sets `accept_gaps`; for a rewritten input, give the tool a copy it does not change and re-run |
| unconfirmed | the latest record is the last line and head.json is one record behind it | re-run; the next append confirms |
| log_mismatch | the record's run log is missing or no longer matches its digest | re-run |
| unevidenced | no record for the role, or the ledger chain is broken | run it through `record` |
| failed | the command exited outside `--ok-exit`, timed out, or its outputs were unreadable | fix and re-run |
| not_covered | a claimed output is not in the record | re-run naming it in `--outputs` |
| stale | an output, input or recorded tool script changed (`changed`, `inputs_changed`, `tool_changed`), or a recorded output file was removed (`removed`) | re-run the named command |

By default verify exits 0 for GO, GO_WITH_GAPS and EVIDENCED_NO_ORDER and 1 for NO_GO, so a caller must read
the verdict word (or `clean_go` in the JSON), not only the exit code. A caller that gates on the exit code passes
`--strict`: 0 only for a clean GO, 1 NO_GO, 2 invalid input, 3 GO_WITH_GAPS, 4 EVIDENCED_NO_ORDER (r5). The
default is kept so existing callers and drills that read the verdict word keep working; `exit_policy` in the JSON
says which mapping was used.

## Interruption and resume

A recorder killed before its command finishes appends nothing, so the step is simply run again by any
worker. A cut-short final line is ignored and dropped on the next append. `.delivery/head.json` holds the sha256 of the last record.
It may lag by one record when an append was cut short after the line was written; that last record is then
`unconfirmed` and vouches for nothing until the next append confirms it, so a single record added by hand
without touching the head does not count. A head.json without a ledger (a deleted or emptied ledger) is a
broken ledger, not a fresh start. An edited, reordered,
removed or replaced record, the last one included, breaks the chain: verify refuses every record and `record` refuses to append (exit 3) until a
person restores the ledger. The work order itself resumes through G04 `handoff.py run`.

## Limits

Records show that a command ran in this folder with that exit code and produced these bytes. They do not
show that the output is correct beyond the specialist tool's own checks, and they authenticate nobody.
The chain and head show self-consistency only: someone who rewrites every record and the head is not caught,
and neither is someone who appends a record with a matching log file and then lets an honest append confirm it.
An input a tool reads without it being named in the command or `--inputs` is not bound. A database a snapshot
was taken from may change afterwards without making the snapshot stale.
Locks are local `fcntl` locks: one machine, no network folder.

Root correction: the conventional `-shm` exception requires a bound, unchanged companion with the SQLite file header. An ordinary file beside a `-shm` suffix is a rewritten-input gap. This is local classification, not proof of a hostile file’s purpose or actor identity.

`--inputs` and `--outputs` are repeatable: every supplied path is retained across occurrences. A file rewritten by the run remains a disclosed gap even when it was named in the first occurrence.
