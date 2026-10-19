# LLM Agent Designer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#prompt], [#rag], [#agent], [#mcp], [#skill], [#eval], [#cost], [#safety], [#promoted?]
```

---

## Pending observations

- **2026-10-18 - G16 offline grounded evals**: added `grounded_eval.py` and `grounded-answer-evals.md`. A file can claim to come from any producer, so the evaluator re-runs the deterministic baseline before it calls a result "fixture behaviour". An unmatched claim is reported as unverified, and outside output is labelled imported, not executed. The baseline needed an exact-identifier rule: at 0.75 key-term coverage it first answered a question about one product with a sibling product's spec sentence. Line-level offsets, document hashes and a journal bound to the corpus hash made "the source changed" and "resume after a failed step" checkable without a model.
  *Proposed rule: Grade grounded answers by exact quoted spans and by numbers that appear in the quotes; require abstention on unanswerable items; never report a deterministic baseline or an imported file as model capability.*
- **2026-10-18 - G16 r2 (M16 self-validation)**: words-in-quotes grading certified contradictions: a dropped "not", a whole-document quote and numbers swapped between subjects all graded supported. r2 checks one sentence per quote, the cited sentence's negation, and each number's unit and subject in one quote; conflicts abstain however the question is phrased; near-miss siblings abstain; outputs never land in the snapshot or on the journal; the journal is hash-chained and flocked.
- **2026-10-18 - G16 r3 (M16 r2 self-validation)**: checking that a negation is present is not checking what it negates: a "not" moved to a trailing clause still graded supported, so each negator is now bound to the word it governs. String path guards miss case variants on APFS; compare file identity and case-folded resolved paths. A self-declared hash is one free field, so a stale verdict needs a declared snapshot that reproduces its own hash. A keyword-pair instruction filter dropped a pond rule ("model boats ... will answer"); the addressee must be automated and bound to the verb. A guard no test reaches (exact identifiers) needs a substring case, or a mutant passes every scorer.
  *Proposed rule: A grounded grader must test that the claim keeps the quote's polarity and binds each number to its own subject; test it with contradiction forgeries, not only fabricated quotes.*
  Tags: [#eval], [#rag], [#safety]

- **2026-04-24 - LLM Agent Designer rebuild**: Solaris IS a an agent SDK product. The 59 employee-plugins are agent designs an agent SDK was made for. The canonical example of "how to design a Solaris-quality agent" is Solaris's own skill scanner / knowledge sweep / roster manager. Self-referential but correct.
  *Proposed rule: When this employee designs an agent or skill, reach for Solaris's own employee-plugin structure as the default template - SKILL + rules + learnings + plugin.json with progressive disclosure + self-learning loop.*
  Tags: [#solaris-as-reference], [#promoted?]

- **2026-04-24 - LLM Agent Designer rebuild**: Clear altitude split between this employee and AI Automation Engineer is critical. LLM Agent Designer does ARCHITECTURE / DESIGN. AI Automation Engineer does NO-CODE WIRING (n8n, Zapier, Make). Collaboration happens but they don't overlap.
  *Proposed rule: When the owner mentions n8n / Zapier / Make by name → route to AI Automation Engineer. When the owner says "design an agent", "prompt engineering", "RAG", "MCP" → this employee.*
  Tags: [#altitude-split], [#routing]

- **2026-04-24 - LLM Agent Designer rebuild**: "Simplest that works" is the single most-violated principle in LLM design. Every new stack addition (agent when single prompt works, multi-agent when single agent works, Opus when Sonnet works) costs cost + latency + complexity debt. Codified as core principle.
  *Proposed rule: ALWAYS start with the smallest possible system. Require an eval delta before adding complexity.*
  Tags: [#simplicity-first], [#promoted?]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-06-13 - v0.6.0 deep quality pass: eval/memory/orchestration absorption
- Created eval-methodology.md (methodology only, no code). Sources: DeepEval (Apache-2.0), RAGAS (Apache-2.0), LangGraph (MIT), mem0 (Apache-2.0). All permissive, no flags.
- Operationalized the eval gate: every prompt/agent/RAG change needs an eval set + per-metric thresholds (G-Eval 0.5, Answer Relevancy 0.7, Faithfulness 0.8, Tool/Argument Correctness 1.0) + recorded delta + CI gate. The QA Engineer hand-off is now concrete.
- Memory got a real mechanism: scoped-memory model (vector + graph + key-value behind one interface; user_id/agent_id/run_id/app_id/org_id). Cross-tenant memory leakage flagged as a Security Auditor finding for Solaris's multi-client setup.
  *Proposed rule: any Solaris agent that remembers across sessions MUST declare scope keys (at least org_id/app_id + agent_id) before writing memory.* Tags: [#memory], [#safety], [#solaris-as-reference]
- Fixed phantom references: rules.md had listed 8 references/*.md files that never existed as files. Replaced with a real file map; clarified those topics live inline in SKILL.md.
  *Proposed rule: a reference link must point to a file that exists; list-vs-exists mismatch is a recurring defect, check it every pass.* Tags: [#skill], [#promoted?]
- Fixed stale SKILL.md reference table (was missing superpowers-methodology.md and eval-methodology.md, the two most important load-first files).
- Added a small-task/prototype fast lane so trivial work does not get dragged through the full design protocol, and prototypes cannot silently graduate to production without an eval. Tags: [#simplicity-first]

## 2026-06-14 - v0.7.0 ECC agent-BUILD deepening (owner flagged agent-building as weak)
- Created references/agent-engineering-craft.md from affaan-m/ECC (MIT). BUILD-side craft, methodology only, no code bundled.
- Lifted: agent-harness-construction (4-budget model: action-space / observation / recovery / context; observation envelope status+summary+next_actions+artifacts; error-recovery contract must carry a stop condition; micro/medium/macro tool granularity; ReAct vs function-calling vs hybrid). agent-architecture-audit (12-layer agent stack; 5 named failure patterns - wrapper regression, memory contamination, tool-discipline failure, rendering corruption, hidden agent layers; code-first fix order; 7 diagnostic questions; report schema). agent-introspection-debugging (4-phase self-debug: capture / diagnose / contained-recovery / report; recovery heuristic order: restate objective -> verify world state -> shrink scope -> one discriminating check -> only then retry). cost-aware-llm-pipeline (route-by-complexity + immutable cost tracker + narrow retry + prompt caching, composed). regex-vs-llm-structured-text (deterministic-first; regex clears 95-98%, LLM only for confidence-flagged edge cases). agent-eval comparison mechanics (YAML tasks + git-worktree isolation + >=3 trials + pinned commit).
- Gate-0 enforced vs eval-methodology.md: the craft file is BUILD craft (construct/audit/debug), the eval file is SCORE craft. Zero eval-metric duplication; craft file references eval file for all thresholds + memory-scope keys.
  *Proposed rule: agent quality is bounded by 4 budgets (action-space, observation, recovery, context) - diagnose which is starved before reaching for a bigger model.* Tags: [#agent], [#promoted?]
  *Proposed rule: before shipping ANY agent/LLM feature to a client, run the 12-layer architecture audit; fixes are code-first, never prompt-first; "must use tool X" in prompt text only is a tool-discipline failure.* Tags: [#agent], [#safety]
- Fleet doctrine honored: memory-scope keys stay in eval-methodology.md (not re-stated); no em-dashes used as sentence punctuation in the new file (hyphens only); SHA-pin/CI guidance left to existing infra. No license flags (ECC is MIT).
## Sources

- Upstream: confident-ai/deepeval (license not stated: ~16k); langchain-ai/langgraph (license not stated: ~35k); vibrantlabsai/ragas (license not stated: ~14k); mem0ai/mem0 (license not stated: ~58k); agno-agi/agno (license not stated: ~41k)
- What was used: methodology absorbed: confident-ai/deepeval; methodology only: langchain-ai/langgraph, vibrantlabsai/ragas, mem0ai/mem0; connected as external reference: mem0ai/mem0, agno-agi/agno
- License notes: licenses not recorded in scan for: confident-ai/deepeval, langchain-ai/langgraph, vibrantlabsai/ragas, mem0ai/mem0, agno-agi/agno - verify before reuse; no code vendored
