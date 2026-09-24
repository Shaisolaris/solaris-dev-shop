# Job-two improvement (named-heading protocol)

Transferable method: force this employee's `evidence.required_artifacts` into the deliverable as named markdown headings so a revision covers more of the contract than job one. Not a project copy.

## Named heading table

Each required artifact MUST appear under this exact heading (or the literal line). Distinctive tokens must survive `scripts/artifact_contract_coverage.py` `tokens_of` / `_present`.

| required_artifact | Deliverable MUST use |
|---|---|
| deliverable path list or plan | `## Deliverable path list or plan` |
| preflight or test/plan command output | `## Preflight or test/plan command output` |
| stack detection note | `## Stack detection note` |
| Gate: passed line | literal line `Gate: passed` (not a heading) |

`Gate: passed` only when SELF-QA is honestly all yes.

## Job-one vs job-two protocol

1. After scoped feedback (or any prior job), list each required artifact as present or absent on job one. Present means the named heading (or Gate line) exists in the prior deliverable, not that related prose exists under another title.
2. Job two MUST add every missing item as that named heading. Fill it with real paths, preflight/test output, and stack detection from the repo, or with an honest N/A / PARTIAL reason.
3. Never claim improvement unless the new heading exists in the job-two deliverable.
4. Keep headings job one already had; do not drop them to make room.

## Fail-closed

If a required artifact cannot be produced (missing UE/MCP/license, denied permission, no repo), emit `PARTIAL` or `BLOCKED` and honest coverage. Do not invent PIE, cook, or package results.

## Safety

- No shipping build distribution without a human.
- No license-key mutation, untrusted plugin execution, or store submission.
- No silent production deploy. No secrets in the project.

## Recovery

One bounded retry on flaky local tests. Preserve partial work. If still blocked, escalate to delivery-lead or cto (scope) / security-auditor (authz/secrets), as named in `capability.contract.json`.
