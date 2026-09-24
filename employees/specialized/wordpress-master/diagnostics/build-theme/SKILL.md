---
name: build-theme
description: Select, install, and activate an FSE block theme from WP.org based on a natural language site description - queries API with full-site-editing tag, evaluates by relevance/popularity/rating, falls back to curated list
requires: [wp-cli, docker-mysql-running]
runs-after: [build-mcp Section 2]
runs-before: [build-content]
---

# Build Theme Skill

Selects, installs, and activates a Full Site Editing (FSE) block theme from WP.org based on the user's natural language site description. This skill queries the WP.org Themes API v1.2 for FSE themes, evaluates results against the NL prompt using Claude's in-context judgment, and installs the best match. A curated fallback list provides guaranteed theme selection when the API returns poor results or is unavailable.

**Critical sequencing:** This skill runs AFTER `build-mcp` Section 2 (MCP adapter activated, DB re-exported) and BEFORE `build-content` (content seeding requires the theme to be active for menu location discovery).

This skill expects the following variables to already be set by the calling command:

- `BUILD_DIR` - absolute path to the build directory (set by build-scaffold Section 2)
- `WP` - the WP-CLI command prefix (e.g., `wp --path=$BUILD_DIR` or the Docker equivalent, set by build-scaffold Section 4)
- `NL_PROMPT` - the user's natural language site description string
- `SITE_TITLE` - site title derived from the NL prompt (set by the calling command before this skill)

## Section 1: WP.org Themes API Query

Query the WP.org Themes API v1.2 for the FSE block theme pool. Use the `full-site-editing` tag to filter - this is the canonical public signal for FSE/block themes. Do NOT combine `search` and `tag` parameters: the API ignores tags when `search` is present. Claude evaluates theme relevance in-context after fetching the pool.

```bash
echo "[Build] Querying WP.org Themes API for FSE theme pool..."

# CRITICAL anti-pattern: Do NOT use ?action=query_themes&request[search]=...&request[tag][]=full-site-editing
# The API ignores tag[] when search is present. Use tag-only query; Claude evaluates relevance in-context.

FSE_THEMES_FILE="/tmp/fse_themes_$$.json"

curl -s --max-time 10 \
  "https://api.wordpress.org/themes/info/1.2/?action=query_themes&request[tag][]=full-site-editing&request[browse]=popular&request[per_page]=50&request[fields][active_installs]=true&request[fields][rating]=true&request[fields][description]=true&request[fields][tags]=true" \
  -o "$FSE_THEMES_FILE"
CURL_EXIT=$?

# Validate response - check exit code, non-empty file, and JSON structure
API_AVAILABLE=false
if [ $CURL_EXIT -eq 0 ] && [ -s "$FSE_THEMES_FILE" ]; then
  # Count themes in response - need at least 3 for Claude to evaluate properly
  THEME_COUNT=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get('themes', [])))" "$FSE_THEMES_FILE" 2>/dev/null || echo "0")
  if [ "$THEME_COUNT" -ge 3 ]; then
    API_AVAILABLE=true
    echo "[Build] WP.org API returned $THEME_COUNT FSE themes for evaluation."
  else
    echo "[Build] WP.org API returned fewer than 3 themes ($THEME_COUNT). Falling back to curated list."
  fi
else
  echo "[Build] WP.org API unavailable - using curated theme list"
fi
```

## Section 2: Theme Evaluation and Selection

Claude reads the API JSON response and evaluates each theme against the `NL_PROMPT`. If the API returned a viable pool, Claude selects the best match using relevance, popularity, and rating. If the API failed or returned too few results, Claude selects from the curated fallback list based on the site category in `NL_PROMPT`.

**Scoring criteria (in priority order):**
1. Name, description, and tag relevance to the site type described in `NL_PROMPT`
2. `active_installs` - popularity signal (higher = better)
3. `rating` - quality signal (higher = better)

**Classic themes are never selected**, even if they would score higher on other metrics.

```bash
if [ "$API_AVAILABLE" = "true" ]; then
  echo "[Build] Evaluating FSE themes against NL prompt: \"$NL_PROMPT\""
  echo "[Build] Reading themes from: $FSE_THEMES_FILE"

  # Claude reads the FSE themes JSON and evaluates each theme:
  # - themes[].name: display name
  # - themes[].slug: WP.org install slug
  # - themes[].description: theme description
  # - themes[].tags: theme feature/category tags
  # - themes[].active_installs: popularity (number of active installations)
  # - themes[].rating: quality rating (0-100 scale)
  #
  # Claude selects the theme with the best combination of:
  # (1) relevance to NL_PROMPT site type
  # (2) high active_installs
  # (3) high rating
  #
  # No-match behavior: If no theme scores well against the NL_PROMPT site type,
  # Claude presents the top 3 candidates to the user and asks them to choose.
  # This breaks autonomous flow intentionally - satisfaction > automation.
  #
  # After selection, Claude sets:
  THEME_SLUG="<slug selected by Claude from API results>"
  THEME_NAME="<display name selected by Claude from API results>"

else
  # Curated fallback list - maps site categories to known FSE-compatible theme slugs
  # These themes are verified FSE block themes maintained on WP.org.
  # Update this list if a theme is removed from WP.org.
  #
  # Category → Slug mappings (Claude extracts site category from NL_PROMPT):
  #
  # portfolio / photography / creative → flavor
  # business / corporate / agency      → flavor
  # blog / magazine / news             → flavor
  # restaurant / food / cafe           → flavor
  # ecommerce / shop / store           → flavor
  # default (any other)                → twentytwentyfour
  #
  # twentytwentyfour is the guaranteed last-resort fallback (maintained by WordPress.org core team).
  #
  # Claude reads NL_PROMPT, determines the site category, and sets:
  THEME_SLUG="<slug selected by Claude from curated fallback list>"
  THEME_NAME="<display name for the selected curated theme>"
fi

echo "[Build] Theme selected: $THEME_NAME ($THEME_SLUG)"
```

## Section 3: Theme Installation and Activation

Install and activate the selected theme using WP-CLI. If installation fails, attempt fallback candidates. Always validate FSE compatibility by checking for `theme.json` post-install. Use warn-and-continue - never abort the build for theme failures.

```bash
echo "[Build] Installing theme: $THEME_SLUG..."

install_theme() {
  local slug="$1"
  if $WP theme install "$slug" --activate 2>&1; then
    echo "[Build] Theme installed and activated: $slug"

    # FSE validation - check for theme.json presence
    # Claude selected from the FSE pool, so this is a secondary confirmation.
    # false negative possible if theme.json is in a subdirectory or named differently.
    if [ -f "$BUILD_DIR/wp-content/themes/$slug/theme.json" ]; then
      echo "[Build] FSE validated: theme.json found."
    else
      echo "[Build] WARNING: theme.json not found - theme may not be FSE-compatible."
      echo "[Build] Proceeding - Claude selected this theme from the full-site-editing tag pool."
    fi

    # Get theme version
    THEME_VERSION=$($WP theme get "$slug" --field=version 2>/dev/null || \
      grep -m 1 "^Version:" "$BUILD_DIR/wp-content/themes/$slug/style.css" 2>/dev/null | \
      sed 's/Version: //' | tr -d '[:space:]' || \
      echo "unknown")

    THEME_INSTALLED=true
    echo "[Build] Theme installed and activated: $slug (v$THEME_VERSION)"
    return 0
  else
    echo "[Build] WARNING: Theme installation failed for slug: $slug"
    THEME_INSTALLED=false
    return 1
  fi
}

# Attempt 1: Install API-selected or curated theme
if ! install_theme "$THEME_SLUG"; then
  # Attempt 2: If API-selected theme failed, try curated fallback
  if [ "$API_AVAILABLE" = "true" ]; then
    echo "[Build] Trying curated fallback theme for site category..."
    # Claude determines the curated fallback slug from NL_PROMPT site category
    # (see Section 2 curated list) and retries
    FALLBACK_SLUG="twentytwentyfour"  # Claude replaces this with category-specific slug if applicable
    if ! install_theme "$FALLBACK_SLUG"; then
      # Attempt 3: Last resort - twentytwentyfour (maintained by WordPress.org)
      if [ "$FALLBACK_SLUG" != "twentytwentyfour" ]; then
        echo "[Build] Trying last-resort fallback: twentytwentyfour..."
        if ! install_theme "twentytwentyfour"; then
          # Final fallback - log warning and continue with WP default theme
          echo "[Build] WARNING: All theme installation attempts failed."
          echo "[Build] WARNING: Build continues with WordPress default theme."
          THEME_SLUG="default"
          THEME_NAME="WordPress Default"
          THEME_VERSION="unknown"
          THEME_INSTALLED=false
        fi
      else
        # twentytwentyfour already failed - continue with default
        echo "[Build] WARNING: All theme installation attempts failed."
        echo "[Build] WARNING: Build continues with WordPress default theme."
        THEME_SLUG="default"
        THEME_NAME="WordPress Default"
        THEME_VERSION="unknown"
        THEME_INSTALLED=false
      fi
    fi
  else
    # Curated theme failed - try twentytwentyfour as last resort
    if [ "$THEME_SLUG" != "twentytwentyfour" ]; then
      echo "[Build] Trying last-resort fallback: twentytwentyfour..."
      if ! install_theme "twentytwentyfour"; then
        echo "[Build] WARNING: All theme installation attempts failed."
        echo "[Build] WARNING: Build continues with WordPress default theme."
        THEME_SLUG="default"
        THEME_NAME="WordPress Default"
        THEME_VERSION="unknown"
        THEME_INSTALLED=false
      fi
    else
      echo "[Build] WARNING: All theme installation attempts failed."
      echo "[Build] WARNING: Build continues with WordPress default theme."
      THEME_SLUG="default"
      THEME_NAME="WordPress Default"
      THEME_VERSION="unknown"
      THEME_INSTALLED=false
    fi
  fi
fi

# Clean up temp API response file
rm -f "$FSE_THEMES_FILE"
```

## Section 4: Site Title Update

Update the WordPress site title and tagline to match the site described in `NL_PROMPT`. The site title was already set during `build-scaffold` WP install (`--title="$SITE_TITLE"`), but this step allows the tagline to be set with a contextual description generated from the NL prompt.

```bash
echo "[Build] Setting site title and tagline..."

# Update site title (may already match from build-scaffold --title, but update to confirm)
$WP option update blogname "$SITE_TITLE" 2>&1

# Claude generates a brief tagline (one line, no quotes) from NL_PROMPT
# Examples:
#   NL_PROMPT: "a portfolio site for a freelance photographer"
#   → Tagline: "Capturing moments that matter"
#
#   NL_PROMPT: "a restaurant website for an Italian bistro in Sydney"
#   → Tagline: "Authentic Italian flavours in the heart of Sydney"
#
# Claude sets SITE_TAGLINE to the generated tagline, then:
SITE_TAGLINE="<Claude-generated tagline from NL_PROMPT>"
$WP option update blogdescription "$SITE_TAGLINE" 2>&1

echo "[Build] Site title set: $SITE_TITLE"
echo "[Build] Site tagline set: $SITE_TAGLINE"
```

## Implementation Notes

**Pipeline position:** This skill runs in the NL build pipeline strictly AFTER `build-mcp` Section 2 (MCP adapter activated, database re-exported) and BEFORE `build-content`. Theme must be active before content seeding because `build-content` uses `$WP menu location list` to discover the active theme's navigation locations - this requires the target theme to already be installed and active.

**Docker MySQL container:** The ephemeral Docker MySQL container from `build-scaffold` Section 3 must still be running when this skill executes. WP-CLI theme installation writes to the WordPress options table (active theme slug). The EXIT trap set in `build-scaffold` Section 3 remains active for the entire build session and fires only when the full command exits - not between skill invocations.

**Output variables:** The following variables are set by this skill and consumed by downstream skills (`build-content`, `build-setup`):
- `THEME_SLUG` - installed theme slug (e.g., `twentytwentyfour`, `flavor`)
- `THEME_NAME` - display name (e.g., `Twenty Twenty-Four`, `Flavor`)
- `THEME_VERSION` - installed version string (e.g., `1.3`, `unknown` if undetectable)
- `THEME_INSTALLED` - `true` if installation succeeded, `false` if all fallbacks failed

**Curated fallback list maintenance:** The curated list maps site categories to known FSE block themes on WP.org. If a curated theme slug is removed from WP.org (causing `wp theme install` to fail with "not found"), update this list with a current FSE-compatible replacement. `twentytwentyfour` is the guaranteed last-resort fallback - it is maintained by the WordPress.org core team and will not be removed.

**No post-install customization (locked decision):** Per user decision captured in CONTEXT.md, no theme.json overrides, child themes, or Global Styles modifications are applied after installation. The theme is installed and activated as-is from WP.org. Its built-in design stands as delivered.

**FSE validation reliability:** The `theme.json` check is a secondary confirmation - Claude already filtered themes by the `full-site-editing` tag in the API query. A "WARNING: theme.json not found" message does not indicate an error: the theme may store `theme.json` at a non-standard location, or the WP.org tag may have been set correctly but the file path check failed. Build continues regardless.

**References:**
- @references/wp-block-themes/SKILL.md - FSE theme structure, theme.json schema, block template patterns
- @references/wp-wpcli-and-ops/SKILL.md - WP-CLI theme command reference, --activate flag, --field output
