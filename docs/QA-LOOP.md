# QA Loop (canonical)

The non-negotiable quality loop for every Solaris Dev Shop deliverable.

## The loop

```
build → independent review → fix → repeat until the review is clean on the final artifact
```

1. **Build** the deliverable.
2. **Independent review** against the actual artifact. No self-certification: the reviewer is a different pass, a different employee, or a different tool than the builder.
3. **Fix** every finding, verified against the artifact (not against the claim).
4. **Repeat** until a full review round finds zero new issues.

## What it covers

- **Mechanically checkable** (code, HTML/JS, scripts, configs, structured docs, spreadsheets, PDFs): full loop, every time.
- **Judgment deliverables** (proposals, client messages, strategy): independent review against the owner's rubric instead of a mechanical check.

## Rules

- Verify each finding against the actual artifact. "No error thrown" is not "task done."
- Log findings to `qa-ledger.jsonl` where the project keeps one.
- Shipping without the loop is a process violation.
- Do not name a model vendor as the employee in any deliverable.
