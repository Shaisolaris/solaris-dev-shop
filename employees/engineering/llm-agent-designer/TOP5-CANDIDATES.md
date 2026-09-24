# TOP-5 VERIFIED 2026 SOURCES - llm-agent-designer

Research date: 2026-06-13. Verified via shields.io live badge endpoints + GitHub repo pages + WebSearch. Star counts rounded as reported by the badge service.

Gate-0 method: grep the employee's ACTUAL current content (SKILL.md, rules.md, learnings.md, superpowers-methodology.md, plugin.json) for each candidate's distinctive concepts. Present-generic = mentioned in passing but no operational depth. Absent = not present at all.

---

## Summary table

| # | Source | URL | Stars | License | Last commit | Maintainer | Gate-0 verdict | Tag |
|---|--------|-----|-------|---------|-------------|------------|----------------|-----|
| 1 | confident-ai/deepeval | https://github.com/confident-ai/deepeval | ~16k | Apache-2.0 | today (v4.0.2, May 2026) | Confident AI (Jeffrey Ip) | ABSENT - no deepeval, G-Eval, tool-correctness, task-completion anywhere | ABSORB + METHODOLOGY |
| 2 | langchain-ai/langgraph | https://github.com/langchain-ai/langgraph | ~35k | MIT | today | LangChain Inc | ABSENT as a framework (only "stateful" re MCP) | METHODOLOGY |
| 3 | vibrantlabsai/ragas | https://github.com/vibrantlabsai/ragas | ~14k | Apache-2.0 | Feb 2026 (release v0.4.3 Jan 2026) | VibrantLabs (formerly explodinggradients) | PRESENT-GENERIC - "faithfulness", "recall@k" named once each, no metric definitions or thresholds | METHODOLOGY |
| 4 | mem0ai/mem0 | https://github.com/mem0ai/mem0 | ~58k | Apache-2.0 | today | Mem0 (Taranjeet Singh, Deshraj Yadav) | PRESENT-GENERIC - memory taxonomy listed, no scoping model or memory-layer source | CONNECT + METHODOLOGY |
| 5 | agno-agi/agno | https://github.com/agno-agi/agno | ~41k | Apache-2.0 | today | Agno (formerly Phidata) | ABSENT - no agno/crewai/autogen/agent-teams | CONNECT |

All five: established, well over 100 stars, permissive licenses (no GPL/AGPL/NOASSERTION flags), commits well within 6 months. No license flags required.

---

## Per-source detail

### 1. confident-ai/deepeval - ABSORB + METHODOLOGY
- What it adds: the single biggest gap-filler. A pytest-style LLM eval framework with research-backed metrics the employee currently only gestures at. Brings concrete, named, thresholded metrics: G-Eval and DAG (custom LLM-as-judge), plus AGENTIC metrics the employee has zero of (Task Completion, Tool Correctness, Argument Correctness, Goal Accuracy, Step Efficiency, Plan Adherence, Plan Quality), RAG metrics (Answer Relevancy, Faithfulness, Contextual Precision/Recall/Relevancy), Multi-Turn metrics, and MCP metrics (MCP Task Completion, MCP Use). CI/CD integration = the missing "regression gate". v4.0 (May 2026) added an eval harness for coding agents and ships a a coding agent skill.
- Gate-0: ABSENT. grep found no deepeval / G-Eval / tool correctness / task completion. The employee names eval tools (Braintrust, Promptfoo, Langfuse, W&B) but DeepEval is absent and is the only one with agentic + MCP metrics, which is exactly this employee's altitude.
- Why ABSORB: this employee designs agents + MCP servers; DeepEval is the eval framework purpose-built for both. Methodology (metric definitions + CI gate pattern) lifted into the new reference file. No code bundled.

### 2. langchain-ai/langgraph - METHODOLOGY
- What it adds: the production-tier agent-orchestration framework (graph nodes/edges, explicit state, checkpoints, rollback, human-in-the-loop interrupts). The employee's agent-patterns guidance is pattern-level (ReAct, Plan-Execute, Reflexion) but names no graph-state framework. LangGraph is the 2026 enterprise default for stateful, auditable multi-agent flows; its checkpoint/interrupt model operationalizes the employee's own "human-in-the-loop checkpoints" and "loop limits" guidance.
- Gate-0: ABSENT as a framework. Only hit was "stateful" describing MCP reconnection.
- Why METHODOLOGY not ABSORB: it is a heavy framework; the employee does design+architecture, not framework lock-in. Lift the graph-state + checkpoint + interrupt design pattern as methodology; cross-reference for when a client needs a durable orchestration layer.

### 3. vibrantlabsai/ragas - METHODOLOGY
- What it adds: reference-free RAG evaluation with precise, citable metric definitions (faithfulness, answer relevancy, context precision, context recall) plus production-aligned synthetic test-set generation. The employee's RAG design protocol ends at "Eval - retrieval recall@k, downstream answer quality" with no formula or threshold. RAGAS supplies the operational definitions and the test-set-generation step the employee lacks.
- Gate-0: PRESENT-GENERIC. "faithfulness" and "recall@k" each appear once with no definition, threshold, or framework. Not a content-duplicate of RAGAS-the-methodology.
- FLAG (not a license flag): the canonical repo moved from explodinggradients/ragas to vibrantlabsai/ragas (org rename; old URL redirects). Use the new org. License remains Apache-2.0. Cadence has slowed (last commit ~Feb 2026, last release v0.4.3 Jan 2026) - still inside 6 months but watch it; DeepEval is the more active eval primary.

### 4. mem0ai/mem0 - CONNECT + METHODOLOGY
- What it adds: a concrete agent memory layer combining vector + knowledge-graph + key-value stores behind one API, with a four-scope namespace model (user_id, agent_id, run_id, app_id, optional org_id) and an extraction pipeline that decides what to store. The employee lists a memory TAXONOMY (short/long/episodic/procedural) but has no memory-layer source and no scoping model - mem0 fills the "how do agents actually persist + isolate memory across sessions/tenants" gap, directly relevant to Solaris's own multi-employee, multi-client setup.
- Gate-0: PRESENT-GENERIC. Memory types listed in SKILL.md line 63; no scoping, no layer, no source. Not a content-duplicate.
- Why CONNECT + METHODOLOGY: most-starred standalone memory framework (~58k). Lift the scoped-memory design pattern as methodology; cross-reference mem0 as the default reach-for memory layer.

### 5. agno-agi/agno - CONNECT
- What it adds: high-performance multi-agent framework (Agents / Teams / Workflows / AgentOS runtime) with very fast agent instantiation and low memory footprint, built-in Agentic RAG + memory + storage. Rounds out the framework landscape alongside LangGraph (control + audit) and CrewAI (role-based crews). Gives the employee a named, current answer to "which multi-agent framework" beyond pattern descriptions.
- Gate-0: ABSENT. No agno / crewai / autogen / agent-teams anywhere.
- Why CONNECT only: framework selection guidance, not methodology to lift wholesale. Added to the framework-selection note + watchlist; CrewAI (~53k, MIT) noted alongside as the role-based-crew alternative.

---

## Verification notes
- Stars/license/last-commit pulled from shields.io live badge JSON (github/stars, github/license, github/last-commit) on 2026-06-13 and corroborated against rendered GitHub repo pages for RAGAS (14.4k, Apache-2.0, v0.4.3 Jan 13 2026) and DeepEval (15.4k, Apache-2.0, v4.0.2 May 13 2026).
- Unauthenticated GitHub REST API returned null (rate-limited); shields.io + HTML repo pages used instead.
- No source carries GPL, AGPL, or NOASSERTION. All permissive (MIT / Apache-2.0). No self-host-only methodology caveat triggered.
