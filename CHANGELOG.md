# Changelog

Scheme: `VERSION` file = single source of truth (`X.Y.Z`); commit `vX.Y.Z: summary`; git tag `vX.Y.Z`; the GitHub Release
is built by CI from the tag. Entries below are newest first. `python scripts/release.py check` keeps VERSION and this file in step.

## v1.0.0 — First public release: images, video cut, trailer, music, live console

- **Images** (`factory.py`): lobby and vertical backgrounds, Qwen Image Edit art through ComfyUI, optional AI upscale,
  title + logo composer, four thumbnails, validator and a promo pack with portal-ready names and sizes.
- **Quality gate:** the horizontal art is compared with its source environment; painted gibberish text is detected and the
  generation is retried with a new seed (`PROMO_QC`, `PROMO_QC_TRIES`).
- **Vertical art without AI** (`PROMO_PLAN_B=bust|direct`): deterministic half-body or full-body composite.
- **Plan B colours:** glow, rim, dust and sparks follow the dominant colour of the background instead of a fixed fire orange.
- **Palette-PNG fix:** backgrounds with a colour-key transparency (`tRNS`) are flattened to RGB on entry (`normalize_background`);
  the original is kept in `input/background_source.png` and the validator flags the trap.
- **Title gradient fix:** the gradient is now laid over the real glyph box (it started at the text origin, so the bottom of the
  letters lost the fill and looked cut off).
- **`dashboard.bat <map>`:** reopens the results page (previews, downloads, zip) of the last run at any time; the page used to die
  with the run window.
- **Renamed to Island Promo Factory** (was "Fortnite Promo Factory") to keep trademarks out of the product name; the docs still say
  it is made for UEFN / Fortnite creators, as a plain description, with the not-affiliated notice in `NOTICE.md`.
- **A/B variants:** the dashboard has "Generate variant B / C" buttons (new seed each time, one at a time). `scripts/variant.py` works in a
  throw-away copy and saves to `Projects/<map>/variants/<B|C>/`; version A is never touched. The POST is protected by a per-session
  token and a localhost check.
- **Prompt control:** `run_all --review-prompt` shows and opens the Qwen prompt before anything starts (saved as `qwen_prompt_custom.txt`,
  delete it to go back to the automatic prompt); `config.json` accepts `"prompt": {"extra": ..., "avoid": ...}`; the template no longer
  suggests companion creatures.
- **Quality gate v2:** invented creatures/objects next to the character and a character outside the left third now trigger a new seed.
- **Cinematic look everywhere** (`--gameplay-look cinematic|hype|off`, default cinematic): the single gameplay video (`gameplay.mp4`, promo slot 07),
  the trailer's real clips and the 3 screenshots get the same treatment: soft warm grade, bloom, vignette, and for videos also film grain,
  2.39:1 letterbox, slow push-ins, speed changes. Gameplay: >= 4 real moments, beat-synced transitions, original audio replaced by our generated
  music (`audio/gameplay_music.wav`). Screenshots stay full 1920x1080 (no bars). `off` keeps everything unedited (Epic asks for real, unedited gameplay).
- `publish.bat` / `publish_skeleton.bat`: run the .ps1 scripts without changing the PowerShell execution policy.
- **Island description notice:** `island_description_disclaimer.txt` is now written for every map: the Disney text for Star Wars maps, an Epic Games
  notice for all others, or your own text from `ip.disclaimer` in `config.json`.
- **One sound for trailer and gameplay:** the trailer uses `audio/gameplay_music.wav` (the generated gameplay track) when it exists; your own
  `audio/music.mp3|m4a|ogg|flac` always wins, `audio/music.wav` is the fallback. `run_all --skip-images` redoes only video, promo pack and lightbox.
- **Character prep** (`prepare_character.py`): crops to the alpha bounding box, keys a flat background, premultiplied resize.
- **Video from one recording** (3-20 min): `video_analyze.py` finds the salient moments (motion + audio) and writes a contact
  sheet; `video_extract.py` cuts the clips, one continuous gameplay segment and up to 3 screenshots, all validated for the portal.
- **Trailer** (`trailer_builder.py`, ffmpeg, no AI video): real clips, artwork end card with title and island code, PEGI and
  "Developed in Fortnite" badges (white or black logo chosen per frame for contrast), generated music.
- **Music** (`music_generator.py`): original, seed-based tracks synthesised from scratch (numpy only), mood `action` by default.
- **Full run + live console:** `run_all.bat` runs everything with timings and opens a local web console (progress, ETA,
  live preview, results gallery, lightbox, one-click ZIP). `lightbox.py` makes the numbered preview board of the pack
  (sizes under every asset, same look as the console), handy to show the results without publishing the full-size files.
- **Versions and updates:** `VERSION`, `scripts/version.py`, `update.bat` / `scripts/update.py` (updates code and docs from the
  newest GitHub Release, never touches Projects, brand files, badges or models), version and "update available" in the console.
- **Gameplay montage** (`video_extract.py --gameplay-montage --gameplay-seconds N`, or `"gameplay":{"montage":true,"seconds":N}`
  in `selection.json`): samples equal-length segments from the best moments of the recording and joins them with hard cuts into
  a 10-40 s `gameplay.mp4`. Recorded in `gameplay.json` and flagged in `UPLOAD_CHECKLIST.md` (the portal asks for real, unedited gameplay).
- **ffmpeg encoder fallback:** `libx264` is used when present, otherwise the best available H.264 encoder (LGPL builds have no libx264;
  the GPL build is recommended for `Resources/bin`).
- **Console:** images and links open in a new tab so the live console is never navigated away.
- **One-root layout:** a root folder (e.g. `C:\IslandPromoFactory`) holds `ComfyUI_windows_portable\` (third-party) next to `island-promo-factory\` (this repo, code only). Maps live in a sibling `Projects\` folder (`PROMO_PROJECTS_DIR` overrides; falls back to `Projects\` inside the repo). Python is found
  automatically (`PROMO_PYTHON` overrides); no hard-coded default map any more (`run_all.bat` lists the maps; a lone map is picked automatically).
  `scripts/cleanup.py` tidies old archived runs, `start_comfyui.bat` starts the bundled ComfyUI. Removed obsolete scripts.
- **First-run experience:** `doctor.bat` (`scripts/doctor.py`) checks Python, Pillow/numpy, ffmpeg and libx264, brand files, Projects, ComfyUI and the models, and prints the fix for
  every missing item. `demo.bat` (`scripts/make_demo.py`) draws an original demo map procedurally (no AI, no third-party IP) and runs the full kit on it. Both are in the smoke test.
- Bundled open-licensed fallback font; bring-your-own brand font and badges. Smoke tests with a mock ComfyUI and GitHub Actions CI.
