# ElevenLabs MCP - access + tools

Official server: elevenlabs/elevenlabs-mcp (MIT). The HOST connects it; this employee calls it.

## Install / connect (host)
- Get an API key from the ElevenLabs settings (free tier ~10k credits/month).
- a desktop agent app config:
```json
{
  "mcpServers": {
    "ElevenLabs": {
      "command": "uvx",
      "args": ["elevenlabs-mcp"],
      "env": { "ELEVENLABS_API_KEY": "<key>" }
    }
  }
}
```
- Other clients: `pip install elevenlabs-mcp` then `python -m elevenlabs_mcp --api-key=... --print` to emit the config.

## Output configuration
- `ELEVENLABS_MCP_BASE_PATH` - base dir for file outputs (default ~/Desktop).
- `ELEVENLABS_MCP_OUTPUT_MODE` - `files` (default; saves + returns paths), `resources` (base64/text in the MCP response, no disk I/O - good for cloud/no-FS clients), or `both`. In `both`, fetch later via the `elevenlabs://filename` URI.
- `ELEVENLABS_API_RESIDENCY` - data-residency region (enterprise feature), default "us".

## Tools available (from README)
- **Text-to-Speech** - generate speech in many voices/languages.
- **Voice Cloning** - create a voice from a sample (consent required).
- **Voice Design** - create a voice from a text description, no sample.
- **Sound Effects** - generate SFX/ambiences from a description.
- **Music** - generate music tracks.
- **Speech-to-Text / Transcription** - with speaker diarization (identify speakers).
- **Voice Isolation** - extract a clean voice from noisy audio (SHARED with video-editor).

## Example asks (README)
- "Generate three voice variations for a wise, ancient dragon, then add my favorite to the library."
- "Create a soundscape of a thunderstorm in a dense jungle with animals reacting."
- "Convert this recording to sound like a medieval knight."
- "Turn this speech into text, identify speakers, then re-voice each with a unique voice."

## Gotchas (README)
- Voice design + audio isolation can be slow; MCP-inspector dev mode may time out even when the job succeeds - production clients (the coding agent) handle it.
- `spawn uvx ENOENT` → use the absolute path from `which uvx` in the config.
- All generation consumes credits - confirm before large batches.
