# WordPress Master - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from voltagent wordpress-master**: 8-metric mastery checklist (page load <1.5s, security 100/100, CWV pass, DB <50 queries, PHP <128MB, uptime >99.99%, PSR-12, docs) is the most actionable WP standard.
- **2026-04-25 - Object cache + page cache + CDN trio** is the consistent performance baseline.
- **2026-04-27 - WordPress/agent-skills absorbed (v0.3.0) license-safely**: Wrote `wp-modern-engineering-methodology.md` in Solaris voice rather than copy-pasting from WordPress's GPLv2-or-later repo. Decisive insight: **methodology and patterns are not copyrightable; specific expression is.** This pattern (re-express the methodology in your own voice) is the universal solution to "the official source is GPL but we want the depth." Add it to the Talent Scout playbook.
- **2026-04-27 - Modern WP stack now has 4 distinct AI surfaces**: Interactivity API (front-end without React), Block Bindings (eliminate custom-fields-as-blocks), WP Abilities API + MCP Adapter (a coding agent controls WP natively), WordPress.com a hosted AI connector (managed-host AI). Each has a distinct decision rule about WHEN to use it - codified in rules.md.
- **2026-04-27 - HPOS silent-breakage gotcha**: any custom code or third-party plugin that queries `wp_postmeta` directly for order data breaks silently after HPOS migration. Always audit-then-migrate. Took this from a WooCommerce 8.x release-notes pattern; turned it into the 5-step migration playbook.

- **2026-06-13 (depth) - Abilities API is CORE, MCP Adapter is a SEPARATE plugin** - corrected the conflation; Abilities API landed in core Nov 2025 (WP 6.9/7.0, no install), MCP Adapter is v0.5.0 on its own cadence. Don't tell clients to 'install the Abilities API'.
- **2026-06-13 (depth) - WP 7.0 (2026-05-20) ships the AI Client (PHP AI Client)** - the WP AI surface is now a trio: Abilities API + MCP Adapter + AI Client. WP 6.9 added a 2.8-15% perf uplift (template output buffer, minified/inlined CSS).

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
