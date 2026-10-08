# Usage

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
- `bust` (default in `run_vertical.bat`): half-body cut-out that fades into the scene, sparks, dark bottom gradient for the title.
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
