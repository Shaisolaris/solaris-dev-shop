# Prompt craft - per-model recipes

## Universal structure
`subject → composition/framing → style/medium → lighting → camera/lens (for photo) → mood → constraints`
Front-load the subject. One clear subject beats three competing ones.

## Photoreal (Gemini 3 Pro / FLUX.2)
- Name the lens and lighting: "85mm f/1.4, soft window light, shallow depth of field".
- Name a film/sensor look if wanted: "shot on Portra 400", "clean digital".
- AVOID words like "illustration", "3D render", "CGI" - they pull toward non-photo.
- Specify environment + time of day for consistent lighting.

## Illustration / concept art
- Name the medium and rendering: "flat vector illustration", "painterly gouache", "cel-shaded anime", "isometric low-poly".
- Describe line weight, shading, palette. Reference a *style* (e.g. "1950s mid-century poster style"), not a living artist's name lifted verbatim.

## Text-in-image (Gemini 3 Pro / Ideogram 3.0 ONLY)
- Quote the exact string: `the words "GRAND OPENING" in bold sans-serif`.
- Keep text short; long paragraphs degrade. Specify placement and font feel.
- Other models will mangle text - do not route text jobs to FLUX/SDXL.

## Local (SDXL / FLUX.2[klein] via ComfyUI)
- Use a **negative prompt** to exclude defects: "blurry, extra fingers, watermark, lowres, jpeg artifacts".
- Set steps (25-40), CFG (4-8 FLUX, 6-9 SDXL), sampler, and seed (lock seed to reproduce/iterate).
- For control: add ControlNet (pose/depth/canny) or IP-Adapter (reference image).

## Hosted (Gemini) note
- Gemini ignores classic negative prompts - phrase positively ("clean hands, sharp focus") and use conversational follow-ups to fix issues.

## Iteration discipline
- Change ONE axis per iteration (subject OR lighting OR style), not the whole prompt - you learn what moved the result.
- Lock the seed (local) so prompt changes are the only variable.
- Once composition is right, switch from draft model to final model with the SAME prompt + seed.
