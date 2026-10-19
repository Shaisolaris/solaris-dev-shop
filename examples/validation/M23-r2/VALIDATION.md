# M23 r2: Grok self-validation of G23 r2 (offline WordPress trace and config diagnosis)

Grok self-validation by the same bot that built the programme. This is not independent review and not manager acceptance.

- Candidate: G23 r2, commit 0ff2641c56c852d9525adaa71442274d8c8453a6 on review/grok-g23-wp-trace-diagnosis (parent d6be00e, the r1 candidate). main stays at 02ba9c5.
- Tool: employees/specialized/wordpress-master/wp_trace_diag.py, TOOL_VERSION 1.1.0.
- Window: 22:31 to 23:00 PT, 2026-10-18. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. The candidate was not modified.

## Verdict: PASS with residuals (no P1, P2 or P3)
All five r1 findings (S1 to S5) are addressed. The native-schema probes, the builder evidence, teeth and the fresh caller all agree. What is left is P4 only.

## Binding (raw/binding-verify.txt)
- The diff d6be00e..0ff2641 is byte-identical to G23-r2.patch (sha256 1d33737d...).
- MANIFEST.sha256: 23 OK, and its file set equals the 02ba9c5..0ff2641 diff set.

## Results (results/)
| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| Builder suite | 114 OK | 114 OK | 114 OK | 114 OK |
| Builder wp_oracle (candidate / noop / naive) | 12/12, 2/12, 1/12 | same | same | same |
| M23 r1 probes (r1 tool got 58/61) | 61/61 | 61/61 | 61/61 | 61/61 |
| New M23 r2 probes, scored (doc + claim) | 51/51 | 51/51 | 51/51 | 51/51 |
| Prep oracle via adapter, core | 5/8 | 5/8 | 5/8 | 5/8 |

- **M23 r2 probes (oracle/m23r2_probes.py):** 38 doc rows take their expectation from the r2 text of wp-trace-diagnosis.md. 13 claim rows test builder claims that the doc does not state: the 256-character and single-line source_file, source_line from 1 to 1e9 as an integer, and the text summary's "sources:" line. 8 obs rows are recorded, not scored.
- **Direction:** the r1 tool (d6be00e) scores 26/51 on the r2 probes, failing all the new S1, S2, S4 and S5 rows. The r2 rows are therefore sensitive to the change.
- **S1 (A01 to A13):**
  - equal, above and below the limit, all give the right wording;
  - 1024M against 1 GiB, 1G against 1 GiB, and lowercase "32m" all compare correctly;
  - a missing WP_MEMORY_LIMIT and a value that is not a size are both stated;
  - two plugins in two lines give one core finding;
  - the peak-90% path is also core;
  - the line's file is still given as the place memory ran out.
- **S2 (B01 to B23):**
  - source_file:line is kept in the evidence and in `sources`;
  - the slowest run leads in both input orders;
  - `sources` is capped at 20;
  - a source_file without a line is allowed;
  - a source_line without a source_file is refused;
  - newline, tab, 257 characters, empty, non-text, 0, 1e9+1, string and bool are all refused with exit 2 and no traceback;
  - 256 characters and 1e9 are accepted;
  - REPEATED_QUERY keeps its source;
  - a wp_acme_ table in the SQL is never turned into a plugin;
  - QM components still win when present.
- **S4 and S5 (C01 to C06, D01 to D13):**
  - `--json --out` prints JSON identical to the file, for both diagnose and compare;
  - `--out` alone prints text;
  - compare `--out` onto an input gives exit 2;
  - a not-comparable compare (exit 3) still writes the report;
  - `--out` gives exit 2 for a folder, a symlink, a dangling symlink, a missing folder, a hardlink to an input, a symlink to an input, and a symlinked folder holding a symlink to an input;
  - the "unknown" component is accepted;
  - a redeclare against code outside wp-content gives PLUGIN_FATAL naming the plugin or theme, in both orders.

## Prep oracle, adjudicated (disclosed, not re-scored; results/cand-adapter-r2-*)
The core score stays 5/8 (K2, K3, K5), with both the r1 adapter and a new oracle/g23_adapter_r2.py. The r2 adapter passes QM `location` and the slow-log entry line into the new source fields.
- **K3:** now substantively met. The finding is core, says "that is the configured WP_MEMORY_LIMIT 32M", and carries the evidence `WP_MEMORY_LIMIT=32M`. It misses only my "wp-config.php line 16" token, and the r2 doc says wp-config line numbers have no field. My decoy rule then fires because the line quotes the media-tools path, which the doc says to report as where memory ran out. The oracle is stricter than the doc.
- **K5:** with the r2 adapter it is now localised: theme:solaris-child, `source wp-content/themes/solaris-child/inc/related.php:58`. It misses only my "2.48" seconds token, because the tool prints 2480.1 ms (a format miss in the oracle). The acme-pricing REPEATED_QUERY decoy is the genuine N+1 already adjudicated in r1.
- **K2:** the 3912 ms query on wp_acme_search_index is reported as "unknown, not tied to a plugin" with `source mysql-slow.log:26`. My oracle wants the acme-search plugin named. The r2 doc now states that a slow log "never guesses a plugin from the SQL". This is a design choice the doc discloses, so it is an owner decision, not a defect.
- **X3 and X4:** same as r1 (the X3 rounding regex in the oracle; the X4 slow-log query is "unknown" by design).

## Teeth (3.9.6; results/teeth-3.9.6/, results/teeth-tally-3.9.6.txt)
- **Mutant set:** 57 in total. 36 are the r1 set, all with anchors still single-occurrence on r2 (35 real plus atomic_rename_EQUIV). 21 are my own r2_* mutants on S1, S2, S4 and S5 (oracle/make_mutants_r2.py).
- **Instruments:** each mutant is scored by the M23 r1 probes plus the M23 r2 probes, the prep oracle through the adapter, the builder tests, and the builder wp_oracle. A kill is any deviation from the candidate's own baseline. All 4 shard baselines are identical.
- **Invalid mutant:** r2_text_sources_off is a SyntaxError mutant caused by my own anchor error, so its kill is trivial. I exclude it below; the raw tally counts it.
- **Counts excluding that mutant (55 real):** union 52/55, builder (tests or oracle) 48/55, Grok (probes or prep) 49/55. The control atomic_rename_EQUIV survives as expected.
- **Killed only by Grok:** r2_size_case, r2_src_257, r2_src_line_1e10, r2_sources_cap_10. The builder tests do not pin lowercase sizes, the exact 256-character bound, the 1e9 line bound or the 20-source cap.
- **Killed only by the builder:** secret_re_no_key, secret_kept, r2_size_G_1000.
- **Survivors (results/survivor-distinguish-r2.txt):**
  - nan_allowed: contract-equivalent, as in r1 (NaN is still refused with exit 2 by the range check).
  - r2_slowest_ge: non-equivalent. With two runs at exactly 200 ms, the lead source flips from A.log:1 to B.log:2. Either run is "the slowest", so it is contract-ambiguous.
  - r2_text_more_6: non-equivalent. With 6 sources the text drops "and 1 more".
- **Builder claim:** the builder claims its tests kill 48/49 non-equivalent mutants on its own set. On my set, builder instruments kill 48/55.

## Fresh caller (results/fresh/)
- **Setup:** env -i, a new HOME, a python3 shim to 3.9.6 and an offline guard. Only the doc's commands are run, transcribed by hand into oracle/fresh-commands-r2.txt.
- **r1 commands:** they behave as before.
- **r2 additions:** all expectations are met:
  - `diagnose --json --out` stdout is JSON ['CONFIG_MEMORY_LIMIT', 'SLOW_QUERY'];
  - `compare --json --out` gives stdout and file both speedup_claimed True;
  - `--out` onto a folder gives exit 2;
  - a memory and slow-log bundle gives CONFIG_MEMORY_LIMIT [core] ("WP_MEMORY_LIMIT is 256M ... PHP's memory_limit is lower") and SLOW_QUERY [unknown] "not tied to a plugin" with `sources: mysql-slow.log:1204`.
- **Prep oracle through the fresh caller:** 5/8 as above.

## Findings
- **P1, P2, P3:** none. No proposed-fix patch (none is needed without a P1 or P2).
- **r1 findings, all addressed:**
  - S1 (P3): fixed (A01 to A13; r1 N21 and N22 now pass).
  - S2 (P3): fixed, with source fields and the Limits text (B01 to B23).
  - S3 (P3): fixed. The r1 "9 unpinned rules" mutants (min_samples_4, slow_gt, hook_gt, mem_warn_95, cache_disabled_only_false, autoload_ge, cmp_no_site, cmp_le, out_folder_unchecked; all 9 killed by the builder tests) are now killed by the builder tests (34/35 of the r1 set).
  - S4 (P4): fixed (C01, C03, O01b).
  - S5 (P4): documented and pinned (D01 to D13).
- **P4 residuals (none blocks):**
  - Q1. A JSON integer `WP_MEMORY_LIMIT: -1` gives "above WP_MEMORY_LIMIT -1, so a higher limit applied". -1 is PHP's "unlimited", so the reason given is wrong (A07b). The string "-1" is honestly reported as not a size (A07). "256MB" is reported as not a size (A08).
  - Q2. A non-integer source_line (12.7) is accepted and silently truncated to 12 (B18).
  - Q3. `--out` through a symlinked parent folder is followed and writes into the target folder (D08). The doc refuses "a symlink" without saying whether that means only the file.
  - Q4. Two declarers both outside wp-content give PLUGIN_FATAL [unknown] "declared twice inside unknown (two copies loaded?)" (D12). This is odd wording for a case the doc does not cover.
  - Q5. Unpinned by the builder tests: lowercase size units, the 256-character and 1e9 bounds, the 20-source cap (the four Grok-only kills), the ms-tie lead order, and the "and N more" boundary (the two survivors).
- **Owner decision:** K2. A slow-log query is never tied to a plugin, by documented design. The prep oracle wanted the plugin named.

## Harness errors and disclosures
- **Fresh caller v1:** my added line used freshb.json after the r1 compare step had written freshB.json. On the case-insensitive macOS disk that overwrote it, so stdout was JSON with no findings. This was my command error, not the candidate's. v1 is kept as results/fresh-commands-v1-case-collision.txt; v2 moves the line to the memory bundle.
- **Teeth, first two launches crashed before scoring any mutant:** make_mutants_r2 had no `apply`, then the shards collided on one baseline binding file. Both were fixed (apply re-exported; binding file name per PID) and teeth reran from scratch. The probe script gained temp-dir cleanup between the 4-interpreter run and teeth; this changes no result.
- **r2_text_sources_off:** an invalid mutant (SyntaxError), excluded from the counts above.
- **Teeth ran on 3.9.6 only.**
- **week-grok** (programme/grok-week-20261018, read-only, never written):
  - before 22:31:01 PT: HEAD 02ba9c5, index c28a2f586b3e3001, status af8386300eb96552 with 80 lines;
  - after 22:54:39 PT: same branch, HEAD and index; status 61afa019748f85b9 with 86 lines;
  - the 6 new entries are the builder's G20 frontend work, with mtimes 22:53:05 to 22:54:24 PT: 4 modified frontend-developer files, async-search-ui.md and tests/test_g20_capability.py. None are from this pass. The status listings and their diff are kept outside the published folder.

## Files
- **oracle/:**
  - the r1 tools repointed to /tmp/m23r2-eval;
  - m23r2_probes.py, g23_adapter_r2.py, make_mutants_r2.py, run_teeth_r2.py, survivor_distinguish_r2.py and fresh-commands-r2.txt.
- **results/:**
  - per-interpreter outputs;
  - r2probes-*, including r2probes-r1tool-3.9.6;
  - cand-*, cand-adapter-r2-*;
  - teeth-3.9.6/, the teeth tally, survivor-distinguish-r2.txt and fresh/.
- **raw/:** the before and after records, fetch, binding-verify, and the status diff.
