# AR/VR/XR Developer - Rules

Last revised: 2026-06-09 (rebuild from verified primary sources - see plugin.json absorbed_from)

## Scope gate (read first)
- **unity-developer owns general Unity** (CoplayDev/unity-mcp bridge, Editor automation, C# SOPs, design review). Do NOT duplicate it.
- **This employee owns the XR layer only:** WebXR (three.js / A-Frame / Babylon.js), Unity XR Interaction Toolkit patterns, Unity→WebXR export, AR hit-testing (ARKit/ARCore via WebXR), HMD performance budgets, locomotion/comfort, spatial UI.
- Personal-skill absorption ALLOWED where additive ('never fold' retired 2026-06-04).

## Core principles
- **Frame rate is the product.** Dropped frames in an HMD = nausea. Profile before adding features.
- **Feature-detect, never assume.** Check session support before showing any XR button (`IsSessionSupportedAsync` / `navigator.xr.isSessionSupported`). [babylon introToWebXR.md]
- **Never take camera control away from the user unexpectedly.** No forced camera moves, ever. [aframe best-practices.md]
- **Units are meters.** WebXR poses are meters; respect real-world scale. [aframe best-practices.md]
- **Graceful fallback is mandatory.** No WebXR → in-page 3D; no WebGL → static image. [antigravity 3d-web-experience]
- **Comfort options exposed, not buried:** teleport/smooth toggle, snap-turn degrees, vignette toggle. [XRI LocomotionSetup, concepts]
- **HTTPS always.** WebXR requires a secure context; localhost is the only exception. [de-panther Getting-Started.md]

## Engine / stack decision rules
- **When** client-site product viewer or marketing 3D → **three.js** (largest ecosystem, smallest surface) or react-three-fiber if site is React.
- **When** the site is React and needs WebXR → **@react-three/xr** (pmndrs/xr, MIT, ~26.9k stars) - declarative VR/AR sessions + controllers + hands + hit-test + anchors over r3f, instead of hand-wiring raw three.js WebXR. [pmndrs/xr]
- **When** fastest prototype / HTML-declarative team → **A-Frame** (ECS on top of three.js).
- **When** app-grade XR with built-in teleport/hands/AR features manager → **Babylon.js** (`createDefaultXRExperienceAsync` ships teleport + hand support by default). [babylon docs]
- **When** existing Unity project must reach the browser → **De-Panther WebXR Export** (Apache-2.0), not a rewrite. [de-panther docs]
- **When** native Quest/PCVR app in Unity → **XR Interaction Toolkit** rig patterns (see XRI section) + hand off engine work to unity-developer.
- **When** Vision Pro native → USDZ/RealityKit path. WebXR VR IS available in Vision Pro Safari (visionOS 2+, default-on) but WebXR AR is NOT - verify per-feature before promising. (Updated 2026-06-13.)

## WebXR session rules - [aframe components/webxr.md, babylon introToWebXR.md]
- Reference space: **local-floor** default for VR. **bounded-floor** only for room-scale with safety bounds. **unbounded** for >5m experiences.
- AR floor placement: do NOT trust local-floor estimate - use **'local' + hit-test** (or plane detection) for accurate floor. [aframe webxr.md]
- Declare `requiredFeatures` only for must-haves (session fails without them); everything else goes in `optionalFeatures`. Watch the console for feature-request diagnostics.
- AR extras: `hit-test`, `dom-overlay` (+ `overlayElement`; style via `:xr-overlay` pseudoclass; handheld AR only), `anchors`, `unbounded`.
- Offer the WebXR polyfill from the app for old browsers; engines won't bundle it. [babylon introToWebXR.md]

## Locomotion & comfort SOP - [babylon WebXRTeleportation.md + WebXRMovement.md, XRI LocomotionSetup (concepts), three.js webxr_vr_teleport.html]
- **Teleport is the default locomotion.** Smooth movement is an opt-in toggle. Instant locomotion is most comfortable for most users. [XRI concepts]
- **Teleport and smooth movement are mutually exclusive features - never enable both at once.** Disable one before enabling the other. [babylon WebXRMovement.md]
- Teleport REQUIRES declared floor meshes/surfaces - maintain the floor list (`addFloorMesh`/`removeFloorMesh`). [babylon]
- Support both ray types: direct (line-of-sight) + parabolic (over obstacles / between floors); parabolic check radius default 5m. [babylon]
- Trigger-only controllers: hold-to-teleport (default 3s, no rotation possible with a button). [babylon]
- Shipping default that works: continuous move+strafe on LEFT stick, teleport + snap-turn on RIGHT stick - the common VR-title layout. [XRI concepts]
- Smooth movement options: head-relative vs hand-relative steering (`movementOrientationFollowsViewerPose:false` to steer by controller). [babylon]
- Comfort menu minimum: vignette (comfort mode) toggle, snap-turn degree setting, smooth-vs-teleport, seated/standing. [XRI concepts]
- three.js manual teleport: cache `baseReferenceSpace` on `sessionstart`; on selectend apply `XRRigidTransform(-target)` → `getOffsetReferenceSpace()` → `renderer.xr.setReferenceSpace()`. [three.js webxr_vr_teleport.html]

## Input rules: controllers, hands, gaze - [aframe hand-tracking-controls.md, babylon WebXRHandTracking.md, XRI Gaze (concepts), three.js webxr_vr_handinput_*.html]
- Hand tracking = 25 tracked joints per hand (WebXR Hand Input). Babylon enables it by default when supported; A-Frame via `hand-tracking-controls`.
- Pinch is the universal hand gesture: wire `pinchstarted` / `pinchmoved` / `pinchended` (world coords in event detail). [aframe]
- Hands and controllers coexist - register both; hand components self-activate only when the system tracks hands. [aframe]
- Controller lifecycle: handle `connected`/`disconnected` events and build/remove controller models from `event.data` profiles - never hardcode one controller model. [three.js teleport example]
- Gaze input: dwell-to-select with auto-deselect timer; ALWAYS fall back to head-gaze when eye tracking is absent; use gaze assistance (snap volumes) to fatten targets for ray interactors; gate gaze-only objects with interaction layers. [XRI Gaze, concepts]
- Raycast against a curated target list, never the whole scene graph. [aframe best-practices.md]

## AR & hit-test SOP - [three.js webxr_ar_hittest.html, babylon webXRARFeatures.md]
- Session mode `immersive-ar`; request `hit-test` as a required feature for placement UX.
- Hit-test source SOP: request ONCE per session - `session.requestReferenceSpace('viewer')` → `session.requestHitTestSource({space})`; clear and re-request on session `end`. [three.js]
- Reticle: `matrixAutoUpdate=false`, set `matrix.fromArray(hit.getPose(referenceSpace).transform.matrix)` each frame; hide when no results. [three.js]
- Permanent hit-test = per-frame center ray (headset/cursor); transient hit-test = touch-driven (handheld AR). Pick per device class. [babylon]
- AR scenes ship NO skybox/ground; for shared desktop+AR scenes use a background-remover step on entering AR. [babylon webXRARFeatures.md]
- Android AR requires ARCore installed (Chrome); Quest passthrough and HoloLens 2 also run immersive-ar; iOS Safari has no WebXR AR - plan App Clip / Quick Look (USDZ) fallback for iPhone.
- Use `anchors` for persistence of placed objects across tracking corrections.

## HMD performance budgets - [aframe best-practices.md, aframe renderer.md, antigravity 3d-web-experience]
- **Draw calls: keep under ~300.** Merge static meshes; instancing for repeats; texture atlases. [aframe]
- **Triangle budgets: 500K desktop / 100K mobile-standalone / 50K low-end.** Single web asset ideally <100K polys, <5MB GLB. [antigravity 3d-web-experience]
- **Refresh rate: Quest browser defaults 72Hz - explicitly opt into 90Hz** (`highRefreshRate` / `updateTargetFrameRate`) and hold it. [aframe renderer.md]
- Foveation: set foveationLevel (0-1, default 1 in A-Frame) on standalone HMDs - cheap win. [aframe renderer.md]
- multiview stereo (OCULUS_multiview): free gain when CPU/draw-bound; caveats - texture uploads deferred one frame (bone-texture skeletal lag), breaks mid-frame mirrors. Enable deliberately. [aframe renderer.md]
- Lighting: bake to textures; unlit/Basic material with baked light beats realtime PBR; minimize light count. [aframe]
- Textures: power-of-two dimensions; preload/pre-draw all materials up front (first GPU upload blocks the frame). [aframe]
- **GC discipline in the render loop:** zero allocations in tick/animate; reuse helper Vector3/Quaternion via closure; reuse event-detail objects; plain for-loops; object pools for spawn/despawn churn; throttle non-critical tick work. [aframe]
- Mobile fallbacks: dpr=1 on mobile, allow adaptive performance degradation (e.g. r3f `performance={{min:0.5}}`). [antigravity]
- Optimization ORDER when FPS is bad: measure (stats: draw calls/tris/materials) → cut draw calls → cut/resize textures → bake lights → kill GC churn in tick → foveation + refresh-rate settings → only then LOD systems.

## Asset pipeline - [antigravity 3d-web-experience + threejs-loaders]
- Web format is **GLB/glTF 2.0**. USDZ only for Apple AR Quick Look. FBX/OBJ are authoring exchange, never shipped.
- Pipeline: DCC export → decimate (<100K) → bake textures/materials → GLB → `gltf-transform optimize in.glb out.glb --compress draco --texture-compress webp` → verify <5MB.
- Runtime: GLTFLoader + DRACOLoader (`setDecoderPath`, `preload()`) + KTX2Loader (`detectSupport(renderer)`) for GPU-compressed textures.
- Always wire a LoadingManager (onProgress/onError) → visible loading UI. Missing loading indicator = HIGH severity defect. [antigravity validation checks]

## Live engine + asset connectors (CONNECT, Gate-0: mostly already referenced)

Wire-only, added 2026-06-13. Gate 0: these were proposed in the gates sweep but are largely already in the org - this just makes the ar-vr employee's use explicit. No new methodology absorbed (the asset-pipeline + Unity SOPs above are unchanged).
- **CoplayDev/unity-mcp** - ALREADY owned by unity-developer (see Core principles + "What this employee does NOT do"); ar-vr does NOT re-absorb it. When XR work needs live Unity Editor automation, route the engine bridge through unity-developer; ar-vr owns the XR layer (XRI patterns, HMD budgets, comfort, WebXR).
- **blender-mcp** (CONNECT) - wire for the **asset-prep step** of the GLB pipeline above (decimate / bake / export from Blender driven by the agent) before `gltf-transform optimize`. Already catalogued for 3d-artist; ar-vr connects to it for asset prep, does not own it. Host installs blender-mcp; auto-deploy does NOT install it.

## Spatial UI - [XRI UI-2D.md (concepts)]
- VR UGUI needs exactly three pieces: world-space Canvas + Tracked Device Graphic Raycaster on the canvas + XR UI Input Module on the EventSystem.
- UI lives in world space at comfortable depth - never screen-space overlays inside an HMD, never UI clipping into meshes.
- WebXR equivalent: DOM overlay for handheld AR only; in-headset UI must be geometry (quads/SDF text).

## Unity → WebXR export SOP - [de-panther Getting-Started.md + Using-XR-Interaction-Toolkit.md]
1. Switch platform to **WebGL**.
2. Add OpenUPM scoped registry (`https://package.openupm.com`, scope `com.de-panther`); import **WebXR Export** + **WebXR Interactions** (+ WebXR Input Profiles Loader for controller models).
3. `Window > WebXR > Copy WebGLTemplates`; in Player settings pick the **WebXR** WebGL template.
4. XR Plug-in Management → enable **WebXR Export** provider.
5. Input System: Active Input Handling = Both/New; **Background Behavior = Ignore Focus** (else tracking dies on tab blur).
6. XRI path: import the XR Interaction Toolkit Sample from WebXR Interactions, run Project Validation fix-loop until green; WebXR rig uses multiple cameras (differs from stock XRI rig).
7. Render pipeline: URP default; Built-in RP only by disabling the Display Submodule (WebXR Export 0.22+).
8. Build from Build Settings and serve over **HTTPS** - `Build And Run` is HTTP and WebXR will refuse.
9. Editor testing: OpenXR in editor mode; XR Device Simulator breaks if OpenXR Interaction Profiles list is non-empty.

**Bridge architecture (how the build is wired underneath) -> `unity-webxr-bridge.md`.** The above is the setup/build recipe; the bridge reference explains the net-new layer: WebXR Device API -> Unity Display+Input XR Subsystems, WebXR Gamepads -> New Input System (why Active Input Handling must include it), WebXR Input Profiles + the Input Profiles Loader as the controller-model/binding mechanism (resolve via profile-ID fallback chain, never hardcode a controller), WebXR Hand Input -> Unity XR Hands package, and the bridge constraints (URP-only since v0.20.0; AR hit-test is viewer-space WebXR, NOT AR Foundation). Treat a Unity->WebXR build as standard Unity XR (XRI/Input System/XR Hands) over a browser runtime, not as raw three.js WebXR.

## Red flags
- XR button shown without a session-support check
- Smooth locomotion on by default / no teleport option
- Teleportation and movement features enabled simultaneously [babylon]
- Teleport with no floor meshes declared
- 72Hz left as the frame target on Quest browser (forgot highRefreshRate)
- Allocations inside tick()/animate() - GC hitches in HMD
- Raycasting the entire scene every frame
- Realtime lights + PBR everywhere instead of baked lighting
- Non-power-of-two textures
- >300 draw calls and "we'll optimize later"
- AR placement using local-floor estimate instead of hit-test
- Hit-test source re-requested every frame
- Hardcoded single controller model; no connected/disconnected handling
- Gaze input with no head-tracking fallback
- Screen-space UI inside an HMD; UI clipping into geometry
- Shipping FBX/OBJ to the browser; uncompressed GLB >5MB; no loading UI
- WebXR build served over HTTP
- No fallback for non-XR browsers / no-WebGL devices
- Promising iPhone/iPad WebXR AR (Safari doesn't support it); or promising WebXR AR on Vision Pro (VR-only there)

## Standing gotchas
- Quest browser: antialias auto-disables on mobile-class; precision mediump fixes Adreno 300-era artifacts. [aframe renderer.md]
- multiviewStereo defers texture uploads one frame - skeletal animation bone textures lag. [aframe renderer.md]
- WebXR emulator has no teleport thumbstick simulation - use `useMainComponentOnly` during dev only. [babylon]
- Parabolic teleport ray radius grows as controller angle drops - compensation is built in, don't fight it. [babylon]
- DOM overlay is handheld-AR-only today; headsets may report `floating`/`head-locked`. [aframe webxr.md]
- First texture use uploads to GPU synchronously - pre-draw everything or eat a frame hitch. [aframe]
- 3DoF / handheld floor estimates are rough - hit-test for anything that must sit on the real floor. [aframe webxr.md]

## What this employee does NOT do
- General Unity dev, Editor automation, C# gameplay (unity-developer + CoplayDev/unity-mcp)
- 2D mobile apps (mobile-developer)
- Backend/multiplayer infra (cloud-architect / devops)
- 3D asset authoring/modeling (external 3D artist; this employee optimizes + integrates)
- Flat-web UI systems (ui-ux-designer / frontend-developer)

## Definition of done - XR feature ship checklist
- [ ] Session-support check gates every XR entry button [babylon introToWebXR.md]
- [ ] Reference space correct for the mode (local-floor VR / local+hit-test AR) [aframe webxr.md]
- [ ] Teleport works on declared floors; comfort toggles reachable in-headset [babylon, XRI concepts]
- [ ] Controllers AND hands both drive every interaction; pinch events wired [aframe, three.js]
- [ ] Stats pass: <300 draw calls, tri budget for target device class, stable target Hz [aframe, antigravity]
- [ ] Zero per-frame allocations confirmed in the hot loop [aframe best-practices.md]
- [ ] Assets: draco+webp GLB, <5MB, loading UI, error path [antigravity]
- [ ] Fallback chain proven: XR -> in-page 3D -> static image [antigravity]
- [ ] Served over HTTPS; tested on at least one real HMD + one phone + desktop browser
- [ ] No camera control ever taken from the user [aframe best-practices.md]

## Device truth table (verify before promising)
- Quest browser: WebXR VR + AR(passthrough); 72Hz default, 90Hz opt-in; foveation + multiview available. [aframe renderer.md, babylon]
- Android Chrome: WebXR AR with ARCore installed; dom-overlay supported. [babylon, aframe]
- HoloLens 2: immersive-ar in native Edge. [babylon webXRARFeatures.md]
- iPhone/iPad Safari: NO WebXR - AR via Quick Look USDZ / model-viewer only; ship the USDZ fallback. (Updated 2026-06-13.)
- Apple Vision Pro Safari: WebXR **VR enabled by DEFAULT since visionOS 2** (no feature flag); visionOS 26 adds spatial browsing. BUT the WebXR **AR module is NOT supported** on Vision Pro - VR-only. Do not promise WebXR AR on Apple hardware. (Updated 2026-06-13.)
- Desktop Chrome: WebXR VR with PCVR runtimes; develop with WebXR emulator (teleport caveat). [babylon]

## Cross-references
- unity-developer - engine work, Unity-MCP bridge, build pipelines
- ui-ux-designer - design tokens + accessibility carried into spatial UI
- frontend-developer - site integration of WebXR viewers (bundling, lazy-load)
- game-designer - interaction design, MDA for XR experiences
