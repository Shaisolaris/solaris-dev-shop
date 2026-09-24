# GameCI - Dockerized Unity CI/CD (canonical)

> **Absorbed v0.3.0 (2026-04-25)** from `game-ci/unity-builder` + `game-ci/docker` + `game-ci/unity-actions` + game.ci docs. Talent Scout v2 caught this. Use this for ANY Unity project's CI pipeline. Cross-references unity-developer employee.

## What GameCI is

GameCI = collection of Dockerized Unity Editor images + GitHub Actions + GitLab CI templates for testing and building Unity projects automatically.

- **Docker images:** `unityci/editor:<unity-version>-<target>-<image-version>` - all major Unity versions for all target platforms (iOS, Android, WebGL, StandaloneWindows64, StandaloneOSX, StandaloneLinux64, etc.)
- **GitHub Actions:** Test runner + Builder + Activate license + Return license
- **License-aware:** Handles Unity Personal + Pro + Enterprise license activation in CI

## Canonical workflow - `.github/workflows/main.yml`

```yaml
name: Build Unity project

on:
  pull_request: {}
  push: { branches: [main] }

env:
  UNITY_VERSION: 2022.3.20f1   # match ProjectSettings/ProjectVersion.txt

jobs:
  test:
    name: Test in EditMode + PlayMode
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true                              # Unity projects almost always have LFS

      - uses: actions/cache@v4
        with:
          path: Library
          key: Library-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}
          restore-keys: |
            Library-

      - uses: game-ci/unity-test-runner@v4
        env:
          UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}
        with:
          unityVersion: ${{ env.UNITY_VERSION }}
          githubToken: ${{ secrets.GITHUB_TOKEN }}
          testMode: all                          # editmode + playmode

  build:
    name: Build for ${{ matrix.targetPlatform }}
    runs-on: ubuntu-latest
    needs: test
    strategy:
      fail-fast: false
      matrix:
        targetPlatform:
          - WebGL
          - StandaloneWindows64
          - StandaloneOSX
          - Android
          # iOS is macOS-only - split into separate job

    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }

      - uses: actions/cache@v4
        with:
          path: Library
          key: Library-${{ matrix.targetPlatform }}-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}
          restore-keys: |
            Library-${{ matrix.targetPlatform }}-
            Library-

      - uses: game-ci/unity-builder@v4
        env:
          UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}
          UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}
          UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}
        with:
          unityVersion: ${{ env.UNITY_VERSION }}
          targetPlatform: ${{ matrix.targetPlatform }}
          # Optional - pin a specific docker image:
          # customImage: 'unityci/editor:2022.3.20f1-webgl-3.1.0'

      - uses: actions/upload-artifact@v4
        with:
          name: Build-${{ matrix.targetPlatform }}
          path: build/${{ matrix.targetPlatform }}
```

## iOS (macOS-only) build job

```yaml
  build-ios:
    runs-on: macos-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }
      - uses: game-ci/unity-builder@v4
        env: { UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }} }
        with:
          unityVersion: 2022.3.20f1
          targetPlatform: iOS
      - uses: actions/upload-artifact@v4
        with: { name: Build-iOS, path: build/iOS }
      # Then: archive + sign + notarize via fastlane (separate workflow)
```

## License setup (one-time per Unity license)

For **Personal** licenses:
1. Run the unity-request-activation-file action once locally to generate `Unity_v<version>.alf`
2. Upload that file to https://license.unity3d.com/manual to get `Unity_v<version>.ulf`
3. Paste `Unity_v<version>.ulf` contents into GitHub repo secret `UNITY_LICENSE`
4. CI is now activated

For **Pro / Enterprise** licenses:
- Set `UNITY_EMAIL`, `UNITY_PASSWORD`, `UNITY_SERIAL` as GitHub secrets
- Use `game-ci/unity-builder@v4` - it handles activation + return automatically

## Caching strategy (critical - saves 5-15 min per build)

The `Library/` folder must be cached. Without it, every build re-imports all assets from scratch (huge for projects with shaders, textures, addressables).

Restore key fallback hierarchy (try most-specific first, then progressively less specific):
```
Library-${{ matrix.targetPlatform }}-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}
Library-${{ matrix.targetPlatform }}-
Library-
```

## Deploy targets per platform

| Platform | Deploy via |
|----------|-----------|
| WebGL | `actions/upload-pages-artifact` → GitHub Pages, OR rsync/FTP to web host |
| Android | Sign + upload to Google Play via `r0adkll/upload-google-play` |
| iOS | Sign with `apple-actions/import-codesign-certs` → upload to TestFlight via `apple-actions/upload-testflight-build` |
| StandaloneWindows64 / StandaloneOSX / StandaloneLinux64 | Upload to Steam via `game-ci/steam-deploy@v3`, or itch.io via `josephbmanley/butler-publish-itchio-action`, or release via `softprops/action-gh-release` |

## Custom Docker image (advanced - for specific Unity modules)

If a build needs Unity modules not in the default image (e.g. specific iOS toolchain, Android NDK version, IL2CPP for additional platforms):

```yaml
- uses: game-ci/unity-builder@v4
  with:
    unityVersion: 2022.3.20f1
    targetPlatform: Android
    customImage: 'unityci/editor:2022.3.20f1-android-3.1.0'   # Override to specific tag
```

Browse images at https://hub.docker.com/r/unityci/editor/tags or build a custom layer:

```dockerfile
FROM unityci/editor:2022.3.20f1-android-3.1.0
RUN apt-get update && apt-get install -y openjdk-17-jdk
```

## Anti-patterns

- ❌ Building Unity in self-hosted runners without GameCI → fight Unity license activation forever
- ❌ Skipping Library/ cache → 10x slower builds
- ❌ Building all platforms on macos-latest → wastes minutes; use ubuntu-latest for non-iOS
- ❌ Using `unityVersion: latest` → builds become non-deterministic; pin exact version
- ❌ Storing `UNITY_LICENSE` in repo files → must be a GitHub secret

## Source provenance

- GameCI org: https://github.com/game-ci
- unity-builder: https://github.com/game-ci/unity-builder
- unity-actions: https://github.com/game-ci/unity-actions
- docker images: https://github.com/game-ci/docker
- Docs: https://game.ci/docs/github/getting-started/
- License: MIT
- Caught by: Talent Scout v2

## Cross-reference

- For Unity-side authoring + Editor automation → see `unity-developer/unity-mcp-operator.md`
- For non-Unity CI/CD patterns → see CI/CD section of this employee's main SKILL.md
