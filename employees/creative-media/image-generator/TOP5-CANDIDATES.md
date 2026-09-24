# Image Generator - TOP 5 verified 2026 candidates

Domain: image generation models / Replicate / ComfyUI. Verified 2026-06-13.

| # | Source | Stars/Status | License | Last update | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|--------------|---------|-------------|------------|--------------|--------|-----|
| 1 | Recraft V4 (https://www.recraft.ai) | released Feb 2026 (ground-up rebuild) | commercial SaaS (check ToS for indemnity) | 2026-02 | Recraft | Successor to V3; better prompt accuracy + design output; still the only true editable-SVG generator. | grep: only "Recraft V3" present; "V4" ABSENT = not a content-duplicate | METHODOLOGY (upgrade vector route) |
| 2 | Qwen-Image / Qwen-Image-2512 (https://github.com/QwenLM) | top-5 open 2026 | Apache-2.0 (permissive) | 2026 | Alibaba Qwen | Apache-2.0 open model with best-in-class multilingual in-image text + layout reasoning; commercially clean local alt to FLUX/SDXL. | grep: "Qwen" ABSENT = not a content-duplicate | ABSORB (methodology) / CONNECT (local + Replicate/fal) |
| 3 | joenorton/comfyui-mcp-server (https://github.com/joenorton/comfyui-mcp-server) | ~153 | Apache-2.0 | 2026 | joenorton | Owned local-GPU gateway. Verified star fix: 333 (stale/overstated) -> ~153. | grep: present (owned) = content-duplicate; refresh stale star count | CONNECT (refresh) |
| 4 | Black Forest Labs FLUX.2 (https://github.com/black-forest-labs) | leading open photo control | klein 4B = Apache-2.0; klein 9B = NON-commercial; dev = conditioned | 2026 | BFL | Already absorbed. License NUANCE found: klein is NOT uniformly Apache-2.0 (4B yes, 9B no). | grep: present; license stated too broadly = fix, not new | CONNECT (refresh + license correction) |
| 5 | Gemini 3 Pro Image / "Nano Banana Pro" (Google, via Replicate/fal) | primary | hosted commercial | 2026 | Google | Already the primary. Confirmed current best all-rounder + in-image text. | grep: present = content-duplicate, no change | CONNECT (confirmed current) |

## Notes
- Net new: Recraft V4 (#1) and Qwen-Image (#2). #3-#5 refresh/correction.
- License correction is the most important safety item: FLUX.2 klein 9B reverts to non-commercial - do NOT treat "klein" as blanket-Apache. Only klein 4B (and FLUX.1 schnell) are Apache-2.0; Qwen-Image and SDXL are the other clean commercial open picks.
- comfyui-mcp-server star count corrected 333 -> ~153.
