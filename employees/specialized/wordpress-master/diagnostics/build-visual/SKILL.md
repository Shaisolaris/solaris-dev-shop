---
name: build-visual
description: Generate a custom FSE block theme from structured HTML/CSS design exports or screenshot images - extracts design tokens, maps HTML to Gutenberg blocks, bundles Google Fonts, and produces an installable theme with custom-{slug} prefix
requires: [wp-cli, docker-mysql-running, python3, curl]
runs-after: [build-mcp Section 2]
runs-before: [build-git Section 3]
---

# Build Visual Skill

Translates a visual design input (HTML/CSS export directory or screenshot image) into a complete, installable WordPress FSE block theme with a `custom-{slug}` naming prefix. This skill is the core engine for Phase 14's visual input mode - it reads a design, extracts tokens, scaffolds the FSE theme directory, downloads and bundles Google Fonts, activates the theme via WP-CLI, and generates a visual-specific SETUP.md.

**Critical sequencing:** This skill runs AFTER `build-mcp` Section 2 (MCP adapter activated, database re-exported) and BEFORE `build-git` Section 3 (dynamic .gitignore update adds custom-{slug} to tracked paths).

This skill expects the following variables to already be set by the calling command:

- `BUILD_DIR` - absolute path to the build directory (set by build-scaffold Section 2)
- `WP` - the WP-CLI command prefix (e.g. `wp --path=$BUILD_DIR` or the Docker equivalent, set by build-scaffold Section 4)
- `VISUAL_PATH` - path to the design input (directory or image file, set by COMMAND.md Section 1)
- `SLUG` - build slug (set by COMMAND.md Section 1)
- `SITE_TITLE` - site title (set by COMMAND.md Section 1)
- `PLUGIN_DIR` - absolute path to the CoWork plugin directory

## Section 1: Input Detection and Design Parsing

Detect whether `VISUAL_PATH` is a directory (HTML/CSS export) or an image file (screenshot), then parse the design to prepare for token extraction.

### 1a: Input Type Detection

```bash
# VISUAL_PATH set by COMMAND.md Section 1 argument parsing
THEME_SLUG="custom-${SLUG}"
THEME_DIR="$BUILD_DIR/wp-content/themes/${THEME_SLUG}"

if [ -d "$VISUAL_PATH" ]; then
  # Check if directory actually contains HTML/CSS files
  HTML_COUNT=$(find "$VISUAL_PATH" -maxdepth 3 -name "*.html" -o -name "*.css" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$HTML_COUNT" -gt 0 ]; then
    VISUAL_MODE="html-css"
    echo "[Build] Visual input: HTML/CSS export directory ($VISUAL_PATH) - $HTML_COUNT files found"
  else
    # Directory contains no HTML/CSS - check for images (Canva/Miro image-only exports)
    IMG_FILE=$(find "$VISUAL_PATH" -maxdepth 3 \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.webp" \) 2>/dev/null | sort -k5 -rn 2>/dev/null | head -1)
    if [ -n "$IMG_FILE" ]; then
      VISUAL_MODE="screenshot"
      VISUAL_PATH="$IMG_FILE"
      echo "[Build] Visual input: directory contained only images - switching to screenshot mode ($VISUAL_PATH)"
    else
      echo ""
      echo "ERROR: --visual directory contains no HTML, CSS, or image files: $VISUAL_PATH"
      echo ""
      exit 1
    fi
  fi
elif [ -f "$VISUAL_PATH" ]; then
  # Check file extension for supported image formats
  EXT=$(echo "${VISUAL_PATH##*.}" | tr '[:upper:]' '[:lower:]')
  case "$EXT" in
    png|jpg|jpeg|gif|webp|bmp|tiff)
      VISUAL_MODE="screenshot"
      echo "[Build] Visual input: Screenshot image ($VISUAL_PATH)"
      ;;
    *)
      echo ""
      echo "ERROR: --visual path must be a directory (HTML/CSS export) or an image file (png, jpg, jpeg, gif, webp, bmp, tiff)"
      echo ""
      exit 1
      ;;
  esac
else
  echo ""
  echo "ERROR: --visual path does not exist: $VISUAL_PATH"
  echo ""
  exit 1
fi

echo "[Build] VISUAL_MODE=$VISUAL_MODE, THEME_SLUG=$THEME_SLUG"
```

### 1b: HTML/CSS Path - File Inventory and Image Collection

When `VISUAL_MODE="html-css"`, collect all design files for Section 2 processing. Copy images to a staging area for later placement in `assets/images/`.

```bash
if [ "$VISUAL_MODE" = "html-css" ]; then
  # Collect CSS files for token extraction
  CSS_FILES=$(find "$VISUAL_PATH" -maxdepth 5 -name "*.css" 2>/dev/null)
  HTML_FILES=$(find "$VISUAL_PATH" -maxdepth 5 -name "*.html" 2>/dev/null)

  # Stage exported images for assets/images/ placement (Section 3g)
  IMAGES_STAGE="/tmp/visual_images_${SLUG}_$$"
  mkdir -p "$IMAGES_STAGE"
  find "$VISUAL_PATH" -maxdepth 5 \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \
    -o -name "*.gif" -o -name "*.webp" -o -name "*.svg" \) 2>/dev/null \
    | while read img; do cp "$img" "$IMAGES_STAGE/" 2>/dev/null; done

  IMG_STAGE_COUNT=$(ls "$IMAGES_STAGE" 2>/dev/null | wc -l | tr -d ' ')
  echo "[Build] Design files staged: $(echo "$CSS_FILES" | wc -l | tr -d ' ') CSS, $(echo "$HTML_FILES" | wc -l | tr -d ' ') HTML, $IMG_STAGE_COUNT images"
fi
```

### 1c: Screenshot Path - Claude Multimodal Vision Analysis

When `VISUAL_MODE="screenshot"`, Claude reads the image file using multimodal vision capability and performs design interpretation. This is an in-context Claude judgment step - no external tool needed.

Claude reads `$VISUAL_PATH` as an image and identifies:

1. **3-6 dominant/brand colors** - output as hex values (e.g. `#2D3748`)
2. **Heading font name + body font name** - or the closest Google Font matches if proprietary
3. **Approximate section boundaries** - header region, hero area, main content sections, footer region
4. **Image placeholder areas** - with approximate aspect ratios (e.g. hero 16:9, portrait 1:1, landscape 4:3)
5. **Navigation labels** - any visible menu text (Home, About, Services, Contact, etc.)

Claude outputs a structured JSON block:

```json
{
  "colors": ["#2D3748", "#4A5568", "#E53E3E", "#F7FAFC", "#1A202C"],
  "fonts": ["Playfair Display", "DM Sans"],
  "sections": {
    "header_height_approx": "80px",
    "hero_present": true,
    "footer_present": true
  },
  "image_areas": [
    {"name": "hero", "width": 1200, "height": 630, "ratio": "16:9"},
    {"name": "about", "width": 800, "height": 600, "ratio": "4:3"}
  ],
  "nav_labels": ["Home", "About", "Services", "Contact"]
}
```

This JSON is consumed identically to the HTML/CSS extraction output in Section 2.

Set output: `VISUAL_MODE` ("html-css" or "screenshot"), `THEME_SLUG` ("custom-${SLUG}"), `THEME_DIR` (absolute path to theme directory).

---

## Section 2: Design Token Extraction

Extract color palette, font families, and spacing values from the design. Both input paths produce identical output JSON for downstream consumption.

### 2a: HTML/CSS Path - Python CSS Parser

Run the Python CSS token extractor against all CSS files from the design export:

```bash
TOKENS_FILE="/tmp/design_tokens_${SLUG}_$$.json"

python3 << 'PYEOF'
import re, json, sys, os, glob

export_dir = os.environ.get('VISUAL_PATH', '')
tokens_file = os.environ.get('TOKENS_FILE', '/tmp/design_tokens.json')

css_files = glob.glob(os.path.join(export_dir, '**/*.css'), recursive=True)

colors = set()
fonts = set()

# Color extraction patterns
COLOR_PATTERNS = [
    r'#[0-9a-fA-F]{6}\b',                                 # 6-digit hex
    r'#[0-9a-fA-F]{3}\b',                                 # 3-digit hex
    r'rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)',              # rgb()
    r'hsl\(\s*\d+\s*,\s*[\d.]+%\s*,\s*[\d.]+%\s*\)',      # hsl()
]

# Font-family extraction
FONT_PATTERN = r'font-family\s*:\s*[\'"]?([^,;\'"{}]+)[\'"]?'

# Generic families to skip
SKIP_FONTS = {'inherit', 'initial', 'unset', 'sans-serif', 'serif', 'monospace',
              'cursive', 'fantasy', 'system-ui', '-apple-system', 'blinkmacsystemfont',
              'segoe ui', 'roboto', 'helvetica neue', 'arial', 'times new roman'}

for css_file in css_files:
    with open(css_file, 'r', errors='ignore') as f:
        css = f.read()
    for pat in COLOR_PATTERNS:
        colors.update(re.findall(pat, css, re.IGNORECASE))
    for m in re.finditer(FONT_PATTERN, css, re.IGNORECASE):
        font = m.group(1).strip().strip("'\"").strip()
        if font and font.lower() not in SKIP_FONTS and len(font) > 2:
            fonts.add(font)

result = {
    'colors': list(colors)[:12],
    'fonts': list(fonts)[:4],
}
with open(tokens_file, 'w') as f:
    json.dump(result, f, indent=2)
print(f"[Build] Tokens extracted: {len(result['colors'])} colors, {len(result['fonts'])} fonts")
PYEOF
```

### 2b: Screenshot Path - Use Claude's Multimodal Output

When `VISUAL_MODE="screenshot"`, the token JSON was already produced in Section 1c. Write it to `$TOKENS_FILE` from Claude's structured output.

### 2c: Font Mapping and Google Font Resolution

Claude reads the extracted `fonts` array from `$TOKENS_FILE` and determines:

- **Google Font match**: If the font name is a known Google Font (e.g. `Playfair Display`, `DM Sans`, `Inter`, `Roboto`), use directly.
- **Proprietary substitution**: If the font is proprietary (Adobe Fonts, paid typefaces) or unrecognisable, find the closest Google Font match by visual characteristics (serif/sans-serif, weight, x-height, personality).

Claude sets `FONT_MAP` as a JSON mapping of original → Google Font slug:

```bash
# Example FONT_MAP (Claude sets based on extraction)
FONT_MAP='{
  "Playfair Display": "playfair-display",
  "DM Sans": "dm-sans"
}'

# Track substitutions for SETUP.md
# Format: "Original Name → Google Font Substitute"
FONT_SUBSTITUTIONS=()
# Claude appends entries if a proprietary font was substituted:
# FONT_SUBSTITUTIONS+=("Aktiv Grotesk → Inter")
```

### 2d: Color Palette Construction

Claude reads the extracted colors and assigns semantic slugs:

```
primary   → dominant brand color (most prominent, used for CTA/headings)
secondary → supporting brand color (complementary to primary)
accent    → action/highlight color (buttons, links, hover states)
light     → background or near-white color
dark      → text or near-black color
custom-1 through custom-7 → additional extracted colors (if any)
```

Convert spacing values from px to rem (divide by 16). Limit palette to 12 colors maximum.

Set output: `EXTRACTED_COLORS` (array of `{slug, color, name}` objects), `EXTRACTED_FONTS` (array of font family names), `FONT_MAP` (mapping JSON), `FONT_SUBSTITUTIONS` (array of substitution strings).

---

## Section 3: Theme Scaffolding (Write All Files)

Create the complete FSE theme directory structure and write all theme files based on extracted tokens and design interpretation.

### 3a: Directory Structure Creation

```bash
echo "[Build] Creating FSE theme directory: $THEME_DIR"
mkdir -p "$THEME_DIR/assets/fonts"
mkdir -p "$THEME_DIR/assets/images"
mkdir -p "$THEME_DIR/templates"
mkdir -p "$THEME_DIR/parts"
mkdir -p "$THEME_DIR/patterns"
```

Expected final structure:
```
$BUILD_DIR/wp-content/themes/custom-${SLUG}/
  style.css
  theme.json
  functions.php
  assets/
    fonts/          (populated in Section 4)
    images/         (exported images or generated placeholders)
  templates/
    index.html
    front-page.html
    single.html
    page.html
    archive.html
    search.html
    404.html
  parts/
    header.html
    footer.html
  patterns/
    front-page.php
```

### 3b: style.css - WordPress Theme Header

Write `$THEME_DIR/style.css` with the WordPress theme file header and responsive CSS:

```css
/*
Theme Name:        Custom {Slug}
Theme URI:
Author:            WP CoWork Builder
Author URI:
Description:       Custom FSE block theme generated from design export. Built with WP CoWork Plugin.
Version:           1.0.0
Requires at least: 6.6
Tested up to:      6.7
Requires PHP:      8.0
License:           GNU General Public License v2 or later
License URI:       http://www.gnu.org/licenses/gpl-2.0.html
Text Domain:       custom-{slug}
*/

/* Responsive inference - stacks desktop columns for mobile */
@media (max-width: 768px) {
  .wp-block-columns {
    flex-direction: column;
  }
  .wp-block-column {
    width: 100% !important;
  }
  /* Scale display headings */
  h1.wp-block-heading { font-size: clamp(1.75rem, 5vw, 2.5rem); }
  h2.wp-block-heading { font-size: clamp(1.5rem, 4vw, 2rem); }
  h3.wp-block-heading { font-size: clamp(1.25rem, 3vw, 1.75rem); }
}

/* Required: prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

Replace `{Slug}` and `{slug}` with the actual slug values (e.g. `Custom Figma Portfolio`, `custom-figma-portfolio`).

### 3c: theme.json - Design Token Encoding

Write `$THEME_DIR/theme.json` using the v3 schema. Populate `settings.color.palette` with `EXTRACTED_COLORS`, populate `settings.typography.fontFamilies` with `EXTRACTED_FONTS` (using `file:./assets/fonts/` src paths - actual filenames updated in Section 4 after download).

```json
{
  "$schema": "https://schemas.wp.org/trunk/theme.json",
  "version": 3,
  "settings": {
    "appearanceTools": true,
    "layout": {
      "contentSize": "800px",
      "wideSize": "1280px"
    },
    "color": {
      "palette": [
        { "slug": "primary",   "color": "#2D3748", "name": "Primary"   },
        { "slug": "secondary", "color": "#4A5568", "name": "Secondary" },
        { "slug": "accent",    "color": "#E53E3E", "name": "Accent"    },
        { "slug": "light",     "color": "#F7FAFC", "name": "Light"     },
        { "slug": "dark",      "color": "#1A202C", "name": "Dark"      }
      ],
      "defaultPalette": false,
      "defaultGradients": false
    },
    "typography": {
      "fontFamilies": [
        {
          "name": "Heading Font",
          "slug": "heading",
          "fontFamily": "Playfair Display, Georgia, serif",
          "fontFace": [
            {
              "fontFamily": "Playfair Display",
              "fontWeight": "400",
              "fontStyle": "normal",
              "fontDisplay": "swap",
              "src": ["file:./assets/fonts/playfair-display-v36-latin-regular.woff2"]
            },
            {
              "fontFamily": "Playfair Display",
              "fontWeight": "700",
              "fontStyle": "normal",
              "fontDisplay": "swap",
              "src": ["file:./assets/fonts/playfair-display-v36-latin-700.woff2"]
            }
          ]
        },
        {
          "name": "Body Font",
          "slug": "body",
          "fontFamily": "DM Sans, system-ui, sans-serif",
          "fontFace": [
            {
              "fontFamily": "DM Sans",
              "fontWeight": "400",
              "fontStyle": "normal",
              "fontDisplay": "swap",
              "src": ["file:./assets/fonts/dm-sans-v15-latin-regular.woff2"]
            },
            {
              "fontFamily": "DM Sans",
              "fontWeight": "700",
              "fontStyle": "normal",
              "fontDisplay": "swap",
              "src": ["file:./assets/fonts/dm-sans-v15-latin-700.woff2"]
            }
          ]
        }
      ],
      "fontSizes": [
        { "slug": "small",  "size": "0.875rem",                 "name": "Small"   },
        { "slug": "medium", "size": "1rem",                     "name": "Medium"  },
        { "slug": "large",  "size": "1.25rem",                  "name": "Large"   },
        { "slug": "xlarge", "size": "1.75rem",                  "name": "X-Large" },
        { "slug": "xxlarge","size": "2.25rem",                  "name": "2X-Large"},
        { "slug": "huge",   "size": "clamp(2.5rem, 4vw, 3.5rem)", "name": "Huge" }
      ]
    },
    "spacing": {
      "units": ["px", "em", "rem", "%"],
      "spacingSizes": [
        { "slug": "xs",  "size": "0.5rem", "name": "XS"  },
        { "slug": "sm",  "size": "1rem",   "name": "SM"  },
        { "slug": "md",  "size": "2rem",   "name": "MD"  },
        { "slug": "lg",  "size": "3rem",   "name": "LG"  },
        { "slug": "xl",  "size": "5rem",   "name": "XL"  },
        { "slug": "xxl", "size": "8rem",   "name": "XXL" }
      ]
    }
  },
  "styles": {
    "color": {
      "background": "var(--wp--preset--color--light)",
      "text": "var(--wp--preset--color--dark)"
    },
    "typography": {
      "fontFamily": "var(--wp--preset--font-family--body)",
      "fontSize": "var(--wp--preset--font-size--medium)",
      "lineHeight": "1.6"
    },
    "elements": {
      "heading": {
        "typography": {
          "fontFamily": "var(--wp--preset--font-family--heading)",
          "lineHeight": "1.2"
        }
      },
      "link": {
        "color": { "text": "var(--wp--preset--color--accent)" }
      },
      "button": {
        "color": {
          "background": "var(--wp--preset--color--accent)",
          "text": "var(--wp--preset--color--light)"
        },
        "border": { "radius": "4px" }
      }
    }
  },
  "templateParts": [
    { "slug": "header", "title": "Header", "area": "header" },
    { "slug": "footer", "title": "Footer", "area": "footer" }
  ]
}
```

Claude replaces the example color and font values above with the actual `EXTRACTED_COLORS` and `EXTRACTED_FONTS` values from Section 2. Spacing values from the design CSS are converted from px to rem (divide by 16) before encoding.

**CRITICAL: Validate JSON immediately after writing:**

```bash
python3 -c "import json; json.load(open('$THEME_DIR/theme.json'))" \
  && echo "[Build] theme.json validated: OK" \
  || echo "[Build] WARNING: theme.json JSON validation failed - check for syntax errors"
```

### 3d: functions.php - Pattern Registration

Write `$THEME_DIR/functions.php` with minimal PHP: register block pattern category for the theme's custom patterns. No font CDN enqueuing - fonts are bundled via `theme.json fontFace`, no external CDN requests.

```php
<?php
/**
 * Custom {Slug} Theme Functions
 * Theme: custom-{slug}
 * Generated by WP CoWork Plugin (visual build)
 */

if ( ! function_exists( 'custom_{slug}_setup' ) ) {
    function custom_{slug}_setup() {
        // Register theme's block pattern category
        if ( function_exists( 'register_block_pattern_category' ) ) {
            register_block_pattern_category(
                'custom-{slug}',
                array( 'label' => __( 'Custom {Slug} Patterns', 'custom-{slug}' ) )
            );
        }
    }
}
add_action( 'after_setup_theme', 'custom_{slug}_setup' );
```

Replace `{slug}` and `{Slug}` with the actual slug values throughout (e.g. `custom_figma_portfolio_setup`, `Figma Portfolio`).

### 3d-ii: patterns/ - Front-Page Starter Pattern

Write `$THEME_DIR/patterns/front-page.php`. This is the primary design translation as a reusable block pattern. Claude interprets the full design and outputs the complete front-page layout using WordPress block comment syntax.

```php
<?php
/**
 * Title: Front Page
 * Slug: custom-{slug}/front-page
 * Categories: custom-{slug}
 * Block Types: core/post-content
 */
?>
<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">

<!-- wp:cover {"url":"","dimRatio":40,"align":"full","style":{"color":{"duotone":"unset"}}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-background-dim-40 has-background-dim"></span>
<div class="wp-block-cover__inner-container">
<!-- wp:heading {"level":1,"textAlign":"center","style":{"typography":{"fontFamily":"var(--wp--preset--font-family--heading)"}}} -->
<h1 class="wp-block-heading has-text-align-center">Welcome to {Site Title}</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {"align":"center"} -->
<p class="has-text-align-center">Your site tagline goes here - describe what makes this site special.</p>
<!-- /wp:paragraph -->

<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"}} -->
<div class="wp-block-buttons">
<!-- wp:button {"backgroundColor":"accent","textColor":"light"} -->
<div class="wp-block-button"><a class="wp-block-button__link has-accent-background-color has-light-color has-background has-text-color wp-element-button">Get Started</a></div>
<!-- /wp:button -->
</div>
<!-- /wp:buttons -->
</div>
</div>
<!-- /wp:cover -->

</div>
<!-- /wp:group -->
```

Claude replaces the hero placeholder with the actual design interpretation. Additional pattern sections (services, about, testimonials, CTA) are added based on what Claude identifies in the design.

### 3e: templates/ - 7 WordPress Block Templates

Claude interprets the design and generates 7 HTML template files using WordPress block comment syntax. All templates reference the shared header and footer template parts.

**HTML-to-Block Mapping Table** (block-native first, Custom HTML fallback):

| HTML Pattern | WordPress Block | Notes |
|---|---|---|
| `<header>` | `wp:template-part {"slug":"header","tagName":"header"}` | Template part boundary |
| `<footer>` | `wp:template-part {"slug":"footer","tagName":"footer"}` | Template part boundary |
| `<nav>` / navigation | `wp:navigation` with `wp:navigation-link` children | Static placeholder labels from design |
| `<h1>`-`<h6>` | `wp:heading {"level":N}` | Preserve heading level from design |
| `<p>` | `wp:paragraph` | |
| `<img>` | `wp:image` | Use src from design export or placeholder |
| Hero with background | `wp:cover {"url":"...","dimRatio":N}` | Overlay opacity → dimRatio (0-100) |
| Two-column layout | `wp:columns` + `wp:column {"width":"50%"}` | |
| Three-column layout | `wp:columns` + `wp:column {"width":"33.33%"}` | |
| `<button>` / `.btn` | `wp:buttons` + `wp:button` | |
| Grid / card layout | `wp:columns {"className":"equal-cards"}` | Equal-width card columns |
| `<ul>` / `<ol>` | `wp:list` + `wp:list-item` | |
| `<blockquote>` | `wp:quote` | |
| `<video>` | `wp:video` | |
| Full-width section | `wp:group {"align":"full","layout":{"type":"constrained"}}` | Every major design section |
| Unmappable element | `wp:html` (Custom HTML block) | Complex carousel, animation, custom widget |

**Template conventions (apply to all 7 templates):**

- Every template starts with `<!-- wp:template-part {"slug":"header","tagName":"header"} /-->` and ends with `<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->`.
- Every major section is wrapped in `<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->`.
- No raw HTML in templates - everything uses `<!-- wp:* -->` comment syntax.
- No decorative HTML comments - only block comments.
- `wp:navigation` block uses actual nav labels detected from the design (or default: Home, About, Services, Contact).

**templates/front-page.html** - Primary design translation. Claude interprets the full design and generates the complete layout. This is the home page template.

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">

<!-- wp:cover {"align":"full","dimRatio":40} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-background-dim-40 has-background-dim"></span>
<div class="wp-block-cover__inner-container">
<!-- wp:heading {"level":1,"textAlign":"center"} -->
<h1 class="wp-block-heading has-text-align-center">Welcome</h1>
<!-- /wp:heading -->
<!-- wp:paragraph {"align":"center"} -->
<p class="has-text-align-center">Your compelling headline goes here.</p>
<!-- /wp:paragraph -->
<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"}} -->
<div class="wp-block-buttons"><!-- wp:button -->
<div class="wp-block-button"><a class="wp-block-button__link wp-element-button">Learn More</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons -->
</div>
</div>
<!-- /wp:cover -->

</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

Claude replaces this skeleton with the actual design content.

**templates/index.html** - Fallback/archive template. Uses design language (colors, fonts) but shows a post loop.

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">
<!-- wp:query {"queryId":0,"query":{"perPage":10,"pages":0,"offset":0,"postType":"post","order":"desc","orderBy":"date","author":"","search":"","exclude":[],"sticky":"","inherit":true}} -->
<div class="wp-block-query">
<!-- wp:post-template -->
<!-- wp:group {"style":{"spacing":{"padding":{"top":"2rem","bottom":"2rem"}}}} -->
<div class="wp-block-group">
<!-- wp:post-title {"isLink":true} /-->
<!-- wp:post-excerpt /-->
</div>
<!-- /wp:group -->
<!-- /wp:post-template -->
<!-- wp:query-pagination -->
<!-- wp:query-pagination-previous /-->
<!-- wp:query-pagination-numbers /-->
<!-- wp:query-pagination-next /-->
<!-- /wp:query-pagination -->
</div>
<!-- /wp:query -->
</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

**templates/single.html** - Single post template.

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">
<!-- wp:post-title {"level":1} /-->
<!-- wp:post-featured-image {"align":"wide"} /-->
<!-- wp:post-content {"layout":{"type":"constrained"}} /-->
<!-- wp:post-date /-->
<!-- wp:post-terms {"term":"category"} /-->
</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

**templates/page.html** - Page template (same as single but for static pages).

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">
<!-- wp:post-title {"level":1} /-->
<!-- wp:post-featured-image {"align":"wide"} /-->
<!-- wp:post-content {"layout":{"type":"constrained"}} /-->
</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

**templates/archive.html** - Archive template (uses design colors/fonts, consistent with site).

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">
<!-- wp:query-title {"type":"archive"} /-->
<!-- wp:term-description /-->
<!-- wp:query {"queryId":1,"query":{"perPage":10,"pages":0,"offset":0,"postType":"post","order":"desc","orderBy":"date","inherit":true}} -->
<div class="wp-block-query">
<!-- wp:post-template -->
<!-- wp:group {"style":{"spacing":{"padding":{"top":"1.5rem","bottom":"1.5rem"}}}} -->
<div class="wp-block-group">
<!-- wp:post-title {"isLink":true} /-->
<!-- wp:post-excerpt /-->
<!-- wp:post-date /-->
</div>
<!-- /wp:group -->
<!-- /wp:post-template -->
<!-- wp:query-pagination -->
<!-- wp:query-pagination-previous /-->
<!-- wp:query-pagination-numbers /-->
<!-- wp:query-pagination-next /-->
<!-- /wp:query-pagination -->
</div>
<!-- /wp:query -->
</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

**templates/search.html** - Search results template.

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">
<!-- wp:query-title {"type":"search"} /-->
<!-- wp:search {"label":"Search","buttonText":"Search","buttonPosition":"button-outside"} /-->
<!-- wp:query {"queryId":2,"query":{"perPage":10,"pages":0,"offset":0,"postType":"post","order":"desc","orderBy":"relevance","inherit":true}} -->
<div class="wp-block-query">
<!-- wp:post-template -->
<!-- wp:group {"style":{"spacing":{"padding":{"top":"1.5rem","bottom":"1.5rem"}}}} -->
<div class="wp-block-group">
<!-- wp:post-title {"isLink":true} /-->
<!-- wp:post-excerpt /-->
</div>
<!-- /wp:group -->
<!-- /wp:post-template -->
<!-- wp:query-no-results -->
<!-- wp:paragraph -->
<p>No results found. Try a different search term.</p>
<!-- /wp:paragraph -->
<!-- /wp:query-no-results -->
</div>
<!-- /wp:query -->
</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

**templates/404.html** - 404 not found template (uses design colors/typography, friendly message).

```html
<!-- wp:template-part {"slug":"header","tagName":"header"} /-->

<!-- wp:group {"align":"full","style":{"spacing":{"padding":{"top":"6rem","bottom":"6rem"}}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group alignfull">
<!-- wp:heading {"level":1,"textAlign":"center"} -->
<h1 class="wp-block-heading has-text-align-center">Page Not Found</h1>
<!-- /wp:heading -->
<!-- wp:paragraph {"align":"center"} -->
<p class="has-text-align-center">The page you're looking for doesn't exist or has been moved.</p>
<!-- /wp:paragraph -->
<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"}} -->
<div class="wp-block-buttons"><!-- wp:button -->
<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="/">Return Home</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons -->
<!-- wp:search {"label":"Or search","buttonText":"Search","buttonPosition":"button-outside"} /-->
</div>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
```

### 3f: parts/ - Header and Footer Template Parts

Claude interprets the design's header and footer regions (AI judgment on boundaries) and generates `header.html` and `footer.html`. Parts must be in the flat `parts/` directory - no subdirectories.

**parts/header.html** - Claude extracts the site header area from the design. Must include the site logo/title and navigation:

```html
<!-- wp:group {"tagName":"header","style":{"spacing":{"padding":{"top":"1rem","bottom":"1rem"}}},"layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"space-between"}} -->
<header class="wp-block-group">
<!-- wp:site-title /-->
<!-- wp:navigation {"layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"right"}} -->
<!-- wp:navigation-link {"label":"Home","url":"/"} /-->
<!-- wp:navigation-link {"label":"About","url":"/about"} /-->
<!-- wp:navigation-link {"label":"Services","url":"/services"} /-->
<!-- wp:navigation-link {"label":"Contact","url":"/contact"} /-->
<!-- /wp:navigation -->
</header>
<!-- /wp:group -->
```

Claude replaces the navigation labels with the actual labels detected from the design (Section 1c for screenshot, or HTML `<nav>` text for HTML/CSS path).

**parts/footer.html** - Claude extracts the site footer area from the design:

```html
<!-- wp:group {"tagName":"footer","style":{"color":{"background":"var(--wp--preset--color--dark)","text":"var(--wp--preset--color--light)"},"spacing":{"padding":{"top":"3rem","bottom":"3rem"}}},"layout":{"type":"constrained"}} -->
<footer class="wp-block-group has-dark-background-color has-light-color has-background has-text-color">
<!-- wp:columns -->
<div class="wp-block-columns">
<!-- wp:column -->
<div class="wp-block-column">
<!-- wp:site-title /-->
<!-- wp:paragraph -->
<p>Brief description of the site or organisation.</p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:column -->
<!-- wp:column -->
<div class="wp-block-column">
<!-- wp:heading {"level":4} -->
<h4 class="wp-block-heading">Quick Links</h4>
<!-- /wp:heading -->
<!-- wp:navigation {"layout":{"type":"flex","orientation":"vertical"}} -->
<!-- wp:navigation-link {"label":"Home","url":"/"} /-->
<!-- wp:navigation-link {"label":"About","url":"/about"} /-->
<!-- wp:navigation-link {"label":"Contact","url":"/contact"} /-->
<!-- /wp:navigation -->
</div>
<!-- /wp:column -->
</div>
<!-- /wp:columns -->
<!-- wp:paragraph {"align":"center","style":{"spacing":{"marginTop":"2rem"}}} -->
<p class="has-text-align-center">&copy; <?php echo date('Y'); ?> {Site Title}. All rights reserved.</p>
<!-- /wp:paragraph -->
</footer>
<!-- /wp:group -->
```

Claude replaces footer content with the actual design's footer layout.

### 3g: assets/images/ - Design Images or Placeholders

**HTML/CSS path:** Copy staged images from `$IMAGES_STAGE` to `$THEME_DIR/assets/images/`:

```bash
if [ "$VISUAL_MODE" = "html-css" ] && [ -n "$IMAGES_STAGE" ] && [ -d "$IMAGES_STAGE" ]; then
  cp "$IMAGES_STAGE/"* "$THEME_DIR/assets/images/" 2>/dev/null
  IMG_COUNT=$(ls "$THEME_DIR/assets/images/" 2>/dev/null | wc -l | tr -d ' ')
  echo "[Build] Copied $IMG_COUNT design images to assets/images/"
  rm -rf "$IMAGES_STAGE"
fi
```

**Screenshot path:** Generate placeholder images using the Python image generator. Claude detects image areas and aspect ratios from the multimodal vision analysis in Section 1c.

```python
#!/usr/bin/env python3
"""
Generate placeholder images for screenshot-path visual builds.
Reuses the build-content Pillow/stdlib pattern.
"""
import os, struct, zlib

theme_dir = os.environ.get('THEME_DIR', '')
primary_color = os.environ.get('PRIMARY_COLOR', '#4A5568')  # from EXTRACTED_COLORS
images_dir = os.path.join(theme_dir, 'assets', 'images')
os.makedirs(images_dir, exist_ok=True)

# Parse hex color → RGB
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# Claude sets IMAGES based on detected image areas from Section 1c vision analysis
# Default set (overridden by actual detection):
IMAGES = [
    ('hero',    1200, 630),   # Default 16:9 hero (or detected ratio)
    ('about',   800,  600),   # Default 4:3 about section
    ('profile', 400,  400),   # Square portrait
    ('feature', 600,  400),   # Feature image 3:2
]

r, g, b = hex_to_rgb(primary_color)

def write_png(path, width, height, color_rgb):
    """Write a solid-color PNG using Python stdlib only (no Pillow needed)."""
    r, g, b = color_rgb
    raw_data = b''
    for _ in range(height):
        row = bytes([0]) + bytes([r, g, b] * width)
        raw_data += row
    compressed = zlib.compress(raw_data, 9)

    def chunk(tag, data):
        length = struct.pack('>I', len(data))
        crc = struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
        return length + tag + data + crc

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', ihdr)
    png += chunk(b'IDAT', compressed)
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)

for name, w, h in IMAGES:
    out_path = os.path.join(images_dir, f'{name}.png')
    write_png(out_path, w, h, (r, g, b))
    print(f'[Build] Generated placeholder: {name}.png ({w}x{h})')
```

---

## Section 4: Font Downloading

Download identified Google Fonts using the gwfh API and bundle them in `assets/fonts/`. After downloading, scan the directory and update `theme.json fontFace src` entries to match exact downloaded filenames.

### 4a: Font Download Function

```bash
# Download a Google Font to assets/fonts/ using gwfh (google-webfonts-helper) API
# THEME_DIR must be set. Returns 0 on success, 1 on failure.
download_google_font() {
  local font_slug="$1"
  local subsets="${2:-latin}"
  local variants="${3:-regular,700}"

  mkdir -p "$THEME_DIR/assets/fonts"

  local zip_file="/tmp/font_${font_slug}_$$.zip"
  local api_url="https://gwfh.mranftl.com/api/fonts/${font_slug}?download=zip&subsets=${subsets}&variants=${variants}&formats=woff2"

  echo "[Build] Downloading font: $font_slug (subsets=$subsets, variants=$variants)..."

  if curl -s --max-time 30 -L -o "$zip_file" "$api_url" && [ -s "$zip_file" ]; then
    # Extract woff2 files directly into assets/fonts/
    unzip -j -o "$zip_file" "*.woff2" -d "$THEME_DIR/assets/fonts" 2>/dev/null
    local exit_code=$?
    rm -f "$zip_file"
    if [ $exit_code -eq 0 ]; then
      echo "[Build] Font downloaded: $font_slug -> assets/fonts/"
      return 0
    else
      echo "[Build] WARNING: Could not extract woff2 files from $font_slug zip."
      rm -f "$zip_file"
      return 1
    fi
  else
    echo "[Build] WARNING: Font download failed for $font_slug (gwfh unavailable or font not found)."
    rm -f "$zip_file"
    return 1
  fi
}
```

### 4b: Download Each Font from FONT_MAP

For each font in `FONT_MAP`:

1. Convert font name to gwfh slug: lowercase, spaces → hyphens (e.g. `"Playfair Display"` → `"playfair-display"`)
2. Download with `download_google_font "$gwfh_slug" "latin" "regular,700"`
3. If italic was detected in the design, add `"italic"` to variants: `"regular,italic,700,700italic"`

```bash
# Claude iterates over each entry in FONT_MAP and calls download_google_font
# Example for two fonts:

FONT_DOWNLOAD_FAILED=()

download_google_font "playfair-display" "latin" "regular,700" \
  || FONT_DOWNLOAD_FAILED+=("Playfair Display")

download_google_font "dm-sans" "latin" "regular,700" \
  || FONT_DOWNLOAD_FAILED+=("DM Sans")

echo "[Build] Font downloads complete. Failed: ${#FONT_DOWNLOAD_FAILED[@]}"
```

### 4c: Scan Downloaded Files and Update theme.json

After all downloads, scan `assets/fonts/` and auto-generate the `fontFace.src` entries from actual filenames (gwfh encodes version numbers in filenames - e.g. `playfair-display-v36-latin-regular.woff2`):

```python
#!/usr/bin/env python3
"""
Scan assets/fonts/ and update theme.json fontFace src entries to match
actual downloaded filenames. This resolves the gwfh version-in-filename issue.
"""
import json, os, re, glob

theme_dir = os.environ.get('THEME_DIR', '')
fonts_dir = os.path.join(theme_dir, 'assets', 'fonts')
theme_json_path = os.path.join(theme_dir, 'theme.json')

# List all woff2 files
woff2_files = [os.path.basename(f) for f in glob.glob(os.path.join(fonts_dir, '*.woff2'))]
print(f'[Build] Found {len(woff2_files)} woff2 files in assets/fonts/')
for f in woff2_files:
    print(f'[Build]   {f}')

# Load theme.json
with open(theme_json_path, 'r') as f:
    theme = json.load(f)

# For each fontFamily entry, find matching woff2 files by slug
font_families = theme.get('settings', {}).get('typography', {}).get('fontFamilies', [])
for family in font_families:
    slug = family.get('slug', '')
    font_faces = family.get('fontFace', [])
    for face in font_faces:
        weight = face.get('fontWeight', '400')
        style  = face.get('fontStyle', 'normal')
        # Build search pattern: slug-v*-latin-{variant}.woff2
        variant = weight if style == 'normal' else f'{weight}italic'
        if weight == '400' and style == 'normal':
            variant = 'regular'
        # Convert slug (font-family slug) to gwfh filename prefix
        # e.g. slug "heading" → look at family["fontFamily"] for the actual name
        family_name = family.get('fontFamily', '').split(',')[0].strip().lower().replace(' ', '-')
        pattern = f'{family_name}-v*-latin-{variant}.woff2'
        matches = [f for f in woff2_files if re.match(pattern.replace('*', '\\d+'), f)]
        if matches:
            face['src'] = [f'file:./assets/fonts/{matches[0]}']
            print(f'[Build] Updated fontFace src: {family_name} {weight} {style} -> {matches[0]}')
        else:
            print(f'[Build] WARNING: No woff2 match for {family_name} {weight} {style} (pattern: {pattern})')

# Write updated theme.json
with open(theme_json_path, 'w') as f:
    json.dump(theme, f, indent=2)
print('[Build] theme.json fontFace src entries updated.')
```

### 4d: Failed Font Fallback (No CDN - System Font Stack)

**CRITICAL:** If `download_google_font` fails for a font, do NOT fall back to a CDN URL. Per locked decision: no external CDN requests, GDPR-friendly builds only.

For each failed font in `FONT_DOWNLOAD_FAILED`:

1. Replace the failed font's `fontFace` entry in `theme.json` with a system font stack appropriate for the font's classification:
   - Sans-serif: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif`
   - Serif: `Georgia, "Times New Roman", Times, serif`
   - Monospace: `"Courier New", Courier, monospace`
2. Remove the `fontFace` array from that fontFamily entry in `theme.json`.
3. Add a Critical warning to `SETUP.md` (Section 6) with:
   - Font name that failed
   - Manual download URL: `https://gwfh.mranftl.com/api/fonts/{font-slug}`
   - Expected filenames based on the gwfh pattern
   - Target directory: `wp-content/themes/custom-{slug}/assets/fonts/`

### 4e: Final theme.json Validation

Re-validate theme.json after font src updates:

```bash
python3 -c "import json; json.load(open('$THEME_DIR/theme.json'))" \
  && echo "[Build] theme.json post-font-update validation: OK" \
  || echo "[Build] WARNING: theme.json validation failed after font src update"
```

---

## Section 5: WP-CLI Theme Activation and Database Export

Activate the custom theme and re-export the database. Same pattern as `build-theme` Section 3 but for the locally generated custom theme.

### 5a: Theme Activation

```bash
echo "[Build] Activating custom theme: $THEME_SLUG"

$WP theme activate "$THEME_SLUG" 2>&1
ACTIVATE_EXIT=$?

if [ $ACTIVATE_EXIT -eq 0 ]; then
  THEME_INSTALLED=true
  echo "[Build] Theme activated: $THEME_SLUG"
else
  THEME_INSTALLED=false
  echo "[Build] WARNING: Theme activation failed for $THEME_SLUG"
  echo "[Build] WARNING: Build continues - check theme files for errors"
fi
```

### 5b: Site Configuration

Set static front page and update site metadata:

```bash
# Set static front page (prevents WordPress blog index from replacing the design's home page)
HOME_PAGE_ID=$($WP post create \
  --post_type=page \
  --post_title="Home" \
  --post_status=publish \
  --porcelain 2>/dev/null || echo "")

if [ -n "$HOME_PAGE_ID" ]; then
  $WP option update show_on_front "page" 2>&1
  $WP option update page_on_front "$HOME_PAGE_ID" 2>&1
  echo "[Build] Static front page set (page ID: $HOME_PAGE_ID)"
fi

# Update site title
$WP option update blogname "$SITE_TITLE" 2>&1

# Claude generates a brief tagline from the design context (one line, no quotes)
# Based on the detected design personality, color palette, and content areas
SITE_TAGLINE="<Claude-generated tagline based on design context>"
$WP option update blogdescription "$SITE_TAGLINE" 2>&1

echo "[Build] Site title: $SITE_TITLE"
echo "[Build] Site tagline: $SITE_TAGLINE"
```

### 5c: Database Re-Export

```bash
echo "[Build] Exporting database..."
$WP db export "$BUILD_DIR/database.sql" --add-drop-table 2>&1
DB_EXPORT_EXIT=$?

if [ $DB_EXPORT_EXIT -eq 0 ]; then
  echo "[Build] Database exported: $BUILD_DIR/database.sql"
else
  echo "[Build] WARNING: Database export failed (exit code: $DB_EXPORT_EXIT)"
fi
```

Set output variables:
- `THEME_SLUG` - `"custom-${SLUG}"` (e.g. `custom-figma-portfolio`)
- `THEME_NAME` - `"Custom ${SITE_TITLE}"` (e.g. `Custom Figma Portfolio`)
- `THEME_VERSION` - `"1.0.0"`
- `THEME_INSTALLED` - `true` or `false` based on activation result

---

## Section 6: SETUP.md for Visual Builds

Generate `$BUILD_DIR/SETUP.md` following the 3-tier priority structure (Critical / Important / Optional). This is the visual-mode equivalent of the NL build SETUP.md.

```markdown
# Setup Guide - {Site Title}

**Build mode:** Visual (from {html-css export | screenshot image})
**Theme:** custom-{slug} (FSE block theme)
**Generated:** {timestamp}

---

## What's Installed

| Item | Value |
|------|-------|
| Theme | Custom {Slug} (custom-{slug}) |
| Theme version | 1.0.0 |
| Fonts bundled | {Yes - {font names} | No - system font stack fallback} |
| Image source | {Exported from design | AI-generated placeholders} |
| WordPress version | {wp_version} |

---

## Critical (Do First)

### 1. Replace placeholder images
{Include ONLY for screenshot path builds}
Placeholder images were generated for these areas detected in your design:
- `hero.png` (1200×630) - hero/banner area
- `about.png` (800×600) - about section
Add your actual images to: `wp-content/themes/custom-{slug}/assets/images/`
Then update the image blocks in Appearance > Editor to point to your files.

### 2. Review font substitutions
{Include ONLY if FONT_SUBSTITUTIONS is non-empty}
The following fonts from your design were substituted with Google Fonts equivalents:
{List each entry from FONT_SUBSTITUTIONS:}
- Original: Aktiv Grotesk → Bundled: Inter
Review the typography in Appearance > Editor > Styles > Typography.

### 3. Manual font bundling required
{Include ONLY if any fonts in FONT_DOWNLOAD_FAILED}
The following fonts could not be downloaded automatically and are using system font fallbacks:
**{Font Name}**
- Download: https://gwfh.mranftl.com/api/fonts/{font-slug}
- Expected files: `{font-slug}-v{N}-latin-regular.woff2`, `{font-slug}-v{N}-latin-700.woff2`
- Place in: `wp-content/themes/custom-{slug}/assets/fonts/`
- Update `theme.json` fontFace src entries to match the exact filenames.

---

## Important (Do Soon)

### 4. Review page content
All text content is placeholder. Update headings, paragraphs, and calls to action in
Appearance > Editor > Templates > Front Page.

### 5. Update navigation menu labels and links
Open Appearance > Editor > Patterns > Header to customise the navigation links.
Current placeholder labels: Home, About, Services, Contact
Update to match your actual site structure.

### 6. Add your logo
Go to Appearance > Editor > Patterns > Header and replace the site title with your logo image.

---

## Optional (When Ready)

### 7. Fine-tune colors and typography
Appearance > Editor > Styles gives you a visual interface to adjust the design tokens
extracted from your design. Current palette: {list color names and hex values}.

### 8. Add additional pages and templates
Create new pages in Pages > Add New and customise their layout in the Site Editor.
New templates can be added at Appearance > Editor > Templates.

### 9. Add block patterns
Reusable sections are available at Appearance > Editor > Patterns > custom-{slug}.
The front-page pattern can be duplicated and adapted for other pages.

---

*Generated by WP CoWork Plugin - Visual Build*
*Reference: skills/build-visual/SKILL.md*
```

Claude populates all `{...}` placeholders with actual values from the build:
- `{Site Title}` → `$SITE_TITLE`
- `{slug}` → `$SLUG`
- `{Slug}` → title-cased slug
- Font substitutions from `$FONT_SUBSTITUTIONS` array
- Failed fonts from `$FONT_DOWNLOAD_FAILED` array
- Color palette from `$EXTRACTED_COLORS`
- Timestamp from `date -u +"%Y-%m-%d %H:%M UTC"`

**Conditional sections:**
- "Replace placeholder images" - screenshot path builds only
- "Review font substitutions" - only if `FONT_SUBSTITUTIONS` is non-empty
- "Manual font bundling required" - only if `FONT_DOWNLOAD_FAILED` is non-empty

---

## Implementation Notes

**Pipeline position:** This skill runs in the visual build pipeline after `build-mcp` Section 2 (MCP adapter activated, database re-exported) and before `build-git` Section 3 (dynamic .gitignore update - `custom-{slug}` must NOT be excluded from git tracking). Full pipeline:

```
build-scaffold Sections 2-4 → build-git Sections 1-2-4 → build-mcp Sections 1-3
→ build-visual Sections 1-6 → build-git Section 3 → git commit → SETUP.md → zip
```

**Docker MySQL container lifetime:** The ephemeral Docker MySQL container from `build-scaffold` Section 3 must still be running for Section 5 (WP-CLI database export). The EXIT trap from `build-scaffold` remains active for the entire build session.

**Output variables consumed by downstream skills:**
- `THEME_SLUG` - consumed by `build-git` Section 3 for `.gitignore` Phase 2 dynamic update
- `THEME_NAME`, `THEME_VERSION`, `THEME_INSTALLED` - consumed by `commands/build/COMMAND.md` for `build.json` manifest
- `FONT_SUBSTITUTIONS` - consumed by Section 6 SETUP.md generation (same skill)
- `FONT_DOWNLOAD_FAILED` - consumed by Section 6 SETUP.md generation (same skill)

**The `custom-` prefix is critical:** All generated themes use `custom-{slug}` naming. The `custom-` prefix is the signal used by `build-git` Phase 2 dynamic `.gitignore` logic to include the generated theme in git tracking. Without this prefix, the theme directory would be excluded from the build's git history.

**No external CDN requests in generated themes:** The generated theme must never make external CDN requests for fonts or assets. All fonts are bundled via `file:./assets/fonts/` paths in `theme.json fontFace`. If `download_google_font` fails, fall back to system font stacks - never to `fonts.googleapis.com` or any remote URL in theme.json `src`.

**Custom HTML block best practices:** When using `<!-- wp:html -->` as a fallback for unmappable elements, ensure all HTML inside is well-formed: close all tags, use valid nesting, avoid deprecated attributes. Malformed HTML inside wp:html blocks causes "Block has been modified externally" errors in the editor.

**Spacing units:** Never use absolute pixel values from design export CSS directly in `theme.json` spacing. Convert px to rem by dividing by 16 (e.g. 48px → 3rem, 16px → 1rem). Use `clamp()` for heading font sizes to ensure responsive scaling.

**Font filename matching:** gwfh encodes version numbers in filenames (e.g. `playfair-display-v36-latin-regular.woff2`). The version number changes over time. Always scan `assets/fonts/` after download and auto-generate `fontFace.src` entries from actual filenames (Section 4c). Never hard-code assumed version numbers.

**Anti-patterns (never do):**
- No raw HTML in templates - only `<!-- wp:* -->` comment syntax; unmappable elements use `<!-- wp:html -->`
- No `position: absolute` from design export CSS directly in templates - interpret design intent and use block layout equivalents
- No absolute pixel values in theme.json spacing - convert to rem
- No font CDN URLs in theme.json `src` - use `file:./assets/fonts/` only
- No template parts in subdirectories - `parts/header.html` only, never `parts/layout/header.html`
- No decorative HTML comments in templates - only WordPress block comments
- No external image URLs - only images from design export or Python-generated placeholders

**References:**
- `@references/wordpress-block-theming/SKILL.md` - FSE theme structure, theme.json v3 schema, block template markup, font handling, animation patterns, card layouts
- `@references/wp-block-themes/SKILL.md` - Block theme workflow, template/parts folder rules, debugging patterns
- `@skills/build-content/SKILL.md` - Placeholder image generation Python pattern (Pillow + stdlib fallback)
- `@skills/build-git/SKILL.md` - `custom-*` prefix logic for git tracking
- `@commands/build/COMMAND.md` - Visual pipeline structure (Section 3b)
