# Unity Mobile Performance + Build-Size Playbook

Load this file for: a slow mobile game, a too-big install, frame drops / GC stutter, thermal/battery problems, draw-call counts, or "make this run on a cheap Android phone." This is the optimization discipline that the scattered profiler tips in `unity-testing-pipeline.md` only gestured at. Profiling tooling lives there; the concrete fixes live here.

> Methodology absorbed 2026-06-13 from GuardianOfGods/unity-mobile-optimization (92 stars, MIT, active maintainer HoangVanThu) plus standard Unity mobile guidance. Knowledge only; no code lifted. Always profile first (Unity Profiler / Frame Debugger / Memory Profiler) to confirm the bottleneck before applying any fix below.

## Order of operations: profile, then cut the biggest cost

1. Record a 10s Profiler sample on a real device build (Development Build + Autoconnect Profiler).
2. Identify the dominant cost: CPU frame time, GC.Alloc spikes, draw calls, or memory/build size.
3. Apply the matching section below. Re-profile to confirm. Do not optimize on a hunch.

## Reduce build size (usually dominated by textures)

Textures are almost always the biggest slice of memory and install size. Import settings, per texture:
- **Lower Max Size** to the smallest that still looks acceptable. Non-destructive, instant memory win.
- **Power-of-two (POT) dimensions** - required for mobile compression formats (ASTC / ETC).
- **Atlas** related textures (Unity Sprite Atlas or TexturePacker) to cut draw calls and speed rendering.
- **Disable Read/Write Enabled** unless you genuinely read pixels at runtime - when on, it keeps a second CPU copy, doubling the texture's memory.
- **Disable Mip Maps** for UI/2D sprites that stay a fixed on-screen size; keep them for 3D meshes that change distance from camera.
- **Compression:** ASTC (RGBA Compressed ASTC) for modern devices; ETC2/ETC for older Android. Set the global default in Player Settings -> Texture Compression, override per-texture where needed.

Audio:
- **Force To Mono** for almost all SFX - halves the data, and on mobile stereo is rarely audible.
- **Vorbis** for most clips (MP3 for non-looping); **ADPCM** for short, very frequent sounds (footsteps, hits) - small and cheap to decode.
- **22,050 Hz** is plenty for mobile SFX. Trust your ears before going higher.
- **Load type by size:** small clips (<200KB) Decompress On Load; medium (>=200KB) Compressed In Memory; large music Streaming.
- Keep source assets as **uncompressed WAV** to avoid double-compression quality loss; let Unity do the final compression.

Mesh + animation:
- **Mesh Compression** on; disable Read/Write; strip rigs/BlendShapes/normals/tangents you do not use.
- **Animation compression error tolerances** (rotation/position/scale error) shrink clip size - raise carefully, they introduce visible error if pushed too far.

## Reduce CPU frame time (scripting)

GC.Alloc spikes cause the worst mobile stutter. Hunt per-frame allocations:
- **No string concatenation per frame.** `Debug.Log("a" + x + "b")` allocates; build the string once or use cached/format-free paths. Strip Debug.Log entirely in release.
- **No LINQ in Update/hot loops** - it allocates enumerators and closures every call.
- **No `new List<>()` / `new T[]` per frame** - allocate once, clear and reuse.
- **Structs on the stack, classes on the heap.** Small, short-lived data = struct; complex shared objects = class.
- **Prefer plain C# events over UnityEvents** in hot paths - UnityEvent is slower and allocates.

**Centralized Update (manager pattern).** 100 enemies each with their own `Update()` means Unity makes 100 managed->native calls per frame. Instead, give the manager one `Update()` that iterates a list and ticks each entity. This is the single highest-leverage CPU pattern for crowds. (Empty `Update()` methods are not free either - delete them; Unity still calls them.)

## Reduce GC + spawning cost (object pooling)

`Instantiate`/`Destroy` are expensive and `Destroy` generates garbage; doing it per shot/enemy/particle causes spikes. **Pool** instead: pre-instantiate a set, deactivate on "destroy", reactivate + reposition on "spawn". Unity has a built-in `UnityEngine.Pool.ObjectPool<T>` since 2021. Pool bullets, enemies, pickups, damage numbers, and any UI that recycles.

**Recyclable scroll views.** For long lists (leaderboards, inventories, level select), never instantiate 9,999 items. Reuse a handful of cells that rebind their data as the user scrolls. Use a recyclable scroll component rather than a plain ScrollRect with thousands of children.

## Reduce GPU cost (draw calls + overdraw)

- **GPU Instancing** for many copies of the same mesh+material - collapses them into one draw call.
- **Static/dynamic batching** and **SRP Batcher** (URP) - keep materials shared so batching can kick in.
- **Bake/combine meshes** that never move to cut draw calls.
- **Fake shadows** (a blob sprite under the character) instead of real-time shadows - often a huge mobile win.
- **LOD** groups: fewer triangles for distant meshes.
- **Overdraw** is the silent mobile killer - use the Frame Debugger and the overdraw view; reduce transparent layering and full-screen alpha.

## Physics

- **Fixed Timestep:** default 0.02s (50Hz). On low-end devices, 0.033s (~30Hz physics) is a safe, large saving. You can detect device tier at runtime and set `Time.fixedDeltaTime` accordingly.
- **Layer Collision Matrix:** if two layers never need to interact, untick them so the physics engine stops checking the pair. Per-collider layer exclusion exists in newer Unity.
- **No non-convex MeshColliders on moving objects** - use primitive or convex colliders.

## Quick wins checklist (mobile)

```
□ Textures: Max Size minimized, ASTC/ETC compression, Read/Write off, mips off for UI
□ Audio: Force-to-mono, Vorbis/ADPCM, 22.05kHz, load-type set by clip size
□ Meshes: compressed, Read/Write off, unused channels stripped
□ No per-frame allocations (no LINQ/string-concat/new in Update) - verified in Profiler
□ Crowds use Centralized Update, not per-entity Update()
□ Spawned objects pooled (UnityEngine.Pool), long lists use recyclable scroll
□ GPU instancing / shared materials so batching works; overdraw checked in Frame Debugger
□ Fake shadows + LOD where real shadows/full meshes are not needed
□ Physics: fixed timestep tuned for low-end, layer matrix pruned
□ Linear vs Gamma color space chosen deliberately; Incremental GC considered; VSync off if appropriate
□ Stay on Unity LTS for stability
```

## Sources

- GuardianOfGods/unity-mobile-optimization (https://github.com/GuardianOfGods/unity-mobile-optimization, MIT) - the structured mobile build-size + perf checklist this file is modeled on.
- Unity Profiler / Frame Debugger / Memory Profiler - confirm every bottleneck before fixing (see `unity-testing-pipeline.md`).
