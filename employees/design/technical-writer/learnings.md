# Technical Writer - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from wshobson docs-architect**: 3-phase Discovery + Structuring + Writing process + 10-section structure is the most actionable long-form doc framework.
- **2026-04-25 - Diátaxis 4-quadrant separation** (Tutorial vs How-to vs Reference vs Explanation) is the framework that fixes most messy docs sites.

- **2026-06-13 (depth) - llms.txt operationalized as a deliverable** - now the de-facto Business-to-Agent docs standard (Cursor/Claude Code/Copilot/Cline/Aider fetch /llms.txt + /llms-full.txt). Was only a one-line maintenance note; now a first-class deliverable for any docs site.
- **2026-06-13 (depth) - Core frameworks confirmed current** - Diataxis, OpenAPI 3.1, Keep a Changelog all still 2026 standards; no replacement needed. Pass was additive.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |

- **2026-06-15 (DEEPEN, v0.5.0) - doc-ingestion front door added** - absorbed docling-project/docling (MIT, 61,598 stars) + microsoft/markitdown (MIT, 153,753 stars), methodology only (nothing installed). Net-new (Gate-0 PASS, grep confirmed no prior content): the INPUT/ingestion layer (any-doc -> clean Markdown for docs sites/migrations + RAG), with a Docling-vs-MarkItDown selection rule (Docling = fidelity/tables/OCR/sensitive; MarkItDown = bulk LLM-ready), convert-locally for sensitive docs, verify-against-source (zero-hallucination applied to ingestion), restructure-to-Diataxis not dump, RAG chunk-on-headings. Wired: doc-ingestion-2026.md + Workflow 0 + a rules.md ingestion section. Boundary recorded vs delivery-lead (engagement intake) + knowledge-base (corpora) - same tools, different consumers.

- **2026-08-13 - named-heading protocol**: measured D5 gap was job-two omitting contract-required artifact headings; closed by named-heading protocol in `job-two-improvement.md`.
