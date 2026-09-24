# Job-two improvement (named-heading protocol)

Transferable method: force this employee's `evidence.required_artifacts` into the deliverable as named markdown headings so a revision covers more of the contract than job one. Not a project copy.

## Named heading table

Each required artifact MUST appear under this exact heading (or the literal line). Distinctive tokens must survive `scripts/artifact_contract_coverage.py` `tokens_of` / `_present`.

| required_artifact | Deliverable MUST use |
|---|---|
| verdict + coverage statement | `## Verdict + coverage statement` |
| threat model or N/A with reason | `## Threat model` (include N/A with reason in the section body when no model applies) |
| findings with evidence + reproduction + remediation | `## Findings with evidence` (each finding still carries reproduction + remediation) |
| Gate: passed line | literal line `Gate: passed` (not a heading) |

`Gate: passed` only when SELF-QA is honestly all yes.

## Job-one vs job-two protocol

1. After scoped feedback (or any prior job), list each required artifact as present or absent on job one. Present means the named heading (or Gate line) exists in the prior deliverable, not that related prose exists under another title.
2. Job two MUST add every missing item as that named heading. Fill it with real evidence / repro / remediation, or with an honest N/A / PARTIAL reason.
3. Never claim improvement unless the new heading exists in the job-two deliverable.
4. Keep headings job one already had; do not drop them to make room.

## Fail-closed

If a required artifact cannot be produced (missing repo, missing tool, denied permission, no written scope), emit `PARTIAL` or `BLOCKED` and honest coverage. Do not invent findings, CVEs, CVSS, or scanner output.

## Safety

- No production exploit, live production scan, or destructive verification without written human approval and scope.
- No silent disclosure, credential rotation, or merge/deploy.
- No invented CVE, CVSS, or tool output. No binding audit-opinion language when not engaged as auditor.

## Recovery

One bounded retry on flaky local tooling. Preserve partial work. If still blocked, escalate to compliance-auditor (control evidence), legal-advisor (disclosure), or delivery-lead (remediation ownership), as named in `capability.contract.json`.
