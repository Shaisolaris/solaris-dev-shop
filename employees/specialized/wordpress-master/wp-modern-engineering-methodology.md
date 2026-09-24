# WordPress Modern Engineering Methodology

> Solaris-original synthesis. Methodology absorbed from observing WordPress/agent-skills (the official WordPress org's AI skills repo at https://github.com/WordPress/agent-skills, 1.3K stars, daily commits) and combining its patterns with what voltagent/wordpress-master already provided. Written in Solaris voice; no copy-paste from the source.
>
> **Why a fresh write:** WordPress.org content historically ships under GPLv2-or-later, which is incompatible with the Solaris HARD RULE (MIT/Apache/BSD only for client work). Methodology and patterns are not copyrightable - only specific expression is. So we extract the *patterns* and re-express them in Solaris voice + Solaris's existing voltagent foundation, keeping the depth without inheriting any GPL strings.

⚠️ ALWAYS load this file FIRST when modern WordPress engineering is in scope (post-2024 patterns: FSE, Interactivity API, Block Bindings, WP Abilities API).

---

## What changed in WordPress 2024-2026 that the voltagent base doesn't fully cover

The voltagent wordpress-master.md is solid on the classic stack (PHP 8 + WP_Query + classic theme + plugin OOP + WooCommerce + Wordfence). It's thinner on the modern surface that's emerged since 2023:

1. **Full Site Editing (FSE) maturity** - block themes now production-default for most new builds.
2. **Interactivity API** - WordPress's own client-side framework for blocks (NOT React-everywhere).
3. **Block Bindings API** - bind block attributes to dynamic data sources (post meta, options, custom sources).
4. **WP Abilities API + MCP Adapter** - WordPress core's MCP bridge so AI tools (a coding agent / Cursor) can discover and call WordPress capabilities natively.
5. **Block API v3 patterns** - `block.json` is the canonical metadata; the older PHP-only `register_block_type` is legacy.
6. **HPOS (High-Performance Order Storage)** for WooCommerce - required-by-default in new stores.

This file extends voltagent's base into those areas.

---

## FSE (Full Site Editing) - production default decision rules

### When FSE is the right call
- Brand-new build for a marketing/content site
- Client team will edit layout themselves
- Simple-to-medium templating needs
- WordPress 6.4+ target (FSE matured significantly through 6.x line)

### When classic theme + Gutenberg is still the right call
- Complex bespoke layouts where designer wants pixel control
- Heavy custom widget areas / sidebars
- Tight integration with non-block plugins (some still don't ship FSE-friendly)
- Headless setup (FSE doesn't apply - front-end is Next.js / Astro / etc.)

### FSE baseline `theme.json` we use on all FSE projects
A `theme.json` is the canonical config for FSE themes. The Solaris baseline:
- Define color palette as **CSS custom properties** so brand colors flow into both block editor AND custom CSS
- Define typography scale (5-7 sizes max - more is design debt)
- Define spacing scale (T-shirt sizes: xs / s / m / l / xl)
- Lock down user-editable sections via `templateParts` to prevent client team from breaking the design
- `appearanceTools: true` to give editor users layout controls (margin / padding / border)
- Settings differentiated by block (e.g. headings can have unique font sizes; paragraphs cannot)

### Block templates + template parts pattern
- `templates/` - full page templates (single.html, page.html, archive.html, 404.html, search.html)
- `parts/` - reusable parts (header.html, footer.html, sidebar.html)
- Each is a static HTML file with block markup; live-edited via Site Editor
- Override priority: child theme `templates/` > parent theme `templates/` > core fallback

---

## Interactivity API - the under-recognized win

The Interactivity API ships in WordPress core (since 6.5) and provides **directives-based reactivity** for blocks WITHOUT bundling React for the front-end. This is a big deal because:

- **No React on the front-end** = smaller payload, faster TTI, no hydration mismatch headaches
- Same mental model as Alpine.js / Vue templating but native to WordPress
- Server-side rendered blocks stay fully SEO-friendly
- Client-side state lives in lightweight `wp.interactivity` store

### When to use Interactivity API
- Block needs client-side behavior (toggle, filter, modal, image gallery, search-as-you-type)
- Block must be SEO-friendly (server-rendered)
- You want to avoid shipping a React bundle to every visitor

### When NOT to use it
- Block is a one-off admin-only tool (fall back to React + `@wordpress/element`)
- Block is deeply embedded in a headless front-end (Next.js / Astro have their own client model)
- Page is fully static and needs no interactivity

### Pattern
```html
<div data-wp-interactive='{"namespace":"solaris/gallery"}'
     data-wp-context='{"isOpen": false}'>
  <button data-wp-on--click="actions.toggle">Open</button>
  <div data-wp-class--hidden="!context.isOpen">...</div>
</div>
```

The `actions.toggle` handler lives in a TypeScript file registered via `register_block_type` PHP. Client-side store handles state; server-side render handles SEO.

---

## Block Bindings API - kill custom-fields-as-blocks

Pre-Bindings, displaying a custom field value required a custom block + ServerSideRender + PHP shortcode-style approach. The Block Bindings API lets a stock Paragraph or Image or Heading block bind its attribute to **any data source** (post meta, options, custom REST endpoint, or a registered binding source).

### Solaris pattern
- Register a binding source that returns post meta:
  - Source name: `solaris/post-meta`
  - Bind via block markup: `<!-- wp:paragraph {"metadata":{"bindings":{"content":{"source":"solaris/post-meta","args":{"key":"job_title"}}}}} -->`
- Editor shows `[Bound: job_title]` placeholder; front-end renders the actual meta value
- Eliminates 80% of historical custom blocks (anything that was just "show this dynamic value")

---

## WP Abilities API + MCP Adapter - the AI surface

WordPress shipped a first-class **Abilities API** (post-6.6) that exposes WP capabilities as discoverable, schema'd "abilities." The MCP Adapter then exposes those abilities to AI tools (a coding agent / Cursor / a desktop agent app) via the standard Model Context Protocol.

### What this gives Solaris
- New client WP project → install MCP Adapter plugin → a coding agent can natively create posts, install plugins, manage taxonomies, audit security through chat. Same pattern as Stripe MCP, Notion MCP - but for WP.
- Existing client WP audits → run the audit through a coding agent with the MCP adapter, instead of grepping wp-config and manually inspecting plugins.

### Decision rules
- **When** building a new WordPress site for a client → install the WordPress MCP adapter as part of standard setup. a coding agent becomes a first-class admin tool for the dev work.
- **When** doing a security audit → MCP adapter + a coding agent for inventory; Wordfence / Sucuri for the actual security scan (the MCP isn't a security scanner, it's a control surface).
- **When** the client wants their own team to use AI for content ops → train them on the WordPress.com a hosted AI connector (live since Feb 2026 per WordPress.com blog) or self-host the MCP adapter.

---

## Performance - beyond the voltagent baseline

The voltagent base covers caching layers (page / object / DB query / CDN / browser) and optimization (WebP, lazy loading, query optimization). These additions land specifically because of FSE + block theme patterns:

### Block-rendered pages need different cache invalidation
- **Page cache** must invalidate on `save_post` for any post that uses the block in question
- **Block patterns** with dynamic data (Bindings) cannot be statically cached at the block level - must cache the rendered page or use fragment caching
- **Reusable blocks** (now called "synced patterns") invalidate every page that includes them - be careful with broad reuse

### Modern image pipeline
- Native `<img loading="lazy" fetchpriority="auto">` on most images
- `fetchpriority="high"` on the LCP image (typically hero) - manually flag in template
- `<img sizes>` always set; use the `wp_get_attachment_image` helper, never raw URLs
- AVIF + WebP fallback chain via the Performance Lab plugin (WordPress core won't ship AVIF default until ~6.8)

### Critical CSS for FSE
- The theme.json + block patterns make it harder to extract critical CSS automatically
- Critical CSS plugins (WP Rocket, Autoptimize, Cwd Critical CSS) work but need per-template configuration
- Or: ship the full FSE stylesheet (it's smaller than people expect once minified) and skip critical CSS entirely

---

## Security - beyond the voltagent baseline

The voltagent base covers WAF, 2FA, file permissions, login throttling. Additions:

### Block editor / FSE-specific surface
- **Block patterns from third-party sources** can include arbitrary HTML - review patterns before allowing user import
- **Theme.json `appearanceTools`** gives editors layout control - for client builds, restrict to power users only via capability filter
- **Site Editor (FSE)** is gated behind `edit_theme_options` cap - for non-admin editors, lock down via custom role

### Headless WP-specific surface
- **REST API** must auth properly - for headless, use Application Passwords or custom OAuth, never expose `?author=N` enumeration endpoints publicly
- **WPGraphQL** has its own auth model - must enable proper introspection lock-down in production
- **CORS** policy on REST API - restrictive whitelist, never `*`

### Modern threat patterns we audit for
- Plugin supply chain (a compromised plugin = full site compromise) - pin versions, monitor advisories, prefer plugins that publish a security policy
- Compromised admin accounts via password reuse - mandatory 2FA on every admin role
- Insecure direct object reference in custom REST endpoints - capability checks on every endpoint, every operation
- XSS via custom blocks that don't escape attributes - `wp_kses_post` on output, `sanitize_text_field` on input

---

## WooCommerce HPOS (High-Performance Order Storage)

Required default for new stores since WooCommerce 8.x. Old stores need migration.

### What HPOS changes
- Orders move from `wp_posts` + `wp_postmeta` to dedicated tables: `wp_wc_orders`, `wp_wc_order_addresses`, `wp_wc_order_operational_data`, `wp_wc_orders_meta`
- Custom queries that hit `wp_postmeta` directly for order data **break silently** - must rewrite to use the WC API or `wc_get_orders()`
- Plugin compatibility: plugins must declare HPOS-compatible via `before_woocommerce_init`

### Solaris migration playbook
1. Audit all custom code for direct `wp_postmeta` queries against orders
2. Audit all installed plugins for HPOS compat declaration
3. Run sync mode (HPOS + posts both written) for at least one full billing cycle
4. Validate order parity (count, total, status) between the two storage modes
5. Switch to HPOS-only mode
6. Monitor for 2 weeks before declaring migration done

---

## Block development checklist (Solaris standard for any custom block)

Every custom block we ship goes through this checklist before merge:
- [ ] `block.json` is canonical metadata (no inline `register_block_type` config)
- [ ] Block variations declared in `block.json` rather than separate registration
- [ ] Server-side render path uses `render_callback` for dynamic content (NOT JS-only render)
- [ ] Block tested in Editor + front-end + FSE Site Editor + classic post editor (if applicable)
- [ ] No direct DOM manipulation outside the Interactivity API store
- [ ] `wp_kses_post` on any user-supplied output
- [ ] `nonce_verify` on any AJAX action the block triggers
- [ ] Block translation strings registered via `__()` / `_n()` / etc.
- [ ] Block respects `theme.json` color / typography / spacing tokens (no hardcoded hex/px)
- [ ] Block has an Editor `View` → live preview that matches front-end
- [ ] Block has at least one default style variation
- [ ] Performance: block render doesn't trigger N+1 queries

---

## Cross-references inside Solaris

- **Full-Stack Developer** - owns the frontend choice for headless WP (Next.js / Astro / Nuxt). Hand off to them for any decoupled architecture.
- **DevOps Engineer** - owns hosting + CI/CD. WP-Engine / Kinsta / Pantheon all play well with GitHub Actions for deploy; coordinate.
- **Security Auditor** - owns deep security audits. WordPress Master does best-practice config; Security Auditor does threat model + pen test.
- **Code Reviewer** - flags anti-patterns: direct `wp_postmeta` queries on orders post-HPOS, missing nonce verification on AJAX, hardcoded colors in blocks, React on front-end where Interactivity API would do.
- **CTO** - sign-off on the FSE-vs-classic theme decision for new client builds.
- **Payments Specialist** - coordinates on WooCommerce payment gateway integration; HPOS migration playbook intersects with payment flow audits.
