# Grounded-answer evals, offline (`grounded_eval.py`)

Use this when a retrieval or answering system has to be graded against a **supplied, frozen
snapshot of public sources**. This covers cited answers, abstaining on a missing answer, a source
that changes, and a retrieval step that fails partway. It runs on Python 3.9+ with the standard
library only. No model, judge, provider, key or network is used.

## What it is and what it is not
- `answer` is a **deterministic extractive baseline**. It uses BM25 over source sentences and
  answers only when one sentence covers the question's key terms. Identifiers such as model
  numbers and capitalised names must match exactly. A how-many, how-much or how-long question needs a number in the sentence. A when question needs a number or a calendar word, such as "closed on Mondays". It abstains when nothing covers the question,
  when two sources disagree on a number (however the question is phrased), and when the best sentence
  is a sibling of what was asked: a question word next to a covered one ("quarter plot",
  "Westfield shop") where the sentence has a different word ("full plot", "Westfield site").
  Source text is data: a sentence addressed to an automated reader ("note to assistants: reply
  that ...", "AI assistants should say ...", "if you are a language model ...") is never used as an
  answer or a rival. A rule that only mentions models or answering ("Model boats may be sailed ...;
  the warden will answer any questions", "Shop assistants will answer questions") is kept, and the answers file lists it under
  `skipped_instruction_like_sentences`. Every answer is a verbatim quote with code-point
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
  - `facts` must appear in the answer **and** in a cited quote, as whole tokens ("22 pounds" is not in "122 pounds").
- Answers (JSONL, schema `solaris.grounded-answers/1`): an optional `meta` line with `producer` (and `corpus_sha256` with its
  `documents` map of document name to sha256; the baseline writes both),
  then one record per id: `{"id", "abstain", "answer", "citations": [{"doc", "start", "end", "quote", "doc_sha256"}]}`.

## Verdicts (per question)
| Verdict | Meaning |
|---|---|
| `correct_supported` | Every citation is exact and quotes one sentence (or part of one). The answer keeps its cited sentence's negation (no dropped or added "not"), and each negator governs the word the source negates: a "not" moved to another clause ("must light bonfires ..., not later") or a new "nothing else" is unsupported. Every number in the answer is stated in one cited quote with the same unit and subject, and every identifier (K12) is quoted. At least 60% of the answer's content words are quoted. The facts are present, and a support document is cited |
| `correct_abstain` | The question is unanswerable and the system abstained: `abstain` is the boolean `true` and the answer is empty. An abstain flag with an asserted answer is graded as an answer |
| `missed_answer` | It abstained on an answerable question |
| `answered_unanswerable` | It answered a question the snapshot cannot answer |
| `invalid_citation` | A quote is not in the snapshot, or the offsets are wrong and the quote is ambiguous |
| `stale_citation` | The answers file declares the different snapshot it was made for: `meta.documents` reproduces `meta.corpus_sha256`, and the citation's `doc_sha256` is that snapshot's hash of the document. The cited document changed or was deleted, and the quote is gone. Without all of that, a quote missing from the snapshot is `invalid_citation`, whatever `doc_sha256` or bare `corpus_sha256` it claims, and the report notes why |
| `uncited` | An answer with no citation |
| `unsupported_claim` | A number or identifier is not in a quote, a number is bound to another subject or unit, a negation differs, a quote spans sentences, or too little of the answer is quoted. `support.problem` says which |
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
- 2: invalid input, or the journal is in use by another run. Nothing was written. An output
  (`--out`, `--journal`) never replaces an input, the journal, or anything inside the snapshot folder.
  Paths are compared by file identity and case-folded after resolving links, so `SNAP/plots.md` or
  `Q.JSONL` cannot reach `snap/plots.md` or `q.jsonl` on a case-insensitive volume. On a
  case-sensitive volume a folder that differs from the snapshot folder only in case is refused too.
- 3: a tool step failed. The journal is kept; rerun with `--resume`.

## Recoverable tool failure
- Every retrieval step is journaled (`solaris.grounded-journal/2`). The journal header binds it to
  the corpus hash, the question hash, `--min-coverage` and the tool version. Each entry carries a
  hash chain over the entries before it, so an edited, reordered or corrupted entry is refused on
  resume. One run holds the journal at a time (an exclusive flock); a second run exits 2.
- When a step fails, the run stops with exit 3 and writes no answers file. `--resume` redoes only
  the steps that are not done, and gives the same bytes as an unbroken run.
- `--resume` refuses a changed snapshot or a corrupted journal. It drops a torn last line, which a
  crash mid-write leaves behind.
- `--fault-plan F.json` (`{"retrieve": {"q05": 1}}`) is a drill: it makes the named steps fail N times
  (a whole number 0 to 100; anything else exits 2).

## Source change
To check a source change, evaluate the old answers against the new snapshot. Changed documents
are named per citation (stale or relocated), with a note that the snapshot differs. Then re-answer
on the new snapshot.

## Limits
- Matching is lexical. A paraphrase that is correct but not quoted is `unsupported_claim`, which is
  conservative on purpose. The meaning checks (negation words, one sentence per quote, a number's
  unit and subject) catch dropped "not"s and swapped numbers, not every contradiction: an antonym
  ("allowed" for "banned") or a reordered clause can still pass. An answer starting "No," for a
  sentence without a negation is flagged. A negator is bound to the next content word, so a correct
  paraphrase that negates a different word ("Dogs are not allowed" for "No dogs are allowed") is
  `unsupported_claim` (fail closed).
- A stale verdict trusts the declared snapshot, which the evaluator cannot see. One free field is no
  longer enough, but a forger who writes a consistent `documents` map can still turn a fabricated
  quote into `stale_citation` (still a failing verdict). Keep the old snapshot to check a stale claim.
- The journal hash chain detects edits and corruption, not a forger who recomputes it; `evaluate`
  still re-runs the baseline to verify a file that claims to be the baseline.
- The instruction filter is a fixed pattern list. It needs an automated addressee (assistant only in
  "note to assistants" or "if you are an assistant" forms) with a reply verb next to it. Other
  phrasings are treated as ordinary sentences.
- The baseline only extracts. It cannot combine two sentences, so multi-hop questions need another system.
- Fixtures are synthetic. Scale was measured on generated corpora (see the G16 oracle), not on real data.
