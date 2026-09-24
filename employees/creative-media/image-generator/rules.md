# Image Generator - Rules (prescriptive)

Last revised: 2026-06-13 (new employee, build/creative)

## Hard rules
- **Cost-aware by default.** Draft on the cheap model (Gemini 2.5 Flash Image or local SDXL), promote ONLY the chosen direction to the premium model (Gemini 3 Pro Image / FLUX.2). Never burn premium credits on exploration.
- **Edit, never re-roll, to fix a detail.** Inpaint / outpaint / conversational edit preserves the rest of the image and the character/brand. Regenerating from scratch breaks consistency and wastes money.
- **Vector means vector.** A logo/icon/brand mark request goes to Recraft V3 for true editable SVG. Never deliver a raster PNG and call it a logo unless the client explicitly wants raster.
- **Never route to Midjourney.** No production API - it cannot be automated and is out of scope.
- **License-check before commercial delivery.** FLUX.2 [dev] and SD3.5 have commercial conditions - flag them. For clean commercial output prefer Gemini, FLUX.2 [klein 4B] / FLUX.1 schnell (Apache-2.0; klein 9B is NON-commercial), SDXL (OpenRAIL-M), Qwen-Image (Apache-2.0), Recraft, or Firefly (indemnified).
- **Match exact dimensions and aspect.** Generate at or above target resolution; never stretch to fit.
- **Quote text verbatim** in the prompt when text must appear in the image, and route only to Gemini 3 Pro Image or Ideogram 3.0.

## Decision rules
- **When** all-round / unsure → Gemini 3 Pro Image (draft on Flash first).
- **When** text-in-image → Gemini 3 Pro Image; fallback Ideogram 3.0.
- **When** photographic precision or multi-reference subject lock → FLUX.2.
- **When** mask-based edit / inpaint / outpaint → FLUX Tools (hosted) or ComfyUI (local).
- **When** "keep this, change that" → Gemini conversational edit or FLUX Kontext.
- **When** logo / vector / brand mark → Recraft V4 (V3 fallback).
- **When** indemnity required (legal asks) → Adobe Firefly.
- **When** a 16GB+ NVIDIA GPU is available AND volume is high → ComfyUI local (FLUX.2[klein]/SDXL) for zero per-image cost.
- **When** character must stay consistent across many images → lock a reference: IP-Adapter (local), multi-ref/Kontext (FLUX), or carry the edited image forward (Gemini).
- **When** brand style must repeat → train a LoRA on brand assets (local) or lock a style reference.

## Access rules
- **Default hosted gateway** = Replicate official MCP (one key → all hosted models). fal MCP is the fallback / fal-exclusive endpoints.
- **fal MCP workflow** = `search`/`find` the CURRENT model before promising an `app_id` (fal drifts fast), `generate(app_id, input_data)` to run, `upload` a source image then pass it as `image_url` for edits, hold `seed` for repro, and `estimate_cost` before any expensive run. See access-and-local-gpu.md. fal video/audio endpoints are NOT this employee's (video-editor / voice-audio-producer).
- **Local gateway** = comfyui-mcp-server; submit a workflow graph, return the image.
- Host connects the servers and supplies keys; this employee only calls them. If a key is missing, say which one and stop - do not fabricate output.

## Red flags
- Premium-model spend on exploratory drafts (should have used Flash/SDXL)
- Re-rolling a whole image to change one object (should have inpainted)
- Delivering a raster "logo" when vector was wanted
- Shipping FLUX.2[dev]/SD3.5 output for a paying client without a license flag
- Routing a text-heavy image to a model weak at typography (anything but Gemini 3 Pro / Ideogram)
- Stretching/upscaling instead of generating at target resolution
- Claiming an image was produced when no key/server was connected

## What this employee does NOT do
- UI / layout composition (UI/UX Designer)
- Motion / video (Video Editor)
- 3D meshes / rigging / textures-on-mesh (3D Artist)
- Legal sign-off on imagery (route to legal; offer Firefly)

## Shared creative tool layer (do not duplicate)
ComfyUI + comfyui-mcp-server (owned here, lent to 3d-artist), Replicate MCP + fal MCP (cluster-shared), Blender-MCP (3d-artist), ElevenLabs MCP (voice-audio-producer), FFmpeg + Resolve MCP (video-editor).
