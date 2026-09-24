# Job-two improvement (named-heading protocol)

Transferable method: force this employee's `evidence.required_artifacts` into the deliverable as named markdown headings so a revision covers more of the contract than job one. Not a project copy.

## Named heading table

Each required artifact MUST appear under this exact heading (or the literal line). Distinctive tokens must survive `scripts/artifact_contract_coverage.py` `tokens_of` / `_present`.

| required_artifact | Deliverable MUST use |
|---|---|
| typed deliverable | `## Typed deliverable` |
| claim_ledger or explicit none-declared | `## Claim ledger or explicit none-declared` |
| approval_preview when external action proposed | `## Approval preview when external action proposed` |
| Gate: passed line | literal line `Gate: passed` (not a heading) |
| provenance_ledger | `## Provenance ledger` |
| partial_or_blocked_note | `## Partial or blocked note` |

If no claims exist, the claim-ledger heading still ships with an explicit none-declared line. If no external action is proposed, the approval-preview heading still ships stating none proposed.

`Gate: passed` only when SELF-QA is honestly all yes.

## Job-one vs job-two protocol

1. After scoped feedback (or any prior job), list each required artifact as present or absent on job one. Present means the named heading (or Gate line) exists in the prior deliverable, not that related prose exists under another title.
2. Job two MUST add every missing item as that named heading. Fill it with the real typed plan / ledger / preview, or with an honest none-declared / PARTIAL reason.
3. Never claim improvement unless the new heading exists in the job-two deliverable.
4. Keep headings job one already had; do not drop them to make room.

## Fail-closed

If a required artifact cannot be produced (missing footage, missing licensed tool, denied permission), emit `PARTIAL` or `BLOCKED` under `## Partial or blocked note`. Do not invent renders, Resolve grades, or tool output.

## Safety

- No autonomous publish, paid promotion, or spend.
- No unlicensed fonts, stock, or audio presented as cleared.
- No voice-clone use without a documented consent record.

## Recovery

One bounded retry. Preserve partial drafts. Do not retry send/spend/publish. If still blocked, escalate to the project owner or department lead (legal-advisor for counsel questions), as named in `capability.contract.json`.
