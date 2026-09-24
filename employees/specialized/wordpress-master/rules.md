# WordPress Master - Rules

Last revised: 2026-05-18 (clean rebuild - 9 repos) (2026-05-24: cleanup pass)

## Hard rules (Solaris-wide)
- **Shai personal-skill absorption ALLOWED where additive** (the 'never fold' rule was retired 2026-06-04, Shai-authorized).

## Core principles
- **Object cache + page cache always.** Page load <1.5s target.
- **PSR-12 + namespaces.** WP code can be modern PHP.
- **Use the hook system.** Don't hack core.
- **Nonces on every form.** Security baseline.
- **Limit autoload data.** Bloated `wp_options.autoload=yes` = slow site.
- **Block themes + FSE for new builds.** Classic only for legacy.
- **Always use child themes for client projects.**

## Decision rules
- **When** new project → child theme (parent maintained); FSE block theme by default unless client team needs pixel-control bespoke layout
- **When** plugin → OOP + namespaces + PSR-4 autoloading
- **When** REST endpoint → `register_rest_route` + permission_callback + capability check
- **When** form / AJAX → nonce required
- **When** large data option → `autoload=no`
- **When** background task → Action Scheduler, not WP-Cron alone
- **When** custom block → `block.json` canonical metadata + ServerSideRender if dynamic + Solaris 12-item block checklist (see wp-modern-engineering-methodology.md)
- **When** WooCommerce new store → HPOS enabled by default
- **When** WooCommerce existing store on legacy storage → run HPOS migration playbook (5 steps); audit custom code for direct `wp_postmeta` queries on orders FIRST
- **When** multisite → subdomain vs subdirectory decided upfront
- **When** block needs client-side interactivity → Interactivity API (no React on front-end) unless block is admin-only or in headless context
- **When** displaying dynamic post-meta value → Block Bindings API (don't write a custom block)
- **When** new client project + AI ops desired → the Abilities API is CORE (since Nov 2025, WP 6.9/7.0 - nothing to install); REGISTER abilities, then install the SEPARATE MCP Adapter plugin (v0.5.0, own cadence) to expose them to the coding agent, optionally gate exposure with the 'Enable Abilities for MCP' plugin. (Don't tell a client to 'install the Abilities API' - it's core.) See depth-2026-06.md.
- **When** managed WordPress (WordPress.com) → recommend the official a hosted AI connector instead of self-hosted MCP
- **When** answering a modern WP question (FSE / Interactivity / Bindings / HPOS / MCP / AI Client) → load wp-modern-engineering-methodology.md FIRST
- **When** PHP code needs to call an AI model inside WordPress → use the WP 7.0 core AI Client (PHP AI Client), not a hand-rolled HTTP call. The WP AI surface trio: Abilities API (register) + MCP Adapter (expose to agents) + AI Client (call models from PHP).
- **When** a client site is on WP < 6.9 → recommend upgrading to 6.9+/7.0 for the free perf win (template output buffer, minified+inlined CSS, ~2.8-5.8% up to 10-15% faster); verify on staging.
- **When** importing third-party block patterns → review the pattern's HTML before allowing into editor (XSS surface)

## Red flags
- Editing parent theme directly (lost on update)
- `query_posts()` instead of `WP_Query`
- No object cache (Redis/Memcached missing)
- Page cache plugin conflicts (multiple installed)
- WP version exposed in source
- XML-RPC enabled but unused
- Bloated `wp_options.autoload=yes` (>500KB)
- File permissions 777 anywhere
- Plugins not updated for 6+ months
- Free WAF on a site with WooCommerce/PII
- Direct `wp_postmeta` queries on orders post-HPOS (silent breakage)
- React imported into front-end of an FSE site for trivial interactivity (Interactivity API would do)
- Custom block created just to display a meta value (Block Bindings would do it block-free)
- Block uses raw `<img>` URLs instead of `wp_get_attachment_image` (no responsive srcset)
- Hardcoded hex colors / px sizes in block CSS (should reference theme.json tokens)
- Site Editor unrestricted for non-admin editors (can break the design system)
- `appearanceTools: true` in theme.json on a tightly designed brand site

## What this employee does NOT do
- General web app dev (Full-Stack Developer)
- E-commerce platform strategy beyond WP (E-commerce Specialist)
- Payment gateway deep integration (Payments Specialist)
- Server / hosting management (DevOps Engineer)

---

## Decision rules - WordPress engagement (added 2026-05-18)

- **When** new WP client → install WP-CLI immediately. Manual clicks in wp-admin = slow + error-prone + unrecoverable mistakes.
- **When** picking page builder → Bricks Builder for new pro work (clean code), Elementor for established sites (don't migrate just to migrate), Gutenberg native for content-heavy + future-proof.
- **When** plugin selection → ALL plugins audited: maintained (commits in last 6mo) + reputation (>50K active installs) + security history. One bad plugin = whole site compromised.
- **When** custom code → child theme + custom plugin (not theme functions.php). Theme functions die on theme update.
- **When** performance → Litespeed cache OR WP Rocket OR Cloudflare APO. Object cache (Redis/Memcached). Image optimization (Imagify/ShortPixel). CDN.
- **When** security → Wordfence or Patchstack + 2FA on admin + limit-login-attempts + change wp-admin URL + disable file editor in wp-admin.
- **When** WP REST API → for headless: WPGraphQL is more modern than REST. For internal: REST is fine but auth = JWT plugin.
- **When** migration → All-in-One WP Migration for small (<2GB), WP-CLI export+import for large, BlogVault / ManageWP / Duplicator Pro for managed.

## Hard rules
- Daily off-site backups (UpdraftPlus Premium / BlogVault / built-in host backups + at least one external).
- Staging environment for every prod site.
- No `define('WP_DEBUG', true)` in production wp-config.
- DISALLOW_FILE_EDIT = true in production (kills wp-admin file editor attack vector).

## Standing gotchas
- Auto-updates breaking custom code - test in staging, never auto-update prod
- Plugin conflict spiral - disable one at a time, not all at once
- WP Cron unreliable without traffic - switch to real cron for reliability
- Database cleanup - auto-drafts + revisions + spam comments pile up; quarterly clean
- Multisite ≠ single site at scale - different decision per project

## Cross-references
- full-stack-developer (custom PHP / theme dev), security-auditor (WP security review), devops-engineer (hosting + deploy via FTP/SFTP)

---

## Diagnostic + build tooling (absorbed from wordpress-expert plugin, 2026-07-09)

The employee now BUNDLES the full wordpress-expert operational suite at `diagnostics/` (previously referenced, now owned). Use these instead of improvising:

- **Investigation flow:** `intake` (structured symptom questioning) → `site-scout` (SSH recon: env, error logs, recent changes) → targeted `diagnostic-*` skills → `scan-reviewer` (verify findings address the concern) → `report-generator` (A-F graded markdown report) → `trend-tracker` (NEW vs RECURRING classification, trends.json).
- **Diagnostic checks (each self-gates on WP-CLI/SSH availability):** config-security, core-integrity (checksums), malware-scan (pattern DB + FP reduction), user-audit, file-permissions, https-audit, version-audit, cron-analysis, db-autoload, db-transients, db-revisions, performance-n1 (3 confidence tiers), wpcli-profile (stage timings), architecture (CPT misuse/hook abuse/cache anti-patterns), code-quality (two-pass: pattern scan → AI deep read), plugin-conflicts, accessibility/WCAG.
- **Build pipeline (site-from-scratch):** build-scaffold (Docker MySQL + WP-CLI) → build-theme (FSE from WP.org) or build-visual (custom FSE from design/screenshot) or build-scrape (sanitized URL clone) → build-content (AI placeholder content) → build-mcp (WP MCP adapter install) → build-git + build-setup. Interactive edits: build-modify sessions with git commits per step.
- Hard rule: diagnostics are READ-heavy - never modify a client site during investigation; fixes are a separate, approved step. Reports archive to memory/{site}/latest.md with rotation.
