# Post-TTS audio mastering + QA (execution-depth, 2026-06-15)
The missing chain that turns raw TTS into delivery-grade audio. Methodology-only (FFmpeg/tools host-installed). Raises success rate: outputs hit broadcast-compliant loudness instead of guessing.

## Loudness normalization (FFmpeg loudnorm, 2-pass - THE core technique)
1. MEASURE pass: ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null -  -> read measured_I, measured_TP, measured_LRA, measured_thresh, target_offset.
2. APPLY pass: feed those measured_* back as measured_I/measured_TP/measured_LRA/measured_thresh/offset to loudnorm with the target. Two-pass = accurate; single-pass = drifts.
## LUFS targets by platform
- YouTube / Spotify / Apple Music: -14 LUFS, TP -1 dB.
- Podcast: -16 LUFS (Apple) to -19 (some networks); spoken-word -16.
- Broadcast EBU R128: -23 LUFS.
## QA gate (before delivery)
- pyloudnorm (MIT, ITU-R BS.1770-4) to programmatically MEASURE the rendered file and FAIL if it misses the target +/- 0.5 LU. Gate every deliverable.
## Cleanup (CONNECT, host installs; commercial-safe)
- DeepFilterNet (MIT/Apache, real-time 48k speech denoise) - run before mastering. FLAG: mature, last release 2023.
- ClearerVoice-Studio (Apache, active) - 16k->48k speech super-resolution/bandwidth-extension + SpeechScore (DNSMOS/PESQ) objective QA.
- Demucs (MIT) - vocal/stem isolation for cleanup + music-bed prep.
## FLAG license (mastering toolkits): Spotify Pedalboard (GPLv3 - in-house batch OK, do NOT ship inside proprietary client binaries), Matchering (GPL-3.0 reference-master). Use FFmpeg/pyloudnorm for the clean-license default path.
