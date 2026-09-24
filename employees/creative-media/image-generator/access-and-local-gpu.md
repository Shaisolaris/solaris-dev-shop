# Access: hosted MCPs + local-GPU path

The HOST connects these servers and supplies API keys. This employee only calls them. If a required key/server is missing, name it and stop - never fabricate an image.

## 1. Replicate official MCP (default hosted gateway)
- Endpoint: `mcp.replicate.com`. ONE Replicate key reaches Gemini 3 Pro Image, FLUX.2, Recraft V3, Ideogram 3.0, SDXL.
- Pattern: call the model by its Replicate slug with `{prompt, ...params}`; the run is async - poll until status is `succeeded`, then read the output image URL(s).
- Host connect item: Replicate API token (`REPLICATE_API_TOKEN`).

## 2. fal official MCP (fallback / fal-exclusive)
- Endpoint: fal.ai MCP. Same model families; sometimes cheaper/faster per endpoint.
- Host connect item: fal API key (`FAL_KEY`).
- **Drift warning (hard):** fal model IDs (`app_id`), pricing, input params, output formats, and MCP tool names change fast. `search`/`find` (or `models`) the CURRENT metadata before promising a specific model, parameter, or cost - never quote a stale `app_id`.
- **fal MCP tool surface (distinct from Replicate's slug+poll):** `search` (find models by keyword), `find` (get a model's params), `models` (list popular), `generate(app_id, input_data)` (run), `result`/`status` (check an async job), `cancel` (kill a running job), `estimate_cost` (price a run before spending), `upload` (push a local file and get a URL to use as an `image_url` input).
- **Image call shape:** `generate(app_id:"<current image model id>", input_data:{prompt, image_size, num_images:1-4, seed, guidance_scale})`. To edit/condition on an existing image, `upload` it first, then pass the returned URL as `image_url` (inpaint / outpaint / style transfer / variation). `seed` is reproducibility - hold it fixed while iterating a prompt, vary it only to explore.
- **Cost gate:** call `estimate_cost` before any expensive run, then draft on a cheap/fast tier and only promote the chosen direction to the high-fidelity model - same cost discipline as the Replicate path.
- **Scope note:** fal also exposes text/image-to-video and audio endpoints; those are NOT this employee's job - video routes to video-editor, audio to voice-audio-producer. This section is the fal IMAGE workflow only.

## 3. ComfyUI + comfyui-mcp-server (free local-GPU path)
- joenorton/comfyui-mcp-server (~153★, Apache-2.0). Requires a running ComfyUI instance on a 16GB+ NVIDIA GPU.
- The MCP server submits a ComfyUI **workflow graph** (JSON: nodes for checkpoint loader → CLIP encode → KSampler → VAE decode → save) and returns the rendered image.
- This path unlocks ControlNet, IP-Adapter, LoRA, custom samplers, and inpaint/outpaint at zero per-image cost.
- Models to keep local: FLUX.2 [klein] (Apache-2.0), SDXL (OpenRAIL-M) + a ControlNet pack + IP-Adapter + any brand LoRAs.
- Host connect items: ComfyUI install + GPU + comfyui-mcp-server pointed at the ComfyUI host/port.

## Choosing the path
- Low volume / no GPU → Replicate MCP (pay per image).
- High volume / has GPU / budget-zero / full pipeline control → ComfyUI local.
- fal → when a specific endpoint is cheaper there or Replicate is down.

## Cost discipline at the access layer
- Always draft on the cheap tier (Flash / local SDXL) before spending on Pro/FLUX finals.
- Batch related variations in one request where the API supports it.
