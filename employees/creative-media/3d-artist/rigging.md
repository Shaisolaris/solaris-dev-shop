# Stage 3 - Rigging

## Humanoid → Mixamo (free, fastest)
- Upload the mesh in a clean T/A-pose via the browser (Web Operator).
- Mixamo auto-rigs (place chin/wrists/elbows/knees/groin markers) and gives a free animation library.
- Download as FBX (rig only, or rig+animation). Humanoid ONLY.

## Anything (human/animal/object) → UniRig (open, GPU, MIT)
VAST-AI-Research/UniRig (SIGGRAPH'25). Two stages + merge. Supports `.obj`, `.fbx`, `.glb`, `.vrm`. Needs CUDA GPU with 8GB+ VRAM.

Exact CLI (from README):
```bash
# 1. Skeleton prediction
bash launch/inference/generate_skeleton.sh --input model.glb --output results/model_skeleton.fbx
#   try --seed N for skeleton variations

# 2. Skinning weight prediction (uses the edited skeleton)
bash launch/inference/generate_skin.sh --input results/model_skeleton.fbx --output results/model_skin.fbx

# 3. Merge predicted skin onto the original mesh
bash launch/inference/merge.sh --source results/model_skin.fbx --target model.glb --output results/model_rigged.glb
```
- CRITICAL (README): refine the skeleton before skinning. A skeleton missing tail/wing bones degrades skin badly. Merge the SKIN file (model_skin.fbx), not the skeleton-only file, or there will be no skinning.
- Successor **SkinTokens** (released 2026, UniRig authors) unifies skeleton+skin in one autoregressive sequence, +98-133% skinning accuracy / +17-22% bone prediction. Prefer it over the two-stage flow when license-compatible; UniRig stays the fallback. See depth-2026-06.md.

## Any creature, hosted (no GPU) → Meshy / Tripo rig APIs
- Pay-per-use auto-rig for non-humanoids. Use when no GPU and Mixamo can't (it's humanoid-only).

## After rigging
- Verify the rig in Blender (pose a few bones, check deformation).
- Export rigged assets as FBX 2020 binary with embedded media (see engine-import-contract.md).
