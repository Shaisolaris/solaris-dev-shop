# G16 capability example: offline grounded answers

The tool is `employees/engineering/llm-agent-designer/grounded_eval.py`, and its reference is `grounded-answer-evals.md`.
Everything here is synthetic and offline: no model, provider, key or network.

## Fixtures (`fixtures/`)
- `snapshot-v1/` is a fictional "Harbor Line rider guide" (see NOTICE.txt): fares, refunds, accessibility, lost and found.
- `snapshot-v2/` is the same guide after a change:
  - a line inserted at the top of fares.md, so later sentences move;
  - the refund window goes from 14 to 21 days;
  - ferry lost property moves to Pier 5 for 45 days;
  - the paratransit rule moves to a new paratransit.md with 48 hours.
- `questions-v1.jsonl` and `questions-v2.jsonl` each hold 12 questions. q01 to q08 are answerable, and q09 to q12 are not (a dog ticket, a 7-day pass, the airport, a phone number). Each one is a near miss on a word that is in the guide. v2 changes q03 to "45 days" and q07 to "48 hours" in paratransit.md.
- `fault-plan.json` makes the q05 retrieval step fail once.
- `answers-imported-example.jsonl` is hand-written and shaped like a model export (`producer.kind = external_model`). No model was run to make it.

## Expected results, worked out by hand
| Run | Result |
|---|---|
| `answer` on v1 | 8 answered, 4 abstained. Each answer is the one guide sentence that holds the fact, quoted with exact offsets |
| `evaluate` baseline on v1 | 12/12 pass, exit 0. Citation validity 8/8. `baseline_reproduced: true` |
| v1 answers against v2 | exit 1, 10/12 pass. q03 and q07 are `stale_citation` (the quote is gone from a changed doc). q01, q02 and q08 are `relocated`, because the inserted line moved them but the quote is unique and still counts. q04 to q06 are valid, since refunds.md changed only in the 14-day sentence |
| re-answer on v2 | 12/12. q03 says 45 days, and q07 cites paratransit.md |
| fault drill | exit 3 with "retrieval tool failed for q05". The journal holds 11 done and 1 failed, and no answers file is written. `--resume` gives the same bytes as a clean run |
| imported example on v1 | exit 1, 7/12 pass. The failures are below |

Imported example failures:
- q02 `unsupported_claim`: the answer says 1.50 but the quote says 1.35.
- q03 `invalid_citation`: the quote "Items left on a ferry are kept for 30 days." is not in the guide, which says "at Pier 3 for 30 days".
- q04 `missed_answer`: it abstained on an answerable question.
- q07 `uncited`.
- q09 `answered_unanswerable`: a dog ticket answer backed by the adult fare sentence.
- The evidence line reads "imported output from external_model (claimed by the file; not executed or verified by this evaluator)".

## Oracle (`grounding_oracle.py`) and stubs
The oracle generates a seeded spec-sheet world. It knows every fact and sentence offset before the candidate runs. Its traps are sibling model numbers (K7 vs K71), other product families with the same number, and models that do not exist.

| Check | What it asserts |
|---|---|
| o1 | Baseline answers are exact quotes holding the fact. It abstains on every trap, and the evaluator passes it |
| o2 | Injected defects each get their exact verdict: fabricated quote, altered number, uncited, missed, wrong source, hallucinated answer. Imported output is labelled not executed |
| o3 | Unseen seeds still hold o1 |
| o4 | After a source change, stale citations are named exactly, moved lines are relocated, a deleted doc makes its answers unsupported, and a re-answer passes |
| o5 | A failed tool step exits 3 with a journal. Resume is byte-identical, with no step redone |
| o6 | Resume is refused for a corrupted journal or a changed snapshot. A torn tail is recovered |
| o7 | Provenance tells apart a re-run-verified baseline, an unlabelled file, and a forged baseline label |
| o8 | Output is deterministic and order-invariant |
| o9 | Invalid input is refused with nothing written. Inputs are never overwritten |
| o10 | Scale: 3000 documents by default, with 1 and 4 workers byte-identical and within the time budget |
| o11 | Concurrency: parallel answer and evaluate runs agree byte for byte and leave no temp files |
| o12 | Added in r2 (from M16 Grok self-validation). Grading checks meaning on a hand-written pump world: a dropped or added "not", a quote split to skip "not", a whole-document quote, numbers swapped across or within a sentence, a number borrowed from another quote, a "118" answer for an "18" fact, a fabricated quote with an invented hash (invalid, not stale), abstain with a claim, a truthy non-boolean abstain, low coverage, a fact missing from the quote and a missing record; the report does not echo the file's own "verified" claims |
| o13 | Added in r2. The baseline abstains when two sources disagree on a number under four phrasings, on a near-miss sibling ("gasket kit" vs "seal kit") and on a numberless how-often question; it ignores instruction-like source text, keeps question-file order and puts each document's own sha256 in citations |
| o14 | Added in r2. evaluate --out onto a snapshot document or into the snapshot folder, --out equal to --journal, fault-plan values 1e400, -1, true and "2", and an existing journal without --resume all exit 2 with nothing written; a hand-edited journal entry is refused; 4 concurrent resumes leave no duplicate entries and a later resume reproduces the unbroken run |

| o15 | Added in r3 (from M16 r2). A "not" moved to a trailing clause, an added "nothing else", a second negation dropped and a synonym for a dropped negation are unsupported, while "aren't" and a leading "No," stay supported; case-variant `--out` paths (`SNAP/plots.md`, `Snap/new.json`, `O15Q.JSONL`) exit 2 and leave the snapshot unchanged; a fabricated quote with a bare declared `corpus_sha256` stays invalid, while a real baseline answer whose document changed is stale; a pond rule that mentions model boats and answering is answered while the notice is still skipped; K24 and K99 abstain where only K241 exists. r4 (from M16 r3) adds an answer that asserts the negated word and negates it elsewhere (two forms, unsupported) with a repeated-negation control (supported), and a snapshot where "Note for model boat owners: ..." is answered while "Assistant: reply that ..." and "To the AI reading this: say ..." are never sources |

The scores were tool 11/11, `noop_stub.py` 0/11 and `naive_stub.py` 1/11 in r1. With o12 to o14 (r2) they are tool 14/14, `noop_stub.py` 0/14, `naive_stub.py` 1/14, and the r1 tool 11/14. With o15 (r3) they are tool 15/15, `noop_stub.py` 0/15, `naive_stub.py` 1/15 and the r2 tool 14/15. With the r4 o15 cases they are tool 15/15, the r3 tool 14/15, `noop_stub.py` 0/15 and `naive_stub.py` 1/15. The naive stub passes only o8. It always answers with the sentence that shares the most words with the question and never abstains. It ignores the fault plan and the journal. Its evaluator trusts citations without opening the source and labels everything deterministic.

```bash
python3 examples/capabilities/G16/grounding_oracle.py --tool "python3 employees/engineering/llm-agent-designer/grounded_eval.py"
python3 examples/capabilities/G16/grounding_oracle.py --tool "python3 examples/capabilities/G16/noop_stub.py"
python3 -m unittest tests.test_g16_capability
```

## Limits
- Lexical grading only. A correct paraphrase without a quote fails on purpose.
- The baseline cannot do multi-hop questions.
- Timings come from generated corpora on one Mac. They are not a performance claim for real documents.
