# Voice + audio recipes

## Narration / voiceover
1. Lock the final, sign-off script.
2. Pick a library voice OR Voice-Design one to the brand persona.
3. Set delivery: language/accent, stability (higher = consistent, lower = expressive), pacing.
4. Generate; review proper nouns/jargon; fix mispronunciations with phonetic respelling.
5. Isolate/clean if needed; hand clean file to video-editor for mix-into-video, or deliver standalone.

## Character voice (games / brand)
1. Design (from description) or Clone (from a consented sample) ONE voice per character.
2. Save it to the voice library with a clear name.
3. Generate ALL lines for that character from the saved voice - never re-design per line.
4. Keep a line manifest (character, line ID, text, file) for the engine/editor.

## Sound effects
- Describe precisely: material + action + environment + duration ("heavy wooden door creak open, stone hall reverb, 3s").
- Generate 3-5 variations; pick best; name and file into the SFX library.
- For game UI: short, dry, consistent loudness across the set.

## Music
- Specify mood, tempo (BPM range), instrumentation, length, and whether it must loop seamlessly.
- For games, generate per-state stems (menu, gameplay, tension, victory).

## Transcription (captions / logging)
- Single speaker: straight STT.
- Multiple speakers: enable diarization; set min/max speakers if known.
- Output feeds video-editor's caption pipeline (it burns-in or soft-subs).

## Voice isolation (shared with video-editor)
- Run on noisy/echoey dialogue to extract a clean voice before cloning or before video-editor mixes it.
- This is the one ElevenLabs tool another employee (video-editor) calls - owned here.

## Handoff to video-editor
- Deliver clean audio as files (WAV/MP3) with a manifest.
- video-editor handles loudness normalization, ducking under music, EQ, and the mix into the video timeline (its FFmpeg/Resolve job).
