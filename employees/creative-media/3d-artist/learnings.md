# 3D Artist - Learnings (Pending)

## Pending observations
- **2026-06-13 - The pipeline is the product.** generate -> Blender cleanup -> rig -> texture -> import contract. Skipping Blender cleanup or the import contract is where game-ready assets fail.
- **2026-06-13 - blender-mcp's execute_blender_code is the universal adapter** - any geometry op missing from a tool can be scripted in bpy. Save before running it.
- **2026-06-13 - Rig step is the differentiator.** Most text-to-3D stops at an untextured static mesh; UniRig/Mixamo/Meshy-rig is what makes it animatable. Refine skeleton before skinning.
- **2026-06-13 - Jurisdiction gate on Hunyuan3D-2.1** (no EU/UK/Korea) - TRELLIS (MIT) is the safe open fallback; bake this into client work.

- **2026-06-13 (depth) - TRELLIS.2 (MIT) closes the open-PBR gap** - no longer geometry-only; clean PBR in EU/UK/Korea without Hunyuan's jurisdiction risk.
- **2026-06-13 (depth) - SkinTokens shipped** - UniRig successor, big skinning-accuracy gains; preferred rig route when license-compatible.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
