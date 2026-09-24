// skills/build-scrape/scraper.js
// Standalone Node.js Playwright scraper for URL clone mode.
//
// Usage:  node scraper.js <url> <output_dir>
// Stdout: Single JSON line, { success: true, manifest: {...} }
//                         or { success: false, error: "..." }
//
// Dependencies: playwright, fs (stdlib), path (stdlib), url (stdlib)
// Do NOT require readline, interactive confirmation is handled by SKILL.md shell code.
// Do NOT call page.screenshot() or download any images.

'use strict';

const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');
const { URL } = require('url');

// ── CLI arguments ─────────────────────────────────────────────────────────────
const [, targetUrl, outputDir] = process.argv;

if (!targetUrl || !outputDir) {
  process.stdout.write(JSON.stringify({
    success: false,
    error: 'Usage: node scraper.js <url> <output_dir>'
  }) + '\n');
  process.exit(1);
}

// ── Exclusion patterns for inner page discovery (Pitfall 4) ──────────────────
const EXCLUDE_PATTERNS = /\/(page\/\d|tag\/|category\/|feed|wp-admin|wp-login|author\/)|[?#]|\.xml|\.json|\.rss$/i;

// Priority patterns for inner page ordering
const PRIORITY_PATTERNS = /\/(about|contact|services|blog|work|portfolio|team|pricing|faq|products)/i;

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Convert a page path to a safe filename.
 * e.g. "/about-us/team" → "about-us-team.html"
 */
function pathToFilename(pageUrl) {
  try {
    const u = new URL(pageUrl);
    const slug = u.pathname
      .replace(/\//g, '-')   // slashes → hyphens
      .replace(/^-/, '')      // strip leading hyphen
      .replace(/-$/, '')      // strip trailing hyphen
      .replace(/-{2,}/g, '-');// collapse double hyphens
    return (slug || 'inner-page') + '.html';
  } catch {
    return 'inner-page.html';
  }
}

/**
 * Navigate to a URL with networkidle, falling back to domcontentloaded
 * if a timeout occurs (Pitfall 7).
 */
async function gotoWithFallback(page, url) {
  try {
    await page.goto(url, { timeout: 30000, waitUntil: 'networkidle' });
    return { usedFallback: false };
  } catch (e) {
    if (e.message && (e.message.includes('Timeout') || e.message.includes('timeout'))) {
      // Retry with domcontentloaded
      await page.goto(url, { timeout: 15000, waitUntil: 'domcontentloaded' });
      return { usedFallback: true };
    }
    throw e;
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

(async () => {
  let browser;

  const pagesVisited  = [];   // { url, filename, features }
  const failedPages   = [];   // { url, error }
  const images        = [];   // { src, width, height, alt }
  const fonts         = new Set();
  let   allCSSText    = '';
  let   spaFallbackUsed = false;

  try {
    // Create output directory structure
    fs.mkdirSync(path.join(outputDir, 'styles'), { recursive: true });

    // Launch browser with custom user agent
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (compatible; WPCoWork/1.0; +https://github.com/wpcowork)'
    });

    // Parse base URL for same-origin checks
    const baseOrigin = new URL(targetUrl).origin;

    // ── Per-page scrape function ─────────────────────────────────────────────
    async function scrapePage(url, filename) {
      const page = await context.newPage();
      try {
        const { usedFallback } = await gotoWithFallback(page, url);
        if (usedFallback) spaFallbackUsed = true;

        // Full HTML
        const html = await page.content();

        // CSS from document.styleSheets (Pitfall 2: wrap in try/catch for CORS)
        const cssData = await page.evaluate(() => {
          const cssTexts  = [];
          const fontHrefs = [];
          const blockedHrefs = [];

          for (const sheet of document.styleSheets) {
            try {
              if (sheet.href && sheet.href.includes('fonts.googleapis.com')) {
                fontHrefs.push(sheet.href);
              } else {
                for (const rule of sheet.cssRules || []) {
                  cssTexts.push(rule.cssText);
                }
              }
            } catch (e) {
              // CORS-blocked external stylesheet, record href but skip rules
              if (sheet.href) blockedHrefs.push(sheet.href);
            }
          }

          return { cssTexts, fontHrefs, blockedHrefs };
        });

        allCSSText += cssData.cssTexts.join('\n') + '\n';
        cssData.fontHrefs.forEach(href => fonts.add(href));

        // Image dimensions via DOM (no image bytes downloaded)
        const pageImages = await page.evaluate(() => {
          return Array.from(document.querySelectorAll('img')).map(img => {
            const rect = img.getBoundingClientRect();
            return {
              src:    img.src,
              width:  img.naturalWidth  || rect.width  || 0,
              height: img.naturalHeight || rect.height || 0,
              alt:    img.alt || ''
            };
          }).filter(img => img.width > 10 && img.height > 10);
        });
        images.push(...pageImages);

        // Dynamic feature detection via DOM selectors
        const features = await page.evaluate(() => {
          const found = [];

          // E-commerce: cart / checkout signals
          if (document.querySelector(
            '[class*="cart"],[id*="cart"],[href*="/cart"],[href*="/checkout"]'
          )) found.push('ecommerce');

          // Search
          if (document.querySelector(
            'input[type="search"],[role="search"],[class*="search-form"]'
          )) found.push('search');

          // Login / registration
          if (document.querySelector(
            '[action*="login"],[href*="login"],[class*="login"],[href*="register"]'
          )) found.push('login');

          // Contact form (specific WP form plugins + semantic selectors)
          if (document.querySelector(
            'form[class*="contact"],form[id*="contact"],[class*="wpcf7"],[class*="wpforms"]'
          )) {
            found.push('contact-form');
          } else if (
            document.querySelectorAll('form').length > 0 &&
            !found.includes('login')
          ) {
            // Generic form (only if no more-specific contact-form or login already found)
            found.push('form');
          }

          // Maps
          if (document.querySelector(
            'iframe[src*="maps.google"],iframe[src*="openstreetmap"],[id*="map"],[class*="google-map"]'
          )) found.push('maps');

          // Video embeds
          if (document.querySelector(
            'iframe[src*="youtube"],iframe[src*="vimeo"],video'
          )) found.push('video-embed');

          // Social feeds
          if (document.querySelector(
            '[class*="instagram-feed"],[class*="twitter-feed"],[class*="facebook"]'
          )) found.push('social-feed');

          return found;
        });

        // Write raw HTML to output directory (the coding agent sanitises in SKILL.md Section 3)
        fs.writeFileSync(path.join(outputDir, filename), html, 'utf8');

        pagesVisited.push({ url, filename, features });

      } finally {
        await page.close();
      }
    }

    // ── Discover inner page links ────────────────────────────────────────────
    async function discoverInnerLinks() {
      const page = await context.newPage();
      try {
        await gotoWithFallback(page, targetUrl);

        const links = await page.evaluate(
          ({ base, excludePattern, priorityPattern }) => {
            const EXCLUDE = new RegExp(excludePattern, 'i');
            const PRIORITY = new RegExp(priorityPattern, 'i');

            const allLinks = Array.from(document.querySelectorAll('a[href]'))
              .map(a => {
                try { return new URL(a.href).href; } catch { return null; }
              })
              .filter(href => {
                if (!href) return false;
                try {
                  const u = new URL(href);
                  return (
                    u.origin === new URL(base).origin &&
                    u.pathname !== '/' &&
                    !EXCLUDE.test(href)
                  );
                } catch { return false; }
              });

            // Deduplicate
            const seen = new Set();
            const unique = allLinks.filter(h => {
              const key = new URL(h).pathname;
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            });

            // Priority links first, then the rest
            const priority = unique.filter(h => PRIORITY.test(h));
            const others   = unique.filter(h => !PRIORITY.test(h));
            return [...priority, ...others].slice(0, 5);
          },
          {
            base:           targetUrl,
            excludePattern: EXCLUDE_PATTERNS.source,
            priorityPattern: PRIORITY_PATTERNS.source
          }
        );

        return links;
      } finally {
        await page.close();
      }
    }

    // ── Scrape homepage ──────────────────────────────────────────────────────
    await scrapePage(targetUrl, 'index.html');

    // ── Discover and scrape inner pages (up to 4 additional) ────────────────
    let innerLinks = [];
    try {
      innerLinks = await discoverInnerLinks();
    } catch (e) {
      // Discovery failure is non-fatal, continue with homepage only
      failedPages.push({ url: targetUrl + ' (inner-link discovery)', error: e.message });
    }

    for (const link of innerLinks.slice(0, 4)) {
      const filename = pathToFilename(link);
      try {
        await scrapePage(link, filename);
      } catch (e) {
        // Inner page failure: degrade gracefully (Pitfall 3 / CONTEXT.md Area 1)
        failedPages.push({ url: link, error: e.message });
      }
    }

    // ── Write concatenated CSS ───────────────────────────────────────────────
    // Deduplication not required, the Python CSS extractor uses set() for tokens
    fs.writeFileSync(path.join(outputDir, 'styles', 'main.css'), allCSSText, 'utf8');

    // ── Deduplicate dynamic features across all pages ────────────────────────
    const allFeatures = [];
    for (const p of pagesVisited) {
      for (const f of (p.features || [])) {
        if (!allFeatures.includes(f)) allFeatures.push(f);
      }
    }

    // ── Write scrape.json manifest ───────────────────────────────────────────
    const manifest = {
      source_url:       targetUrl,
      scraped_at:       new Date().toISOString(),
      pages:            pagesVisited,
      images:           images.slice(0, 20),   // cap at 20
      fonts:            Array.from(fonts),
      dynamic_features: allFeatures,
      css_size_bytes:   Buffer.byteLength(allCSSText, 'utf8'),
      failed_pages:     failedPages,
      // robots_status will be added by SKILL.md Section 3 after confirmation
      spa_fallback_used: spaFallbackUsed
    };

    fs.writeFileSync(
      path.join(outputDir, 'scrape.json'),
      JSON.stringify(manifest, null, 2),
      'utf8'
    );

    process.stdout.write(JSON.stringify({ success: true, manifest }) + '\n');

  } catch (err) {
    // Homepage failure, abort with error
    process.stdout.write(JSON.stringify({ success: false, error: err.message }) + '\n');
    process.exit(1);

  } finally {
    // Always close the browser (Pitfall 3: avoid leaving temp resources open)
    if (browser) {
      await browser.close();
    }
  }
})();
