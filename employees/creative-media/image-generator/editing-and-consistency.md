# Editing + consistency procedures

## Inpaint (fix/replace a region)
- Hosted: FLUX Tools "fill" - supply image + mask + prompt for the masked area.
- Local: ComfyUI inpaint graph (SDXL/FLUX[klein] inpaint model) - mask node + sampler at reduced denoise (0.6-0.9) so edges blend.
- Keep the mask tight; feather edges; prompt only what goes IN the mask.

## Outpaint (extend the canvas)
- Hosted: FLUX Tools "expand".
- Local: ComfyUI pad + inpaint the new border region.
- Extend in steps (don't 4x in one go) for coherent continuation.

## Conversational edit (instruction-driven, no mask)
- Gemini 3 Pro Image: "make the jacket red, keep the face and background identical."
- FLUX.2 Kontext: image + instruction, preserves structure.
- Best for small targeted changes - far cheaper and more consistent than regenerating.

## Character consistency (same character, many images)
1. Generate/lock ONE strong reference image of the character.
2. Carry it forward:
   - Gemini: feed the reference + conversational edits ("same character, now running").
   - FLUX: multi-reference / Kontext with the reference image.
   - Local: IP-Adapter (face/style adapter) pointing at the reference; optionally train a small LoRA for a recurring character.
3. Keep wardrobe/colors/features explicit in every prompt as a backstop.

## Brand consistency (repeatable house style)
- Train a **LoRA** on 15-40 brand images (local) → call it on every generation for instant on-brand output.
- OR lock a style-reference image + IP-Adapter.
- For the logo/mark itself: Recraft V3 (editable SVG), kept as the canonical asset.

## Background removal / clean cutout
- Local: ComfyUI with a segmentation/matting node (e.g. rembg-style) → transparent PNG.
- Hosted: many Replicate/fal models offer one-shot bg-removal endpoints.

## Upscale / detail
- Local: ComfyUI upscale (ESRGAN/4x) or FLUX/SDXL hires-fix pass.
- Prefer generating at target resolution over upscaling when quality is critical.
