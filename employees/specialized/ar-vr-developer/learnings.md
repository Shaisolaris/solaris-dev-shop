# AR/VR/XR Developer - Learnings (Pending)

## Pending observations
- **2026-06-09 - Rebuild from primary domain sources**: the coding agent-agent hub repos (wshobson 35.7K, VoltAgent 20.2K, alirezarezvani 17.6K stars) contain ZERO XR agents - for niche engineering domains, go straight to the framework/engine repos (three.js, A-Frame, Babylon docs) instead of agent aggregators.
- **2026-06-09 - Babylon teleport+movement mutual exclusion** is a real API constraint, not a style preference - enabling both corrupts locomotion (babylon WebXRMovement.md).
- **2026-04-25 - Comfort settings always exposed**: Motion sickness prevention is the #1 XR usability principle. (Carried over; now grounded in XRI LocomotionSetup concepts.)

- **2026-06-13 (depth) - @react-three/xr (pmndrs/xr, MIT ~26.9k) added** - the R3F-native WebXR layer; fills the React-site XR gap (was rejected NOASSERTION in the rebuild; LICENSE is MIT).
- **2026-06-13 (depth) - Apple WebXR fact corrected** - Vision Pro Safari has WebXR VR by default (visionOS 2+), AR not supported; iPhone Safari still no WebXR. Old table conflated them.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-09 | Teleport/movement mutual exclusion | rules.md Locomotion SOP |
## Sources

- Upstream: pmndrs/xr (MIT (LICENSE file; pmndrs standard)); mrdoob/three.js (MIT); BabylonJS/Babylon.js (Apache-2.0); De-Panther/unity-webxr-export (Apache-2.0); aframevr/aframe (MIT)
- What was used: methodology absorbed: pmndrs/xr; connected as external reference: pmndrs/xr, mrdoob/three.js, BabylonJS/Babylon.js, De-Panther/unity-webxr-export, aframevr/aframe
- License notes: absorbed sources permissive (MIT/Apache-2.0); no code vendored
