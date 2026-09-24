# Stage 1 - Generation (commercial + open paths)

## Commercial (pay-per-use, ~$0.30-0.40/asset)
- **Rodin Gen-2 (Hyper3D)** - SIGGRAPH'25 best paper; the cleanest, most game-ready topology of the commercial generators. Already wired into blender-mcp's Hyper3D integration, so it can generate directly into the Blender scene. First choice when topology quality matters and budget is fine.
- **Tripo (tripo-mcp official)** - strong text/image-to-3D; official MCP makes it agent-callable. Has rigging APIs.
- **Meshy-6** - generate + **rig + animation** in one vendor via its API. Pick when you want the whole character pipeline from one source without a GPU.

Input: text prompt OR a reference image (image-to-3D usually gives better-controlled results). Always specify poly budget and hero-vs-background.

## Open (16GB+ NVIDIA GPU, zero per-asset cost)
- **TRELLIS / TRELLIS.2 (Microsoft, MIT, 12.8k+ stars)** - best raw geometry of the open models; **TRELLIS.2 (O-Voxel) now adds full PBR materials**, so MIT-clean PBR is available in every jurisdiction incl. EU/UK/Korea. Default open choice, and the required choice where Hunyuan3D is barred.
- **Hunyuan3D-2.1 (Tencent, 13.9k+ stars)** - produces real PBR materials out of the box. BUT its license **excludes EU/UK/Korea** - do not use for clients in those regions.
- **Hunyuan3D-Paint** - companion texture-only model: take an untextured mesh, generate PBR textures.

## Choosing
- Need cleanest topology, budget ok → Rodin Gen-2.
- Need generate+rig, no GPU → Meshy/Tripo.
- Zero cost + GPU + any region → TRELLIS.
- Zero cost + GPU + PBR + ANY region → TRELLIS.2 (MIT, preferred); Hunyuan3D-2.1 only where region allows.

## Access
- Commercial: API keys (Rodin/Hyper3D via blender-mcp, Tripo via tripo-mcp, Meshy key). Some reachable via Replicate/fal MCP.
- Open: local GPU running the model; output meshes import into Blender via the backbone.
