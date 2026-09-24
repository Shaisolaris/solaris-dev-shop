# Unity to WebXR bridge methodology (De-Panther)

Methodology reference adapted from De-Panther/unity-webxr-export (Apache-2.0, ~1.2k
stars; itself based on Mozilla's Unity WebXR/WebVR Exporter, Apache-2.0). Patterns only;
no package or C#/JS code is bundled and Claude does not run Unity. This goes DEEPER than
the 9-step "Unity -> WebXR export SOP" in rules.md, which covers Editor setup/build. The
net-new layer here is the BRIDGE ARCHITECTURE (how a Unity C#/XR project actually drives,
and is driven by, the browser's WebXR session through Unity WebGL) plus the WebXR Input
Profiles controller-mapping and WebXR Hand Input mapping. rules.md keeps the
setup/build/serve checklist; this file explains what that build is wired to underneath.

## Gate-0: what is net-new vs the existing SOP

Existing rules.md "Unity -> WebXR export SOP" = the Editor setup recipe (WebGL platform,
OpenUPM scoped registry, WebGLTemplate, provider toggle, Ignore-Focus, URP, HTTPS serve).
Existing hand-tracking notes are JS-stack (Babylon/A-Frame). NOT previously covered:
- How the JS WebXR API binds to Unity's XR subsystems (the bridge itself).
- The WebXR Input Profiles registry + loader as the controller-model/binding mechanism.
- WebXR Hand Input mapped into the Unity XR Hands package (Unity-side, not Babylon).
- The render-pipeline + AR-feature constraints that follow from the bridge design.
This file is exactly that layer.

## The bridge: JS WebXR API <-> Unity WebGL via XR Subsystems

The export integrates the browser's WebXR JavaScript API into a Unity WebGL build so you
author in C# in the familiar Editor and ship a browser experience. The integration is not
a black box; it maps onto Unity's standard XR plumbing:

- **WebXR Device API -> Unity Display + Input XR Subsystems.** The session's views/poses
  feed Unity's Display subsystem (stereo rendering, per-eye cameras) and its Input
  subsystem (head + controller poses). Because it implements the standard subsystems,
  much of the normal Unity XR stack works on top of it - including the XR Interaction
  Toolkit - rather than a one-off API.
- **WebXR Gamepads Module -> Unity New Input System** (including haptic actuators where
  the device supports them). This is WHY rules.md insists Active Input Handling include
  the New Input System: controller buttons/axes/haptics arrive through it.
- **Unity XR SDK support since export v0.20.0.** This is the version line where the bridge
  became a first-class XR provider; build doctrine should assume a recent version on this
  SDK path.

Practical consequence for the agent: when reasoning about a Unity->WebXR project, treat
input/camera/interaction as standard Unity XR (XRI rigs, Input System actions, XR Hands),
NOT as raw three.js WebXR. The browser is the runtime; Unity's subsystem abstractions are
the interface. (Contrast: a three.js/A-Frame/Babylon project IS raw-ish WebXR in JS - the
existing rules.md sections own that path.)

## WebXR Input Profiles - controller models + bindings (net-new)

Controllers must never be hardcoded (a standing red flag in rules.md). The standard
mechanism is the immersive-web **WebXR Input Profiles** registry, consumed via the
De-Panther **WebXR Input Profiles Loader**, which feeds the XR Interaction Toolkit:

- Each connected XR input source reports a list of **profile IDs** (most-specific first,
  e.g. an exact Quest Touch profile, then a generic-trigger/generic-button fallback).
- The loader resolves the first available profile to a 3D controller model + an
  **asset/layout description** that maps the device's gamepad button/axis indices to named
  components (trigger, grip, thumbstick, A/B). That mapping is what XRI binds interactions
  to - so the same interaction code works across controllers.
- **Always honor the fallback chain.** If the exact profile is unavailable, fall back to a
  generic profile rather than showing nothing or assuming a specific controller. This is
  the concrete fix for the "hardcoded single controller model / no connected-disconnected
  handling" red flag.
- Use the public **WebXR Input Profile Viewer** to inspect a device's components/mappings
  while wiring bindings, instead of guessing index numbers.

## WebXR Hand Input -> Unity XR Hands (net-new, Unity side)

Separate from the Babylon/A-Frame 25-joint notes already in rules.md, the Unity bridge
maps **WebXR Hand Input** into Unity's **XR Hands** package:

- Joints arrive as the standard hand-joint set and surface through XR Hands subsystem
  APIs, so Unity-side hand interactors (XRI hand-tracking) work the same way they would on
  a native build.
- Controllers and hands coexist: design every interaction to be driven by either, with
  hand components self-activating only when the device reports tracked hands (same
  coexistence rule as the JS stack, now expressed through XR Hands).
- Pinch/poke gestures map to XRI's interactor model; do not invent a bespoke gesture layer
  when XRI already exposes one over XR Hands.

## Render pipeline + AR feature constraints that follow from the bridge

These are bridge-imposed facts the agent must respect (and that the setup SOP only hints
at):

- **URP is the supported render pipeline; Built-in RP support was dropped at v0.20.0**
  (re-addable in 0.22+ only by disabling the Display Submodule, per rules.md). Default new
  Unity->WebXR work to URP; do not promise a Built-in-RP path without that caveat.
- **WebXR Augmented Reality Module is supported**, including passthrough/seethrough.
- **Hit-Test is currently limited to viewer-space hit-test source and is NOT routed
  through AR Foundation.** So AR placement on this bridge uses the viewer-space hit-test
  (consistent with the three.js AR SOP in rules.md: request the hit-test source once per
  session against the viewer reference space), NOT AR Foundation's planes/anchors API. AR
  Foundation support is roadmap, not present - do not assume ARF features.
- **Polyfill fallback:** the build ships the WebXR Polyfill so non-WebXR browsers still
  run the content (degraded) - reinforces the mandatory fallback-chain rule.

## When to choose this bridge (decision, unchanged but grounded)

rules.md already says: existing Unity project that must reach the browser -> De-Panther
export, not a rewrite. This file adds the why-it-works confidence: because it implements
standard Unity XR subsystems + Input System + XR Hands + XRI via Input Profiles, an
existing XRI-based Unity project ports with its interaction code largely intact, rather
than being rebuilt in three.js. For a NET-NEW browser-first XR experience with no Unity
codebase, the JS engines (three.js / @react-three/xr / Babylon / A-Frame) remain the
lighter choice - this bridge earns its weight when Unity/C# investment already exists.

## Anti-patterns (bridge-specific, additive to rules.md red flags)

- Treating a Unity->WebXR build as raw three.js WebXR - it is standard Unity XR over a
  browser runtime; use Input System + XR Hands + XRI, not JS WebXR calls.
- Hardcoding a controller model instead of resolving via WebXR Input Profiles + the
  loader's fallback chain.
- Assuming AR Foundation hit-test/planes - this bridge uses viewer-space WebXR hit-test
  only (today).
- Targeting Built-in RP on v0.20.0+ without the Display-Submodule-disable caveat.
- Forgetting the New Input System / Ignore-Focus settings - the bridge routes input and
  loses tracking on tab blur without them (already in the setup SOP; restated because it
  is a direct bridge consequence).

---
Source: De-Panther/unity-webxr-export (Apache-2.0, ~1.2k stars; based on Mozilla Unity
WebXR/WebVR Exporter, Apache-2.0). README + WebXR-APIs-support section read 2026-06-15.
Companion: immersive-web/webxr-input-profiles + De-Panther/webxr-input-profiles-loader
(referenced as the mapping mechanism). Methodology absorbed (bridge architecture, input
profiles, hand-input mapping, render/AR constraints); no package/code bundled or run.
No em-dashes.
