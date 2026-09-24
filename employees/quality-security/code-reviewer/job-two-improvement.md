# Job-two improvement (named-heading protocol)

Transferable method: force this employee's `evidence.required_artifacts` into the deliverable as named markdown headings so a revision covers more of the contract than job one. Not a project copy.

## Named heading table

Each required artifact MUST appear under this exact heading (or the literal line). Distinctive tokens must survive `scripts/artifact_contract_coverage.py` `tokens_of` / `_present`.

| required_artifact | Deliverable MUST use |
|---|---|
| verdict summary | `## Verdict summary` |
| findings with file:line evidence | `## Findings with file:line evidence` |
| coverage statement | `## Coverage statement` |
| dependency/CVE section when manifests exist | `## Dependency/CVE section` |
| Gate: passed line | literal line `Gate: passed` (not a heading) |

If no dependency manifest exists, still emit `## Dependency/CVE section` with an honest N/A reason. Do not invent CVE IDs or scanner output.

`Gate: passed` only when SELF-QA is honestly all yes.

## Job-one vs job-two protocol

1. After scoped feedback (or any prior job), list each required artifact as present or absent on job one. Present means the named heading (or Gate line) exists in the prior deliverable, not that related prose exists under another title.
2. Job two MUST add every missing item as that named heading. Fill it with real file:line evidence, or with an honest N/A / PARTIAL reason.
3. Never claim improvement unless the new heading exists in the job-two deliverable.
4. Keep headings job one already had; do not drop them to make room.

## Fail-closed

If a required artifact cannot be produced (missing repo, missing tool, denied permission), emit `PARTIAL` or `BLOCKED` and honest coverage. Do not invent findings, CVEs, or tool output.

## Safety

- No production exploit, live production scan, or destructive verification without written human approval.
- No silent merge or deploy.
- No invented CVE, CVSS, or scanner output.

## Recovery

One bounded retry on flaky local tooling. Preserve partial work. If still blocked, escalate to security-auditor (deep pentest) or delivery-lead (merge/scope), as named in `capability.contract.json`.
