# WordPress Master - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from voltagent wordpress-master**: 8-metric mastery checklist (page load <1.5s, security 100/100, CWV pass, DB <50 queries, PHP <128MB, uptime >99.99%, PSR-12, docs) is the most actionable WP standard.
- **2026-04-25 - Object cache + page cache + CDN trio** is the consistent performance baseline.
- **2026-04-27 - WordPress/agent-skills absorbed (v0.3.0) license-safely**: Wrote `wp-modern-engineering-methodology.md` in Solaris voice rather than copy-pasting from WordPress's GPLv2-or-later repo. Decisive insight: **methodology and patterns are not copyrightable; specific expression is.** This pattern (re-express the methodology in your own voice) is the universal solution to "the official source is GPL but we want the depth." Add it to the skill scanner playbook.
- **2026-04-27 - Modern WP stack now has 4 distinct AI surfaces**: Interactivity API (front-end without React), Block Bindings (eliminate custom-fields-as-blocks), WP Abilities API + MCP Adapter (a coding agent controls WP natively), WordPress.com a hosted AI connector (managed-host AI). Each has a distinct decision rule about WHEN to use it - codified in rules.md.
- **2026-04-27 - HPOS silent-breakage gotcha**: any custom code or third-party plugin that queries `wp_postmeta` directly for order data breaks silently after HPOS migration. Always audit-then-migrate. Took this from a WooCommerce 8.x release-notes pattern; turned it into the 5-step migration playbook.

- **2026-06-13 (depth) - Abilities API is CORE, MCP Adapter is a SEPARATE plugin** - corrected the conflation; Abilities API landed in core Nov 2025 (WP 6.9/7.0, no install), MCP Adapter is v0.5.0 on its own cadence. Don't tell clients to 'install the Abilities API'.
- **2026-06-13 (depth) - WP 7.0 (2026-05-20) ships the AI Client (PHP AI Client)** - the WP AI surface is now a trio: Abilities API + MCP Adapter + AI Client. WP 6.9 added a 2.8-15% perf uplift (template output buffer, minified/inlined CSS).

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## 2026-10-18 - G23 trace and config diagnosis (synthetic fixtures only)
- No WordPress, PHP or database on the build host: the analyzer reads a bundle, and every report says that nothing was run and carries the bundle's source line.
- A bisect log alone can be ambiguous: three runs over four plugins left four pairs equally possible (fixture 08). Report the failure as unlocalized with its candidates instead of naming a pair.
- Merge a `Cannot redeclare` fatal and a bisect result that name the same pair into one finding; two findings for one fault read as two faults.
- Fold IN lists into one query shape or N+1 loops of `post_id IN (...)` hide; the same folding made 12 meta-cache primes look like an N+1 in an early fixture, so the clean control uses a realistic 4.
- r2 (M23 self-validation): the plugin in an `Allowed memory size ... exhausted` line is only where PHP ran out, so blaming it sent the fix to the wrong place; the fault is the limit, and the useful fact is whether the configured WP_MEMORY_LIMIT is above the size PHP died at. Keep a record's source file and line through to the finding, and say when a slow-log query cannot be tied to a plugin instead of guessing.
- Reference: wp-trace-diagnosis.md, wp_trace_diag.py.
## Sources

- Upstream: WordPress/mcp-adapter (GPL-2.0+ (FLAG copyleft; methodology only)); WordPress Abilities API (GPL (core)); WordPress 7.0 AI Client / PHP AI Client (GPL); WordPress/agent-skills (GPL-2.0+ (methodology absorbed in own voice)); WordPress 6.9 perf + Interactivity API iteration (GPL)
- What was used: methodology only: WordPress/mcp-adapter, WordPress Abilities API, WordPress 6.9 perf + Interactivity API iteration; methodology absorbed: WordPress 7.0 AI Client / PHP AI Client, WordPress/agent-skills; connected as external reference: WordPress 7.0 AI Client / PHP AI Client
- License notes: WordPress/mcp-adapter: GPL-2.0+ (FLAG copyleft; methodology only); WordPress Abilities API: GPL (core); WordPress 7.0 AI Client / PHP AI Client: GPL; WordPress/agent-skills: GPL-2.0+ (methodology absorbed in own voice); WordPress 6.9 perf + Interactivity API iteration: GPL
