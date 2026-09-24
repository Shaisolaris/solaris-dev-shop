# Eval, Memory, and Orchestration Methodology

> Load when: designing an eval set, evaluating a RAG pipeline, scoring an agent or MCP server, designing agent memory, or choosing an orchestration layer. This file operationalizes the gates the SKILL.md and rules.md only gesture at ("eval before optimization", "retrieval recall@k", "memory: short/long/episodic").

Methodology only. No code is bundled. All sources are permissive (MIT / Apache-2.0); install any framework yourself if you choose to use it.

Absorbed 2026-06-13 from: confident-ai/deepeval (Apache-2.0), vibrantlabsai/ragas (Apache-2.0), langchain-ai/langgraph (MIT), mem0ai/mem0 (Apache-2.0). Verdicts and verification in TOP5-CANDIDATES.md.

---

## 1. The eval gate (operationalized)

The rule "a prompt without an eval set is a hope, not a system" needs a concrete gate. Use this one.

### Definition of done for any prompt / agent / RAG change
A change is shippable only when ALL of:
1. An eval set exists (10-50 representative cases, with expected output OR a judge rubric).
2. Every metric meets its threshold on the eval set.
3. The eval delta vs the previous version is recorded (no silent regressions).
4. The eval runs in CI (or at minimum, is re-run by hand before ship and the result pasted into the PR / handoff).

If you cannot state the threshold a change must clear, you do not have an eval; you have a vibe.

### Metric thresholds (starting defaults, tune per project)
Treat each metric as a 0-1 score with a pass threshold. Defaults below come from DeepEval's pytest-style harness (G-Eval and friends). Raise thresholds for high-stakes domains; lower only with a written reason.

| Metric | What it measures | Default pass threshold |
|--------|------------------|------------------------|
| G-Eval (custom criteria) | LLM-as-judge against your own rubric | 0.5 |
| Answer Relevancy | output relevant to the input | 0.7 |
| Faithfulness | output is grounded in retrieval context (no hallucination) | 0.8 |
| Contextual Precision | relevant retrieved chunks ranked above irrelevant ones | 0.7 |
| Contextual Recall | retrieval context covers what the expected answer needs | 0.7 |
| Tool Correctness | right tool called with right arguments | 1.0 (binary per call) |
| Task Completion | agent actually accomplished the goal | 0.7 |
| Argument Correctness | tool-call arguments are valid | 1.0 |

### CI regression gate (the missing piece)
1. Store the eval set as test cases (pytest-style: input, actual_output, expected_output or retrieval_context, plus the metric + threshold).
2. Run on every prompt / agent change. A metric below threshold = a failed test = a blocked merge.
3. Record P50/P95 latency and cost per case alongside scores so a quality win that doubles cost is visible.
4. This is the QA Engineer "regression suite / CI eval gate" hand-off made concrete. Hand the eval suite to QA Engineer to wire into CI.

---

## 2. RAG evaluation (concrete, RAGAS-style)

The RAG design protocol's step 8 ("Eval: retrieval recall@k, downstream answer quality") expands to four reference-free metrics. Evaluate retrieval and generation separately so you know which half to fix.

### Retrieval quality
- **Contextual Precision** = of the chunks retrieved, how many are actually relevant, and are they ranked first. Low precision means the reranker or k is wrong.
- **Contextual Recall** = did retrieval surface everything the correct answer needs. Low recall means chunking, embedding, or k is wrong (raise k, fix chunk size, re-embed).
- **recall@k** = fraction of the gold-relevant chunks that appear in the top-k. Track it as you tune k; this is the formula behind the SKILL.md mention.

### Generation quality
- **Faithfulness** = every claim in the answer is supported by the retrieved context. This is the anti-hallucination gate. Threshold 0.8+; for legal/medical, 0.95+.
- **Answer Relevancy** = the answer addresses the question (not just true, but on-topic).

### The fix-order rule (from rules.md "retrieval quality drives downstream quality")
If Faithfulness is low but Contextual Recall is high: the generation prompt is the problem.
If Contextual Recall is low: retrieval is the problem; do not touch the prompt yet.
Fix retrieval before tweaking the generation prompt, always.

### Test-set generation
You rarely have a labeled RAG eval set. Generate one: from the corpus, synthesize question + ground-truth-answer + relevant-context triples (RAGAS does this as "production-aligned test set generation"). 30-50 synthetic cases beats zero real cases. Validate a sample by hand before trusting the set.

---

## 3. Agent and MCP scoring

The SKILL.md agent eval protocol ("trajectory scoring (LLM-as-judge), success rate") needs named metrics. Use these (DeepEval agentic + MCP metric families):

- **Task Completion** - did the agent achieve the user goal. The headline success metric.
- **Tool Correctness** - was the right tool called with the right args. Binary per call; this catches the "hallucinated tool call" gotcha from rules.md.
- **Argument Correctness** - were tool arguments valid against the schema.
- **Step Efficiency** - did the agent take unnecessary steps (cost + latency signal; pairs with the "agent loops runaway" gotcha).
- **Plan Adherence / Plan Quality** - for Plan-Execute agents, did it follow a sound plan.
- **MCP Task Completion / MCP Use** - for MCP servers: can an agent actually accomplish tasks with your tools, and does it use the right servers. Run this BEFORE shipping an MCP server; it is the concrete form of the rules.md gate "test with the coding agent / MCP Inspector: verify the LLM can use the tools without guidance."

Scoring an MCP server you built is now a checklist item, not a hope: feed a held-out set of tasks, measure MCP Task Completion, fix the lowest-scoring tools' schemas and error messages, repeat.

---

## 4. Agent memory (scoped memory model)

The SKILL.md lists a memory taxonomy (short-term, long-term, episodic, procedural) but no mechanism for HOW agents persist and isolate memory. Add the scoped-memory model (mem0-style).

### Three storage layers behind one interface
- **Vector** - semantic similarity recall (the "long-term / episodic" store).
- **Knowledge graph** - entity relationships ("X is the CTO of Y").
- **Key-value** - structured facts ("user prefers metric units").
An extraction step decides what is worth storing on write; retrieval queries all three and merges.

### Four-scope namespace (the isolation model)
Every memory is tagged with a scope so it is shared or isolated correctly:
- `user_id` - per end user (derive from the calling app's auth, do not invent it).
- `agent_id` - per agent / employee.
- `run_id` - per session / conversation (the "short-term" store).
- `app_id` - per application; optional `org_id` for tenant isolation.

### Why this matters for Solaris specifically
Solaris runs many employees across many clients. Memory MUST be scoped by client (org/app) and by employee (agent_id) or one client's context leaks into another's. When designing any Solaris agent that remembers across sessions, declare the scope keys up front. Treat cross-tenant memory leakage as a security finding (hand to Security Auditor).

### Decision rule
- Single-session agent, no persistence needed -> conversation buffer only; no memory layer.
- Cross-session recall needed -> reach for a scoped memory layer (mem0 is the ~58k-star default); declare scope keys before writing.
- Heavy entity-relationship reasoning -> include the knowledge-graph layer, not vector-only.

---

## 5. Orchestration layer selection

The agent-patterns guidance (ReAct, Plan-Execute, Reflexion) is pattern-level. When a client needs a durable, auditable orchestration RUNTIME, name one. Decision order (keep "simplest that works"):

1. **No framework** - single agent loop + tools. Default. Most jobs end here.
2. **Graph-state orchestration (LangGraph-style)** - when you need explicit state, checkpoints, rollback, and human-in-the-loop interrupts in a long or auditable flow. The checkpoint/interrupt model operationalizes the SKILL.md "human-in-the-loop checkpoints" and "loop limits + budget ceilings" guidance. Reach for this for enterprise/production flows that must be resumable and inspectable.
3. **Role-based crews (CrewAI-style) or high-performance teams (Agno-style)** - when the work genuinely decomposes into specialist roles collaborating. Only after proving a single agent cannot do it (rules.md: "never start multi-agent").

Framework choice is a CONNECT, not a lock-in: design the agent's reasoning and tool contracts first; the runtime is an implementation detail chosen last. Cross-reference ai-automation-engineer for the no-code wiring altitude.

---

## Cross-references
- `rules.md` - eval red flags, retrieval-quality gotcha, hallucinated-tool-call gotcha.
- `superpowers-methodology.md` - TDD-first: the eval test IS the failing test you write before iterating the prompt.
- QA Engineer - receives the eval suite to wire into CI as a regression gate.
- Security Auditor - cross-tenant memory leakage and agent tool-access review.
- ai-ml-engineer - owns the embedding/model layer when RAG eval points at embedding drift.
