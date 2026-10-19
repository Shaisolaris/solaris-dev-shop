"""M23 prep: exact single-occurrence mutants of the Grok reference diagnostic stub (Grok self-validation)."""
import json, os
here = os.path.dirname(os.path.abspath(__file__)); stubs = os.path.join(here, "..", "stubs")
src = open(os.path.join(stubs, "reference_diag.py")).read()
M = [
 ("slow_by_count", ["K2_slow_query_custom_table"], [("tbl = max(agg, key=lambda k: (max(agg[k]), sum(agg[k])))", "tbl = max(agg, key=lambda k: len(agg[k]))")]),
 ("slug_shortest_any", ["X4_slug_substring_trap"], [('cands = [p for p in active if tbl.startswith("wp_" + p.replace("-", "_"))]',
                                                     'cands = [p.get("name") for p in plist if tbl.startswith("wp_" + p.get("name").split("-")[0])]'),
                                                    ("owner = max(cands, key=len)", "owner = cands[0]")]),
 ("memory_blames_plugin", ["K3_config_memory_limit"], [('F("CONFIG-MEMORY", "Critical", "Configuration", f"WP_MEMORY_LIMIT {v} exhausted",',
                                                        'F("FATAL", "Critical", "Fatal error", f"Fatal error in {m.group(2).split(\'/plugins/\')[-1].split(\'/\')[0]}",')]),
 ("speedup_ignores_cache", ["X2_speedup_not_comparable"], [("if st[\"before\"] != st[\"after\"] or len(st[\"before\"]) != 1:", "if False:")]),
 ("wp_cache_always", ["C1_control_cache_ok"], [('if defs.get("WP_CACHE", ("false",))[0] == "true" and rd("wp-content/advanced-cache.php") is None:',
                                               'if defs.get("WP_CACHE", ("false",))[0] == "true":')]),
 ("historical_as_active", ["X5_historical_fatal_removed_plugin"], [("if s and s.group(1) not in active:", "if False:")]),
 ("redeclare_one_side", ["K1_conflict_redeclare"], [('f"Function {m.group(1)}() declared by both {a} and {c}",', 'f"Function {m.group(1)}() conflict in {c}",'),
                                                    ('f"{m.group(2).split(\'/wp-content/\')[-1]}:{m.group(3)}"', 'f"line {m.group(3)}"')]),
 ("qm_ignored", ["K5_slow_query_theme_qm"], [('    if top["time"] >= 0.5:', '    if False:')]),
 ("qm_threshold_low", ["C0_control_clean"], [('    if top["time"] >= 0.5:', '    if top["time"] >= 0.01:')]),
 ("crash_on_bad_json", ["X6_malformed_inputs"], [('try:\n    plist = json.loads(rd("plugins.json") or "[]")\nexcept ValueError:\n    plist = []; F(',
                                                  'if True:\n    plist = json.loads(rd("plugins.json") or "[]")\nif False:\n    plist = []; F(')]),
 ("fabricated_timing", ["X7_no_runtime_data"], [('"No runtime timing evidence in bundle; runtime profiling needs WP-CLI profile on a disposable site", "", "")',
                                                 '"Estimated bootstrap 420 ms; runtime profiling needs WP-CLI profile on a disposable site", "", "")')]),
 ("mean_instead_of_median", [], [("statistics.median(float(r[\"ttfb_ms\"])", "statistics.mean(float(r[\"ttfb_ms\"])")]),  # control: 2.01x is accepted (same measurements)
]
os.makedirs(os.path.join(stubs, "mutants"), exist_ok=True)
plan = []
for name, kills, edits in M:
    s = src
    for a, b in edits:
        assert s.count(a) == 1, (name, a[:60], s.count(a))
        s = s.replace(a, b)
    open(os.path.join(stubs, "mutants", f"{name}.py"), "w").write(s)
    bnd = json.load(open(os.path.join(stubs, "binding-reference.json")))
    bnd["name"] = f"mutant:{name} (of Grok reference)"; bnd["cmd"] = ["/usr/bin/python3", "{binding_dir}/" + f"{name}.py", "{bundle}"]
    json.dump(bnd, open(os.path.join(stubs, "mutants", f"binding-{name}.json"), "w"), indent=1)
    plan.append({"mutant": name, "expected_killers": kills})
json.dump(plan, open(os.path.join(stubs, "mutants", "plan.json"), "w"), indent=1)
print(len(plan), "mutants written")
