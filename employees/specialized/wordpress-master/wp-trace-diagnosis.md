# WordPress diagnosis from a trace and config bundle (offline)

Runnable reference: `wp_trace_diag.py` (Python 3.9+, standard library only). It reads one JSON bundle per
site and never runs PHP, WordPress, WP-CLI or a database, and never connects anywhere. Every report carries
`evidence_scope`, which says so and repeats the bundle's own `source` line. The bundles in
`examples/capabilities/G23/` are **synthetic** (invented plugins, queries and timings); a report on them is
not evidence about any real site.

## When to use it
- A client sends a Query Monitor / SAVEQUERIES export, `wp profile` output, a PHP error log, wp-config
  constants or a bisect log, and wants the fault named: plugin conflict, slow or repeated query, or a
  configuration fault.
- Before and after a fix, to decide whether a speedup can be claimed at all.

## Bundle (schema `solaris.wp-trace/1`)
| field | from | notes |
|---|---|---|
| `site`, `environment`, `source` | you | environment is production, staging or local; `source` says where the data came from (required) |
| `env` `{php, wp, host}` | `wp --info`, `wp core version` | must match for a comparison |
| `measurement` `{tool, warm_cache, runs_per_url, concurrency}` | how timings were taken | must match for a comparison |
| `wp_config` | wp-config.php constants | `DB_*`, `*_KEY`, `*_SALT`, passwords and tokens are dropped on read and never echoed |
| `dropins` | `wp-content/*.php` drop-ins | e.g. `advanced-cache.php` |
| `active_plugins` | `wp plugin list --status=active` | slugs |
| `autoload_bytes`, `autoload_top` | `wp option list --autoload=on` | WordPress 6.6 Site Health warns above 800 KB |
| `system_cron` | the server's crontab | true, false or null (unknown) |
| `requests[]` `{id, url, total_ms, peak_memory_mb, queries[], hooks[]}` | Query Monitor / SAVEQUERIES, `wp profile hook` | a query is `{sql, ms, caller, component, source_file, source_line}`; component is `core`, `plugin:<slug>`, `mu-plugin:<slug>`, `theme:<slug>` or `unknown`; `source_file` and `source_line` (optional) say where the record came from, such as `mysql-slow.log` line 1204 or Query Monitor's file:line, and are kept in the report |
| `php_errors[]` | `wp-content/debug.log` or the PHP error log | raw lines |
| `bisect[]` `{plugins, result}` | each activation test, result `fail` or `ok` | the plugin-conflicts binary search, recorded |

Unknown fields, duplicate keys, NaN, booleans as numbers, symlinks, over-deep JSON and files over 64 MiB are
refused (exit 2, nothing written).

## What it reports
| code | evidence |
|---|---|
| `PLUGIN_CONFLICT` | `Cannot redeclare f() (previously declared in A) in B` with A and B in different components; `Cannot declare class X, because the name is already in use in B` (one side named); bisect runs where exactly one pair is in every failing run and in no passing run |
| `PLUGIN_FAULT` | bisect: one plugin in every failing run and in no passing run (it fails alone, not a conflict) |
| `PLUGIN_FAILURE_UNLOCALIZED` | bisect records a failure but several plugins or pairs explain the runs; candidates named, no culprit claimed |
| `PLUGIN_FATAL` | `Call to undefined function` (missing dependency), a function declared twice inside one plugin, or a redeclare whose other declarer is outside `wp-content` (no second component to name) |
| `SLOW_QUERY` | a query shape (strings, numbers and IN lists folded) whose slowest run is at least `--slow-ms` (50, Query Monitor's default), with its component and share of query time; the source file and line of its slowest run (and `sources`, up to 20) when the bundle gives them |
| `REPEATED_QUERY` | the same query shape from one caller at least `--repeat` (10) times in one request: an N+1 loop |
| `SLOW_HOOK_CALLBACK` | a hook callback at least `--slow-hook-ms` (100) |
| `CONFIG_DEBUG_DISPLAY` | production, `WP_DEBUG` true and `WP_DEBUG_DISPLAY` not false (it defaults to true) |
| `CONFIG_SAVEQUERIES` | production with `SAVEQUERIES` on |
| `CONFIG_MEMORY_LIMIT` | an `Allowed memory size ... exhausted` line, or peak memory at 90% of `WP_MEMORY_LIMIT`. The component is `core` (the limit); the line's file is reported as where memory ran out, not as the cause. The finding cites `WP_MEMORY_LIMIT` and says when it is above the size PHP died at (PHP's own `memory_limit` caps it) |
| `CONFIG_CACHE_DROPIN_MISSING` / `CONFIG_CACHE_DISABLED` | `WP_CACHE` true without `advanced-cache.php`, or the drop-in present with `WP_CACHE` not true (only the JSON value `true` counts; `"true"` and `1` do not) |
| `CONFIG_CRON_NOT_RUNNING` | `DISABLE_WP_CRON` true and `system_cron` false (null is noted, not judged) |
| `CONFIG_AUTOLOAD_BLOAT` | `autoload_bytes` above 800000, with the largest options |

Exit codes: 0 healthy, 1 faults found, 2 invalid input. Thresholds are flags, and the report records them.

## Speedup claims (`compare BEFORE AFTER`)
A speedup is claimed only from the same measurements: same site, environment, `env`, `measurement`, the same
URLs, the same sample count per URL and at least 5 samples each. Otherwise the answer is "not comparable"
(exit 3) with the reasons, and no speedup. When comparable, each URL reports both medians and is "faster" only
if every after-sample beats every before-sample; overlapping ranges are "inconclusive". The overall claim
needs every URL faster.

## Commands
    python3 wp_trace_diag.py diagnose bundle.json [--json] [--out report.json]
    python3 wp_trace_diag.py compare before.json after.json [--json] [--out report.json]

`--out` writes the JSON report atomically, refuses to overwrite an input, a symlink or a folder, needs its
folder to exist (exit 2 otherwise), and an invalid run leaves the previous report as it was. Stdout is JSON
with `--json`, with or without `--out`; `--out` alone prints the text summary.

## Limits (stated, not hidden)
- No WordPress, PHP, WP-CLI or database was available or run on the build host. The detection rules were
  checked against synthetic bundles only; message formats follow PHP 8 error text and the documented
  Query Monitor, `wp profile` and wp-config conventions.
- JavaScript, CSS, REST route and hook-priority conflicts are not visible in this bundle format; use the
  plugin-conflicts guide's browser and REST steps for them.
- Bisect localization assumes the fault is deterministic and caused by one plugin or one pair.
- A class clash names only the second declarer; run bisect for the first.
- Attribution comes only from the bundle's `component` and `caller` fields, that is from Query Monitor or
  `wp profile`. A MySQL slow log has neither, so its queries are `unknown`: the finding says it is not tied
  to a plugin and keeps `source_file:source_line` so you can find the entry; it never guesses a plugin from
  the SQL. Response headers and wp-config line numbers have no field.
- `total_ms` is required per request; slow-log-only data needs a stated stand-in (for example the sum of
  its query times), and `source` should say which.
- A memory-exhausted line shows where PHP ran out, not what used the memory; profile the failing request
  before blaming the plugin in that line.

Evidence: `examples/capabilities/G23/` (oracle, stubs, fixtures) and `tests/test_g23_capability.py`.
