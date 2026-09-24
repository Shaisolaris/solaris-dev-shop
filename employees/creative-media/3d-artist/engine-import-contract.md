# Stage 5 - Engine import contract (METHODOLOGY)

The contract that guarantees an asset drops into Unity/Unreal without rework.

## Container by asset type
- **Static mesh** (props, environment, non-deforming): **GLB** (glTF 2.0 binary, textures embedded).
- **Rigged / skinned / animated** (characters, creatures): **FBX 2020 binary**, with media embedded.

## Scale + orientation
- 1 unit = 1 meter. Apply transforms in Blender before export so scale/rotation bake in.
- glTF is Y-up; Blender is Z-up - the Blender glTF exporter converts axes. Verify orientation on import, don't assume.

## Unity
- **Static GLB** → import via **glTFast** (Unity's recommended runtime/edit-time glTF importer). Clean PBR mapping.
- **Rigged FBX** → standard Unity FBX importer; set rig type (Humanoid for Mixamo humanoids → retargetable; Generic for creatures). Configure avatar.
- Materials: map the PBR set to URP/HDRP/Standard inputs (basecolor→albedo, normal→normal, etc.).

## Unreal
- **Static GLB** → native glTF import.
- **Rigged FBX** → FBX import with skeletal mesh; import skeleton + animations; check up-axis.

## Texture delivery
- Embed in the container OR deliver a named PBR set: `_basecolor`, `_normal`, `_roughness`, `_metallic`, `_ao`. Document which channels are packed if using ORM packing.

## Pre-export checklist
- [ ] Poly budget met (decimated/retopo'd)
- [ ] UVs clean, no overlaps for baked maps
- [ ] Scale 1u = 1m, transforms applied, origin set
- [ ] Rig verified (if applicable), skin weights sane
- [ ] PBR set complete
- [ ] Correct container (GLB static / FBX 2020 rigged)
- [ ] Imports clean in target engine (test once)
