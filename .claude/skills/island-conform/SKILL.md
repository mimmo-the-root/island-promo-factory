---
name: island-conform
description: Case "make my thumbnail conform" - the user already has a finished thumbnail and wants the portal-ready files made from it instead of generating new artwork. Use when the user says they already have a thumbnail / old thumb and wants it made compliant.
---

# Make my thumbnail conform

The user brings a finished thumbnail (usually WITH the title drawn in). Goal: the files the Creator Portal asks for, made from it.
Same rules as `island-promo` (you run every command, one change at a time, English release text). Use `PY` as defined there.

Entry points: `/promo-conform`, or `/promo-pack` -> new map -> "make my existing thumbnail conform".

## Steps
1. **Map**: list maps (`PY intake.py`); ask in plain text: continue a map or new? New: ask only island code + title, create it with `PY intake.py --project <slug> --init --title "..." --island-code ...`, open the live console (`PY services.py console --project <slug>`).
2. **Thumbnail**: tell the user to put it in `Projects/<slug>/input/` (any file name and image format; say the folder's absolute path). Wait, or let them come back later (`/promo-pack` or `/promo-conform` -> continue the map). Copy/rename it to `input/thumbnail_original.<ext>`; never edit the original.
3. **Look at it** (Read tool): which text is the title, who is the hero (the player character, equipped, usually facing the centre) and who is the enemy / creature, what is the environment. If it is unclear who the hero is, ask ONE question.
4. **Landscape WITH text** (available now): `PY conform.py landscape --project <slug>` -> `final/thumbnail_horizontal_title.png`, 1920x1080 PNG < 5 MB. 16:9 images are scaled, other ratios are centre-cropped (reported), small images are upscaled with a WARN (detail will be soft). Show the result to the user.
5. **Landscape art only (EXPERIMENT, text removed, characters STAY)** - this is portal field "landscape - image only". Tell the user it is a test.
   - Start ComfyUI if it is not running (`PY services.py comfy`; if it cannot start, say why and stop here).
   - Default prompts are in `Resources/prompts/qwen_prompt_untitle.txt` (+ negative). If this image needs different words, write `Projects/<slug>/qwen_prompt_untitle.txt` from what you SAW in step 3 (name the title text; keep every character, weapon, colour and light unchanged; add nothing).
   - Run (background, poll; a few minutes) THROUGH the activity wrapper so the live console shows progress: `PY activity.py run --project <slug> --label "Removing the title" --expected 240 -- qwen_run.py untitle`, then `PY conform.py art --project <slug>` -> `final/thumbnail_horizontal.png` (1920x1080).
   - Open it (Read tool) next to the original and judge honestly: title gone without residue, nothing else changed (characters, pose, house, moon), no new letters. Show it with a verdict in two lines. If it is bad, offer one retry with a stricter prompt (keep the first result in `final/_previous/`), then stop.
6. **Clean background for the portrait (EXPERIMENT, text AND characters removed)**:
   - If `background/` has no real capture, copy the thumbnail to `background/background.png` (never overwrite a real capture).
   - Write `Projects/<slug>/qwen_prompt_clean_background.txt` from what you SAW: name the title text and every character/creature to remove, tell Qwen to keep the house, tower, moon and sky in the SAME positions and fill only the removed areas; and `qwen_negative_clean_background.txt` (text, letters, logo, people, characters, creatures, weapon, extra objects, distorted architecture).
   - Run through the wrapper: `PY activity.py run --project <slug> --label "Cleaning the background" --expected 240 -- qwen_run.py clean`, then `PY conform.py background --project <slug>` (fits it to 1920x1080; the raw file stays in `background/_previous/`). Judge it like above: leftovers, new letters, moved or invented buildings. Keep the first attempt if you retry.
7. **Not built yet - say so plainly, do not fake it**: portrait versions (with/without text) from the clean background plus the hero extracted from the thumbnail, logo, lobby background. Offer them only after the user has judged steps 5 and 6.

Limits to tell the user: a character cut by the image border has hard edges when extracted; removing the title and the characters from a finished image and rebuilding what is behind them has to be judged on the real image.
