---
name: build-mcp
description: Install, activate, and configure the WordPress MCP adapter in a build - copy from vendor/, activate via WP-CLI, re-export the database, write README.md, and update build.json
requires: [wp-cli, docker-mysql-running]
runs-after: [build-scaffold Section 4]
runs-before: [zip-packaging]
---

# Build MCP Skill

Installs the WordPress MCP adapter (pre-compiled, bundled at `vendor/mcp-adapter/`) into the build's `wp-content/plugins/` directory, activates it via WP-CLI so activation is captured in the SQL export, writes a `README.md` with STDIO transport configuration, and updates `build.json` with MCP adapter metadata.

**Critical sequencing:** This skill runs AFTER `build-scaffold` Section 4 (WP-CLI pipeline including first `wp db export`) and BEFORE zip packaging. The Docker MySQL container from `build-scaffold` must still be running when this skill executes - the EXIT trap set in `build-scaffold` Section 3 must remain active for the duration of this skill.

This skill expects the following variables to already be set by the calling command:

- `BUILD_DIR` - absolute path to the build directory (set by build-scaffold Section 2)
- `WP` - the WP-CLI command prefix (e.g. `wp --path=$BUILD_DIR` or the Docker equivalent, set by build-scaffold Section 4)
- `PLUGIN_DIR` - absolute path to the CoWork plugin directory (set by COMMAND.md before invoking this skill)

## Section 1: MCP Adapter Copy

Copy the pre-compiled MCP adapter from the CoWork plugin's `vendor/mcp-adapter/` directory into the build's WordPress plugins directory.

```bash
MCP_ADAPTER_SOURCE="${PLUGIN_DIR}/vendor/mcp-adapter"
MCP_ADAPTER_DEST="${BUILD_DIR}/wp-content/plugins/mcp-adapter"

echo "[Build] Installing MCP adapter..."

if [ ! -d "$MCP_ADAPTER_SOURCE" ]; then
  echo "[Build] WARNING: MCP adapter not found at $MCP_ADAPTER_SOURCE"
  echo "[Build] WARNING: Skipping MCP adapter installation. Install manually after import."
  echo "[Build] WARNING: See README.md for manual setup instructions."
  MCP_ADAPTER_INCLUDED=false
  MCP_ADAPTER_ACTIVE=false
else
  mkdir -p "$MCP_ADAPTER_DEST"
  cp -r "$MCP_ADAPTER_SOURCE/." "$MCP_ADAPTER_DEST/"
  # Remove dev artifacts and git files not needed in the build
  rm -rf "$MCP_ADAPTER_DEST/.git" \
         "$MCP_ADAPTER_DEST/.github" \
         "$MCP_ADAPTER_DEST/tests" \
         "$MCP_ADAPTER_DEST/.gitignore" \
         "$MCP_ADAPTER_DEST/phpunit.xml.dist" \
         "$MCP_ADAPTER_DEST/phpcs.xml.dist" \
         "$MCP_ADAPTER_DEST/phpstan.neon.dist" \
         "$MCP_ADAPTER_DEST/composer.json" \
         "$MCP_ADAPTER_DEST/composer.lock" \
         "$MCP_ADAPTER_DEST/package.json" \
         "$MCP_ADAPTER_DEST/package-lock.json" \
         "$MCP_ADAPTER_DEST/CONTRIBUTING.md" \
         "$MCP_ADAPTER_DEST/README-INITIAL.md"
  echo "[Build] MCP adapter copied to wp-content/plugins/mcp-adapter/"
  MCP_ADAPTER_INCLUDED=true
fi
```

## Section 2: Plugin Activation and Database Re-export

Activate the MCP adapter plugin via WP-CLI so the activation state is captured in the database. Then re-export the database to overwrite the initial export from build-scaffold. This re-export is intentional and documented - it ensures the zip contains a database with the adapter already active.

**Critical:** The Docker MySQL container from build-scaffold Section 3 must still be running. If activation fails with "Error establishing a database connection", check that the container is still alive.

```bash
if [ "$MCP_ADAPTER_INCLUDED" = "true" ]; then
  echo "[Build] Activating MCP adapter..."

  if ! $WP plugin activate mcp-adapter 2>&1; then
    echo "[Build] WARNING: MCP adapter activation failed."
    echo "[Build] WARNING: The plugin is installed but not active."
    echo "[Build] WARNING: Activate it manually in WP Admin after import."
    MCP_ADAPTER_ACTIVE=false
  else
    echo "[Build] MCP adapter activated."
    MCP_ADAPTER_ACTIVE=true

    # Re-export the database to capture activation state in the SQL dump
    # This overwrites the initial export from build-scaffold - intentional
    echo "[Build] Re-exporting database with adapter active..."
    if ! $WP db export "$BUILD_DIR/database.sql" --add-drop-table 2>&1; then
      echo "[Build] WARNING: Database re-export failed. Using initial export (adapter may not be active in imported DB)."
      MCP_ADAPTER_ACTIVE=false
    else
      echo "[Build] Database re-exported. Activation state captured in SQL dump."
    fi
  fi
fi
```

## Section 3: README.md Generation

Write a `README.md` to the build directory containing Local WP import instructions, the copy-pasteable `.mcp.json` STDIO transport configuration, and admin credential notes.

```bash
# Read adapter version from version file if available
MCP_ADAPTER_VERSION="unknown"
if [ -f "${PLUGIN_DIR}/vendor/mcp-adapter-version.txt" ]; then
  MCP_ADAPTER_VERSION=$(cat "${PLUGIN_DIR}/vendor/mcp-adapter-version.txt")
fi

echo "[Build] Writing README.md..."

cat > "$BUILD_DIR/README.md" << 'README_EOF'
# WordPress Build - Local WP Import Guide

## Import into Local WP

1. Open Local WP
2. Click the "+" button (Add Local Site) → **Import existing site**
3. Select the `.zip` file from this build directory
4. Follow the import wizard (accept defaults for site name and environment)
5. Click **Import site** and wait for the import to complete

## Connect Claude (MCP Adapter)

This build includes the WordPress MCP adapter, pre-installed and activated.
After importing into Local WP, connect Claude with this configuration:

**Save as `.mcp.json` in your project directory or Claude's config location:**

```json
{
  "mcpServers": {
    "wordpress": {
      "command": "/path/to/local-wp/wpcli",
      "args": [
        "--path=/path/to/local-wp-site/app/public",
        "mcp-adapter",
        "serve",
        "--server=mcp-adapter-default-server",
        "--user=admin"
      ]
    }
  }
}
```

**To find your paths after import:**

- **WP-CLI path:** In Local WP, right-click your site → **Open Site Shell** → run `which wp`
  - This is Local WP's bundled WP-CLI binary - use this path, not `/usr/local/bin/wp`
- **Site path:** In Local WP, right-click your site → **Reveal in Finder** → navigate to `app/public`
  - Typically: `~/Local Sites/{site-name}/app/public`

**Note:** The MCP adapter requires WordPress 6.9 or later for full MCP functionality.
On earlier WordPress versions, the plugin loads without errors but MCP features are unavailable.

## Admin Credentials

- **WP Admin URL:** Use the site URL shown in Local WP after import (e.g. `http://sitename.local/wp-admin`)
- **Username:** `admin`
- **Password:** Shown in terminal at build time - not stored in any file

## About the MCP Adapter

README_EOF

# Append version-specific content (can't use single-quote heredoc with variables)
cat >> "$BUILD_DIR/README.md" << README_VERSION
- **Adapter version:** v${MCP_ADAPTER_VERSION}
- **Source:** [WordPress/mcp-adapter](https://github.com/WordPress/mcp-adapter)
- **Transport:** STDIO via WP-CLI (no web server required)
README_VERSION

echo "[Build] README.md written."
```

## Section 4: Build Manifest Update

Update `build.json` to include MCP adapter metadata. The manifest was initially written by `build-scaffold` Section 6. This section reads it and rewrites it with the `mcp_adapter` object added. Uses Python for reliable JSON handling if available; falls back to a full rewrite using known variables.

```bash
echo "[Build] Updating build manifest with MCP adapter fields..."

if [ -f "$BUILD_DIR/build.json" ] && command -v python3 > /dev/null 2>&1; then
  # Python available - parse and update existing JSON cleanly
  python3 - "$BUILD_DIR/build.json" "$MCP_ADAPTER_INCLUDED" "$MCP_ADAPTER_ACTIVE" "$MCP_ADAPTER_VERSION" << 'PYEOF'
import sys, json

build_json_path = sys.argv[1]
included_str = sys.argv[2]
active_str = sys.argv[3]
version = sys.argv[4]

with open(build_json_path, 'r') as f:
    data = json.load(f)

data['mcp_adapter'] = {
    'included': included_str == 'true',
    'activated': active_str == 'true',
    'version': version
}

with open(build_json_path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
PYEOF
  echo "[Build] Build manifest updated."
else
  echo "[Build] WARNING: Could not update build.json (python3 not available or build.json missing)."
  echo "[Build] WARNING: MCP adapter fields omitted from manifest."
fi
```

## Section 5: Build Summary Extension

Print the MCP adapter status lines as an extension to the build summary output from `build-scaffold` Section 7. These lines appear after the build-scaffold summary block.

```bash
# Read version for display
MCP_DISPLAY_VERSION="${MCP_ADAPTER_VERSION:-unknown}"

echo ""
if [ "$MCP_ADAPTER_INCLUDED" = "true" ] && [ "$MCP_ADAPTER_ACTIVE" = "true" ]; then
  echo "  MCP Adapter:    installed (v${MCP_DISPLAY_VERSION}) | active"
  echo "  MCP Setup:      see README.md in build directory"
elif [ "$MCP_ADAPTER_INCLUDED" = "true" ] && [ "$MCP_ADAPTER_ACTIVE" = "false" ]; then
  echo "  MCP Adapter:    installed (v${MCP_DISPLAY_VERSION}) | NOT active (activate in WP Admin)"
  echo "  MCP Setup:      see README.md in build directory"
else
  echo "  MCP Adapter:    not installed (see README.md for manual setup)"
fi
echo ""
```

## Implementation Notes

**Docker container lifetime:** This skill must run while the Docker MySQL container from `build-scaffold` Section 3 is still alive. The `wp plugin activate mcp-adapter` command writes to the WordPress database, which requires MySQL. The EXIT trap registered in `build-scaffold` fires when the entire command session ends - not between individual skill invocations - because Claude executes all skill steps in one continuous session. If you see "Error establishing a database connection" during activation, the container has stopped prematurely.

**PLUGIN_DIR resolution:** The calling COMMAND.md must set `PLUGIN_DIR` to the absolute path of the CoWork plugin directory before invoking this skill. This is the directory containing `CLAUDE.md`, `skills/`, `commands/`, and `vendor/`. Claude can resolve this from the known location of the COMMAND.md file it is executing.

**Warn-and-continue pattern:** No `exit 1` is used for MCP adapter failures. Build completion is more important than adapter installation. Failures produce warnings that explain the situation and point the user to README.md for manual setup. Only hard build failures (Docker, WP core download, WP install) should abort the build.

**Database re-export:** The re-export in Section 2 intentionally overwrites `database.sql`. The zip packaging step (which runs after this skill) uses the re-exported file. If this skill fails before completing the re-export, the initial export from build-scaffold remains. The adapter will appear installed (files are present) but inactive in the imported database.

**Adapter vendor/ structure:** The mcp-adapter plugin v0.4.1 has zero Composer production dependencies - the `vendor/` directory inside the adapter contains only the Composer autoloader. This is intentional: the wordpress/abilities-api dependency is either bundled within the plugin's `includes/` directory or not required at runtime on WP 6.9+ where it is built into core.

**WP version note:** The MCP adapter requires WordPress 6.9+ for full MCP functionality via the Abilities API. On WP < 6.9, the plugin activates and loads without errors but MCP features are unavailable. The README documents this requirement.

**Version file:** The pinned version string is read from `$PLUGIN_DIR/vendor/mcp-adapter-version.txt`. Update this file when upgrading to a new adapter version. If the file is missing, the version is reported as "unknown" in README.md and build.json.
