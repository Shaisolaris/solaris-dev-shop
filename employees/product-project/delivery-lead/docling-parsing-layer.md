# Docling - the document-parsing layer feeding doc generation

Source: docling-project/docling (verified live 2026-06-13: MIT, 61,489★, last push 2026-06-13; LF AI & Data project, started at IBM Research). CONNECT - has an official MCP server; the host runs it. This file is how Delivery Lead uses it.

## Why it exists here (the gap it closes)
Delivery Lead already owns the OUTPUT side: the client-docs bundle (project.js + Doc 1-8 const blocks: SOW/PLAN/INVOICE/RECEIPT/REPORT/CR), the registry, the interview protocol, STATUS.md routing. What it lacked was the INPUT side: turning the messy inbound materials a client sends (a PDF contract, an RFP, a scanned brief, an XLSX price list, a DOCX scope) into structured data WITHOUT manual transcription. Docling is that parsing layer. It feeds `project.js` and the doc bundle instead of a human re-typing fields.

## What Docling parses (real capabilities)
- Formats: **PDF, DOCX, PPTX, XLSX, HTML, images (PNG/TIFF/JPEG), audio (WAV/MP3/WebVTT), LaTeX, Markdown, plain text** + app-specific XML (USPTO patents, JATS, XBRL financial reports).
- **Advanced PDF understanding:** page layout, reading order, **table structure**, code, formulas, image classification, chart understanding (bar/pie/line -> tables).
- **OCR** for scanned PDFs/images (the scanned-brief case).
- Output: a unified **DoclingDocument** -> export to **Markdown / HTML / JSON (lossless) / DocTags**.
- **Structured information extraction** (beta) - pull named fields out of a document.
- **Local / air-gapped execution** - critical for NDA/contract intake (data never leaves the machine).

## How the host connects it
- Quick: `pip install docling`, then CLI `docling <file-or-url>` -> Markdown in the cwd.
- Python: `from docling.document_converter import DocumentConverter; DocumentConverter().convert(src).document.export_to_markdown()`.
- MCP: Docling ships an **MCP server** (docs: docling-project.github.io/docling/usage/mcp/) - host runs it so the coding agent can parse in-session.
- VLM pipeline for hard docs: `docling --pipeline vlm --vlm-model granite_docling <file>`.

## How Delivery Lead uses it (the wire into doc generation)
1. **Intake.** Client sends a contract/RFP/SOW/scan/spreadsheet. Run it through Docling -> Markdown/JSON (+ tables). Sensitive doc -> local pipeline, never cloud.
2. **Extract the fields, then VERIFY.** Pull the project facts (client name, scope items, dates, amounts, deliverables, line items) from the parsed output. Docling is a parser, not an oracle - read the structured output back against the source before trusting a number into a contract/invoice. (This is the existing "Verify before you claim" rule applied to parsing.)
3. **Fill, don't retype.** Populate `project.js` (persistent fields) and the relevant Doc const block from the extracted data, per templates/client-docs/field-maps/FIELD-MAP.md. The badge must still go green; the drop-rules still decide which docs apply.
4. **Tables -> structured.** A price list / BOQ in a client XLSX/PDF parses to a table -> line items in the SOW/invoice, not hand-keyed.
5. **Route + register as usual.** Output still flows through STATUS.md + the registry (register-doc.py) BEFORE sending. Docling changed the INPUT, not the output discipline.

## Boundaries (no duplication)
- Docling does NOT replace the doc-generation bundle, the registry, or the interview protocol - those are unchanged. Docling only replaces *manual transcription of inbound documents*.
- The interview protocol still runs for the GAPS: parse what the documents give, then ask only what's missing (one batched round), exactly as today's "READ BEFORE ASKING" rule says - now "read" includes "parse the inbound docs first."
- knowledge-base (meta) also uses Docling for KB ingestion. Same tool, different consumer: Delivery Lead parses ONE engagement's intake into the doc workflow; knowledge-base ingests corpora into searchable KBs. Coordinate the Docling install; don't duplicate it.

## Honesty / limits
- Docling parses; it can misread a bad scan or an unusual table. Always verify extracted figures against the source before they enter a client-facing doc.
- It is CONNECT: if the host hasn't installed Docling / its MCP, say so and either install it (pip) or fall back to the manual interview - don't claim a doc was parsed when it wasn't.
