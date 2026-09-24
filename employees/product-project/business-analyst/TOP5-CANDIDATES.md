# Business Analyst - TOP-5 verified 2026 source scan (2026-06-13)

Domain: requirements / process mapping / BPMN / diagrams / feasibility / project economics.

| # | Source | Stars | License | Last commit | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|-------|---------|-------------|------------|--------------|--------|-----|
| 1 | github.com/jtlicardo/bpmn-assistant | 140 | MIT | 2026-04-29 | jtlicardo | LLM tool to CREATE/EDIT/INTERPRET BPMN; the INTERPRET path (read a client's existing BPMN XML and explain the process) is net-new | PASS (narrow) - BA owned BPMN authoring + mermaid render but NOT reverse-interpretation of a supplied BPMN diagram | METHODOLOGY/CONNECT (interpret-existing-BPMN slice only) |
| 2 | github.com/sartography/SpiffWorkflow | 1,900 | LGPL-3.0 (FLAG) | 2026-06-11 | sartography | BPMN 2.0 EXECUTION engine (run a process model as code) | REJECT for BA - executable workflow engineering, not BA requirements/mapping methodology; LGPL; belongs to engineering if anywhere | REJECT (out of domain + LGPL) |
| 3 | github.com/hustcc/mcp-mermaid | (100+) | MIT | recent | hustcc | Mermaid render of any diagram type | CONTENT-DUPLICATE (already absorbed -> diagram-generation-tooling.md) | (absorbed) |
| 4 | github.com/alirezarezvani/claude-skills (process-mapper + bpmn_essentials) | 17,992 | MIT | 2026-06-12 | alirezarezvani | as-is/to-be, bottleneck anti-patterns, BPMN essentials | CONTENT-DUPLICATE (absorbed) | (absorbed) |
| 5 | awesome-bpmn / awesome-bpm lists; imixs/open-bpmn modeler | mixed | mixed/EPL | mixed | various | tool indexes + a desktop modeler | LIST/TOOL - no transferable BA methodology; modeler is a GUI app, not absorbable | REJECT |

## Verdict
The BA is already deep (full BPMN Silver method-and-style + as-is/to-be + bottleneck rules + mermaid rendering). The only narrow net-new is **jtlicardo/bpmn-assistant (140 MIT)**: its INTERPRET capability - read a client's EXISTING BPMN XML and explain/critique the process - covers a gap (the BA could author + render but not reverse-read a supplied diagram). Absorbed as a short methodology/CONNECT slice. SpiffWorkflow (1,900, LGPL) is a process-EXECUTION engine - out of BA's domain (engineering territory) and LGPL-flagged - rejected. mcp-mermaid + alirezarezvani process-mapper are content-duplicates already absorbed. No forced absorption.
