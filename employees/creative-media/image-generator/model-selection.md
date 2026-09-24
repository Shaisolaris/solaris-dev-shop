# Image model selection - landscape, cost, license (verified 2026-06-13)

## Primary: Gemini family (Google)
- **Gemini 3 Pro Image** ("Nano Banana Pro") - the default. Best all-rounder: photoreal AND illustration, best in-image text rendering in the field, conversational editing, strong character consistency across edits. Cost ~$0.13–0.24 per 4K image. Use for finals and anything with text.
- **Gemini 2.5 Flash Image** - ~$0.039/image. The draft horse. Use for 2-4 quick composition explorations before promoting the winner to Pro.

## Alt / lock-in hedge: FLUX.2 (Black Forest Labs)
- Strongest photographic control and multi-reference subject consistency. Editing ecosystem:
  - **FLUX Tools** - fill (inpaint), expand (outpaint), depth/canny ControlNet-style guidance.
  - **FLUX.2 Kontext** - in-context editing: give an image + instruction, keep structure, change specifics.
- Available hosted (Replicate/fal) OR local on GPU.
- License tiers: **[klein 4B] = Apache-2.0 (clean commercial); [klein 9B] = NON-commercial (flag it)**; **[dev] = commercially conditioned (flag it)**; FLUX.1 schnell = Apache-2.0; [pro] hosted via API.

## Specialists
- **Recraft V4** (Feb 2026 rebuild; V3 still valid fallback) - true editable SVG output. The ONLY right answer for logos, icons, brand marks, and anything that must scale/edit as vector. Also strong raster brand styles + brand-kit system.
- **Ideogram 3.0** - text-in-image reserve when Gemini is unavailable or for typographic poster styles.
- **Adobe Firefly** - trained on licensed/owned data, offers commercial indemnification. Use ONLY when legal requires indemnity; otherwise it underperforms the leaders.

## Open / local (16GB+ NVIDIA GPU, zero per-image cost)
- **FLUX.2 [klein]** (Apache-2.0) - best local quality, commercially clean.
- **SDXL** (OpenRAIL-M) - mature ecosystem: ControlNet, IP-Adapter, thousands of LoRAs.
- **Qwen-Image / Qwen-Image-2512** (Apache-2.0) - open + commercially clean; best-in-class multilingual in-image text + layout reasoning. Strong pick when license-clean local output or non-English text is needed. Runs in ComfyUI; also hosted on Replicate/fal.
- Run via ComfyUI + comfyui-mcp-server. This is the route for high-volume or budget-zero work and for full pipeline control.

## Excluded / flagged
- **Midjourney** - no production API. Cannot be automated. Never route to it.
- **SD3.5** - commercial-license conditions; flag before client use.
- **FLUX.2 [dev]** - non-commercial conditions; flag before client use.

## Cost-aware default ladder
1. Explore: Flash Image or local SDXL (cheap/free).
2. Final realism/illustration/text: Gemini 3 Pro Image.
3. Final photographic/multi-ref: FLUX.2 [pro] or local FLUX.2 [klein].
4. Vector/logo: Recraft V3.
5. Indemnity: Firefly.
