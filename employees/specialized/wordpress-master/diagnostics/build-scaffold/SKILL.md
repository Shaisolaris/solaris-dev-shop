---
name: build-scaffold
description: Scaffold a blank WordPress installation with Docker MySQL, WP-CLI, SQL export, zip packaging, and build.json manifest
requires: [docker, wp-cli]
---

# Build Scaffold Skill

Complete blank WordPress installation pipeline. Spins up an ephemeral Docker MySQL container, uses WP-CLI to download and install WordPress, exports the database, packages everything as a Local WP importable zip, and writes a build.json manifest.

This skill expects the following variables to be set by the calling command before invocation:

- `MODE` - build mode (e.g. "blank")
- `SLUG` - directory name slug (e.g. "blank-site")
- `WP_VERSION` - WordPress version to install (default: "latest")
- `SITE_TITLE` - Site title string (default: "Blank WordPress Site")

## Section 1: Prerequisite Checks

Check that Docker and WP-CLI are available before proceeding.

```bash
# Check Docker is running
if ! docker info > /dev/null 2>&1; then
  echo ""
  echo "ERROR: Docker is required for /build. Start Docker Desktop and try again."
  echo ""
  exit 1
fi

# Check for local WP-CLI first (preferred)
if which wp > /dev/null 2>&1; then
  WP_CLI_MODE="local"
  echo "[Build] Prerequisites OK - Docker ✓, WP-CLI ✓ (local)"
else
  # Fall back to Docker-based WP-CLI
  echo "[Build] Local WP-CLI not found. Checking Docker WP-CLI fallback..."
  if docker run --rm wordpress:cli wp --version > /dev/null 2>&1; then
    WP_CLI_MODE="docker"
    echo "[Build] Prerequisites OK - Docker ✓, WP-CLI ✓ (docker)"
  else
    echo ""
    echo "ERROR: WP-CLI is required for /build but was not found."
    echo ""
    echo "Install WP-CLI:"
    echo "  curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar"
    echo "  chmod +x wp-cli.phar"
    echo "  sudo mv wp-cli.phar /usr/local/bin/wp"
    echo ""
    echo "Full instructions: https://wp-cli.org"
    echo ""
    exit 1
  fi
fi
```

## Section 2: Build Directory Setup

Create a timestamped build directory in the user's current working directory.

```bash
# Input variables (set by calling command)
# MODE, SLUG, WP_VERSION, SITE_TITLE

# Apply defaults
WP_VERSION="${WP_VERSION:-latest}"
SITE_TITLE="${SITE_TITLE:-Blank WordPress Site}"
SLUG="${SLUG:-blank-site}"
MODE="${MODE:-blank}"

# Generate datestamp and directory name
DATESTAMP=$(date +%Y-%m-%d)
BUILD_DIR_NAME="${DATESTAMP}-${SLUG}"
BUILD_DIR="${PWD}/${BUILD_DIR_NAME}"

# Collision check - append random suffix if directory already exists
if [ -d "$BUILD_DIR" ]; then
  SUFFIX=$(openssl rand -hex 2)
  BUILD_DIR_NAME="${BUILD_DIR_NAME}-${SUFFIX}"
  BUILD_DIR="${PWD}/${BUILD_DIR_NAME}"
fi

# Create the directory
mkdir -p "$BUILD_DIR"

echo "[Build] Directory: $BUILD_DIR"
```

## Section 3: Ephemeral Docker MySQL

Spin up a temporary MySQL 8.0 container on port 3307. Set an EXIT trap so the container is always cleaned up, even if the build fails.

```bash
# Container name using PID for uniqueness
MYSQL_CONTAINER="wpbuild-mysql-$$"

# Generate random passwords (never hardcoded)
MYSQL_ROOT_PASS="wpbuild_root_$(openssl rand -hex 8)"
MYSQL_PASS="$(openssl rand -hex 12)"

# Pre-flight: check port 3307 is free
if lsof -i :3307 > /dev/null 2>&1; then
  echo ""
  echo "ERROR: Port 3307 is already in use."
  echo "Close the conflicting process (check with: lsof -i :3307) and try again."
  echo ""
  exit 1
fi

# Cleanup trap - runs on EXIT (normal or error)
cleanup_mysql() {
  echo "[Build] Cleaning up Docker container..."
  docker rm -f "$MYSQL_CONTAINER" 2>/dev/null || true
  echo "[Build] Cleanup complete."
}
trap cleanup_mysql EXIT

# Start MySQL container
docker run -d \
  --name "$MYSQL_CONTAINER" \
  -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASS" \
  -e MYSQL_DATABASE=wordpress \
  -e MYSQL_USER=wp \
  -e MYSQL_PASSWORD="$MYSQL_PASS" \
  -p 127.0.0.1:3307:3306 \
  mysql:8.0 \
  --default-authentication-plugin=mysql_native_password \
  > /dev/null

echo "[Build] Starting MySQL container..."

# Wait for MySQL to be ready (up to 30 seconds)
WAIT_COUNT=0
until docker exec "$MYSQL_CONTAINER" mysqladmin ping --silent 2>/dev/null; do
  WAIT_COUNT=$((WAIT_COUNT + 1))
  if [ "$WAIT_COUNT" -ge 30 ]; then
    echo ""
    echo "ERROR: MySQL container failed to start within 30 seconds."
    echo ""
    exit 1
  fi
  sleep 1
done

echo "[Build] Database ready."
```

## Section 4: WP-CLI Build Pipeline

Download WordPress core, configure it, run the install, and export the database. All steps check for errors and abort with a clear message on failure.

```bash
# Set WP command based on WP_CLI_MODE
if [ "$WP_CLI_MODE" = "local" ]; then
  WP="wp --path=$BUILD_DIR"
else
  # Docker WP-CLI - mount build directory as WordPress root
  WP="docker run --rm -v \"$BUILD_DIR:/var/www/html\" --network host wordpress:cli wp --allow-root"
fi

# Step 1: Download WordPress core
echo "[Build] Downloading WordPress core..."
if ! $WP core download --version="$WP_VERSION" 2>&1; then
  echo ""
  echo "ERROR: WordPress core download failed. Check your internet connection."
  echo ""
  exit 1
fi

# Step 2: Create wp-config.php
echo "[Build] Configuring WordPress..."
if ! $WP config create \
  --dbname=wordpress \
  --dbuser=wp \
  --dbpass="$MYSQL_PASS" \
  --dbhost=127.0.0.1:3307 \
  --skip-check \
  --extra-php='
define( "WP_DEBUG", true );
define( "WP_DEBUG_LOG", true );
define( "WP_DEBUG_DISPLAY", false );
' 2>&1; then
  echo ""
  echo "ERROR: wp-config.php creation failed."
  echo ""
  exit 1
fi

# Step 3: Run WordPress install
echo "[Build] Installing WordPress..."
# Generate random admin password (displayed in terminal, never stored)
ADMIN_PASS="$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)"

if ! $WP core install \
  --url=http://localhost \
  --title="$SITE_TITLE" \
  --admin_user=admin \
  --admin_password="$ADMIN_PASS" \
  --admin_email=admin@example.local \
  --skip-email 2>&1; then
  echo ""
  echo "ERROR: WordPress install failed. Check the MySQL container is running."
  echo ""
  exit 1
fi

# Step 4: Export database
echo "[Build] Exporting database..."
if ! $WP db export "$BUILD_DIR/database.sql" --add-drop-table 2>&1; then
  echo ""
  echo "ERROR: Database export failed."
  echo ""
  exit 1
fi
```

## Section 5: Zip Packaging (Local WP Compatible)

Package wp-content/ and database.sql into a zip file at the Local WP importable format. CRITICAL: cd into BUILD_DIR before zipping to avoid nested path prefixes in the archive.

```bash
# Compute absolute zip path BEFORE changing directory
ZIP_PATH="$(dirname "$BUILD_DIR")/${BUILD_DIR_NAME}.zip"

echo "[Build] Packaging for Local WP..."

# cd into build dir so zip uses relative paths (wp-content/ and database.sql at root)
# NOTE: This is the BASE zip command. COMMAND.md pipelines MUST extend this to include
# additional files generated by later skills: README.md, SETUP.md, .git/, .gitignore,
# and scrape.json (URL builds). The COMMAND.md zip step is the canonical command.
(
  cd "$BUILD_DIR" && \
  zip -r "$ZIP_PATH" wp-content/ database.sql \
    $([ -f README.md ] && echo "README.md") \
    $([ -f SETUP.md ] && echo "SETUP.md") \
    $([ -d .git ] && echo ".git/") \
    $([ -f .gitignore ] && echo ".gitignore") \
    $([ -f scrape.json ] && echo "scrape.json") \
    $([ -f build.json ] && echo "build.json")
)

ZIP_EXIT=$?
if [ $ZIP_EXIT -ne 0 ]; then
  echo ""
  echo "ERROR: Zip packaging failed (exit code: $ZIP_EXIT)."
  echo ""
  exit 1
fi

# Verify zip structure (should show wp-content/ and database.sql at root)
echo "[Build] Verifying zip structure..."
unzip -l "$ZIP_PATH" | head -10

echo "[Build] Zip created: $ZIP_PATH"
```

## Section 6: Build Manifest (build.json)

Write a build.json manifest to the build directory. Admin password is NOT included - displayed in terminal only.

```bash
# Generate build ID
BUILD_ID="build-$(date +%Y%m%d%H%M%S)-$(openssl rand -hex 4)"

# Get actual WP version installed
WP_VERSION_ACTUAL=$($WP core version 2>/dev/null || echo "$WP_VERSION")

# Write build.json
cat > "$BUILD_DIR/build.json" << MANIFEST
{
  "build_id": "${BUILD_ID}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "mode": "${MODE}",
  "wp_version": "${WP_VERSION_ACTUAL}",
  "build_dir": "${BUILD_DIR}",
  "zip_path": "${ZIP_PATH}",
  "site_url": "http://localhost",
  "admin_user": "admin"
}
MANIFEST

echo "[Build] Manifest written: $BUILD_DIR/build.json"
```

## Section 7: Build Summary Output

Display a formatted build summary. Admin password is displayed here and nowhere else - it is not stored in any file.

```bash
echo ""
echo "Build complete!"
echo ""
echo "  Build ID:       $BUILD_ID"
echo "  Mode:           $MODE"
echo "  WP Version:     $WP_VERSION_ACTUAL"
echo "  Build Dir:      $BUILD_DIR"
echo "  Zip File:       $ZIP_PATH"
echo ""
echo "  Admin URL:      http://localhost/wp-admin"
echo "  Admin User:     admin"
echo "  Admin Password: $ADMIN_PASS"
echo ""
echo "Import $ZIP_PATH into Local WP to get started."
echo ""
```

## Section 8: Cleanup

The EXIT trap set in Section 3 handles Docker container cleanup automatically on script exit (both normal and error paths). No additional cleanup is needed here.

```bash
# Cleanup is handled automatically by the EXIT trap (cleanup_mysql function)
# set in Section 3. The trap fires when the script exits for any reason:
#   - Normal completion
#   - Error exit
#   - User interrupt (Ctrl+C)

# No manual cleanup required here.
# The [Build] Cleanup complete. message is printed by cleanup_mysql.
```

## Implementation Notes

- All progress messages use the `[Build]` prefix for consistent output parsing
- Each WP-CLI step checks the exit code and aborts with a clear error message on failure
- Admin password is generated with `openssl rand` - never hardcoded, never stored in files
- Docker container name includes the shell PID (`$$`) to prevent naming conflicts when running multiple builds simultaneously
- Port 3307 is used for Docker MySQL to avoid conflicts with a locally running MySQL on port 3306
- The `--allow-root` flag is automatically included when using Docker WP-CLI (runs as root inside the container)
- Zip packaging uses a subshell `(cd "$BUILD_DIR" && zip ...)` to preserve cwd for the parent process
- build.json records all metadata EXCEPT admin password - admin password is terminal-only
