---
name: build-scrape
description: Scrape a URL with Playwright headless browser, check robots.txt and display copyright disclaimer, sanitise all content with AI-generated placeholders, detect dynamic features, and produce a clean HTML/CSS directory for the build-visual FSE pipeline
requires: [node, playwright, robots-parser, python3]
runs-after: [build-scaffold Section 2, build-mcp Section 2]
runs-before: [build-visual Section 2]
---

# Build Scrape Skill

Scrapes a target URL with Playwright headless Chromium, enforces ethical guardrails (robots.txt check + copyright disclaimer + interactive confirmation), sanitises all content with AI-generated placeholder text and dimensions, and produces a clean HTML/CSS directory that feeds directly into the `build-visual` FSE pipeline - as if the user had exported a Figma or Canva design.

**Critical sequencing:** This skill runs AFTER `build-scaffold` and `build-mcp` complete (WordPress is installed, MCP adapter is active) and BEFORE `build-visual` Sections 2-6 (CSS token extraction, theme scaffolding, font download, activation, SETUP.md).

This skill expects the following variables to already be set by the calling command:

- `SOURCE_URL` - the URL to scrape (set by COMMAND.md Section 1 argument parsing)
- `BUILD_DIR` - absolute path to the build directory (set by build-scaffold Section 2)
- `SLUG` - build slug (set by COMMAND.md Section 1)
- `SITE_TITLE` - site title (set by COMMAND.md Section 1)
- `PLUGIN_DIR` - absolute path to the CoWork plugin directory
- `WP` - WP-CLI command prefix (set by build-scaffold Section 4)

---

## Section 0: Prerequisite Check

Check that Playwright and robots-parser are installed before proceeding. Create the temp scrape directory and register an EXIT trap for cleanup.

```bash
echo "[Build] build-scrape: checking prerequisites..."

# Check Playwright
if ! node -e "require('playwright')" 2>/dev/null; then
  echo ""
  echo "ERROR: Playwright is required for URL clone mode."
  echo "  Install with:"
  echo "    npm install playwright"
  echo "    npx playwright install chromium"
  echo ""
  exit 1
fi

# Check robots-parser
if ! node -e "require('robots-parser')" 2>/dev/null; then
  echo ""
  echo "ERROR: robots-parser is required for URL clone mode."
  echo "  Install with:"
  echo "    npm install robots-parser"
  echo ""
  exit 1
fi

echo "[Build] Prerequisites: playwright OK, robots-parser OK"

# Create temp scrape directory
SCRAPE_DIR="/tmp/scrape_${SLUG}_$$"
mkdir -p "$SCRAPE_DIR"

# EXIT trap: always clean up temp directory (Pitfall 3)
trap "rm -rf '$SCRAPE_DIR'" EXIT

echo "[Build] Scrape temp directory: $SCRAPE_DIR"
```

---

## Section 1: Pre-Scrape Guard (robots.txt + Copyright Disclaimer + Confirmation)

Fetch and parse robots.txt, display the review banner with the copyright disclaimer, and require explicit interactive confirmation before any page request to the target site.

**IMPORTANT:** No network requests to `$SOURCE_URL` are made until after the user confirms.

### 1a: robots.txt Check

```bash
echo "[Build] Checking robots.txt for $SOURCE_URL..."

ROBOTS_CHECK=$(SOURCE_URL="$SOURCE_URL" node - <<'NODEOF'
const robotsParser = require('robots-parser');
const https = require('https');
const http  = require('http');
const { URL } = require('url');

const sourceUrl = process.env.SOURCE_URL;
const base      = new URL(sourceUrl);
const robotsUrl = `${base.origin}/robots.txt`;

const client = robotsUrl.startsWith('https') ? https : http;

const req = client.get(robotsUrl, { timeout: 10000 }, (res) => {
  let body = '';
  res.on('data', d => body += d);
  res.on('end', () => {
    const robots   = robotsParser(robotsUrl, body);
    const allowed  = robots.isAllowed(sourceUrl, 'WPCoWork/1.0');
    const disallowed = robots.isDisallowed(sourceUrl, 'WPCoWork/1.0');
    process.stdout.write(JSON.stringify({
      robots_url:  robotsUrl,
      source_url:  sourceUrl,
      allowed:     allowed !== false,
      disallowed:  disallowed === true,
      raw_preview: body.substring(0, 500)
    }) + '\n');
  });
});

req.on('error', () => {
  // No robots.txt or unreachable - treat as allowed per RFC 9309
  process.stdout.write(JSON.stringify({
    allowed: true,
    disallowed: false,
    error: 'No robots.txt found or unreachable - treating as allowed'
  }) + '\n');
});

req.on('timeout', () => {
  req.destroy();
  process.stdout.write(JSON.stringify({
    allowed: true,
    disallowed: false,
    error: 'robots.txt fetch timed out - treating as allowed'
  }) + '\n');
});
NODEOF
)

ROBOTS_ALLOWED=$(echo "$ROBOTS_CHECK" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('true' if d.get('allowed', True) else 'false')")
```

### 1b: Display Review Banner and Copyright Disclaimer

```bash
echo ""
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│                    URL CLONE MODE - REVIEW REQUIRED                    │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Source URL: $SOURCE_URL"
echo ""

if [ "$ROBOTS_ALLOWED" = "false" ]; then
  echo "WARNING: robots.txt for this site disallows scraping of this URL."
  echo "         Proceeding is your responsibility under applicable laws."
else
  echo "robots.txt check: OK (crawling not restricted for this URL)"
fi

echo ""
echo "IMPORTANT: This tool reproduces visual layout structure only."
echo "           All text and images are replaced with AI-generated placeholders."
echo "           You are responsible for ensuring your use complies with"
echo "           applicable copyright and terms of service laws."
echo ""
echo "The generated site will contain:"
echo "  - Source site's color palette and typography (flagged in SETUP.md)"
echo "  - AI-generated fictional placeholder content (no scraped text)"
echo "  - Dimension-matched placeholder images (no source images downloaded)"
echo ""
```

### 1c: Interactive Confirmation Gate

```bash
# TTY check required - read -p hangs in non-interactive contexts (Pitfall 6)
if [ -t 0 ]; then
  read -p "Proceed with URL clone? (y/N): " USER_CONFIRM
else
  echo "ERROR: URL clone mode requires an interactive terminal (TTY not detected)."
  echo "       Run this command in an interactive shell, not a piped or CI context."
  echo ""
  exit 1
fi

if [ "$USER_CONFIRM" != "y" ] && [ "$USER_CONFIRM" != "Y" ]; then
  echo ""
  echo "URL clone cancelled."
  echo ""
  exit 0
fi

echo ""
echo "[Build] User confirmed. Recording robots status..."

# Store robots status for scrape.json update in Section 3
if [ "$ROBOTS_ALLOWED" = "true" ]; then
  ROBOTS_STATUS="allowed"
else
  ROBOTS_STATUS="disallowed-override"
fi

echo "[Build] robots_status=$ROBOTS_STATUS"
echo "[Build] Beginning Playwright scrape..."
```

---

## Section 2: Playwright Scraping

Invoke `scraper.js` as a Node.js subprocess. Parse the JSON result and handle homepage failures as build-aborting errors. Inner page failures are already handled gracefully inside `scraper.js` (they appear in `failed_pages`).

```bash
SCRAPE_RESULT=$(node "$PLUGIN_DIR/skills/build-scrape/scraper.js" "$SOURCE_URL" "$SCRAPE_DIR" 2>&1)

# Check whether the scrape succeeded
SCRAPE_SUCCESS=$(echo "$SCRAPE_RESULT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('true' if d.get('success') else 'false')" 2>/dev/null || echo "false")

if [ "$SCRAPE_SUCCESS" != "true" ]; then
  SCRAPE_ERROR=$(echo "$SCRAPE_RESULT" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d.get('error','Unknown scrape error'))" 2>/dev/null || echo "$SCRAPE_RESULT")
  echo ""
  echo "ERROR: Failed to scrape $SOURCE_URL"
  echo "       $SCRAPE_ERROR"
  echo ""
  exit 1
fi

SCRAPE_MANIFEST="$SCRAPE_DIR/scrape.json"

# Log scrape summary
PAGES_COUNT=$(python3 -c \
  "import json; d=json.load(open('$SCRAPE_MANIFEST')); print(len(d.get('pages',[])))" 2>/dev/null || echo "?")
CSS_SIZE=$(python3 -c \
  "import json; d=json.load(open('$SCRAPE_MANIFEST')); print(d.get('css_size_bytes',0))" 2>/dev/null || echo "?")
FEATURES=$(python3 -c \
  "import json; d=json.load(open('$SCRAPE_MANIFEST')); print(', '.join(d.get('dynamic_features',[])) or 'none')" 2>/dev/null || echo "?")
IMAGES_COUNT=$(python3 -c \
  "import json; d=json.load(open('$SCRAPE_MANIFEST')); print(len(d.get('images',[])))" 2>/dev/null || echo "?")

echo "[Build] Scrape complete:"
echo "[Build]   Pages scraped:     $PAGES_COUNT"
echo "[Build]   CSS size (bytes):  $CSS_SIZE"
echo "[Build]   Dynamic features:  $FEATURES"
echo "[Build]   Images noted:      $IMAGES_COUNT (dimensions only - no downloads)"
```

---

## Section 3: Content Sanitisation (Claude In-Context Step)

This section is executed by Claude as an in-context judgment step. Claude reads each HTML file written by `scraper.js` and rewrites it with fictional placeholder content. No external tool is called - Claude performs all replacements using its own language capability.

**Claude performs the following replacements on each `.html` file in `$SCRAPE_DIR`:**

### 3a: HTML Content Replacements (per file)

1. **Text content replacement:** For all text inside `<p>`, `<span>`, `<li>`, `<td>`, `<h1>`, `<h2>`, `<h3>`, `<h4>`, `<h5>`, `<h6>` tags - replace with fictional placeholder text that matches the approximate word count. Use generic business/site copy relevant to a generic version of the detected site type (e.g. professional services, retail, portfolio, blog). Do NOT use Lorem Ipsum - use readable placeholder prose ("Providing expert solutions for modern businesses", "Our team brings over a decade of experience", etc.).

2. **Brand name replacement:** Detect the source brand name from: `<title>`, `<meta name="description">`, logo `<img alt="...">`, prominent `<h1>`. Replace all occurrences of the detected brand name throughout the file with "Your Brand" or "Company Name".

3. **Logo image replacement:** For `<img>` elements that function as the site logo (identified by: alt text containing brand name, `class*="logo"`, `id*="logo"`, inside `<a>` pointing to `/`): remove the `src` attribute, add `data-placeholder="logo"` attribute. Example: `<img class="site-logo" data-placeholder="logo" alt="Company Name Logo">`.

4. **Navigation link text replacement:** For all `<a>` elements inside `<nav>`, `<header>`, or elements with `role="navigation"`: replace the link text with generic navigation labels (Home, About, Services, Work, Portfolio, Blog, Contact, Team, Pricing, FAQ). Keep `href` attributes intact - layout preservation depends on the link structure remaining valid.

5. **Script tag removal:** Remove all `<script>` tags (both inline and external `<script src="...">` tags). JS is not needed for design token extraction and its presence may interfere with static analysis in the build-visual pipeline.

6. **External stylesheet link removal:** Remove `<link rel="stylesheet">` tags that point to the source domain or its CDN (the CSS is already captured in `styles/main.css`). Keep `<link rel="stylesheet">` tags for Google Fonts (these are useful font references that the build-visual pipeline can leverage).

7. **Brand-identifying meta tag removal:** Strip the following `<meta>` tags to prevent brand information from leaking into the theme: `og:title`, `og:site_name`, `og:description`, `twitter:title`, `twitter:site`, `twitter:description`, `name="description"` (the original site description). Replace the `<title>` tag content with `{SITE_TITLE}` (the user's chosen site title from the build arguments).

8. **Dynamic feature placeholder insertion:** Where a dynamic feature was detected on a page (cross-reference with that page's `features` array in `scrape.json`), insert a styled placeholder `<div>` immediately after the detected element's parent section. Use this format:

   ```html
   <div style="border: 2px dashed #aaa; padding: 2rem; margin: 1rem 0; text-align: center; color: #666; background: #f9f9f9;">
     [Search functionality - manual setup required. See SETUP.md for recommended plugins.]
   </div>
   ```

   Use the appropriate feature name in the placeholder text (Search, Contact Form, E-commerce Cart, Member Login, Map, Video Embed, Social Feed).

**Claude writes the sanitised HTML back to the same file path**, overwriting the raw scraped version.

### 3b: CSS Sanitisation (Python script - automated)

Strip `content: "..."` CSS declarations that contain text (Pitfall 5):

```bash
python3 -c "
import re, sys
css_file = '$SCRAPE_DIR/styles/main.css'
with open(css_file, 'r', errors='ignore') as f:
    css = f.read()
# Replace content: '...' or content: \"...\" with content: \"\"
css = re.sub(r'content\s*:\s*[\"\\']([^\"\\'>{]+)[\"\\']', 'content: \"\"', css)
with open(css_file, 'w') as f:
    f.write(css)
print('[Build] CSS content: declarations sanitised')
"
```

### 3c: Update scrape.json with robots_status

```bash
python3 -c "
import json
manifest_path = '$SCRAPE_DIR/scrape.json'
with open(manifest_path, 'r') as f:
    manifest = json.load(f)
manifest['robots_status'] = '$ROBOTS_STATUS'
with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)
print('[Build] scrape.json updated with robots_status=$ROBOTS_STATUS')
"
```

---

## Section 4: SETUP.md URL Clone Appendix

After `build-visual` Section 6 writes the base `SETUP.md`, this section **appends** URL-clone-specific content. This section is run by COMMAND.md Section 3c after the build-visual pipeline completes.

Claude reads `$SCRAPE_DIR/scrape.json` and generates the following markdown, then appends it to `$BUILD_DIR/SETUP.md`:

```bash
CLONE_TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

python3 - <<PYEOF
import json, sys, os

manifest_path = os.environ.get('SCRAPE_MANIFEST', '$SCRAPE_DIR/scrape.json')
build_dir     = os.environ.get('BUILD_DIR', '$BUILD_DIR')
setup_md_path = os.path.join(build_dir, 'SETUP.md')
clone_ts      = '$CLONE_TIMESTAMP'

with open(manifest_path, 'r') as f:
    manifest = json.load(f)

source_url   = manifest.get('source_url', 'unknown')
dynamic_feats = manifest.get('dynamic_features', [])
pages        = manifest.get('pages', [])
failed_pages = manifest.get('failed_pages', [])
spa_fallback = manifest.get('spa_fallback_used', False)

# Dynamic feature to WP.org plugin mapping (all 7 features)
PLUGIN_MAP = {
    'ecommerce':    ('E-commerce (cart, checkout)',       'WooCommerce',                              'wordpress.org/plugins/woocommerce/'),
    'search':       ('Site search',                       'WordPress built-in search (no plugin needed)', ''),
    'login':        ('Member login / registration',       'Theme My Login',                           'wordpress.org/plugins/theme-my-login/'),
    'contact-form': ('Contact form',                      'WPForms Lite',                             'wordpress.org/plugins/wpforms-lite/'),
    'form':         ('Generic form',                      'WPForms Lite',                             'wordpress.org/plugins/wpforms-lite/'),
    'maps':         ('Map embed',                         'WP Google Maps',                           'wordpress.org/plugins/wp-google-maps/'),
    'video-embed':  ('Video embed',                       'WordPress built-in Video block (no plugin needed)', ''),
    'social-feed':  ('Social media feed',                 'Smash Balloon Social Post Feed',           'wordpress.org/plugins/custom-facebook-feed/'),
}

# Build which pages each feature was found on
feature_pages = {}
for page in pages:
    for feat in page.get('features', []):
        feature_pages.setdefault(feat, []).append(page.get('url', 'unknown'))

appendix = []
appendix.append('')
appendix.append('---')
appendix.append('')
appendix.append('## URL Clone Information')
appendix.append('')
appendix.append(f'**Cloned from:** [{source_url}]({source_url})')
appendix.append(f'**Cloned at:** {clone_ts}')
appendix.append('')
appendix.append('### Color Palette Attribution')
appendix.append('')
appendix.append('The color palette used in this theme was extracted from the source URL.')
appendix.append('**Before going live, replace with your own brand colors:**')
appendix.append('')
appendix.append('1. Open Appearance > Editor > Styles > Colors')
appendix.append(f'2. Current palette was sourced from: {source_url}')
appendix.append('3. Colors are not copyrighted by themselves, but this theme\'s visual')
appendix.append('   resemblance to the source is your responsibility.')
appendix.append('')

if dynamic_feats:
    appendix.append('### Dynamic Features Detected (Not Cloned)')
    appendix.append('')
    appendix.append('The following interactive features were detected on the source site but cannot')
    appendix.append('be automatically reproduced from a URL scrape. Visual placeholder blocks have')
    appendix.append('been inserted in the templates. Manual setup required:')
    appendix.append('')
    appendix.append('| Feature | Detected On | Recommended WP Plugin |')
    appendix.append('|---------|-------------|----------------------|')
    for feat in dynamic_feats:
        if feat in PLUGIN_MAP:
            label, plugin, url = PLUGIN_MAP[feat]
            detected_on = ', '.join(feature_pages.get(feat, ['unknown']))
            if url:
                plugin_link = f'[{plugin}]({url})'
            else:
                plugin_link = plugin
            appendix.append(f'| {label} | {detected_on} | {plugin_link} |')
    appendix.append('')
else:
    appendix.append('### Dynamic Features Detected')
    appendix.append('')
    appendix.append('No dynamic features (e-commerce, forms, search, maps, video, social feeds) were detected on the scraped pages.')
    appendix.append('')

appendix.append('### Pages Scraped')
appendix.append('')
appendix.append('| Page | Filename | Status |')
appendix.append('|------|----------|--------|')
for page in pages:
    url = page.get('url', 'unknown')
    filename = page.get('filename', 'unknown')
    appendix.append(f'| {url} | {filename} | Scraped |')
for fp in failed_pages:
    url   = fp.get('url', 'unknown')
    error = fp.get('error', 'unknown error')
    appendix.append(f'| {url} | - | Failed: {error[:80]} |')
appendix.append('')

if spa_fallback:
    appendix.append('> **Note:** One or more pages used the `domcontentloaded` fallback due to')
    appendix.append('> continuous background network activity. Dynamic feature detection may be')
    appendix.append('> incomplete for JavaScript-heavy or SPA-rendered pages.')
    appendix.append('')

appendix.append('---')
appendix.append('')
appendix.append('*URL Clone mode - build-scrape skill + build-visual FSE pipeline*')
appendix.append(f'*Source: {source_url}*')

with open(setup_md_path, 'a') as f:
    f.write('\n'.join(appendix) + '\n')

print('[Build] SETUP.md URL clone appendix written.')
PYEOF
```

---

## Section 5: Output Variables

The following variables are set by this skill for consumption by COMMAND.md Section 3c and the downstream `build-visual` skill:

```bash
# Set by Section 0
# SCRAPE_DIR="/tmp/scrape_${SLUG}_$$"   - already set above

# Set by Section 2
# SCRAPE_MANIFEST="$SCRAPE_DIR/scrape.json"

# Set by Section 1c
# ROBOTS_STATUS="allowed" or "disallowed-override"

# Set for build-visual consumption
VISUAL_PATH="$SCRAPE_DIR"     # build-visual Section 2 reads CSS from this directory
VISUAL_MODE="html-css"        # ALWAYS html-css for URL builds - NEVER "screenshot"

echo "[Build] Output variables:"
echo "[Build]   SCRAPE_DIR=$SCRAPE_DIR"
echo "[Build]   SCRAPE_MANIFEST=$SCRAPE_MANIFEST"
echo "[Build]   ROBOTS_STATUS=$ROBOTS_STATUS"
echo "[Build]   VISUAL_PATH=$VISUAL_PATH"
echo "[Build]   VISUAL_MODE=$VISUAL_MODE"
```

**Variable reference:**

| Variable         | Value                              | Consumer                           |
|------------------|------------------------------------|------------------------------------|
| `SCRAPE_DIR`     | `/tmp/scrape_{SLUG}_{PID}`         | COMMAND.md Section 3c, build-visual |
| `SCRAPE_MANIFEST`| `$SCRAPE_DIR/scrape.json`          | Section 4 (SETUP.md appendix)      |
| `ROBOTS_STATUS`  | `"allowed"` or `"disallowed-override"` | Section 3c, scrape.json          |
| `VISUAL_PATH`    | `$SCRAPE_DIR`                      | build-visual Section 2a (CSS token extraction) |
| `VISUAL_MODE`    | `"html-css"` (always)              | build-visual Section 1a (input detection skipped - mode pre-set) |

---

## Implementation Notes

**build-scrape always produces html-css output:** `VISUAL_MODE` must always be set to `"html-css"` when this skill is used. URL builds produce a directory containing `.html` and `.css` files - never a screenshot image. Setting `VISUAL_MODE="screenshot"` for URL builds is an anti-pattern that will cause build-visual to misroute the input.

**SCRAPE_DIR lifetime:** The temp directory is cleaned up by the EXIT trap registered in Section 0. After `build-visual` completes its pipeline (Sections 2-6), COMMAND.md Section 3c copies `scrape.json` to `$BUILD_DIR` before the EXIT trap fires. Only `scrape.json` is preserved in the final build zip - the raw and sanitised HTML/CSS are temporary.

**build-visual Section 1 is skipped for URL builds:** COMMAND.md Section 3c sets `VISUAL_MODE="html-css"` before calling `build-visual` Sections 2-6. The input detection logic in `build-visual` Section 1a is not needed - the mode is already determined by `build-scrape`.

**Content sanitisation is Claude's in-context judgment:** Section 3a requires Claude to read, rewrite, and overwrite each HTML file. There is no automated verification that all verbatim text has been removed. The CONTEXT.md decision is that this is an AI judgment step - acceptable accuracy is achieved by following the 8 replacement rules explicitly. No post-sanitisation text-extraction verification is performed at build time.

**Dynamic feature detection confidence:** MEDIUM for JavaScript-heavy SPAs. The Playwright `waitUntil: 'networkidle'` strategy gives JS frameworks time to mount their UI before DOM selectors are evaluated. However, sites with continuous background API calls fall back to `domcontentloaded` - in these cases, some dynamically rendered elements may not be present in the DOM when selectors run. The `spa_fallback_used` flag in `scrape.json` signals this condition.

**robots-parser RFC 9309 compliance:** `robots-parser` v3.0.1 handles wildcard paths, `$` end-of-line patterns, and case variants correctly. Do not replace it with inline regex. If robots.txt is unreachable or absent, the check defaults to "allowed" per RFC 9309 Section 2.3 (treat missing robots.txt as allow-all).

**Anti-patterns (never do):**
- Never skip Section 1 (robots.txt check + disclaimer) - transparency is required even if the check result is "allowed"
- Never set `VISUAL_MODE="screenshot"` for URL builds
- Never download source images - `scraper.js` collects dimensions only via `getBoundingClientRect()` / `naturalWidth/Height`
- Never pass raw (unsanitised) HTML to `build-visual` - Section 3a must run before `VISUAL_PATH` is used
- Never persist `$SCRAPE_DIR` in the build zip - only `scrape.json` is copied to `$BUILD_DIR`
- Never use `--no-confirm` or bypass the TTY check - URL clone mode always requires interactive confirmation
- Never hardcode `playwright` binary path - use `require('playwright')` (Section 0 prerequisite check surfaces missing installs)

**References:**
- `@skills/build-visual/SKILL.md` - downstream consumer of `VISUAL_PATH` and `VISUAL_MODE`; Section 2a CSS token extraction; Section 1a html-css input detection (skipped for URL builds)
- `@commands/build/COMMAND.md` - Section 3c URL build execution; `VISUAL_PATH` handoff pattern
- `@.planning/phases/15-url-clone-creation/15-RESEARCH.md` - Playwright patterns, robots-parser API, pitfalls 1-7, anti-patterns
- `@.planning/phases/15-url-clone-creation/15-CONTEXT.md` - Locked decisions: scraping scope, copyright guardrails, content replacement, dynamic feature detection
