# Excel reporting + delivery (excel-mcp-server)

Absorbed from haris-musa/excel-mcp-server (MIT, ~3.9k stars, commit main @ 2026-06-13). Net-new for data-analyst: native .xlsx authoring/reading WITHOUT Microsoft Excel installed (openpyxl-backed). The analyst already does SQL + dashboards; this closes the "deliver it as the spreadsheet the stakeholder actually opens" gap - most business stakeholders live in Excel, not in a BI tool.

## When to use
- A stakeholder wants the numbers AS an .xlsx (recurring report, ad-hoc cut, model handoff), not a dashboard link.
- Reading an inbound client .xlsx into analysis (read first, validate, THEN analyze - see the existing data-quality gate).
- Building a formatted, formula-driven workbook (pivot + chart + conditional formatting) as a deliverable.

## Tool map (the workbook authoring loop)
- **Workbook/sheet:** `create_workbook`, `create_worksheet`, `get_workbook_metadata` (with `include_ranges`), copy/rename/delete worksheets.
- **Data I/O:** `write_data_to_excel` (list-of-dicts → range), `read_data_from_excel` (range → data). Read inbound files here before any analysis.
- **Formulas:** `apply_formula`, and ALWAYS `validate_formula_syntax` first - validate before writing so a bad formula doesn't silently land as text or #ERROR.
- **Formatting:** `format_range` (font/colour/border/alignment + conditional formatting), `merge_cells`/`unmerge_cells`/`get_merged_cells`.
- **Structured output:** `create_table` (named Excel table with styling), `create_pivot_table` (data_range → pivot for analysis), `create_chart` (line/bar/pie/scatter/area at a target cell).

## Doctrine (keep the analyst's existing rigor)
- Reading a client spreadsheet runs the existing data-quality gate FIRST (types, nulls, dupes, units) - Excel hides dirty data behind formatting; don't trust a clean-looking sheet.
- `validate_formula_syntax` before `apply_formula`, always. A wrong formula in a stakeholder deliverable is worse than no formula.
- Numbers in the workbook trace to the same source-of-truth query as any dashboard - the .xlsx is a presentation surface, not a second source of truth. Don't let an Excel export drift from the canonical metric definition.
- Label every sheet: source query/date, refresh cadence, owner - same discipline as a dashboard.

## CONNECT note (host installs)
Host installs `uvx excel-mcp-server stdio` (local use; filepath passed per call). For SSE/streamable-HTTP transports the server needs `EXCEL_FILES_PATH` and tool `filepath`s become relative to it (absolute paths + directory traversal are rejected - a safety feature; respect it). Stdio is the default for local analyst work.
