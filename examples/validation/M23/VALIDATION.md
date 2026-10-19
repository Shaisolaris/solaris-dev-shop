# M23 r1: Grok self-validation of G23 (offline WordPress trace and config diagnosis)

Label: Grok self-validation. This is not independent review. The same programme produced the candidate and this check.

- Candidate: branch review/grok-g23-wp-trace-diagnosis, commit d6be00e9fcfb1b15f047df096a27073e4b2b8e42 (base 02ba9c5).
- Binding: the handback MANIFEST.sha256 checks 23/23, and its file set equals the diff set. G23.patch is not byte-identical to `git diff`, but `git apply --index` on the base gives tree cd21776815d53c87be4fe4cda8a9197cf70f3f2b, which equals the d6be00e tree (raw/binding-verify.txt).
- Fetched 19:48:23 PT. Pass run 19:48 to 20:25 PT on 2026-10-18.
- Interpreters: 3.9.6 (/usr/bin/python3), 3.11.16 and 3.13.15 (uv), and 3.12.14 (packaging venv).
- The candidate was not modified. No WordPress, PHP, WP-CLI or database exists here. Like the candidate's own evidence, everything is synthetic.

## Verdict: PASS with residuals (no P1 or P2)

This verdict rests on the native-schema probes, the builder evidence reproduced, teeth and the fresh caller.

The pre-registered prep oracle, written before G23 existed and for raw-file bundles, scores core 5/8 (FAIL). Each of its 3 core misses is adjudicated below:
- One is a real P3 (S1).
- Two come from the documented bundle schema not carrying the evidence the prep oracle asks for (S2).

The owner may weigh these differently. Nothing was hidden or re-scored.

Acceptance, item by item:
- **Known fault localised from trace/config: met.**
  - Conflicts are localised from log and from bisect (N01 to N09).
  - Config faults are found (N14 to N19).
  - A QM-attributed slow query names theme:solaris-child, its caller and 2480 ms (K5).
  - Memory faults are found but misattributed (S1).
- **Valid control unflagged: met.** N20 exits 0 with no findings, and prep controls C0 and C1 PASS.
- **Speedup from the same measurements only: met.** P01 to P16 pass on 4 interpreters:
  - site, environment, env, measurement, URL set, sample count and the 5-sample minimum are all enforced;
  - "faster" needs strictly disjoint ranges, with ties counting as inconclusive;
  - an overall claim needs every URL faster.
- **No fabricated WP installation: met.** Every report states "offline analysis ... no PHP, WordPress, WP-CLI or database was run" and carries the bundle's source text. The "Limits" section states the remaining runtime dependency.

## Results
| instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| builder suite (unittest discover) | 107 OK | 107 OK | 107 OK | 107 OK |
| builder wp_oracle: candidate / noop / naive | 12/12, 2/12, 1/12 | same | same | same |
| M23 r1 native probes (m23r1_probes.py, 61) | 58/61 | 58/61 | 58/61 | 58/61 |
| M23 prep oracle via g23_adapter (core 8) | 5/8 | 5/8 | 5/8 | 5/8 |

- **Original tests preserved:** 107 - 23 new = 84. The only test file the diff touches is the new tests/test_g23_capability.py.
- **Discrimination on the builder stubs (3.9.6):**
  - native probes: noop 4/61, naive 8/61;
  - prep oracle: noop 3/8, naive 3/8.
- **Probe failures**, identical on every interpreter: N21, N22 (S1) and O01b (S4).
- **Fresh caller** (m23_fresh_caller_g23.sh, results/fresh-3.9.6):
  - setup: env -i, a new HOME, a python3 shim, an offline socket guard, and only the doc's commands, transcribed by hand;
  - all 6 hand-written expectations were met: text and --json diagnose, --out, refusal to overwrite an input, a comparable compare (exit 0, claimed), and a warm-cache mismatch (exit 3, no claim).
  - The `[exit 0]` on the --out line belongs to my chained read-back command. The tool's own exit there is 1, as shown by probe O01a.

## Teeth (3.9.6; 35 mutants plus 1 _EQUIV control; oracle/make_mutants_g23.py)
Each mutant is an exact single-occurrence anchor, with the count asserted to be 1. A kill is any deviation from the unmutated candidate's own baseline on that instrument.

**Kills by instrument:**
- native probes 29/35
- prep oracle 0/35
- builder G23 tests 22/35
- builder oracle 15/35
- builder total 22/35, Grok total 29/35, union 31/35

The `atomic_rename_EQUIV` control survived, as expected. The builder G23 test file stands in for the full suite because it is the only test file that references the module.

**Survivors** (results/survivor-distinguish-3.9.6.txt):
- `nan_allowed`: contract-equivalent. NaN is still refused with exit 2 in all 4 numeric field kinds by the range check, so only the message differs.
- `out_symlink_allowed`: non-equivalent. With --out as a symlink, the candidate exits 2 and the mutant exits 0 and replaces the link. The doc is silent on this.
- `component_no_unknown`: non-equivalent. With the documented component "unknown", the candidate exits 1 (SLOW_QUERY) and the mutant exits 2.
- `pair_skip_unknown_side`: non-equivalent. When the first declarer is outside wp-content, the candidate gives PLUGIN_FATAL and the mutant gives PLUGIN_CONFLICT.

**Killed only by Grok** (builder test gaps, S3): min_samples_4, slow_gt, hook_gt, mem_warn_95, cache_disabled_only_false, autoload_ge, cmp_no_site, cmp_le, out_folder_unchecked.

**Killed only by builder:** secret_re_no_key and secret_kept. My E01 sees no echo either way, so these protections are pinned only by the builder tests.

## Findings
**S1 (P3), memory exhaustion is blamed on the allocating component, not the config.**
- On an `Allowed memory size ... exhausted` line, CONFIG_MEMORY_LIMIT names only the plugin that made the last allocation as its component ("last allocation in plugin:media-tools"). It never cites or compares the configured `WP_MEMORY_LIMIT`, even though the bundle carries it.
- Evidence:
  - K3: WP_MEMORY_LIMIT '32M', and the decoy plugin is blamed.
  - N21: no core or config component.
  - N22: the configured value is 256M while PHP died at 32 MiB, a php memory_limit cap. The mismatch, which is the actual root cause there, is not surfaced.
- The code, the 32 MiB and the fix text ("raise WP_MEMORY_LIMIT ... only after checking why that component needs it") are right, so this is P3, not P2.
- Suggested direction, not a patch: add core/config to the components, cite the configured value, and add a note when the configured limit is greater than the exhausted size.

**S2 (P3), the bundle schema drops evidence that raw sources hold, and the doc's Limits section does not say so.**
- With honest transcription (oracle/g23_adapter.py):
  - a MySQL slow-log entry has no caller, so its component is "unknown". The candidate reports the right query, table and 3912 ms against "unknown" (K2, X4), which is correct and not fabricated, but nothing is localised to a plugin;
  - QM `location` file:line, wp-config line numbers and response headers have no field, so K5 cannot cite related.php:58 and X1 cache headers are not visible;
  - a request's total_ms is required, so QM or slow-log-only data needs a stated stand-in (the adapter uses the sum of query ms, recorded).
- Suggestion: state in Limits that attribution comes only from QM or `wp profile` components, and that slow logs give "unknown".

**S3 (P3), the builder tests do not pin 9 documented rules.**
- The 9 rules: the 5-sample minimum, slow >= 50, hook >= 100, memory 90%, cache disabled when WP_CACHE is not true, autoload > 800000, compare on site, strict all-faster on ties, and the --out missing folder.
- Mutants breaking any of these pass 107/107 and 12/12. The behaviour is correct today (my probes pin it).

**S4 (P4): with `--out`, `--json` is silently ignored.** Stdout is text while the file is JSON (O01b). The synopsis allows both flags together, so a scripted caller parsing stdout would break.

**S5 (P4), behaviours nobody pins:**
- --out symlink refusal (correct, undocumented);
- acceptance of the documented "unknown" component;
- PLUGIN_FATAL, not CONFLICT, when one declarer is outside wp-content.

No proposed-fix patch is needed (no P1 or P2).

## Oracle disagreements, adjudicated (disclosed, not re-scored)
- **K5 decoy:** the prep oracle counts acme-pricing REPEATED_QUERY as blaming a decoy. The fixture really holds 40 same-shape queries from one caller in one request, a genuine N+1 at the doc's threshold of 10, so I judge the finding correct and my decoy rule too strict. K5 also misses on file:line (S2).
- **X3:** the candidate correctly accepts the speedup (comparable, ratio 1.993, medians 801 to 402). My accept regex wanted "1.99" with no further digit, so it is a rounding-format miss in the oracle.
- **X2:** this PASS is weak evidence. My X2 claim detector looks for "20.5x" or "95%" text, and the candidate states claims as `speedup_claimed` with `ratio`. Mutant cmp_no_measurement made a false 20x claim on X2 and the prep oracle missed it. Native probe P02 covers the rule and killed that mutant.
- **Prep oracle teeth 0/35:** through the adapter, its core tokens need fields the schema lacks, and its speedup judges are text-bound. It is not a strong instrument for this candidate's format.

## Harness errors and disclosures
- **First per-interpreter prep run (core 1/8):** I wrote bindings to /tmp, so `{binding_dir}` missed the adapter. Discarded, kept in raw/discarded-harness-error/, and rerun.
- **First survivor-distinguish run:** the 4 NaN cases shared one file name. Discarded, kept as v1, and rerun.
- **O01 and O06:** O01 was split into O01a/O01b, and the O06 expression was simplified before the 4-interpreter run. The 3.9.6 first-run output was overwritten by that rerun.
- **Teeth ran on 3.9.6 only.**
- **week-grok** (programme/grok-week-20261018, read-only):
  - before 19:48:08 PT: HEAD 02ba9c5, index c28a2f586b3e3001, status 6d0cd79bd0bad5c0 with 79 lines;
  - after 20:21:27 PT: same branch, HEAD and index, status af8386300eb96552 with 80 lines;
  - the one new entry is `?? employees/engineering/frontend-developer/async_search_core.js`, created 19:55:21 PT by the builder's frontend work, not by this pass;
  - the status listing is kept outside the published folder.

## Files
- **oracle/:**
  - m23r1_probes.py, g23_adapter.py and the binding-g23*.json files;
  - make_mutants_g23.py, run_teeth_g23.py, tally_teeth_g23.py and survivor_distinguish.py;
  - m23_fresh_caller_g23.sh and fresh-commands-g23.txt;
  - the prep oracle copied unchanged (m23_world.py, m23_oracle.py and the others), plus prep-stubs/.
- **results/:** per-interpreter outputs, teeth-3.9.6/, and the teeth tally.
- **raw/:** before and after records, fetch, binding-verify, and discarded runs.
