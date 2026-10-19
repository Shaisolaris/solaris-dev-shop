#!/usr/bin/env python3
"""M23 r2 mutants (Grok self-validation): every r1 mutant whose anchor still occurs exactly once in the r2 tool,
plus Grok's own r2_* mutants on S1, S2, S4, S5. Exact single-occurrence anchors; _EQUIV is a control."""
import make_mutants_g23 as R1
SRC = open("/tmp/m23r2-eval/employees/specialized/wordpress-master/wp_trace_diag.py").read()
R2 = [
 ("r2_mem_comp_where", '["core"], detail, evidence, fix))', '[where], detail, evidence, fix))'),
 ("r2_mem_gt_ge", "if limit > lim:", "if limit >= lim:"),
 ("r2_mem_eq_off", "elif limit == lim:", "elif False:"),
 ("r2_mem_no_ev", "evidence.append(f\"WP_MEMORY_LIMIT={cfg['WP_MEMORY_LIMIT']}\")", "pass"),
 ("r2_mem_missing_msg", 'if "WP_MEMORY_LIMIT" not in cfg:\n            detail', 'if False:\n            detail'),
 ("r2_size_case", r'"\s*(\d+)\s*([KMG]?)\s*", v, re.I)', r'"\s*(\d+)\s*([KMG]?)\s*", v)'),
 ("r2_size_G_1000", '"G": 1024 ** 3}', '"G": 1000 ** 3}'),
 ("r2_src_newline", 'any(c in f for c in "\\n\\r\\t")', 'any(c in f for c in "\\r\\t")'),
 ("r2_src_257", 'f"{where}.source_file", 256)', 'f"{where}.source_file", 257)'),
 ("r2_src_line_0", "f'{where}.source_line', 1, 1e9)", "f'{where}.source_line', 0, 1e9)"),
 ("r2_src_line_1e10", "f'{where}.source_line', 1, 1e9)", "f'{where}.source_line', 1, 1e10)"),
 ("r2_line_needs_file_off", 'if "source_line" in q and "source_file" not in q:', "if False:"),
 ("r2_slowest_ge", 'q["ms"] > g["max"]:', 'q["ms"] >= g["max"]:'),
 ("r2_slowest_first_only", 'if g["slowest"] is None or q["ms"] > g["max"]:', 'if g["slowest"] is None:'),
 ("r2_sources_cap_10", 'len(g["sources"]) < 50', 'len(g["sources"]) < 10'),
 ("r2_not_tied_off", 'g["components"] == {"unknown"} and not g["callers"]', "False"),
 ("r2_src_ev_drop", "src = ([f\"source {g['slowest']}\"]", "src = [] and ([f\"source {g['slowest']}\"]"),
 ("r2_json_out_text", 'print(data if a.json else render(rep), end="")', 'print(render(rep) if a.out else data if a.json else render(rep), end="")'),
 ("r2_outside_other_a", 'other = c if a == "unknown" else a', "other = a"),
 ("r2_text_sources_off", 'if f.get("sources"):  # M23 S2', "if False:"),
 ("r2_text_more_6", '> 5 else ""', '> 6 else ""'),
]
M, SKIPPED = [], []
for m in R1.M + R2:
    (M if SRC.count(m[1]) == 1 else SKIPPED).append(m)
if __name__ == "__main__":
    print(len(M), "usable;", "skipped:", [(m[0], SRC.count(m[1])) for m in SKIPPED])

apply = R1.apply
