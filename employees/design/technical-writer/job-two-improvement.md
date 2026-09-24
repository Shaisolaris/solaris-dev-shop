# Job-two improvement (named-heading protocol)

Transferable method: force this employee's `evidence.required_artifacts` into the deliverable as named markdown headings so a revision covers more of the contract than job one. Not a project copy.

## Named heading table

Each required artifact MUST appear under this exact heading (or the literal line). Distinctive tokens must survive `scripts/artifact_contract_coverage.py` `tokens_of` / `_present`.

| required_artifact | Deliverable MUST use |
|---|---|
| doc file paths on disk | `## Doc file paths on disk` |
| audience + last-updated present | `## Audience` and `## Last-updated present` |
| provenance or TODO gaps | `## Provenance or TODO gaps` |
| Gate: passed line | literal line `Gate: passed` (not a heading) |

`Gate: passed` only when SELF-QA is honestly all yes.

## Job-one vs job-two protocol

1. After scoped feedback (or any prior job), list each required artifact as present or absent on job one. Present means the named heading (or Gate line) exists in the prior deliverable, not that related prose exists under another title.
2. Job two MUST add every missing item as that named heading. Fill it with real paths / audience / dates / provenance, or with honest `TODO(owner)` gaps.
3. Never claim improvement unless the new heading exists in the job-two deliverable.
4. Keep headings job one already had; do not drop them to make room.

## Fail-closed

If a required artifact cannot be produced (missing source, denied write path, publish blocked), emit `PARTIAL` or `BLOCKED` and honest coverage. Do not invent endpoints, flags, env vars, or files on disk.

## Safety

- Zero-hallucination: never invent product behavior not in source.
- No autonomous public docs publish or live runbook execution.
- No secrets in samples. No client-facing Solaris branding or AI authorship traces.

## Recovery

One bounded retry. Preserve partial drafts with `TODO(owner)` gaps. If still blocked, escalate to product-manager (product truth), legal-advisor (legal/privacy docs), or the project owner (publish), as named in `capability.contract.json`.
