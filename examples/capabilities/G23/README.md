# G23 - WordPress diagnostics from a trace and config bundle (synthetic fixtures only)

Everything here is synthetic. `make_fixtures.py` wrote every bundle in `fixtures/` (invented plugins
acme-* and shop-*, invented queries, timings and log lines); none was captured from a real site. No
WordPress, PHP, WP-CLI or database was installed or run on the build host, and the tool never runs one.
Every report states this in `evidence_scope`.

| file | what it is |
|---|---|
| `wp_oracle.py` | black-box oracle, 12 checks, its own generated synthetic bundles |
| `noop_stub.py` | finds nothing and claims every comparison as a speedup; must fail |
| `naive_stub.py` | flags each query over 50 ms, ignores config, logs and bisect, compares means unchecked; must fail |
| `make_fixtures.py` | writes `fixtures/` deterministically |
| `fixtures/01-clean-control.json` | healthy production config and fast requests: exit 0, no findings |
| `fixtures/02-plugin-conflict.json` | a `Cannot redeclare` fatal between acme-seo and acme-forms, and bisect runs that agree: one PLUGIN_CONFLICT |
| `fixtures/03-slow-and-repeated-query.json` | a 420 ms meta LIKE query and a 40-lookup loop, both from shop-filters |
| `fixtures/04-config-faults.json` | debug display in production, cache drop-in missing, cron off with no system cron, 1.65 MB autoload |
| `fixtures/05-before.json`, `06-after-same-measurements.json` | same measurement set: speedup claimed per URL |
| `fixtures/07-after-different-measurements.json` | cold cache and 5 samples instead of 7: not comparable, no claim |
| `fixtures/08-bisect-ambiguous.json` | a failure the bisect runs do not single out: unlocalized, candidates named |

## Run

    T="python3 employees/specialized/wordpress-master/wp_trace_diag.py"
    $T diagnose examples/capabilities/G23/fixtures/02-plugin-conflict.json
    $T compare examples/capabilities/G23/fixtures/05-before.json examples/capabilities/G23/fixtures/06-after-same-measurements.json
    python3 examples/capabilities/G23/wp_oracle.py --tool "$T"
    python3 -m unittest tests.test_g23_capability

## Oracle checks
o1 clean control; o2 redeclare (both PHP spellings) and class clash; o3 bisect: unique pair, lone culprit,
ambiguity, all-pass; o4 slow query by component and threshold; o5 N+1 against a few repeats; o6 each config
fault alone, valid look-alikes clean, a memory-exhausted line blamed on the limit (core) with the configured value cited, not on the allocating plugin (r2); o7 same-measurement speedup from the samples' medians, overlap claims
nothing; o8 five kinds of mismatched measurements and too few samples; o9 invalid bundles, report kept,
recovery, `--out` onto a symlink or into a missing folder refused, `--json` with `--out` printing the same JSON (r2); o10 secrets never echoed; o11 3000 requests, order irrelevant; o12 unseen random fault mixes.

r2 (M23 self-validation): queries may carry `source_file` and `source_line` (for example a MySQL slow-log
entry), kept in the finding's evidence and `sources`; `tests/test_g23_capability.py` class `M23Rework` pins the
nine documented rules (5 samples, 50 ms, 100 ms, 90%, WP_CACHE true only, autoload over 800000, same site,
ties inconclusive and every URL faster, `--out` folder must exist).

Not covered: real WordPress output (no installation here), JavaScript or CSS conflicts, REST route clashes.
