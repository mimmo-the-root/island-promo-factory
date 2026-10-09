---
name: island-intake
description: Step 0 of Island Promo Factory - collect and verify the prerequisites for a map (island code, title, background, character, recording), create or reuse the map project, and confirm everything is READY before the pipeline starts.
---

# Island intake (step 0)

Goal: a map project that `scripts/intake.py` reports as READY. Ask only for what is missing, in the user's language, a few questions at a time.

## 1. Which map?
Run `PY intake.py` to list the existing maps. Ask: new map or an existing one? For an existing map go to step 3 (check only).

## 2. New map - ask ONLY for
1. **Island code** (format `1234-5678-9012`) - shown on the trailer end card and in the upload checklist.
2. **Title** exactly as shown in Discover (it is drawn on the thumbnails).
Nothing else. Do NOT ask for the title style or the character description: you decide them in step 3b from the images.
Create the map right away (slug = lowercase title with dashes):
`PY intake.py --project <slug> --init --title "TITLE" --island-code 1234-5678-9012`
The command prints the folders. Open the live console now (`PY services.py console --project <slug>`), so the user sees the map from the first minute.

## 3. Tell the user where each file goes (do not ask for paths)
Show the ABSOLUTE folder paths printed by intake (the map folder is `Projects/<slug>/`, next to the kit) and say what goes in each. **The file names in the table are only examples: any file name works** (any image format for the images, any video name), say so in your message. Then offer two ways on, in one short sentence: drop the files now and tell you when they are in, **or** leave and come back later - the map is saved, and the next `/promo-pack` ("continue an existing map") resumes exactly here with the intake check. Wait for the user's answer; do not start any stage without the files:
| What | Put it in | Rule |
|---|---|---|
| Environment | `background/` (any name, any image format) | island capture without characters, at least 1920 px wide |
| ONE character | `characters/` | transparent PNG with a small margin; a render on a flat background also works (you cut it out with `PY prepare_character.py <image> --project <slug>`) |
| Gameplay recording | `captures/gameplay/` | mp4, 5+ minutes, 1080p, game UI visible; without it gameplay, trailer clips and screenshots are skipped |
| Own music (optional) | `audio/` as `music.mp3` | otherwise the kit generates original music |
Whatever the user's names are, copy/rename the files to the standard names yourself (`background/background.png`, `characters/character_01.png`); originals stay in `input/`.

## 3b. Decide style and character yourself
Look at the background and the character image (Read tool). Then:
- **Style:** pick the title style that suits the artwork from `Resources/brand/brand.json` (`typography.styles`; for example SCI_FI for tech/space, FIRE for fire/war/lava, WHITE for clean/snow/light). Write it with `--style`.
- **Character identity:** write ONE sentence describing what you see and what must stay exactly as is (helmet/face/hair, armor, weapon, companion). Invent nothing.
Save both: `PY intake.py --project <slug> --init --style STYLE --identity "..."`. Tell the user the two choices in one line; change them only if the user objects.

## 4. Verify
Run `PY intake.py --project <slug>` (add `--json` if you want to parse it). Fix every **BLOCK** with the user, mention every **WARN** (ComfyUI off = no AI artwork; start it with `PY services.py comfy` or use `--no-qwen`). Repeat until it prints **READY**, then hand back to `island-promo`.
