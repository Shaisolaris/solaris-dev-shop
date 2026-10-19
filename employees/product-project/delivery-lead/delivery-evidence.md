# Delivery evidence across specialists (delivery_evidence.py)

The delivery lead orchestrates; specialists do the work with their own tools. This reference says how a
delivery claim is backed by evidence that the work actually ran, and when a claim stops counting.

## Record each specialist run

```bash
T=employees/product-project/delivery-lead/delivery_evidence.py
python3 $T record ROOT --role data/data-engineer --worker ana --outputs reports/metrics.json \
  -- python3 employees/data/data-engineer/csv_reconcile.py reconcile data/contract.json --out reports/metrics.json
```

`record` runs the specialist command once in ROOT and appends, after it finishes, one line to
`ROOT/.delivery/contributions.jsonl`: role, worker (a plain-text claim), command, exit code, sha256 of every
`.py` tool in the command and of every output (G05 `artifact_digests`), and the log digest. Each line carries
the sha256 of the line before it. `--ok-exit` lists the exit codes the caller accepts (default 0): a data
reconciliation that exits 1 for disclosed gaps blocks the delivery unless the caller accepts 0,1 on purpose.
The role must be an employee in this repository. Credential-shaped values in the command are refused.

## Verify the delivery claim

```json
{"schema": "solaris.delivery-claims/1", "order": "order.json",
 "contributions": [{"role": "data/data-engineer", "outputs": ["reports/metrics.json"]}]}
```

`verify ROOT --claims CLAIMS.json [--json] [--out F]` gives GO only when every claimed contribution is
`evidenced` and the G04 work order (`handoff.py status`) has every step done and exactly one delivery for its
revision. Otherwise NO_GO with the state and the action for each blocker:

| State | Meaning | Action |
|-------|---------|--------|
| evidenced | latest record ok; outputs and tool scripts hash as recorded | none |
| unevidenced | no record for the role, or the ledger chain is broken | run it through `record` |
| failed | the command exited outside `--ok-exit`, timed out, or its outputs were unreadable | fix and re-run |
| not_covered | a claimed output is not in the record | re-run naming it in `--outputs` |
| stale | an output or a recorded tool script changed after the run | re-run the named command |

## Interruption and resume

A recorder killed before its command finishes appends nothing, so the step is simply run again by any
worker. A cut-short final line is ignored and dropped on the next append. `.delivery/head.json` holds the sha256 of the last record
(it may lag by one record when an append was cut short after the line was written). An edited, reordered,
removed or replaced record, the last one included, breaks the chain: verify refuses every record and `record` refuses to append (exit 3) until a
person restores the ledger. The work order itself resumes through G04 `handoff.py run`.

## Limits

Records show that a command ran in this folder with that exit code and produced these bytes. They do not
show that the output is correct beyond the specialist tool's own checks, and they authenticate nobody.
The chain and head show self-consistency only: someone who rewrites every record and the head is not caught.
Locks are local `fcntl` locks: one machine, no network folder.
