# Unity Testing Pipeline

Load this file for: testing on device, emulating a phone, build errors, Unity Remote, Device Simulator, AltTester, visual QA, screenshots, iOS/Android/WebGL targets, or the "why do I need my phone to test this basic thing" problem.

The entire goal of this file is to reclaim the hours Shai has lost to slow test loops.

## Tier 0 - MCP-driven autonomous execute-AND-verify loop (net-new, IvanMurzak/Unity-MCP, deepened 2026-06-13)

Before the human-in-the-loop tiers below, there is a tier where **Claude tests its own work without Shai touching the Editor at all.** CoplayDev/unity-mcp (the primary bridge) is comparatively weak on automated play/edit-mode testing; IvanMurzak/Unity-MCP closes the execute-and-verify loop. The individual tools live in `unity-mcp-operator.md` - this is the *methodology* that strings them into a self-correcting loop.

**The loop (run it as a loop, not one-shot):**
1. **Make the change** - `script-update-or-create` / `gameobject-*` / `assets-*` to apply the edit.
2. **Compile-check** - confirm compilation finished via `editor-application-get-state` (it reports the compilation flag). Don't run tests against a stale/erroring compile.
3. **Run the right test mode** - `tests-run` with a filter:
   - **EditMode** tests for logic/serialization/asset-graph correctness (fast, no playmode).
   - **PlayMode** tests for runtime behavior, coroutines, physics, spawning, scene-flow.
4. **Drive playmode when there's no test yet** - `editor-application-set-state` to enter playmode, let it run, `screenshot-game-view` to see it, `editor-application-set-state` to stop. This is the "does it actually play" check without authoring a formal test.
5. **Read the result, don't guess** - `console-get-logs` for failures/exceptions; `inspect` live state via `reflection-method-find` + `reflection-method-call` (works on private methods + compiled DLLs) or a one-off `script-execute` (Roslyn) to probe a value.
6. **Fix and re-run** - apply the fix, go back to step 2. Iterate until `tests-run` is green AND the playmode screenshot/logs are clean.

**Rules for the loop:**
- **Verify, don't declare.** A fix isn't done until `tests-run` passes for the relevant filter OR a playmode screenshot + clean logs prove it. "Should work now" is not a result.
- **Author a PlayMode test the second time a bug recurs.** First occurrence: drive playmode + screenshot. Second occurrence anywhere: write a PlayMode test so it can never silently regress (promote per the Self-Learning Protocol).
- **Any C# method is a test probe.** Don't add print statements and rebuild - `reflection-method-call` the method directly, or `script-execute` an assertion live in the Editor.
- **Turn a repeated check into a tool.** If you keep running the same verification by hand, add a `[McpPluginTool]`-attributed C# method (3 lines → becomes an MCP tool; see `unity-mcp-operator.md`) so the loop gets a dedicated verb.
- **CI / headless:** the same loop runs under `-batchmode -nographics` with `UNITY_MCP_KEEP_CONNECTED=true` (see the operator file's batch example) - so the autonomous loop is reproducible in CI, not just interactively.

This Tier-0 loop is *the* reason IvanMurzak is kept alongside CoplayDev: CoplayDev is primary for breadth (tool groups, Roslyn validation, multi-instance, remote auth), IvanMurzak is the fallback specifically when you need the closed play/edit-mode verify loop and any-C#-method probing.


## The testing pyramid for Unity - what to use when

Stop using the phone as the primary test device. Build in this order, every time:

### Tier 1 - Editor Play Mode (fastest, 90% of checks)
Just hit Play in the Editor. No build. No device.
- Core logic, state transitions, UI layout at reference resolution
- Physics sanity, basic gameplay loop
- Scripts compile and don't throw

**Shortcut muscle memory:** Ctrl/Cmd+P is Play, Ctrl/Cmd+Shift+P is Pause. If you're building to test a button, you're wasting time.

### Tier 2 - Unity Device Simulator (90% of mobile checks, still no device)
Built into Unity (Window → General → Device Simulator). Simulates iPhone/Android screens, safe areas, touch input, device rotation - all inside the Editor.

- Test responsive UI across iPhone SE → iPhone 15 Pro Max → Pixel 7 → iPad Pro
- Confirm safe area / notch handling
- Verify touch hit targets (44px minimum on iOS)
- See screen rotation behavior

**Setup:** `Window → Package Manager → Unity Registry → Device Simulator` (install if missing). Then `Window → General → Device Simulator`. Default devices cover common phones; add custom devices via `.deviceinfo` JSON files.

### Tier 3 - Unity Remote 5 (real device, no build, ~5s latency)
Stream the Editor directly to a USB-connected phone. Input from phone (touch, gyroscope), display on both. No APK build. Setup takes 10 minutes once.

- Real device feel - touch latency, actual screen size
- Gyroscope / accelerometer / real device motion
- Camera/mic input from the phone

**Setup:**
1. Install "Unity Remote 5" from App Store / Play Store on phone
2. Connect via USB (enable USB debugging on Android, trust this computer on iOS)
3. Unity → Edit → Project Settings → Editor → "Device" set to "Any Android Device" or "Any iOS Device"
4. Launch Unity Remote on phone
5. Hit Play in Editor - it streams

**Caveat:** Unity Remote is for feel-testing, not perf-testing. Actual game runs on your desktop; phone just renders + sends input. Real performance only shows up in Tier 4.

### Tier 4 - Actual build on device (final pass only)
- Real performance (framerate, thermal, battery)
- Platform-specific APIs (IAP, ads, push notifications, native plugins)
- App store submission validation

Build ONE TIME before shipping a feature, not every time you tweak a value.

## Automated UI testing - AltTester

AltTester (formerly AltUnityTester) is the Playwright equivalent for Unity games. Open-source and stable (alttester/AltTester-Unity-SDK, 102 stars, latest V.2.3.0 2026-01-28).

> ⚠️ **License flag: AltTester SDK is GPL-3.0 (copyleft).** Use it as an EXTERNAL test harness driving the build over the network. Do NOT ship the SDK source or binaries inside a released game build without legal review, because GPL would then attach to the shipped binary. For test-only/CI use this is fine; for shipped code it is not.

**What it does:** lets you script user flows in C# or Python - tap this button, wait for this screen, assert this value appears - and run them headlessly in the Editor or against a build.

**Install:**
- Unity: Package Manager → `+` → "Install package from git URL" → `https://github.com/alttester/AltTester-Unity-SDK.git` (repo name is case-sensitive)
- Add AltInstrumentation prefab to your bootstrap scene
- Inspector → AltRunner → enable "Run Server On Start"

**Example test (Python driver):**
```python
from alttester import AltDriver
driver = AltDriver()
driver.find_object(By.NAME, "StartButton").tap()
driver.wait_for_object(By.NAME, "LoadingScreen", timeout=5)
driver.wait_for_object(By.NAME, "GameplayHUD", timeout=30)
assert driver.find_object(By.NAME, "ScoreText").get_text() == "0"
```

**What to automate first (in order):**
1. Happy-path flow: launch → main menu → play → win condition → return to menu
2. Loss flow: launch → play → die → retry → play
3. Pause flow: launch → play → pause → resume → pause → quit to menu
4. Settings persistence: change a setting → quit → relaunch → verify persisted
5. Purchase flow (if applicable) - with sandbox IAP

Run these in CI on every commit once you have them. Same philosophy as Playwright for web.

## Visual regression testing - screenshot diffing

Manual visual QA doesn't scale. Every time you ship a change you don't notice the scrollbar you broke in the settings menu six commits ago.

**The simple version (no extra tools):**
1. Add a "ScreenshotTest" MonoBehaviour to a dedicated TestScene
2. On Start, it loads each UIScreen in sequence, calls `ScreenCapture.CaptureScreenshot()`, saves to `Tests/Screenshots/`
3. Commit a `baseline/` folder
4. On each run, compare output/ to baseline/ with a Python script that diffs pixels (tolerance ~2%)
5. Any diff = manual review required

**The concrete diff gate (drop-in, no extra deps beyond Pillow):**

```python
# tools/visual_diff.py  -  run: python tools/visual_diff.py baseline/ output/
import sys, pathlib
from PIL import Image, ImageChops

TOLERANCE = 0.02  # 2% of pixels may differ before we fail

def diff_ratio(a_path, b_path):
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return 1.0  # size change = always a regression
    bbox_img = ImageChops.difference(a, b)
    diff_pixels = sum(1 for px in bbox_img.getdata() if px != (0, 0, 0))
    total = a.size[0] * a.size[1]
    return diff_pixels / total

def main(baseline, output):
    base, out = pathlib.Path(baseline), pathlib.Path(output)
    failures = []
    for shot in sorted(out.glob("*.png")):
        ref = base / shot.name
        if not ref.exists():
            failures.append(f"NEW (no baseline): {shot.name}"); continue
        r = diff_ratio(ref, shot)
        status = "FAIL" if r > TOLERANCE else "ok"
        print(f"{status:4}  {r*100:5.2f}%  {shot.name}")
        if r > TOLERANCE:
            failures.append(f"{shot.name}: {r*100:.2f}% > {TOLERANCE*100:.0f}%")
    if failures:
        print("\nVISUAL REGRESSION:"); [print(" -", f) for f in failures]
        sys.exit(1)
    print("\nAll screenshots within tolerance.")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

**The gate formula (what "pass" means):**
- diff_ratio = (pixels that differ from baseline) / (total pixels)
- PASS when diff_ratio <= 0.02 for every screenshot AND no screenshot is missing a baseline AND no size change.
- FAIL (exit 1, blocks the commit/CI) on any of: ratio above tolerance, a new screenshot with no baseline, or a resolution change.
- Tune TOLERANCE per project: 0.02 suits static UI; bump toward 0.05 for screens with animated/idle elements, or capture those on a fixed frame to keep them deterministic.
- Wire it into CI after the screenshot-capture step so a broken scrollbar six commits ago can never reach a build silently.

**The AltTester version:**
Combine AltTester navigation with `ScreenCapture.CaptureScreenshot()` calls - you get E2E flow tests that also capture evidence at each step. This is what a real game QA pipeline looks like.

**What to screenshot:**
- Every UI screen in default state (empty inventory, full inventory, etc.)
- Critical gameplay moments (first level load, boss encounter, UI overlay)
- Both portrait and landscape if supported
- Multiple resolutions: 1080x1920, 1284x2778 (iPhone 14 Pro Max), 800x1280 (low-end)

## Platform-specific build gotchas

### Android
- **"Build failed: Gradle error"** → 95% of the time it's JDK version mismatch. Edit → Preferences → External Tools → "JDK Installed with Unity" checkbox.
- **APK too big** → Player Settings → Publishing → enable "Split Application Binary" and use AAB format.
- **Crashes on launch, works in Editor** → check `Logcat` (Window → Analysis → Android Logcat). Common: null permissions (camera/mic/storage) not declared in manifest.
- **Shaders look wrong on some devices** → use URP (Universal Render Pipeline) and avoid custom vertex shaders for mobile.

### iOS
- **Xcode build fails with signing error** → Player Settings → iOS → Signing → set Team ID and bundle ID. Automatic signing is easier unless you have a real provisioning profile reason.
- **"ITMS-90xxx" App Store rejection** → usually ATS (HTTPS required), deprecated APIs, or missing privacy usage descriptions. Edit → Project Settings → Player → iOS → Other Settings.
- **Black screen on launch** → LaunchScreen.storyboard missing. Set "Launch Screen" → Default under iOS Player Settings.
- **Builds take forever** → enable Player Settings → iOS → "Strip Engine Code" + "Incremental GC". Build Only For Current Architecture in Xcode scheme.

### WebGL
- **Very long build** - normal. Enable "Development Build" during iteration to skip some optimization.
- **Black canvas on load** → usually WebGL memory size too low. Player Settings → Publishing → Memory Size (default 256MB; bump to 512MB for moderate games).
- **Audio not playing** → browsers block autoplay. First audio must be triggered by user click. Unity handles this via `AudioManager.Init()` on first input.

## The fast inner loop - 30 second rule

If your edit → test cycle takes more than 30 seconds on average, something is wrong. Diagnose:

- **Compile too slow?** → Assembly Definitions (`.asmdef`) to isolate folders into separate compilation units. Huge win on large projects.
- **Play mode enters slowly?** → Edit → Project Settings → Editor → Enter Play Mode Options → enable "Disable Domain Reload" and "Disable Scene Reload". (Costs: global state persists between plays - plan for it.)
- **Need to rebuild to test?** → You're probably testing too late. Run it in Editor first.
- **Using real device for layout tweaks?** → Switch to Device Simulator. Faster, same info.

## The debug HUD - poor dev's telemetry

Add a toggleable on-screen debug HUD to every project. Cost: 30 min. Payoff: every session after.

```csharp
public class DebugHUD : MonoBehaviour {
    bool show = false;
    void Update() { if (Input.GetKeyDown(KeyCode.BackQuote)) show = !show; }
    void OnGUI() {
        if (!show) return;
        GUILayout.BeginArea(new Rect(10, 10, 400, 500));
        GUILayout.Label($"FPS: {1f / Time.smoothDeltaTime:F0}");
        GUILayout.Label($"State: {GameStateManager.Instance.CurrentState}");
        GUILayout.Label($"UI Stack: {UIManager.Instance.StackDepth}");
        GUILayout.Label($"Player HP: {Player.Instance?.HP ?? 0}");
        // cheat buttons
        if (GUILayout.Button("Add 100 coins")) Inventory.Add("coin", 100);
        if (GUILayout.Button("Skip to win")) GameStateManager.Instance.RequestTransition(GameState.Win);
        GUILayout.EndArea();
    }
}
```

Tilde key toggles it. Add state info, performance stats, and cheat buttons to skip ahead in the game for testing. Massively speeds up iteration on late-game content.

Strip it in release builds with `#if !UNITY_EDITOR && !DEVELOPMENT_BUILD`.

## Performance profiling - when the game gets slow

Default tools, in order of usefulness:
1. **Profiler** (Window → Analysis → Profiler) - CPU frame time, GC allocations, draw calls. Record a 10s sample, look at spikes.
2. **Frame Debugger** (Window → Analysis → Frame Debugger) - inspect every draw call in a frame. Essential for "why is rendering slow".
3. **Memory Profiler** (separate package) - for memory leaks, heap growth over time.

**Red flags in the Profiler:**
- GC.Alloc spikes → something is allocating per-frame. Hunt it down. (Common: LINQ in Update, string concatenation, `new List<>` per frame.)
- Camera.Render taking >5ms on mobile → overdraw. Use Frame Debugger.
- Physics.Processing > 2ms → too many Rigidbodies, or non-convex MeshColliders on moving objects. Fix.
- Animator.Update taking >3ms → too many Animators; consider Animator LOD or AnimatorController culling mode.

## The testing checklist - run before declaring a feature "done"

```
□ Feature works in Editor Play Mode
□ Feature works in Device Simulator at smallest target resolution
□ Feature works on real device (Unity Remote or build)
□ AltTester automated flow passes
□ Screenshots captured and baseline updated
□ No GC.Alloc spikes in profiler during the feature's active state
□ No console errors or warnings introduced
□ Handles back button / app backgrounding correctly
□ Persists state across quit/relaunch (if stateful)
```
