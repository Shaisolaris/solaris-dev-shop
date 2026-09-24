# Document ingestion methodology (any-doc -> clean Markdown for docs + RAG)

METHODOLOGY absorption (2026-06-15). Two tools, methodology only - nothing is installed or run here; the host runs the converter, the writer owns the discipline and the verification gate.

- **docling-project/docling** (MIT; 61,598 stars; pushed 2026-06-15; not archived) - high-fidelity document understanding: layout, reading order, table structure, formulas, OCR -> a unified DoclingDocument -> Markdown/HTML/JSON.
- **microsoft/markitdown** (MIT; 153,753 stars; pushed 2026-05-26; not archived) - a lightweight Python utility that converts many file types to Markdown for LLM/text-analysis pipelines, preserving headings/lists/tables/links.

## Why it exists here (the gap it closes)
The Technical Writer owns the OUTPUT of docs (Diataxis types, API reference, README, runbooks, manuals, changelog, llms.txt). It had no INPUT discipline for the common job of turning EXISTING source documents - a legacy PDF manual, a Word spec, a deck of slides, an exported Confluence/Notion page, a spreadsheet of config, a scanned guide - into clean Markdown to (a) seed a new docs site or migrate an old one, and (b) build a RAG corpus the docs site or a support bot can retrieve from. This file is that ingestion layer: messy source doc -> clean, structured Markdown -> the writer edits/restructures to Diataxis, or chunks for RAG. It does NOT change any output rule; it adds the front door.

## Tool selection (Docling vs MarkItDown)
Pick by fidelity need, not by habit:

| Need | Reach for | Why |
| --- | --- | --- |
| Complex layout, real table structure, formulas, scanned/OCR docs, anything going into a high-fidelity docs migration | **Docling** | Deep document understanding (layout/reading-order/table-structure/OCR); lossless JSON option; air-gapped/local for sensitive source docs |
| Fast bulk conversion of many ordinary office files into LLM-ready Markdown, RAG ingestion, "good enough" structure | **MarkItDown** | Lightweight, broad format coverage (PDF/DOCX/PPTX/XLSX/HTML/CSV/JSON/XML/images/audio/EPub/ZIP/YouTube), Markdown tuned for LLM consumption (explicitly NOT high-fidelity human-facing conversion) |

Both are MIT, both ship an MCP server (docling MCP; markitdown-mcp), both run locally. Default: Docling when fidelity/tables/OCR matter or the source is sensitive; MarkItDown when you need to convert a pile of files quickly into Markdown for a RAG index. They are complementary, not competing - it is fine to MarkItDown a bulk corpus and Docling the handful of table-heavy or scanned pages.

## What each parses
- **Docling**: PDF (advanced - layout, reading order, table structure, code, formulas, image/chart understanding), DOCX, PPTX, XLSX, HTML, images (PNG/TIFF/JPEG) with OCR, audio (WAV/MP3/WebVTT), LaTeX, Markdown, plain text, plus app-specific XML (USPTO/JATS/XBRL). Output: DoclingDocument -> Markdown / HTML / lossless JSON / DocTags. Structured field extraction (beta). Local/air-gapped path for confidential source docs.
- **MarkItDown**: PDF, PowerPoint, Word, Excel, images (EXIF + OCR), audio (EXIF + transcription), HTML, CSV/JSON/XML, ZIP (iterates contents), YouTube URLs, EPub. Output: Markdown optimized for LLM/text-analysis tools (headings/lists/tables/links preserved; not meant for high-fidelity human-facing reproduction).

## The ingestion workflow (the wire into doc production + RAG)
1. **Choose the tool** by the table above (fidelity/tables/OCR/sensitivity -> Docling; bulk LLM-ready -> MarkItDown).
2. **Convert locally.** Sensitive or NDA source material is parsed on-machine (Docling air-gapped path), never a cloud parse.
3. **VERIFY against the source - this is the zero-hallucination protocol applied to ingestion.** A converter is not an oracle: tables can mis-merge, OCR can transpose digits, reading order can scramble multi-column PDFs. Read the converted Markdown back against the original before any of it becomes a published doc or a RAG chunk. Never publish a converted figure/flag/endpoint you have not checked against the source (this is the existing "never guess endpoints/flags/env vars" rule).
4. **Restructure, do not dump.** Converted Markdown is RAW INPUT, not a finished doc. Run it through the Diataxis compass and split mixed-quadrant content; a converted "manual" is usually a tangle of tutorial + how-to + reference that must be separated. The converter gives you clean text; the writer gives it the right shape.
5. **For a docs site / migration**: convert -> verify -> Diataxis re-sort -> rewrite to the per-type contracts -> standard section order -> ship (with an llms.txt/llms-full.txt for agent consumption, per depth-2026-06.md).
6. **For a RAG corpus**: convert -> verify -> chunk on stable, descriptive headings (the same H1-H3 hierarchy + self-contained-section rules that make docs agent-consumable also make clean RAG chunks) -> keep source + heading path as metadata so retrieval can cite. Markdown is the right intermediate because mainstream LLMs natively handle it.

## Boundaries (no duplication across employees)
- Same tools, three different consumers - coordinate the install, do not duplicate it:
  - **delivery-lead** uses Docling for ONE engagement's INTAKE (parse a client's contract/RFP/SOW/scan/spreadsheet to fill project.js + the client-docs bundle) - see its `docling-parsing-layer.md`. That is delivery intake, not docs production.
  - **knowledge-base (meta)** ingests CORPORA into searchable KBs.
  - **technical-writer (here)** ingests SOURCE DOCUMENTS to produce a docs site / migration / docs-RAG corpus.
  Each is a distinct job on a shared tool. Do not re-implement; reference the others' notes for operational detail.
- This file does NOT change any OUTPUT rule (Diataxis contracts, 8-point endpoint contract, README order, runbook six-attribute, changelog, llms.txt). It adds the INPUT/ingestion front door only.

## Honesty / limits (CONNECT)
- Both tools are CONNECT: if neither the host's Docling nor MarkItDown (or their MCP servers) is installed, say so and either install one (`pip install docling` / `pip install markitdown`) or fall back to manual transcription with the gaps flagged as TODO(owner) - never claim a doc was converted when it was not.
- Converters are parsers, not authors. A clean conversion is the start of the writing job, not the end. The output gate is the same as always: every published sample/figure/endpoint verified, readability > 60, AI-ism scrub, white-label check.

## Sources (methodology only; nothing bundled or run)
- docling-project/docling - MIT - 61,598 stars - pushed 2026-06-15 - not archived. Document understanding (layout/tables/formulas/OCR) -> DoclingDocument -> Markdown/JSON; air-gapped local execution; docling MCP server. Library/CLI/MCP NOT installed here.
- microsoft/markitdown - MIT - 153,753 stars - pushed 2026-05-26 - not archived. Lightweight any-file -> LLM-ready Markdown; broad format coverage; markitdown-mcp server. Library/CLI/MCP NOT installed here.
