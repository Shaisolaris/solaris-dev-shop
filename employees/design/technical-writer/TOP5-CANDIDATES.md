# Technical Writer - TOP 5 verified 2026 candidates

Domain: docs-as-code / API docs. Verified 2026-06-13.

| # | Source | Stars/Status | License | Last update | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|--------------|---------|-------------|------------|--------------|--------|-----|
| 1 | llms.txt standard (https://llmstxt.org) | ~10% domain adoption; B2A gold standard | community spec (CC-ish; methodology) | 2026 (proposed 2024-09) | Answer.AI / community | Operationalize the docs-for-AI-agents deliverable: /llms.txt (curated index) + /llms-full.txt (full corpus). Cursor/Claude Code/Copilot/Cline/Aider fetch these. Employee mentions it only in passing. | grep: "llms.txt" present but ONLY as a one-line maintenance note = not operationalized = real upgrade | ABSORB methodology (new deliverable) |
| 2 | https://github.com/evildmp/diataxis-documentation-framework | ~1.1k | CC-BY-SA-4.0 (attribution) | 2026 | evildmp | Diátaxis compass - already absorbed. CONFIRMED still the 2026 standard (LangChain, StreamingFast adoption). | grep: present = content-duplicate | CONNECT (confirmed current) |
| 3 | OpenAPI 3.1 + Swagger UI/Redoc/Mintlify | standard | various | 2026 | OAI | API-docs source-of-truth, already absorbed. Confirmed current. | grep: present = content-duplicate | CONNECT (confirmed) |
| 4 | https://github.com/olivierlacan/keep-a-changelog | ~6.6k | MIT | 2026 | olivierlacan | Changelog standard 1.1.0, already absorbed. Confirmed current. | grep: present = content-duplicate | CONNECT (confirmed) |
| 5 | https://github.com/google/styleguide (docguide) | ~39k | CC-BY-3.0 | 2026 | Google | Maintenance discipline (MVD, delete-dead-docs), already absorbed. Confirmed current. | grep: present = content-duplicate | CONNECT (confirmed) |

## Notes
- The employee's frameworks are stable 2026 standards (Diátaxis, OpenAPI 3.1, Keep a Changelog all confirmed current) - NO churn, no replacement needed.
- The one genuine net-new: operationalize llms.txt / llms-full.txt as a docs-for-AI-agents DELIVERABLE (it's now the first widely-adopted Business-to-Agent docs standard, fetched by all major coding agents). The employee only name-drops it in the maintenance section.
- No other high-value source emerged; this is a near-complete employee.

## 2026-06-15 DEEPEN pass - document ingestion (any-doc -> clean Markdown for docs/RAG)
| Source | Stars | License | Active | Verdict |
|---|---|---|---|---|
| docling-project/docling | 61,598 | MIT | pushed 2026-06-15, not archived | ABSORB methodology - high-fidelity ingestion (layout/tables/formulas/OCR -> Markdown/JSON), air-gapped local, docling MCP. Default for fidelity/tables/OCR/sensitive source docs. |
| microsoft/markitdown | 153,753 | MIT | pushed 2026-05-26, not archived | ABSORB methodology - lightweight any-file -> LLM-ready Markdown (broad format coverage), markitdown-mcp. Default for bulk RAG ingestion. |

Gate-0 PASS (grep: no prior docling/markitdown/ingest content). Net-new = the INPUT/ingestion front door (Workflow 0 + ingestion standard); all OUTPUT rules unchanged. No rejections. Nothing installed/run. Boundary recorded vs delivery-lead (engagement intake) + knowledge-base (corpora).
