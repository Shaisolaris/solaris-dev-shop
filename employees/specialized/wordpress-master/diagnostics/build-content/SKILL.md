---
name: build-content
description: Install relevant WP.org plugins, generate AI placeholder content (pages, posts, menus), create placeholder images, and re-export the database for NL builds
requires: [wp-cli, docker-mysql-running, python3]
runs-after: [build-theme]
runs-before: [build-setup]
---

# Build Content Skill

Seeds a WordPress installation (with FSE theme already active from build-theme) with relevant plugins, realistic placeholder content, navigation menus, and placeholder images - then re-exports the database to capture all changes in the SQL dump.

**Critical sequencing:** This skill runs AFTER `build-theme` (theme must be active for menu location discovery) and BEFORE `build-setup` (which finalises the zip). The Docker MySQL container from `build-scaffold` must still be running for the duration of this skill.

This skill expects the following variables to already be set by the calling command:

- `BUILD_DIR` - absolute path to the build directory (set by build-scaffold Section 2)
- `WP` - the WP-CLI command prefix (e.g. `wp --path=$BUILD_DIR` or the Docker equivalent, set by build-scaffold Section 4)
- `NL_PROMPT` - the user's natural language site description string
- `SITE_TITLE` - site title derived from the NL prompt (set by the calling command)
- `THEME_SLUG` - installed theme slug (set by build-theme)
- `THEME_NAME` - theme display name (set by build-theme)
- `THEME_VERSION` - theme version string (set by build-theme)
- `THEME_INSTALLED` - true/false (set by build-theme)
- `PLUGIN_DIR` - absolute path to the CoWork plugin directory (set by the calling command)

## Section 1: Plugin Selection and Installation

the coding agent analyses `NL_PROMPT` to determine which free WP.org plugins are relevant for the site type. A curated category baseline provides starting candidates; the coding agent adds or removes entries based on the specific NL description. Up to 10 plugins maximum - if more are selected, trim to the highest-relevance set before installing.

**Curated category baseline (starting candidates by site type):**

```
photography / portfolio / creative → wpforms-lite (contact form)
restaurant / food / cafe           → wpforms-lite (reservations/contact)
business / corporate / agency      → wpforms-lite (contact form)
blog / magazine / news             → wpforms-lite (contact form)
ecommerce / shop / store           → woocommerce, wpforms-lite
events / booking                   → wpforms-lite, the-events-calendar
membership / community             → wpforms-lite
```

the coding agent evaluates the `NL_PROMPT` and may add, remove, or substitute slugs from this list based on the specific site requirements. `wpforms-lite` is near-universal - add it unless the site explicitly has no contact page.

**Plugin verification via WP.org API:**

For each plugin candidate, query the WP.org Plugins API v1.2 to confirm the slug exists and meets quality thresholds before installing:

```bash
# Query WP.org Plugins API for a specific slug
check_plugin_viable() {
  local slug="$1"
  local result
  result=$(curl -s --max-time 10 \
    "https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request[slug]=${slug}&request[fields][active_installs]=true&request[fields][tested]=true&request[fields][requires]=true&request[fields][rating]=true" \
    2>/dev/null)

  if [ -z "$result" ] || echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('slug') else 1)" 2>/dev/null; then
    # API unavailable or plugin not found - proceed with install attempt anyway
    return 0
  fi

  # the coding agent evaluates these fields from the API response:
  # - tested: must be >= current WP version
  # - requires: must be <= current WP version
  # - active_installs: prefer >= 1000 (established plugin)
  # - rating: prefer >= 60 (out of 100)
  # the coding agent sets PLUGIN_VIABLE=true or PLUGIN_VIABLE=false after evaluation
  return 0
}
```

For broader plugin discovery (when the coding agent wants to find alternatives for a category), use the search API:

```bash
# Search WP.org Plugins API for a category keyword
curl -s --max-time 10 \
  "https://api.wordpress.org/plugins/info/1.2/?action=query_plugins&request[search]={keyword}&request[per_page]=10&request[fields][active_installs]=true&request[fields][tested]=true&request[fields][requires]=true&request[fields][rating]=true"
```

**10-plugin maximum enforcement:** Count the selected slugs. If more than 10, remove the lowest-relevance entries before proceeding to installation. Log the trimmed list with a `[Build]` note.

**Installation with warn-and-continue:**

```bash
# Track installation outcomes
INSTALLED_PLUGINS=()
FAILED_PLUGINS=()

install_plugin() {
  local slug="$1"

  if $WP plugin install "$slug" --activate 2>&1; then
    # Secondary check: verify no PHP fatal triggered by activation
    if grep -q "PHP Fatal error" "$BUILD_DIR/wp-content/debug.log" 2>/dev/null; then
      echo "[Build] WARNING: Plugin $slug triggered PHP fatal after activation. Deactivating."
      $WP plugin deactivate "$slug" 2>/dev/null || true
      FAILED_PLUGINS+=("$slug")
      return 1
    fi
    echo "[Build] Plugin active: $slug"
    PLUGIN_NAME=$($WP plugin get "$slug" --field=name 2>/dev/null || echo "$slug")
    PLUGIN_VER=$($WP plugin get "$slug" --field=version 2>/dev/null || echo "unknown")
    INSTALLED_PLUGINS+=("${slug}:${PLUGIN_NAME}:${PLUGIN_VER}")
    return 0
  else
    echo "[Build] Plugin skipped: $slug (install/activate failed)"
    FAILED_PLUGINS+=("$slug")
    return 1
  fi
}

# Install each selected plugin (max 10)
for PLUGIN_SLUG in "${SELECTED_PLUGINS[@]}"; do
  install_plugin "$PLUGIN_SLUG"
done

echo "[Build] Plugins installed: ${#INSTALLED_PLUGINS[@]} active, ${#FAILED_PLUGINS[@]} skipped"
```

Never use `exit 1` for plugin failures. Build completion is more important than any individual plugin. Failed plugins are noted and passed to `build-setup` output variables.

## Section 2: Placeholder Image Generation

**CRITICAL: Run image generation BEFORE page/post content creation.** Content references image URLs - those URLs must exist before content is written.

Check for Python Pillow availability. Use Pillow if available; fall back to a pure Python stdlib PNG writer (struct + zlib) if not.

**Image sizes to generate:**

| Name               | Dimensions | Typical use                      |
|--------------------|------------|----------------------------------|
| hero               | 1200 × 630 | Featured/hero images             |
| profile            | 400 × 400  | Team headshots, author photos    |
| gallery-landscape  | 800 × 600  | Gallery items                    |
| thumbnail-square   | 300 × 300  | Post thumbnails                  |
| banner             | 1600 × 400 | Page banners                     |

**Color selection:** Default neutral gray `(156, 163, 175)`. If `theme.json` is present in the active theme directory, extract the primary palette color and use it instead:

```bash
THEME_JSON="$BUILD_DIR/wp-content/themes/$THEME_SLUG/theme.json"
THEME_PRIMARY_COLOR="9CA3AF"  # Default neutral gray (156, 163, 175)

if [ -f "$THEME_JSON" ]; then
  # Attempt to extract first color from theme.json palette
  EXTRACTED=$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    palette = data.get('settings', {}).get('color', {}).get('palette', [])
    if palette:
        color = palette[0].get('color', '#9CA3AF').lstrip('#')
        print(color)
    else:
        print('9CA3AF')
except Exception:
    print('9CA3AF')
" "$THEME_JSON" 2>/dev/null)
  if [ -n "$EXTRACTED" ]; then
    THEME_PRIMARY_COLOR="$EXTRACTED"
  fi
fi
```

**Image generation script:** Write to a temp file and execute to avoid shell argument length limits.

```bash
mkdir -p "$BUILD_DIR/wp-content/uploads/placeholders"

python3 /tmp/gen_images_$$.py "$BUILD_DIR" "$THEME_PRIMARY_COLOR" << 'PYEOF'
# Script is written to /tmp/gen_images_$$.py before this line runs.
# See the Python script block below.
PYEOF
```

Write the Python image generation script to `/tmp/gen_images_$$.py`:

```python
#!/usr/bin/env python3
"""
Placeholder image generator for NL WordPress builds.
Supports Pillow (preferred) and pure stdlib fallback.
Usage: python3 gen_images_$$.py <build_dir> <hex_color>
"""
import sys
import os
import struct
import zlib

build_dir = sys.argv[1]
hex_color = sys.argv[2].lstrip('#') if len(sys.argv) > 2 else '9CA3AF'

# Parse hex color to RGB
r = int(hex_color[0:2], 16)
g = int(hex_color[2:4], 16)
b = int(hex_color[4:6], 16)

output_dir = os.path.join(build_dir, 'wp-content', 'uploads', 'placeholders')
os.makedirs(output_dir, exist_ok=True)

IMAGES = [
    ('hero',              1200, 630),
    ('profile',           400,  400),
    ('gallery-landscape', 800,  600),
    ('thumbnail-square',  300,  300),
    ('banner',            1600, 400),
]

def write_png_stdlib(path, width, height, r, g, b):
    """Write a solid-color PNG using only Python stdlib (struct + zlib)."""
    def chunk(name, data):
        c = struct.pack('>I', len(data)) + name + data
        crc = zlib.crc32(name + data) & 0xFFFFFFFF
        return c + struct.pack('>I', crc)

    png_sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)

    # Build raw image data: filter byte (0) + RGB pixels per row
    raw_row = bytes([0]) + bytes([r, g, b] * width)
    raw = raw_row * height
    idat = chunk(b'IDAT', zlib.compress(raw, 9))
    iend = chunk(b'IEND', b'')

    with open(path, 'wb') as f:
        f.write(png_sig + ihdr + idat + iend)

try:
    from PIL import Image
    USE_PILLOW = True
except ImportError:
    USE_PILLOW = False

count = 0
for name, width, height in IMAGES:
    path = os.path.join(output_dir, f'placeholder-{name}.png')
    if USE_PILLOW:
        img = Image.new('RGB', (width, height), (r, g, b))
        img.save(path, 'PNG')
    else:
        write_png_stdlib(path, width, height, r, g, b)
    count += 1

print(f'[Build] Generated {count} placeholder images (Pillow: {USE_PILLOW})')
```

Execute the script:

```bash
python3 /tmp/gen_images_$$.py "$BUILD_DIR" "$THEME_PRIMARY_COLOR"
IMAGE_EXIT=$?
rm -f /tmp/gen_images_$$.py

if [ $IMAGE_EXIT -ne 0 ]; then
  echo "[Build] WARNING: Placeholder image generation failed. Content will reference missing image URLs."
else
  echo "[Build] Placeholder images written to $BUILD_DIR/wp-content/uploads/placeholders/"
fi

# Base URL for referencing images in page/post content
IMAGE_BASE_URL="http://localhost/wp-content/uploads/placeholders"
```

## Section 3: Page and Post Creation

**IMPORTANT: Images must be generated in Section 2 before this section runs.** Page and post content references `$IMAGE_BASE_URL` URLs from the placeholder directory.

**Always write page/post content to a temp file** before passing to WP-CLI. This avoids shell argument length limits and heredoc quoting issues.

### Pages (3-5 pages)

Always create: Home, About, Contact. Add 1-2 site-specific pages based on `NL_PROMPT`:

- Photography / portfolio → add "Portfolio" page
- Restaurant / cafe → add "Menu" page
- Agency / services → add "Services" page
- Art / gallery → add "Gallery" page
- Any site with a team → add "Team" page

**Content quality rules:**
- Contextual English prose written by the coding agent - realistic, fictional, specific
- Made-up business names, addresses, phone numbers, team member names
- No Lorem Ipsum - ever
- No `[REPLACE THIS]` markers - ever
- No verbatim real-world content (e.g. no copying real business names/addresses)
- Gutenberg block markup (`<!-- wp:paragraph -->`, `<!-- wp:heading -->`, `<!-- wp:image -->`) so content renders properly in the block editor

**Home page example pattern:**

```bash
cat > /tmp/wp-page-home-$$ << 'CONTENT_EOF'
<!-- wp:cover {"url":"http://localhost/wp-content/uploads/placeholders/placeholder-hero.png","dimRatio":40} -->
<div class="wp-block-cover">
  <img class="wp-block-cover__image-background" src="http://localhost/wp-content/uploads/placeholders/placeholder-hero.png" alt="Hero image" />
  <div class="wp-block-cover__inner-container">
    <!-- wp:heading {"textAlign":"center","level":1} -->
    <h1 class="wp-block-heading has-text-align-center">Welcome to Harlow &amp; Co.</h1>
    <!-- /wp:heading -->
    <!-- wp:paragraph {"align":"center"} -->
    <p class="has-text-align-center">Bespoke interior design for homes that feel like you.</p>
    <!-- /wp:paragraph -->
  </div>
</div>
<!-- /wp:cover -->

<!-- wp:paragraph -->
<p>At Harlow &amp; Co. we believe your home should tell your story. Founded in 2019 by designer Mia Harlow, our studio pairs timeless materials with contemporary sensibility to create spaces that are lived in - and loved.</p>
<!-- /wp:paragraph -->
CONTENT_EOF

HOME_ID=$($WP post create \
  --post_type=page \
  --post_status=publish \
  --post_title="Home" \
  --post_content="$(cat /tmp/wp-page-home-$$)" \
  --porcelain)
rm -f /tmp/wp-page-home-$$
echo "[Build] Created page: Home (ID: $HOME_ID)"
```

**About page example pattern:**

```bash
cat > /tmp/wp-page-about-$$ << 'CONTENT_EOF'
<!-- wp:heading -->
<h2 class="wp-block-heading">Our Story</h2>
<!-- /wp:heading -->

<!-- wp:columns -->
<div class="wp-block-columns">
  <!-- wp:column -->
  <div class="wp-block-column">
    <!-- wp:image -->
    <figure class="wp-block-image">
      <img src="http://localhost/wp-content/uploads/placeholders/placeholder-profile.png" alt="Founder portrait" />
    </figure>
    <!-- /wp:image -->
  </div>
  <!-- /wp:column -->
  <!-- wp:column -->
  <div class="wp-block-column">
    <!-- wp:paragraph -->
    <p>Mia Harlow grew up surrounded by her grandmother's antiques and her father's architectural drawings. That collision of old and new shaped her design philosophy: every space deserves objects with a history and a future.</p>
    <!-- /wp:paragraph -->
    <!-- wp:paragraph -->
    <p>After graduating from the Sydney College of the Arts in 2014, Mia spent five years at Anderson &amp; Webb before launching Harlow &amp; Co. from a converted warehouse in Newtown.</p>
    <!-- /wp:paragraph -->
  </div>
  <!-- /wp:column -->
</div>
<!-- /wp:columns -->
CONTENT_EOF

ABOUT_ID=$($WP post create \
  --post_type=page \
  --post_status=publish \
  --post_title="About" \
  --post_content="$(cat /tmp/wp-page-about-$$)" \
  --porcelain)
rm -f /tmp/wp-page-about-$$
echo "[Build] Created page: About (ID: $ABOUT_ID)"
```

**Contact page example pattern:**

```bash
cat > /tmp/wp-page-contact-$$ << 'CONTENT_EOF'
<!-- wp:heading -->
<h2 class="wp-block-heading">Get in Touch</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>We'd love to hear about your project. Reach out to start a conversation about transforming your space.</p>
<!-- /wp:paragraph -->

<!-- wp:group -->
<div class="wp-block-group">
  <!-- wp:paragraph -->
  <p><strong>Studio address:</strong> 14 Elara Lane, Newtown NSW 2042</p>
  <!-- /wp:paragraph -->
  <!-- wp:paragraph -->
  <p><strong>Phone:</strong> (02) 9123 4567</p>
  <!-- /wp:paragraph -->
  <!-- wp:paragraph -->
  <p><strong>Email:</strong> hello@harlowco.example</p>
  <!-- /wp:paragraph -->
  <!-- wp:paragraph -->
  <p><strong>Studio hours:</strong> Monday, Friday, 9am, 5pm</p>
  <!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
CONTENT_EOF

CONTACT_ID=$($WP post create \
  --post_type=page \
  --post_status=publish \
  --post_title="Contact" \
  --post_content="$(cat /tmp/wp-page-contact-$$)" \
  --porcelain)
rm -f /tmp/wp-page-contact-$$
echo "[Build] Created page: Contact (ID: $CONTACT_ID)"
```

the coding agent generates the actual content for all pages based on `NL_PROMPT`. The example patterns above show structure - replace "Harlow & Co." and all specific details with content appropriate for the NL_PROMPT site type. Use `$IMAGE_BASE_URL/placeholder-{name}.png` for all image references.

Track all page IDs in an array for menu creation:

```bash
PAGE_IDS=("$HOME_ID" "$ABOUT_ID" "$CONTACT_ID")
PAGE_TITLES=("Home" "About" "Contact")
# Add site-specific pages as determined by the coding agent from NL_PROMPT
# e.g. PAGE_IDS+=("$PORTFOLIO_ID"); PAGE_TITLES+=("Portfolio")
PAGES_CREATED=${#PAGE_IDS[@]}
```

**Set static front page:**

```bash
$WP option update show_on_front page
$WP option update page_on_front "$HOME_ID"
echo "[Build] Static front page set to: Home (ID: $HOME_ID)"
```

### Blog Posts (3-5 posts)

Create 3-5 blog posts with topics relevant to the site's industry or niche. Same content quality rules apply as for pages. Use `--post_type=post`.

**Blog post example pattern:**

```bash
cat > /tmp/wp-post-1-$$ << 'CONTENT_EOF'
<!-- wp:image -->
<figure class="wp-block-image">
  <img src="http://localhost/wp-content/uploads/placeholders/placeholder-hero.png" alt="Featured image" />
</figure>
<!-- /wp:image -->

<!-- wp:paragraph -->
<p>Choosing a colour palette for a living room is one of the most personal decisions in interior design. The room where you unwind, entertain, and start your mornings deserves colours that respond to your mood rather than fight it.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">Start with one anchor piece</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Whether it's a vintage rug, a piece of art, or a sofa you've had for years, build your palette outward from an object you already love. Pull two or three colours from it, then add one unexpected accent - something slightly outside what you first see - to keep the room from feeling predictable.</p>
<!-- /wp:paragraph -->
CONTENT_EOF

POST_1_ID=$($WP post create \
  --post_type=post \
  --post_status=publish \
  --post_title="How to Choose a Colour Palette for Your Living Room" \
  --post_content="$(cat /tmp/wp-post-1-$$)" \
  --porcelain)
rm -f /tmp/wp-post-1-$$
echo "[Build] Created post: (ID: $POST_1_ID)"
```

the coding agent generates 3-5 blog post titles and content specific to the `NL_PROMPT` site type. Each post should feel like real published content for that site's niche - not generic filler.

```bash
POSTS_CREATED=<count of posts actually created>
```

Log final count: `[Build] Created $PAGES_CREATED pages and $POSTS_CREATED posts`

## Section 4: Navigation Menu Creation

**IMPORTANT: Must run AFTER all pages are created** (Section 3) so page IDs are available for menu items.

**Create the menu:**

```bash
MENU_ID=$($WP menu create "Primary Menu" --porcelain)
echo "[Build] Menu created (ID: $MENU_ID)"
```

**Add each page as a menu item:**

```bash
for i in "${!PAGE_IDS[@]}"; do
  $WP menu item add-post "$MENU_ID" "${PAGE_IDS[$i]}" --title="${PAGE_TITLES[$i]}" 2>&1
done
echo "[Build] Added ${#PAGE_IDS[@]} items to menu"
```

**Discover theme menu locations dynamically - never hardcode "primary":**

```bash
THEME_LOCATIONS=$($WP menu location list --format=csv 2>/dev/null | tail -n +2 | cut -d, -f1)
FIRST_LOCATION=$(echo "$THEME_LOCATIONS" | head -1 | tr -d '[:space:]')
MENU_ASSIGNED=false
MENU_LOCATION=""

if [ -n "$FIRST_LOCATION" ]; then
  $WP menu location assign "$MENU_ID" "$FIRST_LOCATION" 2>&1
  MENU_ASSIGNED=true
  MENU_LOCATION="$FIRST_LOCATION"
  echo "[Build] Menu created with ${#PAGE_IDS[@]} items, assigned to location: $FIRST_LOCATION"
else
  echo "[Build] NOTE: No classic menu locations found. Menu created but must be assigned via Site Editor Navigation block. See SETUP.md."
  echo "[Build] Menu created with ${#PAGE_IDS[@]} items (unassigned - FSE block theme uses Navigation block)"
fi
```

**FSE block themes and menu locations:** Many Full Site Editing block themes (like Twenty Twenty-Four) do not register classic menu locations - they use the Navigation block in block templates instead. When `wp menu location list` returns empty, this is expected behaviour for block themes. The warning message is informational, not an error. The SETUP.md (written by build-setup) should guide users to the Site Editor to assign the navigation if needed.

## Section 5: Database Re-export

**CRITICAL: Re-export the database AFTER all plugin, content, and menu operations.** This overwrites the previous `database.sql` (from build-theme or build-mcp) intentionally - the new export captures all installed plugins, created pages, posts, and menu structures.

```bash
echo "[Build] Re-exporting database (captures all content, plugins, and menus)..."

if ! $WP db export "$BUILD_DIR/database.sql" --add-drop-table 2>&1; then
  echo "[Build] WARNING: Database re-export failed. Previous export retained - some content may be missing from the imported DB."
else
  echo "[Build] Database re-exported (includes all content and plugins)"
fi
```

The zip packaging step (run by build-setup after this skill) will use this re-exported file.

## Section 6: Output Variables

The following variables are set by this skill and consumed by downstream skills (`build-setup`) for build.json manifest updates, SETUP.md generation, and zip packaging decisions.

| Variable            | Type         | Description                                                        |
|---------------------|--------------|--------------------------------------------------------------------|
| `INSTALLED_PLUGINS` | array        | Slugs of plugins successfully installed and activated              |
| `FAILED_PLUGINS`    | array        | Slugs of plugins that failed to install or were deactivated        |
| `PAGES_CREATED`     | integer      | Count of pages created                                             |
| `POSTS_CREATED`     | integer      | Count of posts (blog posts) created                                |
| `HOME_ID`           | integer      | WordPress post ID of the Home page (set as static front page)      |
| `MENU_ASSIGNED`     | true / false | Whether the menu was assigned to a theme location                  |
| `MENU_LOCATION`     | string       | Name of the assigned menu location, or empty string if unassigned  |

Example manifest update for build.json (handled by build-setup):

```json
{
  "content": {
    "plugins_installed": ["wpforms-lite", "woocommerce"],
    "plugins_failed": [],
    "pages_created": 4,
    "posts_created": 3,
    "menu_assigned": true,
    "menu_location": "primary"
  }
}
```

## Implementation Notes

**Docker container lifetime:** This skill must execute while the Docker MySQL container from `build-scaffold` Section 3 is still alive. WP-CLI plugin activation, post creation, menu creation, and the final `wp db export` all require a live MySQL connection. The EXIT trap set in `build-scaffold` fires when the entire command session ends - not between skill invocations. If "Error establishing a database connection" appears, the container has stopped prematurely.

**Content-to-temp-file pattern:** Always write page and post content to `/tmp/wp-*-$$.sh` before passing to WP-CLI via `$(cat ...)`. Shell command length limits (~2MB on macOS, 131072 chars on Linux) can be hit with rich Gutenberg block content. The temp file approach avoids this limit entirely. Always remove temp files with `rm -f` after use.

**Images before content:** Section 2 must complete before Section 3 begins. If image generation fails, content still runs - it will reference URLs that return 404 until images are generated manually. Log a warning if image generation failed so build-setup can note it in SETUP.md.

**10-plugin cap enforcement:** If the coding agent selects more than 10 plugins, trim the list before running any `install_plugin` calls. Log: `[Build] Plugin list trimmed to 10 (removed: slug1, slug2)`.

**Warn-and-continue everywhere:** No `exit 1` in Sections 1 through 5. Plugin failures, image failures, individual page/post failures, menu assignment failures - all are logged as warnings and the build continues. Only the upstream `build-scaffold` (Docker, WP core download, WP install) should abort a build with `exit 1`.

**Content quality standards (locked decisions):**
- All content is contextual English prose written by the coding agent
- Business names, people's names, addresses, and phone numbers are fictional but realistic
- No Lorem Ipsum in any form
- No placeholder markers like `[YOUR BUSINESS NAME]` or `[REPLACE THIS]`
- No verbatim copying of real-world business details

**FSE menu location note:** FSE block themes commonly return zero results from `wp menu location list`. This is expected - they use block-based navigation instead of classic menus. The `MENU_ASSIGNED=false` state is valid for FSE builds, and SETUP.md should guide users accordingly.

**References:**
- @references/wp-wpcli-and-ops/SKILL.md - WP-CLI post create, menu commands, option update patterns
