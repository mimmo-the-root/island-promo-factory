---
name: island-conform
description: Case "make my thumbnail conform" - the user already has a finished thumbnail and wants the portal-ready files made from it instead of generating new artwork. Use when the user says they already have a thumbnail / old thumb and wants it made compliant.
---

# Make my thumbnail conform

The user brings a finished thumbnail (usually WITH the title drawn in). Goal: the files the Creator Portal asks for, made from it.
Same rules as `island-promo` (you run every command, one change at a time, English release text). Use `PY` as defined there.

Entry points: `/promo-conform`, or `/promo-pack` -> new map -> "make my existing thumbnail conform".

## Steps
Run steps 4 to 9 in ONE go, one after the other, without waiting for the user in between; stop only when a step fails or a Qwen result is clearly bad (then say what and offer one retry). The user judges the whole package at the end, with the review step.

1. **Map**: list maps (`PY intake.py`); ask in plain text: continue a map or new? New: ask only island code + title, create it with `PY intake.py --project <slug> --init --title "..." --island-code ...`, open the live console (`PY services.py console --project <slug>`).
2. **Thumbnail**: tell the user to put it in `Projects/<slug>/input/` (any file name and image format; say the folder's absolute path). Wait, or let them come back later (`/promo-pack` or `/promo-conform` -> continue the map). If `input/` already holds ONE image and the user chose this case, that is the thumbnail: do not ask again. Copy/rename it to `input/thumbnail_original.<ext>`; never edit the original.
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
7. **The hero (EXPERIMENT)** - needed for the portrait. Write `Projects/<slug>/qwen_prompt_hero.txt` from what you SAW in step 3 (say which character is the hero and what must stay: face, outfit, weapon, items; everything else goes). Run through the wrapper: `PY activity.py run --project <slug> --label "Isolating the hero" --expected 200 -- qwen_run.py hero`, then `PY conform.py hero --project <slug>` -> `characters/character_01.png` (cut out, green removed). Open `characters/_hero_raw.png` and the cut-out and judge: same face/outfit/weapon as the thumbnail, no green fringe, nothing invented. A hero cut by the picture border is fine: the portrait uses the bust version. If bad, retry once with a stricter prompt (keep the first), then tell the user what is wrong.
8. **Make the clean background the working background**: `PY conform.py use-clean --project <slug>` (the original stays in `background/_previous/background_source.png`). Decide the title style from the artwork and the hero identity in one sentence from what you saw, and save them: `PY intake.py --project <slug> --init --style STYLE --identity "..."` (see island-intake step 3b: never leave the SCI_FI default).
9. **The rest of the package, automatically**: `PY run_all.py --project <slug> --conform --ui` (images stage = portrait with/without text from the clean background + hero, logo, lobby background; YOUR landscape files 01/02 are kept untouched; then gameplay scenes, trailer, screenshots, promo pack, lightbox). Without a gameplay recording the video stages are skipped, say so. When it finishes, hand over to `island-review`.

Limits to tell the user: the Qwen steps (title removal, clean background, hero) are experiments judged on the real image; the portrait uses the bust version of the hero over the clean background.

Other limits: a character cut by the image border has hard edges when extracted; removing the title and the characters from a finished image and rebuilding what is behind them has to be judged on the real image.
