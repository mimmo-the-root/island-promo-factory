# Usage

## Claude as orchestrator (recommended)
Open this folder in Claude Code and type `/promo-pack` (or just ask for a new package). Claude starts ComfyUI and the live console by itself (`scripts/services.py`) and runs every step; you never double-click .bat files. The skills in `.claude/skills/` load by themselves:
`island-promo` (orchestrator) -> `island-intake` (step 0) -> `island-images` -> `island-video` -> `island-review`.
Step 0 asks for the island code, the title, the title style and a one-sentence character identity, creates or reuses the map,
tells you which files to place (`background/background.png`, `characters/character_01.png`, a recording in `captures/gameplay/`)
and runs `python scripts/intake.py --project <slug>` until it prints READY. Then it runs the pipeline, reviews every output and
writes `RUN_REPORT.md`. One map at a time: the next one starts after you report the portal result.
`intake.py` works without Claude too: `intake.py` lists maps; `intake.py --project <slug> --init --title "T" --island-code 1234-5678-9012` creates one.

## Look of the videos and screenshots
`run_all.bat <map> --gameplay-scenes 2|3` (default 3) makes the gameplay video from that many real scenes with generated music (0 = beat-synced montage).

`run_all.bat <map> --gameplay-look cinematic|hype|off` (default cinematic) sets one look for the gameplay video, the trailer clips and the screenshots:
grade, bloom, vignette; videos add grain, letterbox, push-ins, speed changes and beat-synced transitions. `off` keeps everything unedited.
The recording's own audio is replaced by generated music (`audio/gameplay_music.wav`, reused by the trailer; your own `audio/music.mp3` wins).

## Variants, prompt control, housekeeping
- `dashboard.bat`: live console that keeps running in the background after the run (the batch window closes by itself; the console closes after 30 idle minutes, or now with `python scripts/services.py stop --project <map>`); buttons generate variants B/C (new seed, A untouched). CLI: `variant.py --project <slug> --name B`.
- `run_all.bat <map> --review-prompt`: shows and lets you edit the Qwen prompt before generation (`qwen_prompt_custom.txt`); `prompt.extra` / `prompt.avoid` in `config.json`.
- `python scripts/cleanup.py --project <slug> [--apply]`: moves old archives (`final/_previous`, `_runs`, `captures/_previous`) to `_to_delete/`; nothing is erased.

## Per-map workflow
1. `new_map.bat <slug> "TITLE" [--style SCI_FI]`
2. Add `background/background.png` and `characters/character_01.png`; edit `config.json`.
3. `run_factory.bat <slug>` (or `python scripts/factory.py --project <slug>`). Flags: `--no-qwen`, `--title "X"`.
4. `run_vertical.bat <slug>` for the vertical art without AI.
5. `run_trailer.bat <slug>`.
6. Read `last_run.log`, review `final/` and `promo_pack/`, upload, then start the next map.

## Stage order
lobby background -> vertical background -> prompt builder -> [clean background if the map defines it] -> Qwen horizontal
-> vertical -> upscale (skipped without a model) -> title -> logo -> thumbnails -> validate -> promo pack.

## Per-map overrides
A prompt file with the same name inside `Projects/<map>/` overrides the shared one in `Resources/prompts/`.
`Projects/<map>/qwen_prompt_clean_background.txt` (+ `qwen_negative_clean_background.txt`) enables the one-time
background cleanup (remove unwanted objects). A project copy of `workflows/qwen_workflow_api.json` overrides the shared workflow.

## Vertical art modes (`PROMO_PLAN_B`)
- Default: chosen by itself from the hero (`config.json` `characters[0].complete`, else the cut-out: standing figure whose feet do not touch the bottom edge = `direct`, otherwise `bust`). Force one with `PROMO_PLAN_B=bust|direct`.
- `bust`: half-body cut-out that fades into the scene, sparks, dark bottom gradient for the title.
  Tune with `PROMO_BUST_CROP` (0.58), `PROMO_BUST_H` (0.52), `PROMO_BUST_TOP` (0.10), `PROMO_CHAR_X` (0.50), `PROMO_EDGE_FEATHER` (70).
- `direct`: full-body cut-out (`PROMO_CHAR_H` 0.50, `PROMO_CHAR_FEET` 0.66).
- `1`: composite + Qwen harmonize (experimental: the model may recolor the scene).

## Other environment variables
`PROMO_PROJECT`, `PROMO_SEED`, `PROMO_DEBUG=1`, `COMFY_URL`, `PROMO_REFRESH_BG=1`, `PROMO_UPSCALE_MODEL`,
`VERTICAL_ANCHOR_X` (0.80), `PROMO_TITLE_CX` (0.70), `PROMO_VTITLE_W` (0.78), `PROMO_VTITLE_CY` (0.78),
`PROMO_TRAILER_SECONDS` (20), `PROMO_BADGE_MODE` (full|ends), `FFMPEG_PATH`.

## Video workflow (gameplay + trailer from one recording)
Record 3-20 min of real gameplay and drop it in `Projects/<map>/captures/gameplay/`.
```
python scripts/video_analyze.py   # finds highlights (motion + audio), writes a contact sheet to review
python scripts/video_extract.py --auto --clips 4 --gameplay-seconds 25
#   or: python scripts/video_extract.py --selection selection.json
python scripts/trailer_builder.py # uses captures/clips/clip_*.mp4 + island_code from config.json
```
`selection.json`: `{"clips":[{"start":12,"end":20}],"gameplay":{"start":60,"end":85},"screenshots":[30,90,150]}`
- The gameplay file is ONE continuous, unedited cut (Creator Portal requires real gameplay).
- Set `"island_code": "1234-5678-9012"` in `config.json` to show it on the trailer end card and in `UPLOAD_CHECKLIST.md`.
- `video_validate.py <file> --kind trailer|gameplay` checks portal specs.

## Troubleshooting
- Read `last_run.log` / `last_qwen.log` first: every stage prints its error there.
- `ComfyUI is not running`: start ComfyUI, or use `--no-qwen`.
- `font not found`: put a font in `Resources/brand/font/` (otherwise the bundled fallback is used).
- Hard cut on the character edge: use a render with transparent margin on all sides.
- Never run two instances at once: they lock the same log.
