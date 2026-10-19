#!/usr/bin/env python3
"""M23 r1 mutants of G23 wp_trace_diag.py (Grok self-validation). Each is an exact single-occurrence replacement;
the anchor count is asserted to be 1. _EQUIV names a control expected to survive."""
M = [
 ("min_samples_4", "MIN_SAMPLES = 5", "MIN_SAMPLES = 4"),
 ("secret_re_no_key", "(^DB_|PASSWORD|_KEY|_SALT", "(^DB_|PASSWORD|_SALT"),
 ("nan_allowed", "object_pairs_hook=_no_dupes, parse_constant=_no_const)", "object_pairs_hook=_no_dupes)"),
 ("dupes_allowed", "json.loads(text, object_pairs_hook=_no_dupes, ", "json.loads(text, "),
 ("bool_as_number", "if isinstance(v, bool) or not isinstance(v, (int, float))", "if not isinstance(v, (int, float))"),
 ("symlink_allowed", "if path.is_symlink() or not path.is_file():", "if not path.is_file():"),
 ("env_unchecked", 'if b["environment"] not in ENVIRONMENTS:', "if False:"),
 ("redeclare_same_comp", 'if a != c and "unknown" not in (a, c):', 'if "unknown" not in (a, c):'),
 ("bisect_single_inverted", "singles = [(p,) for p in sorted(common) if not any(p in o for o in oks)]", "singles = [(p,) for p in sorted(common) if any(p in o for o in oks)]"),
 ("bisect_pair_or", "if not any(a in o and b in o for o in oks)]", "if not any(a in o or b in o for o in oks)]"),
 ("repeat_gt", "if n >= repeat:", "if n > repeat:"),
 ("slow_gt", 'if g["max"] >= slow_ms:', 'if g["max"] > slow_ms:'),
 ("hook_gt", "if max(ms) >= slow_hook_ms:", "if max(ms) > slow_hook_ms:"),
 ("debug_display_default_false", 'debug_display = cfg.get("WP_DEBUG_DISPLAY", True)', 'debug_display = cfg.get("WP_DEBUG_DISPLAY", False)'),
 ("debug_any_env", 'if prod and cfg.get("WP_DEBUG") is True', 'if cfg.get("WP_DEBUG") is True'),
 ("savequeries_any_env", 'if prod and cfg.get("SAVEQUERIES") is True:', 'if cfg.get("SAVEQUERIES") is True:'),
 ("mem_warn_95", "MEMORY_WARN = 0.9 ", "MEMORY_WARN = 0.95 "),
 ("cache_disabled_only_false", 'if adv and cfg.get("WP_CACHE") is not True:', 'if adv and cfg.get("WP_CACHE") is False:'),
 ("cron_null_judged", 'if b["system_cron"] is False:', 'if b["system_cron"] is not True:'),
 ("autoload_ge", 'b["autoload_bytes"] > AUTOLOAD_WARN:', 'b["autoload_bytes"] >= AUTOLOAD_WARN:'),
 ("cmp_no_measurement", 'for k in ("site", "environment", "env", "measurement"):', 'for k in ("site", "environment", "env"):'),
 ("cmp_no_site", 'for k in ("site", "environment", "env", "measurement"):', 'for k in ("environment", "env", "measurement"):'),
 ("cmp_no_env", 'for k in ("site", "environment", "env", "measurement"):', 'for k in ("site", "environment", "measurement"):'),
 ("cmp_url_sets", "if sorted(sa) != sorted(sb):", "if False:"),
 ("cmp_sample_count", "if len(sa[u]) != len(sb[u]):", "if False:"),
 ("cmp_min_2", "elif len(sa[u]) < MIN_SAMPLES:", "elif len(sa[u]) < 2:"),
 ("cmp_le", "consistent = y[-1] < x[0]", "consistent = y[-1] <= x[0]"),
 ("cmp_median", "consistent = y[-1] < x[0]", "consistent = y[len(y) // 2] < x[len(x) // 2]"),
 ("cmp_claim_any", 'all(u["result"] == "faster" for u in urls)', 'any(u["result"] == "faster" for u in urls)'),
 ("out_overwrite_input", "if _same(out, p) or fold(out) == fold(p):", "if False:"),
 ("out_folder_unchecked", "if not out.parent.is_dir():", "if False:"),
 ("out_symlink_allowed", "if out.is_symlink() or (out.exists() and not out.is_file()):", "if out.exists() and not out.is_file():"),
 ("component_no_unknown", "^(core|unknown|(plugin", "^(core|(plugin"),
 ("secret_kept", "secrets_seen.append(k)     # never stored, never echoed\n            continue", "secrets_seen.append(k)     # never stored, never echoed"),
 ("pair_skip_unknown_side", '"unknown" not in (a, c)', "True"),
 ("slow_share_high", 'severity_dummy', 'severity_dummy'),
 ("atomic_rename_EQUIV", "os.replace(tmp, path)", "os.rename(tmp, path)"),
]
M = [m for m in M if m[0] != "slow_share_high"]


def apply(src, old, new):
    assert src.count(old) == 1, (old, src.count(old))
    return src.replace(old, new)
