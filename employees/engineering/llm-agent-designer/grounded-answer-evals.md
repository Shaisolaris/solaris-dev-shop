# Grounded-answer evals, offline (`grounded_eval.py`)

Use this when a retrieval or answering system has to be graded against a **supplied, frozen
snapshot of public sources**. This covers cited answers, abstaining on a missing answer, a source
that changes, and a retrieval step that fails partway. It runs on Python 3.9+ with the standard
library only. No model, judge, provider, key or network is used.

## What it is and what it is not
- `answer` is a **deterministic extractive baseline**. It uses BM25 over source sentences and
  answers only when one sentence covers the question's key terms. Identifiers such as model
  numbers and capitalised names must match exactly. A how-many, how-much or how-long question needs a number in the sentence. A when question needs a number or a calendar word, such as "closed on Mondays". It abstains when nothing covers the question,
  or when two sources disagree on a number. Every answer is a verbatim quote with code-point
  offsets and the document's sha256. **It is fixture behaviour, not model intelligence.** Never
  report its score as a model or product result.
- `evaluate` grades **any** answers file against the snapshot and a question set: the baseline,
  or output imported from a model or host.
  - The evaluator itself is deterministic lexical checking. It is not a judge.
  - It re-runs the baseline to check a file that claims to be the baseline. A claim that does not
    match is reported as unverified.
  - An imported file is labelled "imported, not executed or verified by this evaluator". A model
    or host result is only evidence when that run is shown separately, with its own logs.

## Inputs
- Snapshot: a folder of UTF-8 `.md`/`.txt` files. Symlinks and other file types are refused.
- Questions (JSONL): `{"id", "question", "expect": {"answerable": bool, "facts": [...], "support_docs": [...]}}`.
  - Unanswerable questions have `"answerable": false`.
  - `facts` must appear in the answer **and** in the cited quotes.
- Answers (JSONL, schema `solaris.grounded-answers/1`): an optional `meta` line with `producer`,
  then one record per id: `{"id", "abstain", "answer", "citations": [{"doc", "start", "end", "quote", "doc_sha256"}]}`.

## Verdicts (per question)
| Verdict | Meaning |
|---|---|
| `correct_supported` | Every citation is exact. Every number in the answer is in a cited quote. At least 60% of the answer's content words are quoted. The facts are present, and a support document is cited |
| `correct_abstain` | The question is unanswerable and the system abstained |
| `missed_answer` | It abstained on an answerable question |
| `answered_unanswerable` | It answered a question the snapshot cannot answer |
| `invalid_citation` | A quote is not in the snapshot, or the offsets are wrong and the quote is ambiguous |
| `stale_citation` | The cited document changed or was deleted after the answer was made, and the quote is gone |
| `uncited` | An answer with no citation |
| `unsupported_claim` | A number is not in any quote, or too little of the answer is quoted |
| `wrong_source` | The citations are valid but none is from a `support_docs` file |
| `incorrect` | The answer is supported, but an expected fact is missing |
| `missing_record` | There is no record for the question |

The citation status is one of: `valid`; `relocated` (the quote is unique, at other offsets, and still counts); `stale`; or `invalid`.

## Commands
```bash
python3 employees/engineering/llm-agent-designer/grounded_eval.py answer --corpus <snapshot-dir> --questions <questions.jsonl> --out <answers.jsonl> --journal <journal.jsonl>
python3 employees/engineering/llm-agent-designer/grounded_eval.py evaluate --corpus <snapshot-dir> --questions <questions.jsonl> --answers <answers.jsonl> --json --out <report.json>
python3 employees/engineering/llm-agent-designer/grounded_eval.py answer --corpus <snapshot-dir> --questions <questions.jsonl> --out <answers.jsonl> --journal <journal.jsonl> --resume
```
Exit codes:
- 0: pass, or the run completed.
- 1: evaluated with failures.
- 2: invalid input. Nothing was written, and inputs are never overwritten.
- 3: a tool step failed. The journal is kept; rerun with `--resume`.

## Recoverable tool failure
- Every retrieval step is journaled (`solaris.grounded-journal/1`). The journal header binds it to
  the corpus hash, the question hash, `--min-coverage` and the tool version.
- When a step fails, the run stops with exit 3 and writes no answers file. `--resume` redoes only
  the steps that are not done, and gives the same bytes as an unbroken run.
- `--resume` refuses a changed snapshot or a corrupted journal. It drops a torn last line, which a
  crash mid-write leaves behind.
- `--fault-plan F.json` (`{"retrieve": {"q05": 1}}`) is a drill: it makes the named steps fail N times.

## Source change
To check a source change, evaluate the old answers against the new snapshot. Changed documents
are named per citation (stale or relocated), with a note that the snapshot differs. Then re-answer
on the new snapshot.

## Limits
- Matching is lexical. A paraphrase that is correct but not quoted is `unsupported_claim`, which is
  conservative on purpose. Negation and meaning are not checked beyond the exact quote and the
  required facts.
- The baseline only extracts. It cannot combine two sentences, so multi-hop questions need another system.
- Fixtures are synthetic. Scale was measured on generated corpora (see the G16 oracle), not on real data.
