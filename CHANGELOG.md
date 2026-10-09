# Changelog

## v1.1.10 — Conform case: the whole package from your own thumbnail

- **Conform case, now the whole package:** after the landscape files, the skill runs on its own: `qwen_run.py hero` (the hero alone on green) + `conform.py hero` (cut-out into `characters/character_01.png`), `conform.py use-clean` (clean background becomes the working background), then `run_all.py --conform` = portrait with/without text (clean background + hero, no Qwen), logo, lobby background, gameplay scenes, trailer, screenshots, promo pack. Your own landscape thumbnails (01/02) are kept untouched. If `input/` holds a single image it is taken as the thumbnail without asking again.

## v1.1.9 — Title style is chosen from the artwork, not left at the default

- **Title style no longer silently stays SCI_FI:** a new map records `style_chosen: false` until a style is really chosen (`intake.py --style`). `intake.py` warns while the default is still in place, and the intake skill now tells Claude to pick the style from what it sees (HORROR, FIRE, ICE, NEON, GOLD, WHITE; SCI_FI only for tech/space) and to decide as soon as the images are in.

## v1.1.8 — Commands renamed to /promo-*; conform case: clean background experiment

- **Commands renamed** (you create a promo package, not a new island): `/promo-pack` (was `/island-new`), `/promo-conform` (was `/island-conform`), `/promo-update`, `/promo-console`. The next start-up sync removes the old command files from `.claude/commands/` (backed up in `_update_backup/`).
- **Where the deliverables are:** `final/` now contains a `README.txt` saying it holds working files and that the numbered files (01-09, gameplay and trailer included) are in `promo_pack/`; the review step opens that folder in Explorer for you.
- **Kit Lightbox shows the screenshots:** the three screenshots appear as one tile ("SCREENSHOTS (3)") and every tile carries the number of its file (01..09), so you can say which numbers to upload. The asset count counts the real files.
- **Console shows single steps:** new `scripts/activity.py run ...` wraps any kit script so the live console shows it as a running stage (progress, estimate, the map's own log). The console no longer shows another map's `last_run_all.log` when the map has no full run, and an interrupted step is reported instead of staying "running". The skills use it for the Qwen steps.
- **Stale console fixed:** a console left running from an older version is restarted automatically the next time the console is opened (the page you saw still showed the old `v1.1.8 · 64f5aae` header because that process predated the update).
- **Conform case, two Qwen steps (experiments, judged honestly by Claude):** `qwen_run.py untitle` removes ONLY the text from your thumbnail and `conform.py art` makes the portal's landscape art-only image (1920x1080, characters stay); `qwen_run.py clean` removes text and characters to give a clean background for the portrait, and `conform.py background` fits it to 16:9 (raw kept in `background/_previous/`). Prompts come from `Resources/prompts/` or are written per map from what Claude sees.

- **Gameplay video (07) = 2-3 real scenes with our music:** the video is built from the 2-3 best moments of your recording at normal speed (soft dissolves, the look's grade only), and the original audio is replaced by generated music. `--gameplay-scenes N` (default 3; 0 = the old beat-synced montage). `--gameplay-look off` still gives one unedited cut with the original audio (the portal may require real, unedited gameplay).

- **Title with a subtitle:** a title written `MAIN TITLE | Subtitle` is now split into two lines at the bar (the bar is no longer drawn as a stray first character of line 2) in the title and the logo.

## v1.1.7 — /island-new: new artwork or conform my existing thumbnail

- For a new map `/island-new` asks the second fork after code and title: make new artwork from separate images, or make my existing thumbnail conform (`island-conform`). An existing map with `input/thumbnail_original.*` continues in the conform case.

## v1.1.6 — New map: drop the files now or come back later; make my thumbnail conform (step 1)

- After creating a map, Claude lists the folders for the files and offers two ways on: drop them now, or leave and resume later with `/island-new` (continue an existing map).
- **New case, step 1:** `/island-conform` (skill `island-conform`) starts from a thumbnail you already have. `scripts/conform.py landscape` makes the landscape-with-text thumbnail (1920x1080 PNG < 5 MB): 16:9 images are scaled, other ratios centre-cropped, small images upscaled with a warning. Landscape without text, portrait, logo and lobby background from an existing thumbnail follow in the next steps.
- File names shown are examples: any name and image format works; Claude copies them to the names the kit uses. `intake.py` prints the same note.

## v1.1.5 — Security: no request data in response headers (CodeQL alert #5)

- `dashboard.py`: download headers now use fixed file names (`promo_pack.zip`, `variant_B.zip`, `variant_C.zip`); inline files carry no `Content-Disposition`. Closes the HTTP response splitting alert.
- The console header shows only the version (`v1.1.5`), without the commit hash.

## v1.1.4 — /island-new asks again: continue a map or start a new one

- The first question of `/island-new` is again "continue one of your existing maps, or start a new one?", with the list of existing maps; it was lost in v1.1.3.

## v1.1.3 — Simpler new-map start with Claude

- `/island-new` asks only for the island code and the title; it checks for a newer release first, creates the map and opens the live console right away.
- Claude tells you the exact folder for each file (background, character, gameplay, music) and waits; `intake.py` prints those folders when it creates a map.
- Title style and the character description are decided by Claude from your images (no questions); you are told the choice in one line.

## v1.1.2 — Batch windows close by themselves, live console stays available, stage area with rollback

- Every `.bat` now ends on its own after a 10 s countdown; it only waits for a key when something failed (the error stays readable). `demo.bat` and `run_all.bat` no longer hang until Ctrl+C.
- The live console is a separate background process: `run_all --ui` and `dashboard.bat <map>` start it (`scripts/services.py console`) and return. It closes itself after 30 idle minutes (`PROMO_CONSOLE_IDLE_MIN`, 0 = never) and never while a run or a variant is working.
- `python scripts/services.py stop --project <map>` closes the console at once; `console.json` now records its process id.
- **Stage area `_releases/`:** every downloaded release is kept as `_releases/v<version>.zip`, and the version you leave is stored there before an update replaces it (last 5 copies, never overwritten). `update.bat --list` shows them, `update.bat --rollback [version]` goes back (or forward) without touching `Projects/`, brand files or models.
- Demo images in `docs/img/` are real, complete outputs of the STORM CASTLE example run (see NOTICE.md).

Scheme: `VERSION` file = single source of truth (`X.Y.Z`); commit `vX.Y.Z: summary`; git tag `vX.Y.Z`; the GitHub Release
is built by CI from the tag. Entries below are newest first. `python scripts/release.py check` keeps VERSION and this file in step.

## v1.1.1 — Clearer install: setups, ComfyUI + model steps, console and demo images

- README and INSTALL rewritten around setups (Full / Light / Remote ComfyUI): ComfyUI and models are clearly "not included", step-by-step ComfyUI + model install,
  "with Claude Code" and "without Claude" paths, console / thumbnail / lightbox images from an example map (`docs/img/`, see NOTICE.md). `doctor.bat --profile light` (or `PROMO_PROFILE=light`).
- `doctor.bat` now passes its arguments (`--profile light`); `intake.py` honours the light profile.

## v1.1.0 — Claude as orchestrator: step 0 intake, skills, one cinematic look, colour fix

- **Step 0 intake** (`scripts/intake.py`): asks for / checks island code, title, style, character identity, background, character PNG (transparency),
  gameplay recording, ffmpeg, ComfyUI and models; creates or reuses the map (`--init`); prints READY or the exact BLOCK/WARN fixes.
- **Skills** (`island-promo` orchestrator, `island-intake`, `island-images`, `island-video`, `island-review`) and slash commands `/island-new`, `/island-update`,
  `/island-console`. Reference copy in `scripts/claude_kit/`, mirrored into `.claude/` by `scripts/claude_sync.py` (your own `.claude/settings.json` is kept).
- **Claude starts everything for you:** `scripts/services.py` starts ComfyUI (own window, waits until ready) and the live console (opens the browser); `scripts/py.ps1` finds the right
  Python, so nobody has to double-click .bat files. A SessionStart hook (`scripts/session_start.py`) syncs the kit and announces new releases (same technique as the UEFN dream bot team kit).
- **Security (CodeQL alerts #1-#4 in `dashboard.py`):** files are served only by looking the name up in the real folder listing (no request text reaches a
  path), header values can no longer contain line breaks. CI actions moved to `actions/checkout@v5` / `actions/setup-python@v6` (Node 24).
- `update.py` also syncs the Claude kit after an update (or when already up to date).
- **Colour fix:** the bloom no longer shifts chroma (it caused the purple cast); softer warm grade, bloom 0.12.
- **Screenshots** get the same grade/bloom/vignette as the videos (full 1920x1080, no bars); the trailer's real clips get the full cinematic look.
- **One gameplay video:** the cinematic montage is slot 07; old `09_gameplay_cinematic*` files are moved to `_to_delete_stale/` automatically.
- `publish.bat` / `publish_skeleton.bat` (no PowerShell execution-policy problem); `cleanup.py` also covers `captures/_previous`; docs updated.

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
