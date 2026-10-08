---
name: island-video
description: Island Promo Factory video stage - cinematic gameplay montage (slot 07), cinematic trailer (08) and screenshots (09) from the user's recording, with generated music.
---

# Video

Prerequisite: a recording in `captures/gameplay/` and ffmpeg (`PY doctor.py` reports it). Without a recording the stage is skipped - say so.

1. **Run**: `PY run_all.py --project <slug> --redo-video --skip-images` (analyse, cut, trailer, promo pack, lightbox; about 2 minutes). First time for a map: `PY run_all.py --project <slug>`.
2. **One look for everything**: `--gameplay-look cinematic` (default: soft warm grade, bloom, grain, letterbox, push-ins, speed changes, beat-synced transitions), `hype` (punchier, no bars) or `off` (unedited cut). It applies to the gameplay video, the trailer clips and the screenshots. The original recording audio is always replaced by the generated music; the trailer reuses the same track.
3. **Choose the moments yourself**: edit `captures/selection.json` (see `docs/USAGE.md`), then rerun with `--redo-video`.
4. **Music**: `audio/music.mp3` (the user's own) beats `audio/gameplay_music.wav` (generated). A new seed gives a new track: `--seed N`.
5. **Validate**: `PY video_validate.py <file> --kind gameplay|trailer`. Gameplay 10-40 s, 1920x1080, < 400 MB. Badges (PEGI, Developed in Fortnite) must be sharp and undistorted.
6. Never leave a second gameplay file in `promo_pack/`: slot 07 is the only gameplay video.
