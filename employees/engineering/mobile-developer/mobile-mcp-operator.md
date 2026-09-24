# Mobile MCP Operator - mobile-next/mobile-mcp (canonical) + Android-Ui-MCP (fallback)

> **Absorbed v0.3.0 (2026-04-25)** from `mobile-next/mobile-mcp` (PRIMARY) + `infiniV/Android-Ui-MCP` (fallback). Talent Scout v2 caught both. mobile-next/mobile-mcp is the most powerful mobile MCP - works on iOS + Android, real devices + simulators, full app management + UI interaction. Use this every mobile session.

## Why mobile-next/mobile-mcp is the canonical choice

- **Cross-platform**: iOS Real Device + iOS Simulator + Android Real Device + Android Emulator - same API for all four.
- **Full lifecycle**: install → launch → interact → terminate → uninstall - all via MCP.
- **Two interaction modes**: accessibility tree (deterministic, fast, no CV needed) → falls back to screenshot-based coordinates only when a11y data unavailable.
- **Structured data extraction**: pulls semantic info from screen, not just pixels.
- **Cross-app workflows**: LLM can drive multi-app journeys (open Substack → read article → message contact in WhatsApp → set calendar reminder) end-to-end.
- **infiniV/Android-Ui-MCP is a subset**: only screenshots + device list. Use it as fallback when mobile-mcp can't run (older Node, no Xcode, etc.) or for Expo/RN/Flutter dev-loop screenshot iteration.

## Install - mobile-next/mobile-mcp (PRIMARY)

**Standard config** (works in Claude Code, Claude Desktop, Cursor, Cline, Codex, Copilot, Gemini, Goose, Kiro, opencode, Windsurf, VS Code):

```bash
claude mcp add mobile-mcp -- npx -y @mobilenext/mobile-mcp@latest
```

JSON config (manual):
```json
{
  "mcpServers": {
    "mobile-mcp": {
      "command": "npx",
      "args": ["-y", "@mobilenext/mobile-mcp@latest"]
    }
  }
}
```

**SSE server mode** (for cloud / team CI):
```bash
npx @mobilenext/mobile-mcp@latest --listen 0.0.0.0:3000
# With auth:
MOBILEMCP_AUTH=secret npx @mobilenext/mobile-mcp@latest --listen 3000
```

**Disable telemetry**:
```bash
MOBILEMCP_DISABLE_TELEMETRY=1 npx @mobilenext/mobile-mcp@latest
```

### Prerequisites
- Node.js 22+
- Xcode command-line tools (for iOS)
- Android Platform Tools (for Android - `adb` in PATH)
- For iOS Simulator: `xcrun simctl boot "iPhone 16"` first
- For Android Emulator: `avdmanager` + `emulator` running

## Install - infiniV/Android-Ui-MCP (FALLBACK)

Use when mobile-mcp won't run or you only need Android screenshot iteration with Expo/RN/Flutter:

```bash
claude mcp add android-ui-assist -- npx android-ui-assist-mcp
```

## The mobile-mcp tool catalog (canonical)

### Device Management
| Tool | Purpose |
|------|---------|
| `mobile_list_available_devices` | List all simulators, emulators, real devices |
| `mobile_get_screen_size` | Get screen dimensions in px |
| `mobile_get_orientation` | Get current orientation |
| `mobile_set_orientation` | Set portrait/landscape |

### App Management
| Tool | Purpose |
|------|---------|
| `mobile_list_apps` | List installed apps |
| `mobile_launch_app` | Launch by package name (Android) / bundle ID (iOS) |
| `mobile_terminate_app` | Stop running app |
| `mobile_install_app` | Install from `.apk` / `.ipa` / `.app` / `.zip` |
| `mobile_uninstall_app` | Uninstall by bundle ID / package name |

### Screen Interaction
| Tool | Purpose |
|------|---------|
| `mobile_take_screenshot` | Screenshot for inspection |
| `mobile_save_screenshot` | Save screenshot to file |
| `mobile_list_elements_on_screen` | List UI elements with coords + properties (ACCESSIBILITY-FIRST - use this BEFORE coord-based clicks) |
| `mobile_click_on_screen_at_coordinates` | Click at x,y |
| `mobile_double_tap_on_screen` | Double-tap at x,y |
| `mobile_long_press_on_screen_at_coordinates` | Long-press at x,y |
| `mobile_swipe_on_screen` | Swipe up/down/left/right |

### Input & Navigation
| Tool | Purpose |
|------|---------|
| `mobile_type_keys` | Type text into focused element (with optional submit) |
| `mobile_press_button` | Press HOME / BACK / VOLUME_UP / VOLUME_DOWN / ENTER / etc. |
| `mobile_open_url` | Open URL in device browser |

### infiniV fallback (Android only)
| Tool | Purpose |
|------|---------|
| `take_android_screenshot` | Screenshot from Android device/emulator |
| `list_android_devices` | List connected Android devices |

## Decision rules - when to reach for which tool

### Discovery flow (always run first)
1. `mobile_list_available_devices` - confirm what's connected
2. `mobile_list_apps` - confirm target app installed
3. `mobile_launch_app` - bring app to foreground
4. `mobile_take_screenshot` + `mobile_list_elements_on_screen` - understand current screen

### Interaction (PREFER accessibility, fall back to coords)
- **Always try `mobile_list_elements_on_screen` FIRST.** It returns labelled elements with coordinates. Use the labels, not the pixels.
- Only use `mobile_click_on_screen_at_coordinates` when the target has no a11y label.
- For text input: tap the field first (`mobile_click_on_screen_at_coordinates`), then `mobile_type_keys`.

### Cross-app workflows (the killer use case)
- LLM can chain: open Substack → search → read article → highlight section → switch to WhatsApp → message contact → switch back → set calendar reminder.
- Pattern: `mobile_launch_app(appA)` → interact → `mobile_press_button(HOME)` → `mobile_launch_app(appB)` → interact → repeat.

### Visual regression / dev loop
- For Expo/RN/Flutter hot-reload iteration: `mobile_take_screenshot` after every code change.
- For tests: `mobile_save_screenshot` to disk for diff comparison.
- For Android-only dev where mobile-mcp isn't available: fall back to `take_android_screenshot` from infiniV.

## Example prompts (canonical from mobile-next docs)

```
Find the video called "Beginner Recipe for Tonkotsu Ramen" by Way of Ramen,
click like, write a comment "this was delicious, will make it next Friday",
share the video with the first contact in your WhatsApp list.
```

```
Open Eventbrite, search for AI startup meetup events this weekend in
"Austin, TX", select the most popular one, register and RSVP yes,
setup a calendar event as a reminder.
```

```
Open Zoom, schedule a meeting "AI Hackathon" tomorrow at 10AM for 1 hour,
copy the invitation link, send via Gmail to "team@example.com".
```

## When NOT to use mobile-mcp

- **Pure UI design decisions** - that's the UI/UX Designer's job. Use mobile-mcp to verify designs work, not to invent them.
- **Substantial code generation** - write code in the IDE; use mobile-mcp to test the result.
- **Backend/server work** - mobile-mcp drives device UI only.
- **Production e2e test suites** - for production CI use Detox / Maestro / Espresso. mobile-mcp is for AI-driven exploration + dev-loop work.

## Docker (optional - team CI)

mobile-next mobile-mcp:
```json
{
  "mcpServers": {
    "mobile-mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "@mobilenext/mobile-mcp:latest"]
    }
  }
}
```

infiniV Android-Ui-MCP:
```bash
cd docker && docker-compose up --build -d
```

## Source provenance

- mobile-mcp repo: https://github.com/mobile-next/mobile-mcp
- mobile-mcp wiki: https://github.com/mobile-next/mobile-mcp/wiki
- mobile-mcp npm: https://www.npmjs.com/package/@mobilenext/mobile-mcp
- Android-Ui-MCP repo: https://github.com/infiniV/Android-Ui-MCP
- Android-Ui-MCP npm: https://www.npmjs.com/package/android-ui-assist-mcp
- Caught by: Talent Scout v2 (both missed by v1 - see `references/deep-discovery-protocol.md`)

## Comparator queue (Scout to re-evaluate quarterly)

- `CursorTouch/Android-MCP` - alternate Android-only MCP
- `minhalvp/android-mcp-server` - Python ADB-based Android MCP
- `jsuarezruiz/mobile-dev-mcp-server` - alternate cross-platform mobile MCP
- `skydoves/android-skills-mcp` - official Android skills MCP packager (skydoves is reputable)
- `rcosteira79/android-skills` - Android + KMP skills (KMP support is unique)
- `Drjacky/claude-android-ninja` - Compose + Navigation3 + Gradle conventions (Navigation3 is newer than what dpconde covers)
