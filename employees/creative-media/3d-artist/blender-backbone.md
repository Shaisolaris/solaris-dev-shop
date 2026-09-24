# Stage 2 - Blender backbone (blender-mcp)

ahujasid/blender-mcp (22.2k+ stars, MIT, v1.6.4). Socket bridge between Claude and a running Blender; the addon runs a server in Blender, the MCP server relays commands.

## What it can do (from README)
- Two-way socket communication with Blender.
- Object manipulation: create/modify/delete 3D objects; materials/colors.
- Scene inspection: detailed scene + object info; **viewport screenshots** so Claude can see the scene.
- **execute_blender_code**: run ARBITRARY Python in Blender - this is the power tool; it can script any bpy operation and call other tools.
- Asset libraries: **Poly Haven** (HDRIs, textures, models via API), **Sketchfab** model search/download.
- Generation from inside Blender: **Hyper3D Rodin** and **Hunyuan3D** generation.

## Standard cleanup pass (run on every generated mesh)
1. `import` the generated GLB/OBJ/FBX.
2. Screenshot + inspect: object count, triangle count, scale, origin location.
3. **Decimate or retopo** to the poly budget (Decimate modifier for props; retopo for hero/animated meshes where topology flow matters).
4. **UV unwrap** or repair gen UVs (Smart UV Project as a baseline; seams for hero assets).
5. Set origin to geometry/base; **apply** location/rotation/scale; set scale so 1 Blender unit = 1 meter.
6. Assemble multi-part assets; rename objects/meshes/materials sanely (no "Cube.001").
7. Bake/assign PBR materials if not already present.
8. Export per the engine import contract.

## Caution (from README)
- execute_blender_code runs arbitrary Python - powerful but risky. ALWAYS save the .blend before running it. Break complex operations into smaller steps; the socket can time out on big single calls.
- Run ONE instance of the MCP server (don't run it on two clients at once).

## Access (host connects)
- Install the Blender addon (addon.py), enable it, click "Connect to Claude".
- Add blender to the MCP config: `uvx blender-mcp` (env: BLENDER_HOST/BLENDER_PORT, optional DISABLE_TELEMETRY=true).
