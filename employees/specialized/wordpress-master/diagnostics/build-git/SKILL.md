---
name: build-git
description: Initialize git repository at build root, generate dynamic .gitignore excluding WP core and known components, commit after each build stage with conventional prefixes
requires: [git]
runs-after: [build-scaffold Section 2]
---

# Build Git Skill

Initializes a git repository at the build root directory, writes a two-phase `.gitignore` that excludes WordPress core and known reinstallable components while tracking custom-generated content, and provides a commit helper for staged commits after each build skill stage.

This skill runs at multiple points throughout the build pipeline - not as a single step. Git init happens early (after directory setup), `.gitignore` Phase 1 is written before any commits, `.gitignore` Phase 2 is appended after build-content, and commits happen after each skill stage.

This skill expects the following variables to be set by the calling command before invocation:

- `BUILD_DIR` - absolute path to the build directory (set by build-scaffold Section 2)
- `THEME_SLUG` - theme directory slug (required for Section 3, set by build-theme)
- `INSTALLED_PLUGINS` - array of `slug:name:version` entries (required for Section 3, set by build-content)
- `MCP_ADAPTER_VERSION` - MCP adapter version string (required for Section 5 commit messages, set by build-mcp)
- `THEME_NAME` - display name of installed theme (required for Section 5 commit messages, set by build-theme)
- `SLUG` - build slug used as the build(init) commit subject (set in Section 1 of COMMAND.md)
- `PAGES_CREATED` - count of pages created (required for Section 5 commit body, set by build-content)
- `POSTS_CREATED` - count of posts created (required for Section 5 commit body, set by build-content)

## Section 1: Git Initialization and User Config

Initialize a git repository at the build root and configure a fallback git identity if none is globally set.

Runs ONCE, after build-scaffold Section 2 (directory setup), BEFORE WP core download.

```bash
echo "[Build] Initializing git repository at $BUILD_DIR..."
echo ""

# Initialize git at build root with main as default branch
if git -C "$BUILD_DIR" init -b main > /dev/null 2>&1; then
  echo "[Build] Git initialized at $BUILD_DIR (branch: main)"
else
  echo "[Build] WARNING: git init failed at $BUILD_DIR. Git versioning will be skipped."
  echo "[Build] WARNING: Build will continue without git history."
  GIT_INITIALIZED=false
fi

# Check for existing git user config - set project-level fallback if missing
if [ "${GIT_INITIALIZED:-true}" = "true" ]; then
  GIT_USER_NAME=$(git config --global user.name 2>/dev/null || echo "")
  GIT_USER_EMAIL=$(git config --global user.email 2>/dev/null || echo "")

  if [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
    git -C "$BUILD_DIR" config user.name "CoWork Build"
    git -C "$BUILD_DIR" config user.email "build@cowork.local"
    echo "[Build] NOTE: No global git user config found. Using project-level fallback: CoWork Build <build@cowork.local>"
    echo "[Build] NOTE: Run 'git config --global user.name \"Your Name\"' to set your own identity."
  else
    echo "[Build] Git user: $GIT_USER_NAME <$GIT_USER_EMAIL>"
  fi

  GIT_INITIALIZED=true
fi

echo ""
```

## Section 2: .gitignore Phase 1 (Static Exclusions)

Write the static `.gitignore` with all known excluded patterns. This covers WordPress core files, ephemeral directories, database exports, the MCP adapter (bundled, reinstallable), and core bundled themes.

Runs immediately after Section 1, BEFORE the first commit.

```bash
echo "[Build] Writing .gitignore Phase 1 (static exclusions)..."

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

echo "[Build] .gitignore Phase 1 written (static exclusions)"
echo ""
```

## Section 3: .gitignore Phase 2 (Dynamic Exclusions)

Append dynamic exclusions based on what was actually installed in this build. Excludes WP.org-sourced themes and plugins by slug, keeping only custom-* prefixed components tracked.

Runs AFTER build-content (Step 6 in NL pipeline), BEFORE the build(init) commit. SKIPPED for blank builds (no theme or plugins beyond defaults).

```bash
echo "[Build] Appending .gitignore Phase 2 (dynamic exclusions)..."

PHASE2_EXCLUSION_COUNT=0

# Exclude WP.org theme - only if THEME_SLUG is set and NOT custom-* prefixed
if [ -n "${THEME_SLUG:-}" ]; then
  if echo "$THEME_SLUG" | grep -qE "^custom-"; then
    echo "[Build] Theme $THEME_SLUG is custom-prefixed - tracking in git (not excluded)"
  else
    echo "wp-content/themes/$THEME_SLUG/" >> "$BUILD_DIR/.gitignore"
    echo "[Build] Excluded WP.org theme: $THEME_SLUG"
  fi
fi

# Exclude each WP.org plugin by slug
# INSTALLED_PLUGINS is an array of "slug:name:version" entries
if [ ${#INSTALLED_PLUGINS[@]} -gt 0 ]; then
  echo "" >> "$BUILD_DIR/.gitignore"
  echo "# ── WP.org-sourced Plugins (reinstallable) ──────────────────────────────────" >> "$BUILD_DIR/.gitignore"
  for ENTRY in "${INSTALLED_PLUGINS[@]}"; do
    PLUGIN_SLUG=$(echo "$ENTRY" | cut -d: -f1)
    if [ -n "$PLUGIN_SLUG" ]; then
      echo "wp-content/plugins/$PLUGIN_SLUG/" >> "$BUILD_DIR/.gitignore"
      PHASE2_EXCLUSION_COUNT=$((PHASE2_EXCLUSION_COUNT + 1))
    fi
  done
fi

echo "[Build] .gitignore Phase 2 appended ($PHASE2_EXCLUSION_COUNT plugin exclusions)"
echo ""
```

## Section 4: Stage Commit Helper

Define the `git_commit_stage` function for use throughout the pipeline. Stages all changes and commits with the provided message. Failures produce warnings but never abort the build.

Define this function once, early in the build session, before the first commit call.

```bash
# git_commit_stage - helper for staged commits throughout the build pipeline
# Usage: git_commit_stage "commit subject" ["commit body"]
# For multiline commits, pass subject and body as separate arguments.
# Failures are warn-and-continue - git failures never abort the build.

git_commit_stage() {
  local SUBJECT="$1"
  local BODY="${2:-}"

  if [ "${GIT_INITIALIZED:-true}" != "true" ]; then
    echo "[Build] WARNING: Git not initialized - skipping commit: $SUBJECT"
    return 0
  fi

  echo "[Build] Git commit: $SUBJECT"

  # Stage all changes
  if ! git -C "$BUILD_DIR" add -A > /dev/null 2>&1; then
    echo "[Build] WARNING: git add failed for commit: $SUBJECT"
    return 0
  fi

  # Check if there is anything to commit
  if git -C "$BUILD_DIR" diff --cached --quiet 2>/dev/null; then
    echo "[Build] NOTE: Nothing to commit for: $SUBJECT (no changes staged)"
    return 0
  fi

  # Commit - use -m twice for multiline commits (subject + body)
  if [ -n "$BODY" ]; then
    if git -C "$BUILD_DIR" commit -m "$SUBJECT" -m "$BODY" > /dev/null 2>&1; then
      echo "[Build] Committed: $SUBJECT"
    else
      echo "[Build] WARNING: git commit failed for: $SUBJECT"
    fi
  else
    if git -C "$BUILD_DIR" commit -m "$SUBJECT" > /dev/null 2>&1; then
      echo "[Build] Committed: $SUBJECT"
    else
      echo "[Build] WARNING: git commit failed for: $SUBJECT"
    fi
  fi

  echo ""
}
```

## Section 5: Commit Messages Reference

Reference for all commit messages used throughout the build pipeline. Messages follow the conventional commit format with `build(scope):` prefixes. Variable interpolation happens at call time using current shell variable values.

### NL Build - 5 Commits

| Order | When | Commit Subject | Notes |
|-------|------|----------------|-------|
| 1 | After build-scaffold Section 4 | `build(scaffold): blank WordPress installation` | No body needed |
| 2 | After build-mcp | `build(mcp): install MCP adapter v${MCP_ADAPTER_VERSION}` | No body needed |
| 3 | After build-theme | `build(theme): install ${THEME_NAME}` | No body needed |
| 4 | After build-content + .gitignore Phase 2 | `build(init): ${SLUG}` | Multiline body - see below |
| 5 | After build-setup | `build(setup): generate SETUP.md and build manifest` | No body needed |

**build(init) commit body format:**

```
Theme: ${THEME_NAME}
Plugins: ${PLUGINS_SUMMARY}
Pages: ${PAGES_CREATED}, Posts: ${POSTS_CREATED}
```

Where `PLUGINS_SUMMARY` is a comma-separated list of installed plugin names (e.g., `Contact Form 7, WooCommerce, Yoast SEO`). Derive this from the INSTALLED_PLUGINS array by extracting the name field (cut -d: -f2) and joining with ", ".

**Example call for build(init) commit:**

```bash
# Build plugins summary from INSTALLED_PLUGINS array
PLUGINS_SUMMARY=""
for ENTRY in "${INSTALLED_PLUGINS[@]}"; do
  PLUGIN_NAME=$(echo "$ENTRY" | cut -d: -f2)
  if [ -n "$PLUGINS_SUMMARY" ]; then
    PLUGINS_SUMMARY="$PLUGINS_SUMMARY, $PLUGIN_NAME"
  else
    PLUGINS_SUMMARY="$PLUGIN_NAME"
  fi
done

INIT_BODY="Theme: ${THEME_NAME}
Plugins: ${PLUGINS_SUMMARY}
Pages: ${PAGES_CREATED}, Posts: ${POSTS_CREATED}"

git_commit_stage "build(init): ${SLUG}" "$INIT_BODY"
```

### Blank Build - 2 Commits

| Order | When | Commit Subject |
|-------|------|----------------|
| 1 | After build-scaffold Section 4 | `build(scaffold): blank WordPress installation` |
| 2 | After build-mcp | `build(mcp): install MCP adapter v${MCP_ADAPTER_VERSION}` |

## Section 6: Modification Commit (Phase 16 Integration Point)

**Called by Phase 16 - not used during initial build.**

Format for `/modify` command commits. These are appended to the existing git history created during the initial build.

**Commit format:**

```
build(modify): {user's natural language request}

Updated {file}: {specific change description}
```

**Example:**

```bash
# Used by Phase 16 build-modify skill - not during initial build
MODIFY_SUBJECT="build(modify): add contact form to the contact page"
MODIFY_BODY="Updated wp-content/themes/custom-portfolio/templates/page-contact.html: Added Contact Form 7 [contact-form-7] shortcode block"

git_commit_stage "$MODIFY_SUBJECT" "$MODIFY_BODY"
```

**Detecting existing git repos (Phase 16 pattern):**

```bash
# Check if git is already initialized in BUILD_DIR before running init
if git -C "$BUILD_DIR" rev-parse --git-dir > /dev/null 2>&1; then
  echo "[Build] Git repo already exists - appending modification commit"
  GIT_INITIALIZED=true
else
  echo "[Build] No git repo found - initializing for modification tracking"
  # Run Section 1 to initialize
fi
```

**Modification commits use the same `git_commit_stage` helper** defined in Section 4. Phase 16 should source or re-declare this function at the start of its skill execution.

## Section 7: Build Manifest Update

Update `build.json` with git metadata after all commits are complete. Runs after the final commit, before zip packaging.

```bash
echo "[Build] Updating build.json with git metadata..."

# Count commits in the repo
if [ "${GIT_INITIALIZED:-true}" = "true" ]; then
  GIT_COMMIT_COUNT=$(git -C "$BUILD_DIR" rev-list --count HEAD 2>/dev/null || echo "0")
else
  GIT_COMMIT_COUNT=0
fi

# Update build.json using Python 3 - same pattern as build-setup Section 2
python3 - << PYEOF
import json, os

build_json_path = os.path.join("${BUILD_DIR}", "build.json")

try:
    with open(build_json_path, "r") as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

data["git"] = {
    "initialized": ${GIT_INITIALIZED:-true},
    "branch": "main",
    "commits": ${GIT_COMMIT_COUNT}
}

with open(build_json_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(f"[Build] build.json updated with git metadata ({${GIT_COMMIT_COUNT}} commits)")
PYEOF

echo ""
```
