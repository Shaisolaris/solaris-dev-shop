# Notebook-driven ML workflow (Jupyter MCP)

Absorbed from datalayer/jupyter-mcp-server (BSD 3-Clause, ~1.2k★, by Datalayer, verified 2026-06-13) - the real-time notebook control *methodology*. The MCP server is host-installed (`uvx jupyter-mcp-server@latest` or Docker `datalayer/jupyter-mcp-server`) against a running JupyterLab; this file is how the ML engineer works through it. BSD = permissive; patterns distilled, server not vendored.

## Why drive a live notebook instead of writing one big script
ML is iterative and stateful: load data once, then explore / clean / feature-engineer / train / evaluate against that loaded state, reacting to each cell's output (including plots and images). A live kernel keeps state between steps so you don't re-run a 10-minute data load to try one new feature. The MCP gives **real-time, cell-level control of a running kernel with output feedback** - the right granularity for this loop.

## Core loop: execute → read output → adjust
The defining feature is **smart execution with output feedback** - run a cell, read its real output (errors, values, AND rendered images/plots), and adjust the next step based on what actually happened, not what you assumed would happen. Always read the output before writing the next cell. If a cell errors, fix from the traceback in the output, don't blindly re-emit.

## Working rules
- **One concern per cell.** Insert focused cells (`insert_cell` / `insert_execute_code_cell`) - data load, cleaning, a single feature, the fit, the eval - so each is independently re-runnable and the failure surface is one cell, not the whole script. Mirrors the "break the DS workflow into sub-tasks" best practice.
- **Surgical edits over rewrites.** Use `edit_cell_source` (find-and-replace) to tweak an existing cell rather than `overwrite_cell_source`-ing the whole thing - keeps diffs small and kernel state intact.
- **Read before you write.** `read_notebook` (brief) for structure, `read_cell` for the full source+output of a specific cell, before inserting or editing - know the current state and what's already imported/loaded.
- **Keep the kernel honest.** `restart_notebook` when state gets polluted (stale variables, half-failed imports) and re-run from a clean top; don't debug ghosts in a dirty kernel. `run-all-cells` to verify the notebook is reproducible top-to-bottom before handoff.
- **Multimodal is the point.** Set `ALLOW_IMG_OUTPUT=true` and use a multimodal model so plots/confusion-matrices/sample images come back as images you can actually read - that's how you evaluate a model's behavior, not just its scalar metrics.
- **Multi-notebook:** `use_notebook` to create/switch/connect notebooks; keep exploration and the clean final notebook separate.
- **Context the kernel can't infer:** tell the model installed packages, dataset field meanings, cwd, and the concrete task up front (best-practice from the source) - the notebook doesn't carry that.

## Handoff / reproducibility
Before calling a notebook done: restart kernel, run-all-cells, confirm it executes clean end-to-end. A notebook that only works because of out-of-order cell state is a bug, not a deliverable.

## Host setup note
Needs JupyterLab 4.4+ with `jupyter-collaboration` + `pycrdt` (real-time collaboration is required for the MCP to see live changes), started with a token; MCP client gets `JUPYTER_URL` + `JUPYTER_TOKEN`. v1.0.0+ also requires `MCP_TOKEN` in the client config.
