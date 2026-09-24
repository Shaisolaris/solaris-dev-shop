---
name: build-modify
description: Session-aware per-step execution engine for /modify - surgical theme edits, WP-CLI content/plugin changes, lazy Docker startup, and versioned output on session completion
requires: [git]
runs-after: [build-scaffold, build-git, build-content, build-visual]
---

# Build Modify Skill

Session-aware execution engine for the `/modify` command. COMMAND.md owns the interactive session loop and invokes this skill's sections per step. Each atomic modification step produces its own git commit and build.json entry. No zip or SETUP.md regeneration occurs per step - those are deferred to session completion (Section 7).

This skill expects the following variables to be set by the calling command (`/modify`) before invocation:

| Variable | Source | Description |
|---|---|---|
| `WP_DIR` | /modify argument | Path to WordPress directory (set once at session start) |
| `MODIFY_MODE` | /modify session loop | `"nl"` for natural language, `"visual"` for design re-export (set per step) |
| `NL_REQUEST` | /modify session loop | Natural language modification request (set per NL step) |
| `VISUAL_PATH` | /modify session loop | Path to updated design export directory (set per visual step) |

---

## Section 0: Prerequisites and Setup

Set up lazy Docker/WP-CLI helpers, declare the `git_commit_stage` helper function, and register an EXIT trap for MySQL container cleanup. Docker is NOT checked upfront - it is started lazily only when a content or plugin step requires MySQL.

```bash
# ── Lazy Docker/WP-CLI helpers ───────────────────────────────────────────────
# Docker and WP-CLI are only needed for content and plugin steps.
# Theme-only sessions (theme-token, template-edit) work without Docker entirely.

WP_CLI_MODE=""
WP=""
DOCKER_CHECKED=false

ensure_wp_cli() {
  if [ "$DOCKER_CHECKED" = "true" ]; then
    return 0
  fi

  # Check Docker is running
  if ! docker info > /dev/null 2>&1; then
    echo "[Modify] ERROR: Docker is required for content and plugin modifications."
    echo "[Modify] Start Docker Desktop and try again."
    echo "[Modify] Theme-only modifications (theme-token, template-edit) work without Docker."
    return 1
  fi

  # Check for local WP-CLI first (preferred), Docker fallback
  if which wp > /dev/null 2>&1; then
    WP_CLI_MODE="local"
    WP="wp --path=$BUILD_DIR"
    echo "[Modify] WP-CLI ready (local)"
  else
    if docker run --rm wordpress:cli wp --version > /dev/null 2>&1; then
      WP_CLI_MODE="docker"
      WP="docker run --rm -v \"$BUILD_DIR:/var/www/html\" --network host wordpress:cli wp --allow-root"
      echo "[Modify] WP-CLI ready (docker)"
    else
      echo "[Modify] ERROR: WP-CLI is required for content/plugin modifications but was not found."
      return 1
    fi
  fi

  DOCKER_CHECKED=true
  return 0
}

ensure_docker_mysql() {
  # Ensure WP-CLI is available first
  if ! ensure_wp_cli; then
    STEP_SKIPPED=true
    return 1
  fi

  # Check database.sql exists
  if [ ! -f "$BUILD_DIR/database.sql" ]; then
    echo "[Modify] ERROR: database.sql not found in build directory."
    echo "[Modify] Cannot perform content modifications without a database."
    echo "[Modify] Theme-only modifications (theme-token, template-edit) are still possible."
    STEP_SKIPPED=true
    return 1
  fi

  # If MySQL is already running, reuse it
  if [ "$MYSQL_RUNNING" = "true" ]; then
    return 0
  fi

  # Read existing credentials from wp-config.php
  EXISTING_DB_PASS=$($WP config get DB_PASSWORD 2>/dev/null || echo "")
  EXISTING_DB_USER=$($WP config get DB_USER 2>/dev/null || echo "wp")

  if [ -z "$EXISTING_DB_PASS" ]; then
    EXISTING_DB_PASS="$(openssl rand -hex 12)"
    EXISTING_DB_USER="wp"
    echo "[Modify] NOTE: Could not read existing DB credentials - using generated credentials"
  fi

  # Port 3307 conflict check
  if lsof -i :3307 > /dev/null 2>&1; then
    echo "[Modify] ERROR: Port 3307 is already in use. Close the conflicting process and try again."
    STEP_SKIPPED=true
    return 1
  fi

  MYSQL_ROOT_PASS="wpmod_root_$(openssl rand -hex 8)"

  # Start MySQL container with credentials matching wp-config.php
  docker run -d \
    --name "$MYSQL_CONTAINER" \
    -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASS" \
    -e MYSQL_DATABASE=wordpress \
    -e MYSQL_USER="$EXISTING_DB_USER" \
    -e MYSQL_PASSWORD="$EXISTING_DB_PASS" \
    -p 127.0.0.1:3307:3306 \
    mysql:8.0 \
    --default-authentication-plugin=mysql_native_password \
    > /dev/null

  MYSQL_RUNNING=true
  echo "[Modify] Starting MySQL container..."

  # Wait for ready (up to 30 seconds)
  WAIT_COUNT=0
  until docker exec "$MYSQL_CONTAINER" mysqladmin ping --silent 2>/dev/null; do
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ "$WAIT_COUNT" -ge 30 ]; then
      echo "[Modify] ERROR: MySQL container failed to start within 30 seconds."
      STEP_SKIPPED=true
      return 1
    fi
    sleep 1
  done

  echo "[Modify] Database ready."

  # Import existing database.sql
  if ! $WP db import "$BUILD_DIR/database.sql" 2>&1; then
    echo "[Modify] ERROR: Database import failed. Cannot proceed with content modification."
    STEP_SKIPPED=true
    return 1
  fi

  echo "[Modify] Database imported into ephemeral container."
  return 0
}

# ── MySQL container EXIT trap ────────────────────────────────────────────────

MYSQL_CONTAINER="wpmodify-mysql-$$"
MYSQL_RUNNING=false

cleanup_modify_mysql() {
  if [ "$MYSQL_RUNNING" = "true" ]; then
    echo "[Modify] Cleaning up Docker MySQL container..."
    docker rm -f "$MYSQL_CONTAINER" 2>/dev/null || true
    echo "[Modify] MySQL cleanup complete."
  fi
}
trap cleanup_modify_mysql EXIT

# ── git_commit_stage function ────────────────────────────────────────────────
# Redeclared from build-git Section 4 - skills are separate execution contexts.
# Usage: git_commit_stage "commit subject" ["commit body"]
# Failures are warn-and-continue - git failures never abort the modification.

git_commit_stage() {
  local SUBJECT="$1"
  local BODY="${2:-}"

  if [ "${GIT_INITIALIZED:-true}" != "true" ]; then
    echo "[Modify] WARNING: Git not initialized - skipping commit: $SUBJECT"
    return 0
  fi

  echo "[Modify] Git commit: $SUBJECT"

  # Stage all changes
  if ! git -C "$BUILD_DIR" add -A > /dev/null 2>&1; then
    echo "[Modify] WARNING: git add failed for commit: $SUBJECT"
    return 0
  fi

  # Check if there is anything to commit
  if git -C "$BUILD_DIR" diff --cached --quiet 2>/dev/null; then
    echo "[Modify] NOTE: Nothing to commit for: $SUBJECT (no changes staged)"
    return 0
  fi

  # Commit - use -m twice for multiline commits (subject + body)
  if [ -n "$BODY" ]; then
    if git -C "$BUILD_DIR" commit -m "$SUBJECT" -m "$BODY" > /dev/null 2>&1; then
      echo "[Modify] Committed: $SUBJECT"
    else
      echo "[Modify] WARNING: git commit failed for: $SUBJECT"
    fi
  else
    if git -C "$BUILD_DIR" commit -m "$SUBJECT" > /dev/null 2>&1; then
      echo "[Modify] Committed: $SUBJECT"
    else
      echo "[Modify] WARNING: git commit failed for: $SUBJECT"
    fi
  fi

  echo ""
}
```

## Section 1: WordPress Directory Validation and State Loading

Use the WordPress directory path (WP_DIR) directly. Validate wp-content/ exists, load build.json if present, or create a minimal one for external WordPress directories. This section runs once at session start.

```bash
BUILD_DIR="$WP_DIR"
echo "[Modify] WordPress directory: $BUILD_DIR"
echo ""

# ── Validate wp-content/ exists (belt-and-suspenders - COMMAND.md already checked) ──

if [ ! -d "$BUILD_DIR/wp-content" ]; then
  echo "ERROR: wp-content/ not found in $BUILD_DIR"
  echo "This does not appear to be a WordPress installation."
  exit 1
fi

# ── Load or create build.json ────────────────────────────────────────────────

BUILD_JSON_PATH="$BUILD_DIR/build.json"

if [ -f "$BUILD_JSON_PATH" ]; then
  echo "[Modify] Loading state from build.json..."

  STATE_JSON=$(python3 << 'PYEOF'
import json, os, sys

build_json_path = os.path.join(os.environ.get("BUILD_DIR", ""), "build.json")
try:
    with open(build_json_path) as f:
        state = json.load(f)
    print(json.dumps(state))
except Exception:
    print("{}")
PYEOF
  )

  # Extract key state values
  THEME_SLUG=$(echo "$STATE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('theme',{}).get('slug',''))" 2>/dev/null)
  CREATION_MODE=$(echo "$STATE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('creation_mode', d.get('mode','')))" 2>/dev/null)
  EXISTING_MODS=$(echo "$STATE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('modifications',[])))" 2>/dev/null)
else
  echo "[Modify] No build.json found - this appears to be an external WordPress directory."
  echo "[Modify] Creating build.json to track modifications."

  # Auto-detect theme slug: first non-twentytwenty* theme in wp-content/themes/
  THEME_SLUG=$(python3 << PYEOF
import os, sys

themes_dir = os.path.join("$BUILD_DIR", "wp-content", "themes")
if not os.path.isdir(themes_dir):
    print("")
    sys.exit(0)

themes = sorted(os.listdir(themes_dir))
# Prefer non-core themes
for t in themes:
    if os.path.isdir(os.path.join(themes_dir, t)) and not t.startswith("twentytwenty"):
        print(t)
        sys.exit(0)
# Fallback to first theme
for t in themes:
    if os.path.isdir(os.path.join(themes_dir, t)):
        print(t)
        sys.exit(0)
print("")
PYEOF
  )

  CREATION_MODE="external"
  EXISTING_MODS=0

  # Create minimal build.json
  python3 << PYEOF
import json, os
from datetime import datetime, timezone

build_dir = "$BUILD_DIR"
theme_slug = "$THEME_SLUG"
build_id = os.path.basename(os.path.abspath(build_dir))

state = {
    "build_id": build_id,
    "creation_mode": "external",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "build_dir": os.path.abspath(build_dir),
    "theme": {"slug": theme_slug} if theme_slug else {},
    "modifications": []
}

build_json_path = os.path.join(build_dir, "build.json")
with open(build_json_path, "w") as f:
    json.dump(state, f, indent=2)
    f.write("\n")

print(f"[Modify] Created build.json (build_id: {build_id}, theme: {theme_slug or 'unknown'})")
PYEOF
fi

# Derive BUILD_ID from build.json for downstream sections (commit messages, output naming)
BUILD_ID=$(python3 -c "import json; print(json.load(open('$BUILD_DIR/build.json')).get('build_id',''))" 2>/dev/null)

echo "[Modify] Theme: ${THEME_SLUG:-unknown}"
echo "[Modify] Creation mode: ${CREATION_MODE:-unknown}"
echo "[Modify] Existing modifications: ${EXISTING_MODS:-0}"

# ── Compute next version ─────────────────────────────────────────────────────

# Version starts at 1 for the first modification
NEXT_VERSION=$((${EXISTING_MODS:-0} + 1))

echo "[Modify] Next version: v${NEXT_VERSION}"
echo ""

# ── Detect git repo ──────────────────────────────────────────────────────────

if git -C "$BUILD_DIR" rev-parse --git-dir > /dev/null 2>&1; then
  echo "[Modify] Git repo detected - appending modification commits"
  GIT_INITIALIZED=true
else
  echo "[Modify] No git repo found - initializing for modification tracking"
  # Initialize git with the same pattern as build-git Section 1
  if git -C "$BUILD_DIR" init -b main > /dev/null 2>&1; then
    # Set fallback git identity if needed
    GIT_USER_NAME=$(git config --global user.name 2>/dev/null || echo "")
    GIT_USER_EMAIL=$(git config --global user.email 2>/dev/null || echo "")
    if [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
      git -C "$BUILD_DIR" config user.name "CoWork Build"
      git -C "$BUILD_DIR" config user.email "build@cowork.local"
    fi

    # Write .gitignore from build-git Section 2 pattern
    cat > "$BUILD_DIR/.gitignore" << 'GITIGNORE'
# WordPress Build - Generated .gitignore
# Tracks: custom-* prefixed themes and plugins, README.md, SETUP.md, build.json
# Excludes: WP core, ephemeral dirs, database, MCP adapter, WP.org-sourced components

# ── WordPress Core Root Files ──────────────────────────────────────────────
index.php
license.txt
readme.html
wp-activate.php
wp-blog-header.php
wp-comments-post.php
wp-config.php
wp-config-sample.php
wp-cron.php
wp-links-opml.php
wp-load.php
wp-login.php
wp-mail.php
wp-settings.php
wp-signup.php
wp-trackback.php
xmlrpc.php

# ── WordPress Core Directories ─────────────────────────────────────────────
wp-admin/
wp-includes/

# ── Ephemeral wp-content Directories ──────────────────────────────────────
wp-content/cache/
wp-content/upgrade/
wp-content/uploads/
wp-content/backups/
wp-content/w3tc-config/
wp-content/wflogs/
wp-content/updraft/

# ── Database and Debug Logs ────────────────────────────────────────────────
database.sql
wp-content/debug.log

# ── MCP Adapter (bundled, reinstallable from CoWork plugin) ───────────────
wp-content/plugins/mcp-adapter/

# ── WordPress Core Bundled Themes (reinstallable) ─────────────────────────
wp-content/themes/twentytwentyone/
wp-content/themes/twentytwentytwo/
wp-content/themes/twentytwentythree/
wp-content/themes/twentytwentyfour/
wp-content/themes/twentytwentyfive/
GITIGNORE

    # Create initial commit capturing current state
    git -C "$BUILD_DIR" add -A > /dev/null 2>&1
    git -C "$BUILD_DIR" commit -m "build(init): capture existing state for modification tracking" > /dev/null 2>&1
    GIT_INITIALIZED=true
    echo "[Modify] Git initialized with initial state commit"
  else
    GIT_INITIALIZED=false
    echo "[Modify] WARNING: git init failed - modifications will proceed without git history"
  fi
fi

echo ""
```

## Section 2: NL Request Decomposition (NL mode only)

the coding agent reads the NL_REQUEST and decomposes it into a sequence of atomic steps. Each step has a type from the modification taxonomy. Compound requests (e.g. "change the color and add a blog page") are split into separate steps, each getting its own git commit and build.json entry.

**Skip this section entirely for visual mode** - visual modifications are handled as a single atomic step in Section 5.

```
Decomposition is a the coding agent in-context reasoning step, not automated parsing.

the coding agent reads the NL_REQUEST and the current build state (theme slug, installed plugins,
existing content from build.json) to produce an ordered list of atomic steps.

Step Type Taxonomy:
┌──────────────────┬─────────────────────────────────────────────────────────────┐
│ Step Type        │ Description                                                 │
├──────────────────┼─────────────────────────────────────────────────────────────┤
│ theme-token      │ Change a value in theme.json (color, font, spacing)         │
│ template-edit    │ Edit a specific .html template or part file                 │
│ content-edit     │ Modify an existing page or post via WP-CLI (requires MySQL) │
│ content-create   │ Create a new page, post, or menu item (requires MySQL)      │
│ plugin-add       │ Install and activate a WP.org plugin (requires MySQL)       │
│ plugin-remove    │ Deactivate and uninstall a plugin (requires MySQL)          │
└──────────────────┴─────────────────────────────────────────────────────────────┘

Output: an ordered list of atomic steps with type, target, and specific change description.

Example decomposition:

  User request: "change the primary color to forest green and add a blog page"

  Step 1: [theme-token] theme.json → settings.color.palette → primary → #2d5a27
  Step 2: [content-create] Create new page "Blog" with wp post create, link in navigation menu

  Each step produces:
  - One git commit: build(modify): "change the primary color to forest green and add a blog page" (step 1/2)
  - One build.json modifications entry

For a single-step request, omit the "(step N/M)" suffix from the commit message.

IMPORTANT: Content steps (content-edit, content-create, plugin-add, plugin-remove) all
require MySQL. These steps call ensure_docker_mysql() which handles lazy Docker startup.
If Docker is unavailable, content/plugin steps are skipped with a warning - theme-only
steps still succeed.
```

## Section 3: NL Modification Execution

Execute each atomic step from the decomposition. Each sub-section handles a different step type. The per-step finalization (Section 4) runs after each step completes.

### Section 3a: theme-token Steps

Read `theme.json` with Python `json.load`, locate the target token, apply the change, validate, and write back. Never use sed/awk for JSON editing. No Docker required.

```bash
# theme-token modification pattern
# Variables: THEME_SLUG, TARGET_SLUG (e.g. "primary"), NEW_VALUE (e.g. "#2d5a27"), TOKEN_PATH (e.g. "color.palette")

THEME_JSON_PATH="$BUILD_DIR/wp-content/themes/$THEME_SLUG/theme.json"

if [ ! -f "$THEME_JSON_PATH" ]; then
  echo "[Modify] WARNING: theme.json not found at $THEME_JSON_PATH - skipping theme-token step"
  # warn-and-continue
else
  # Read, modify, validate, write - all in Python for JSON safety
  python3 << PYEOF
import json, sys, os, shutil

theme_json_path = "$THEME_JSON_PATH"
target_slug = "$TARGET_SLUG"
new_value = "$NEW_VALUE"
token_path = "$TOKEN_PATH"

# Read current theme.json
with open(theme_json_path) as f:
    theme = json.load(f)

# Back up original for rollback on validation failure
backup_path = theme_json_path + ".bak"
shutil.copy2(theme_json_path, backup_path)

old_value = None
modified = False

# Route by token path type
if token_path.startswith("color.palette"):
    palette = theme.get("settings", {}).get("color", {}).get("palette", [])
    for entry in palette:
        if entry.get("slug") == target_slug:
            old_value = entry.get("color")
            entry["color"] = new_value
            modified = True
            break

elif token_path.startswith("typography.fontFamilies"):
    font_families = theme.get("settings", {}).get("typography", {}).get("fontFamilies", [])
    for entry in font_families:
        if entry.get("slug") == target_slug:
            old_value = entry.get("fontFamily")
            entry["fontFamily"] = new_value
            modified = True
            break

elif token_path.startswith("spacing"):
    spacing = theme.get("settings", {}).get("spacing", {})
    if target_slug in spacing:
        old_value = spacing[target_slug]
        spacing[target_slug] = new_value
        modified = True

if not modified:
    print(f"[Modify] WARNING: Token '{target_slug}' not found in {token_path} - skipping")
    os.remove(backup_path)
    sys.exit(0)

# Validate JSON is still valid
try:
    json.dumps(theme)
except Exception as e:
    print(f"[Modify] ERROR: JSON validation failed after edit - restoring backup")
    shutil.move(backup_path, theme_json_path)
    sys.exit(1)

# Write updated theme.json
with open(theme_json_path, "w") as f:
    json.dump(theme, f, indent=2)
    f.write("\n")

# Verify written file is valid JSON
try:
    with open(theme_json_path) as f:
        json.load(f)
except Exception:
    print(f"[Modify] ERROR: Written file is not valid JSON - restoring backup")
    shutil.move(backup_path, theme_json_path)
    sys.exit(1)

# Clean up backup
os.remove(backup_path)

print(f"[Modify] theme.json updated: {target_slug} {old_value} → {new_value}")
PYEOF

  STEP_FILES_CHANGED="wp-content/themes/$THEME_SLUG/theme.json"
  STEP_TYPE="theme-token"
  STEP_DESCRIPTION="Changed ${target_slug} from ${old_value} to ${new_value}"
  BEFORE_JSON="{\"${target_slug}\": \"${old_value}\"}"
  AFTER_JSON="{\"${target_slug}\": \"${new_value}\"}"
fi
```

### Section 3b: template-edit Steps

Read the target `.html` template file, apply the the coding agent-interpreted change to the specific block comment section, and write back. Preserve all other blocks verbatim - surgical edit, not full rewrite. No Docker required.

```
Template editing is a the coding agent in-context judgment step.

the coding agent reads the current content of the target template file (from templates/ or parts/)
and the user's modification request. the coding agent then:

1. Identifies which block comment section(s) need to change
2. Rewrites only the affected block(s) using WordPress block comment syntax (<!-- wp:* -->)
3. Preserves all other blocks verbatim
4. Writes the updated template file

The template file is at:
  $BUILD_DIR/wp-content/themes/$THEME_SLUG/templates/{template-name}.html
  OR
  $BUILD_DIR/wp-content/themes/$THEME_SLUG/parts/{part-name}.html

File-level write (not JSON, so standard file write is fine).

STEP_FILES_CHANGED should be set to the relative path of the modified template.
STEP_TYPE="template-edit"
STEP_DESCRIPTION should describe which template and block section changed.
BEFORE_JSON and AFTER_JSON should be set to JSON strings representing the old and new block content.
Example:
  BEFORE_JSON='{"block": "<!-- wp:heading --><h2>Old Title</h2><!-- /wp:heading -->"}'
  AFTER_JSON='{"block": "<!-- wp:heading --><h2>New Title</h2><!-- /wp:heading -->"}'
```

### Section 3c: content-edit and content-create Steps (require MySQL)

Content changes require a live WordPress database. Call `ensure_docker_mysql()` for lazy Docker startup, run WP-CLI operations, and re-export.

```bash
# ── Lazy Docker/MySQL startup ────────────────────────────────────────────────

STEP_SKIPPED=false
ensure_docker_mysql

# ── Run WP-CLI content operations ────────────────────────────────────────────

if [ "${STEP_SKIPPED:-false}" != "true" ]; then
  # For content-create steps:
  # $WP post create --post_type=page --post_title="Blog" --post_status=publish
  # $WP menu item add-post primary {POST_ID}
  #
  # For content-edit steps:
  # $WP post update {POST_ID} --post_content="updated content"
  #
  # the coding agent runs the appropriate WP-CLI commands based on the step description.

  echo "[Modify] Running WP-CLI content operations..."

  # After all content operations for this step:
  # Re-export database
  if ! $WP db export "$BUILD_DIR/database.sql" --add-drop-table 2>&1; then
    echo "[Modify] WARNING: Database re-export failed. Previous SQL retained."
  else
    echo "[Modify] Database re-exported successfully."
  fi

  STEP_FILES_CHANGED="database.sql"
  # Set step metadata for Section 4b build.json tracking
  # STEP_TYPE is "content-edit" or "content-create" depending on the operation
  # STEP_DESCRIPTION describes the WP-CLI operation (e.g. "Created page 'Blog'")
  # BEFORE_JSON and AFTER_JSON capture the change:
  #   BEFORE_JSON='{"content": "previous content summary"}' (or '{}' for create)
  #   AFTER_JSON='{"content": "new content summary"}'
fi
```

### Section 3d: plugin-add and plugin-remove Steps (require MySQL)

Call `ensure_docker_mysql()` for lazy Docker startup. Reuse the same MySQL container as content steps (if already running). Plugin installation follows the same WP.org API + WP-CLI pattern from build-content Section 1.

```bash
# ── Lazy Docker/MySQL startup ────────────────────────────────────────────────

STEP_SKIPPED=false
ensure_docker_mysql

# ── plugin-add ───────────────────────────────────────────────────────────────

# If MySQL is already running from a content step, reuse it.

# Install and activate:
# $WP plugin install {PLUGIN_SLUG} --activate

# Update .gitignore - add new plugin exclusion
# echo "wp-content/plugins/{PLUGIN_SLUG}/" >> "$BUILD_DIR/.gitignore"

# Re-export database after plugin activation
# $WP db export "$BUILD_DIR/database.sql" --add-drop-table

# STEP_FILES_CHANGED="database.sql, .gitignore"

# ── plugin-remove ────────────────────────────────────────────────────────────

# Deactivate and uninstall:
# $WP plugin deactivate {PLUGIN_SLUG}
# $WP plugin uninstall {PLUGIN_SLUG}

# Update .gitignore - remove the plugin's exclusion line
# sed -i '' "/wp-content\/plugins\/${PLUGIN_SLUG}\//d" "$BUILD_DIR/.gitignore"

# Re-export database after plugin removal
# $WP db export "$BUILD_DIR/database.sql" --add-drop-table

# STEP_FILES_CHANGED="database.sql, .gitignore, wp-content/plugins/{PLUGIN_SLUG}/"

echo "[Modify] Plugin modification complete."

# Set step metadata for Section 4b build.json tracking
# STEP_TYPE is "plugin-add" or "plugin-remove"
# STEP_DESCRIPTION="Installed and activated {slug}" or "Removed {slug}"
# BEFORE_JSON='{}' (for add) or '{"plugin": "slug"}' (for remove)
# AFTER_JSON='{"plugin": "slug", "version": "x.y.z"}' (for add) or '{}' (for remove)
# STEP_FILES_CHANGED="database.sql, .gitignore, wp-content/plugins/{slug}/"
```

## Section 4: Per-Step Finalization

Runs after each atomic step completes. Updates git and build.json modifications array, then prints a per-step summary. No zip packaging or SETUP.md regeneration - those are deferred to session completion (Section 7).

```bash
# ── 4a: Git commit ───────────────────────────────────────────────────────────

# For compound requests: include step number
# For single-step requests: omit step number suffix
if [ "$TOTAL_STEPS" -gt 1 ]; then
  COMMIT_SUBJECT="build(modify): \"${NL_REQUEST}\" (step ${CURRENT_STEP}/${TOTAL_STEPS})"
else
  COMMIT_SUBJECT="build(modify): \"${NL_REQUEST}\""
fi

COMMIT_BODY="Updated ${STEP_FILES_CHANGED}: ${STEP_DESCRIPTION}"

git_commit_stage "$COMMIT_SUBJECT" "$COMMIT_BODY"

# ── 4b: Update build.json modifications array ───────────────────────────────

python3 << PYEOF
import json, os
from datetime import datetime, timezone

build_json_path = os.path.join("$BUILD_DIR", "build.json")

try:
    with open(build_json_path) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {}

# Ensure modifications array exists
if "modifications" not in state:
    state["modifications"] = []

next_version = len(state["modifications"]) + 1

modification_entry = {
    "version": next_version,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "type": "$STEP_TYPE",
    "request": "$NL_REQUEST",
    "description": "$STEP_DESCRIPTION",
    "files_changed": "$STEP_FILES_CHANGED".split(", "),
    "before": json.loads('${BEFORE_JSON:-{}}'),
    "after": json.loads('${AFTER_JSON:-{}}'),
}

state["modifications"].append(modification_entry)
state["version"] = next_version

with open(build_json_path, "w") as f:
    json.dump(state, f, indent=2)
    f.write("\n")

print(f"[Modify] build.json updated: v{next_version} modification recorded")
PYEOF

# ── 4c: Per-step summary ────────────────────────────────────────────────────
# This summary is displayed by COMMAND.md's session loop before the next prompt.

COMMIT_HASH=$(git -C "$BUILD_DIR" log --oneline -1 2>/dev/null | awk '{print $1}')

echo ""
echo "────────────────────────────────────────────────────────────────────────"
echo "  Step complete"
echo ""
echo "  Files changed: ${STEP_FILES_CHANGED}"
echo "  Step type:     ${STEP_TYPE}"
echo "  Git commit:    ${COMMIT_HASH:-none}"
echo "  Description:   ${STEP_DESCRIPTION}"
echo "────────────────────────────────────────────────────────────────────────"
echo ""
```

## Section 5: Visual Re-export Modification (visual mode only)

For `--visual` modifications, compare the new design export against the current theme to identify what changed, then apply only the delta. Content is always preserved - no MySQL container needed unless plugin re-evaluation triggers install/uninstall.

```
Visual re-export modification is a multi-step process:

1. EXTRACT TOKENS from the new design export
   - Use the same Python CSS parser pattern as build-visual Section 2a
   - Scan all CSS files in VISUAL_PATH for colors (#hex), font-families, font-sizes
   - Produce a set of new design tokens

2. READ CURRENT theme.json to get existing palette and typography values
   - Load $BUILD_DIR/wp-content/themes/$THEME_SLUG/theme.json
   - Extract current palette entries and typography settings

3. COMPUTE TOKEN DELTA
   - Compare new extracted colors/fonts against current theme.json values
   - Identify which tokens changed and which are unchanged
   - Check build.json modifications array for prior theme-token NL modifications
   - WARN if any NL-modified tokens will be overwritten by the visual re-export
     (Visual re-export wins - but log warning in the modification entry)

4. APPLY CHANGED TOKENS surgically
   - Same Section 3a read-modify-write Python pattern
   - Only update tokens that actually changed - preserve unchanged values
   - Validate JSON after each edit

5. TEMPLATE DIFF
   - the coding agent compares new HTML structure from VISUAL_PATH against current template files
   - For each template with structural changes, the coding agent rewrites that template's block markup
   - Templates with no structural changes are left untouched
   - This is an AI judgment step - the coding agent interprets design intent

6. CONTENT PRESERVATION
   - Existing database.sql is untouched during visual-only modifications
   - No MySQL container needed unless plugin re-evaluation triggers install/uninstall
   - pages_created, posts_created, menu_assigned from build.json remain unchanged

7. SMART PLUGIN RE-EVALUATION (optional - the coding agent judgment)
   - If visual re-export changes theme structure significantly (e.g. added gallery section)
   - the coding agent suggests plugin additions/removals based on new layout
   - If plugin changes are needed, call ensure_docker_mysql() and follow Section 3d pattern

8. FINALIZATION
   - Run Section 4 for the visual re-export as a single atomic step
   - Git commit: build(modify): "visual re-export from {VISUAL_PATH}"
   - build.json entry with type "visual-reexport"
```

### Visual Re-export Token Diff Pattern

```python
# Visual re-export token diff (Section 5, step 3)
import json, re, glob, os

NEW_VISUAL_PATH = os.environ.get("VISUAL_PATH", "")
BUILD_DIR = os.environ.get("BUILD_DIR", "")
THEME_SLUG = os.environ.get("THEME_SLUG", "")

# Extract new tokens from updated design export
new_css_files = glob.glob(os.path.join(NEW_VISUAL_PATH, "**/*.css"), recursive=True)
new_colors = set()
for css_file in new_css_files:
    with open(css_file, "r", errors="ignore") as f:
        css = f.read()
    new_colors.update(re.findall(r"#[0-9a-fA-F]{6}\b", css, re.IGNORECASE))
    new_colors.update(re.findall(r"#[0-9a-fA-F]{3}\b", css, re.IGNORECASE))

# Read existing theme tokens
theme_json_path = os.path.join(BUILD_DIR, "wp-content", "themes", THEME_SLUG, "theme.json")
with open(theme_json_path) as f:
    current_theme = json.load(f)

current_palette = {
    e["slug"]: e["color"]
    for e in current_theme.get("settings", {}).get("color", {}).get("palette", [])
}

# Read modifications array to detect NL-modified tokens
build_json_path = os.path.join(BUILD_DIR, "build.json")
with open(build_json_path) as f:
    state = json.load(f)

nl_modified_tokens = set()
for mod in state.get("modifications", []):
    if mod.get("type") == "theme-token":
        # Extract the token slug from the description or after dict
        after = mod.get("after", {})
        for key in after:
            nl_modified_tokens.add(key)

# Report delta and NL override warnings
new_top_colors = list(new_colors)[:10]
print(f"[Modify] Token delta: {len(new_top_colors)} colors extracted from updated export")
print(f"[Modify] Current palette: {current_palette}")
if nl_modified_tokens:
    print(f"[Modify] WARNING: Prior NL modifications found for tokens: {nl_modified_tokens}")
    print(f"[Modify] Visual re-export will overwrite NL-modified values (visual wins).")

# the coding agent evaluates which tokens need updating based on this delta
```

## Section 7: Session Completion

Invoked by COMMAND.md when the user signals "done". Handles SETUP.md regeneration, versioned output directory creation, zip packaging, and full session summary.

```bash
# ── 7a: Regenerate SETUP.md ─────────────────────────────────────────────────

# Full regeneration (not incremental) reflecting final state.
# Read current build.json for theme, plugins, content, modification history.
# the coding agent generates the complete SETUP.md with all sections:
#
# 1. Setup Guide header
# 2. What's Installed (theme, plugins, pages/posts)
# 3. Critical / Important / Optional priority tiers
# 4. Plugin configuration instructions (the coding agent-authored from AI knowledge)
# 5. Content replacement guidance
# 6. Modification History section - list all versions and what changed
#
# The SETUP.md is written to $BUILD_DIR/SETUP.md.
# For URL clone builds, append the URL clone appendix (dynamic features, copyright notice).

echo "[Modify] Regenerating SETUP.md..."

# the coding agent writes the full SETUP.md using current state context.
# This is a the coding agent in-context task - not a template.

echo "[Modify] SETUP.md regenerated."

git_commit_stage "build(modify): regenerate SETUP.md for session completion"

# ── 7b: Compute versioned output directory ──────────────────────────────────

# Pattern: {wp-dir}-v{N}/ where N is computed from existing sibling directories
PARENT_DIR=$(dirname "$BUILD_DIR")
BASENAME=$(basename "$BUILD_DIR")

# Scan for existing versioned directories
NEXT_N=$(python3 << PYEOF
import os, re, sys

parent_dir = "$PARENT_DIR"
basename = "$BASENAME"

# Find existing {basename}-v{N} directories
pattern = re.compile(rf'^{re.escape(basename)}-v(\d+)$')
max_version = 0

if os.path.isdir(parent_dir):
    for entry in os.listdir(parent_dir):
        match = pattern.match(entry)
        if match:
            version = int(match.group(1))
            if version > max_version:
                max_version = version

print(max_version + 1)
PYEOF
)

VERSIONED_DIR="$PARENT_DIR/${BASENAME}-v${NEXT_N}"

echo "[Modify] Versioned output: $VERSIONED_DIR"

# ── 7c: Copy to versioned output ────────────────────────────────────────────
# Copy, not move - original stays for future sessions

if cp -a "$BUILD_DIR" "$VERSIONED_DIR"; then
  echo "[Modify] Copied to versioned directory."
else
  echo "[Modify] ERROR: Failed to copy to versioned directory."
  echo "[Modify] Session modifications are preserved in the original directory via git."
fi

# ── 7d: Zip the versioned copy ──────────────────────────────────────────────

VERSIONED_ZIP="${VERSIONED_DIR}.zip"

if [ -d "$VERSIONED_DIR" ]; then
  echo "[Modify] Packaging zip..."

  # Build the zip inclusion list
  ZIP_INCLUDES="wp-content/ database.sql README.md SETUP.md build.json .git/ .gitignore"

  # Include scrape.json only for URL clone builds
  if [ "$CREATION_MODE" = "url" ] && [ -f "$VERSIONED_DIR/scrape.json" ]; then
    ZIP_INCLUDES="$ZIP_INCLUDES scrape.json"
  fi

  (
    cd "$VERSIONED_DIR" && \
    zip -r "$VERSIONED_ZIP" $ZIP_INCLUDES
  )

  ZIP_EXIT=$?
  if [ $ZIP_EXIT -ne 0 ]; then
    echo "[Modify] WARNING: Zip packaging failed (exit code: $ZIP_EXIT)."
  else
    echo "[Modify] Zip: $VERSIONED_ZIP"
  fi
fi

# ── 7e: Print full session summary ──────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "  Session complete"
echo ""

# List all modifications from this session
python3 << PYEOF
import json, os

build_json_path = os.path.join("$BUILD_DIR", "build.json")
try:
    with open(build_json_path) as f:
        state = json.load(f)
except Exception:
    state = {}

mods = state.get("modifications", [])
if mods:
    print(f"  {len(mods)} modification(s) applied:")
    print()
    for i, mod in enumerate(mods, 1):
        step_type = mod.get("type", "unknown")
        desc = mod.get("description", mod.get("request", ""))
        print(f"  {i}. [{step_type}] {desc}")
    print()
PYEOF

# Git log
if [ "${GIT_INITIALIZED:-true}" = "true" ]; then
  echo "  Git history:"
  git -C "$BUILD_DIR" log --oneline 2>/dev/null | sed 's/^/    /'
  echo ""
fi

echo "  Output:"
echo "    Versioned directory: $VERSIONED_DIR"
if [ -f "$VERSIONED_ZIP" ]; then
  echo "    Zip: $VERSIONED_ZIP"
fi
echo "    Original preserved: $BUILD_DIR"
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
```

---

## Implementation Notes

- **COMMAND.md owns the session loop, SKILL.md owns per-step execution** - the conversation lives in the command, execution logic lives in the skill.
- **NL modifications are surgical** - the coding agent reads specific files and writes minimal changes. No full theme regeneration.
- **Visual re-exports are diff-aware** - only changed tokens/templates are updated, preserving prior NL modifications unless explicitly overridden.
- **Docker/MySQL uses lazy startup** - `ensure_docker_mysql()` is called only when a content or plugin step is detected. Theme-only sessions (theme-token, template-edit) work without Docker entirely.
- **MySQL container lifecycle** - for compound requests with multiple content steps, keep the container running across all content steps. Single EXIT trap covers the full session. Spin down on exit.
- **Error recovery** - warn-and-continue at the step level. Completed steps are preserved (git commits exist). Failed steps are reported. The user can retry the failed step in the next prompt.
- **Pre-Phase 13 builds and external directories** - if no `.git/` directory exists, initialize git and create an initial commit before applying modifications.
- **Pre-Phase 16 builds** - `state.get('modifications', [])` defaults to empty list. The array is created fresh on first modification.
- **External WordPress directories** - directories not created by /build will not have build.json. Section 1 creates a minimal build.json on first /modify invocation to enable modification tracking.
- **wp-config.php credentials** - read existing credentials from wp-config.php and create the MySQL container with matching values. No wp-config.php editing needed.
- **Both modification modes work on ANY WordPress directory** - /build output, Local WP sites, manual installs, or any other source can be modified via NL or visual re-export.
- **Versioned output preserves the original** - `cp -a` copies to `{wp-dir}-v{N}/`, original directory stays intact for future sessions.
