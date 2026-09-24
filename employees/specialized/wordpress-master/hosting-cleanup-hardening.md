# WordPress Hosting Cleanup + Hardening (methodology, license-safe, no copy-paste)

Powers the **Hosting Cleanup** gig from the WordPress side. This is the "make a neglected site clean, fast, and secure" playbook. Pairs with the existing diagnostic suite (wordpress-expert skills) and the depth-2026-06 small-task lane. Network-level TLS/header/CIS hardening routes to network-engineer; CI/secret/supply-chain hardening routes to devops-engineer. This file owns the WordPress-application layer.

## 0. Gate-0 (what we already had vs net-new)
- ALREADY HAD: WP-CLI diagnostics, object cache present/absent check, autoload-size audit, plugin count/age, Query Monitor, CWV check, Wordfence/2FA/DISALLOW_FILE_EDIT security hard rules, page-cache singleton check (depth-2026-06.md lane 4).
- NET-NEW (this file): a sequenced cleanup runbook that turns those point-checks into an ordered cleanup engagement, plus a security-header + TLS posture pass (delegating the raw scan to network-engineer), plus a caching/perf tier-selection decision tree, plus a "pro WordPress health" scorecard the client signs off on.

## 1. Engagement shape - cleanup is a SEQUENCE, not a scan
Order matters. Each step is reversible and gated on a fresh backup.
1. **Snapshot first.** Full backup (files + DB) BEFORE any change. Record current state: WP/PHP/plugin versions, active theme, CWV (field + lab), security-header grade, TLS grade, page-load, DB query count, autoload size. This is the before-column of the scorecard.
2. **Triage, do not rebuild.** Rank findings by impact x effort. A cleanup is not a rebuild; if the fix is a rebuild, flag it and stop.
3. **Safe-clean pass** (low blast radius): remove deactivated plugins/themes, clear orphaned + expired transients, trim post revisions to a sane cap, drop autoloaded-options bloat (the usual `_transient_`, abandoned-plugin leftovers, oversized autoload rows), empty spam/trash. Re-measure autoload + DB size.
4. **Update pass** (medium): update core -> plugins -> theme, each behind a staging dry-run where possible; check for fatal/PHP-deprecation noise after each. Baseline-upgrade to WP 6.9+/7.0 for the free perf win (depth-2026-06 lane 3).
5. **Hardening pass** (see section 2).
6. **Performance pass** (see section 3).
7. **Verify + sign-off**: re-measure every metric into the after-column; hand the client the scorecard.

## 2. Security + hardening pass (WordPress application layer)
Builds on the existing hard rules (Wordfence/2FA/DISALLOW_FILE_EDIT). Net-new for cleanup engagements:
- **Security-header posture.** Confirm HSTS (sane max-age + includeSubDomains once verified), Content-Security-Policy (start report-only, then enforce), X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy, and frame-ancestors / X-Frame-Options. WordPress can emit these via the `send_headers` filter or an mu-plugin; production hosting (LiteSpeed/NGINX/Apache) should set them at the server edge - **route the edge config + the raw scan to network-engineer** (testssl + a header scanner). WordPress-side, ship the mu-plugin fallback only when there is no edge control.
- **TLS posture.** Ask network-engineer to run testssl against the host; act on findings WordPress-side that matter (force-HTTPS, mixed-content sweep via WP-CLI search-replace on http:// -> https:// in content + serialized options, HSTS only AFTER HTTPS is confirmed everywhere). NEVER set HSTS before HTTPS is solid - it is a footgun.
- **Surface reduction.** XML-RPC off (or limited), REST API user-enumeration blocked, author-archive enumeration blocked, file editor disabled, directory listing off, `wp-config.php` + `xmlrpc.php` access tightened at the edge, login throttling + 2FA confirmed.
- **Supply-chain hygiene.** Inventory plugins/themes for abandonment (no update > 12 months), known-vuln status, and nulled/pirated code (a common cleanup finding). A vuln scan against the WPScan vulnerability database is the standard tool here - **WPScan's data/CLI is under a non-OSI license (free for non-commercial; commercial/API use needs a paid plan + API token)** - flag this to the host before relying on it in a paid engagement; the WPScan WP plugin and API both gate behind the token.
- **Malware/integrity.** Core-file integrity check (WP-CLI checksums), scan uploads + must-use for injected PHP, review recently-modified files. This is the existing malware-scan diagnostic, sequenced into the cleanup.

## 3. Performance + caching pass (tier selection, not cargo-cult)
A cleanup should leave caching correct, not just "a cache plugin installed". Decision tree:
- **Object cache:** if Redis/Memcached is available on the host, wire persistent object cache (drop-in). This alone cuts DB queries 60-80% on dynamic sites. If unavailable, do not fake it - note it as a host-upgrade recommendation.
- **Page cache:** pick by server. On LiteSpeed/OpenLiteSpeed -> LiteSpeed Cache (server-integrated, free, best fit, QUIC.cloud optional CDN). On NGINX/Apache without LiteSpeed -> WP Rocket (commercial, most reliable) or a server-level cache (FastCGI/Varnish). Do not stack two page caches.
- **CWV-driven fixes:** LCP (optimize the hero image: WebP/AVIF, preload, correct sizing; lazy-load below the fold), CLS (reserve image/embed dimensions, font-display swap with size-adjust), INP (defer/trim JS, reduce main-thread work - the 2026 metric that replaced FID). Critical CSS + deferred non-critical CSS/JS.
- **Asset hygiene:** kill render-blocking, combine only on HTTP/1.1 (skip under HTTP/2/3), CDN for static, browser-cache headers, DB query cache via transients with TTL.
- Re-measure CWV (lab AND field/CrUX where available) into the scorecard. Target: PageSpeed 90+, CWV all "Good", page load < 1.5s, DB queries < 50.

## 4. Pro WordPress health scorecard (the deliverable)
A signed before/after table the client keeps. Rows: WP/PHP version, plugin count + abandoned count, autoload size, DB query count, page-load, CWV (LCP/CLS/INP), PageSpeed score, security-header grade, TLS grade, vuln count, malware status, backup confirmed. Each row: BEFORE / AFTER / action taken / residual risk + recommendation. This is what makes the engagement "pro" - the client sees exactly what changed and what is left.

## 5. Execution path (wired vs plan-only)
- WIRED: WP-CLI (host SSH) is the primary surface for the cleanup; the WordPress MCP Adapter (host installs v0.5.0 plugin) lets the coding agent drive plugin/option/user ops natively; wordpress-expert connect flow if available.
- DELEGATED: testssl/header raw scan + edge TLS/header config -> network-engineer. CI/secret/supply-chain gates -> devops-engineer.
- PLAN-ONLY otherwise: with no SSH/MCP/site access, produce the runbook + scorecard template and hand the host the connect steps; never claim a change not made.
- License posture: WP + LiteSpeed Cache are GPL; testssl is GPLv2; WPScan data is non-OSI (token-gated). Methodology here is Solaris voice, no copy-paste.
