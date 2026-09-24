# Unity Build + Ship Pipeline

Load this file for: building a game in CI, shipping to the App Store / Play Store, code signing, TestFlight / Play internal track, fastlane, GitHub Actions for Unity, and the "it took a month to republish six games" problem. The Unity MCP bridge automates the Editor; THIS file automates everything after the Editor - the part that actually eats Shai's weeks.

> Methodology absorbed 2026-06-13 from GameCI (game-ci/unity-builder, ~1k stars, MIT, "free for everyone forever", v4.8.1 2025-11-22) + fastlane patterns. No third-party code is bundled here; this is the build-and-ship playbook. Install the actions/tools from their upstream sources.

## The mental model: three stages, automate all three

1. **Build** - turn the Unity project into a platform artifact (`.ipa` for iOS, `.aab`/`.apk` for Android, a WebGL bundle, a desktop binary). Done headless via Unity batchmode or GameCI.
2. **Sign** - attach the right certificate + provisioning profile (iOS) or keystore (Android). This is where most manual time and most mysterious failures live. fastlane `match` (iOS) and a checked-in-encrypted keystore (Android) make it repeatable.
3. **Ship** - upload to TestFlight / App Store Connect (iOS) or the Play internal/closed/production track (Android), with release notes and the right build number. fastlane `pilot`/`deliver` (iOS) and `supply` (Android).

If any of these three is still manual, that is the bottleneck. Automate it once, reuse it for every game in the Solaris portfolio.

## Headless Unity build (the foundation)

A custom C# build method invoked from the command line is the base layer GameCI and your own scripts both call:

```csharp
// Assets/Editor/BuildScript.cs
using UnityEditor;
using UnityEngine;

public static class BuildScript
{
    public static void BuildAndroid()
    {
        var opts = new BuildPlayerOptions {
            scenes = EditorBuildSettings.scenes
                .Where(s => s.enabled).Select(s => s.path).ToArray(),
            locationPathName = "build/game.aab",
            target = BuildTarget.Android,
            options = BuildOptions.None,
        };
        // AAB for Play Store; set EditorUserBuildSettings.buildAppBundle = true
        EditorUserBuildSettings.buildAppBundle = true;
        var report = BuildPipeline.BuildPlayer(opts);
        if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            EditorApplication.Exit(1);   // non-zero exit fails the CI job
    }
}
```

Invoke headless:
```bash
Unity -batchmode -nographics -quit \
  -projectPath "$PROJECT" \
  -executeMethod BuildScript.BuildAndroid \
  -logFile -
```

Key rules:
- **Non-zero exit on failure.** `EditorApplication.Exit(1)` is what makes CI actually catch a broken build. Without it the job goes green on a failed build.
- **`-logFile -`** streams the Unity log to stdout so CI captures it.
- **Pin the Unity version** the CI runner uses to match `ProjectSettings/ProjectVersion.txt`.

## CI with GameCI GitHub Actions (the fast path)

GameCI provides MIT-licensed GitHub Actions that handle Unity license activation + cross-platform builds. Minimal Android build job:

```yaml
# .github/workflows/build.yml
name: build
on: { push: { branches: [main] } }
jobs:
  build-android:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }
      - uses: actions/cache@v4
        with: { path: Library, key: Library-${{ hashFiles('Assets/**','Packages/**','ProjectSettings/**') }} }
      - uses: game-ci/unity-builder@v4
        env:
          UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}
          UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}
          UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}
        with:
          targetPlatform: Android
          androidExportType: androidAppBundle
      - uses: actions/upload-artifact@v4
        with: { name: android-aab, path: build/Android }
```

Notes:
- **License activation:** GameCI's `unity-activate` / the builder action handle personal or pro license activation from `UNITY_LICENSE` (Personal) or serial (Pro). Generate the `.alf` -> `.ulf` once; store as a GitHub secret.
- **Cache `Library/`** keyed on Assets/Packages/ProjectSettings hashes - this is the single biggest CI speedup (skips reimport).
- **Enable Git LFS** if the project stores large binary assets.
- iOS builds need a macOS runner (`runs-on: macos-latest`) and produce an Xcode project that fastlane then archives + signs.

## iOS signing + ship with fastlane

```ruby
# fastlane/Fastfile
platform :ios do
  desc "Build, sign, and push to TestFlight"
  lane :beta do
    match(type: "appstore", readonly: true)          # pulls certs/profiles from the match repo
    build_app(
      project: "build/iOS/Unity-iPhone.xcodeproj",
      scheme: "Unity-iPhone",
      export_method: "app-store"
    )
    upload_to_testflight(skip_waiting_for_build_processing: true)
  end
end
```

- **`match`** stores certificates + provisioning profiles in an encrypted git repo so every machine/CI runner signs identically. This kills the "works on my Mac, fails in CI" signing churn.
- **`build_app`** (gym) archives + exports the `.ipa` from the Xcode project Unity emits.
- **`upload_to_testflight`** (pilot) pushes to TestFlight; swap for `upload_to_app_store` (deliver) for production submission with metadata + screenshots.
- Bump the build number automatically (`increment_build_number` or derive from the CI run number) so App Store Connect never rejects a duplicate.

## Android signing + ship with fastlane

```ruby
platform :android do
  lane :internal do
    # keystore path + passwords come from CI secrets / env, never committed in plaintext
    gradle(task: "bundle", build_type: "Release")    # or build the .aab via BuildScript above
    upload_to_play_store(
      track: "internal",
      aab: "build/game.aab",
      json_key: "play-service-account.json"          # store as encrypted CI secret
    )
  end
end
```

- **Keystore** stays out of the repo (or encrypted with git-crypt); passwords come from secrets.
- **`upload_to_play_store`** (supply) needs a Google Play service-account JSON with release permissions.
- Promote internal -> closed -> production by re-running with a different `track:`.

## Store-submission gotchas (the ITMS / Play rejections that cost a resubmit cycle)

- **iOS privacy:** every data-collecting API needs a usage description in Info.plist (camera, photos, ATT/IDFA). Missing one = ITMS rejection. Set them in Unity Player Settings -> iOS -> Other Settings, and fill App Privacy + ATT in App Store Connect.
- **iOS encryption declaration:** answer the export-compliance question; set `ITSAppUsesNonExemptEncryption=false` in Info.plist if you only use standard HTTPS, to skip the manual prompt each upload.
- **Android target API level:** Play enforces a minimum target SDK each year. Set Player Settings -> Android -> Target API Level to the latest required, or the upload is blocked.
- **Android 64-bit + AAB:** Play requires 64-bit and the App Bundle format. Build IL2CPP with ARM64 in Scripting Backend / Target Architectures.
- **Build number monotonicity:** both stores reject a build number <= the last accepted one. Always increment in the lane.

## IAP + ads - wire it in the ship flow, test in sandbox

The IAP/ads layer is shipped via official SDKs (no safe permissive OSS wrapper beats them as of 2026-06):

- **IAP:** Unity IAP (`com.unity.purchasing`) is the default; RevenueCat is the alternative if you want server-side receipt validation + cross-platform entitlements without building it. Add via `package-add` (see the MCP operator file).
- **Ads / mediation:** Unity LevelPlay (IronSource) or Google AdMob, both with mediation across networks (AppLovin MAX, etc.). Pick ONE mediation layer per game and record it in the project's `AGENTS.md` monetization section.
- **Sandbox testing is part of the build gate, not an afterthought.** iOS: a Sandbox tester account in App Store Connect; Android: a license-test account + the internal track. Add the purchase + rewarded-ad flow to the AltTester E2E suite (see `unity-testing-pipeline.md`) and run it against a real sandbox build before every store submission. A broken purchase flow that ships is a revenue-zero release.
- IAP/ads only work on a real build (Tier 4 in the testing pyramid), never in the Editor - schedule that test in the ship lane.

## The one-command ship checklist

```
□ ProjectVersion.txt Unity version matches the CI runner's Unity version
□ Build number incremented (monotonic, > last accepted)
□ Headless build exits non-zero on failure (CI can actually catch breaks)
□ Library/ cached in CI (build is minutes, not 30+)
□ iOS: match certs/profiles current; ATT + App Privacy + encryption declaration set
□ Android: target API at required minimum; AAB + ARM64/IL2CPP; keystore from secrets
□ IAP + rewarded-ad flow passes against a SANDBOX build (AltTester E2E)
□ Release notes filled; correct track (TestFlight / Play internal -> closed -> production)
□ Tag the git commit with the shipped version so the build is reproducible
```

## Sources

- GameCI: https://github.com/game-ci/unity-builder (MIT) + https://game.ci/docs - license activation + cross-platform GitHub Actions.
- fastlane: https://fastlane.tools (MIT) - match (signing), gym/build_app, pilot/upload_to_testflight, deliver/upload_to_app_store, supply/upload_to_play_store.
- Official monetization SDKs: Unity IAP, Unity LevelPlay, Google AdMob (commercial SDKs; no OSS wrapper absorbed).
