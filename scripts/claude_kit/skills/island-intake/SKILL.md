---
name: island-intake
description: Step 0 of Island Promo Factory - collect and verify the prerequisites for a map (island code, title, background, character, recording), create or reuse the map project, and confirm everything is READY before the pipeline starts.
---

# Island intake (step 0)

Goal: a map project that `scripts/intake.py` reports as READY. Ask only for what is missing, in the user's language, a few questions at a time.

## 1. Which map?
Run `PY intake.py` to list the existing maps. Ask: new map or an existing one? For an existing map go to step 3 (check only).

## 2. New map - ask for
1. **Island code** (format `1234-5678-9012`) - shown on the trailer end card and in the upload checklist.
2. **Title** exactly as shown in Discover (it is drawn on the thumbnails).
3. **Title style** (default SCI_FI; see `Resources/brand/brand.json`).
4. **Character identity** in one sentence: what must be preserved exactly (helmet/face/hair, armor, weapon, companion). Nothing else may be invented.
5. Then create it:
   `PY intake.py --project <slug> --init --title "TITLE" --island-code 1234-5678-9012 --style SCI_FI --identity "..."`
   (slug = lowercase title with dashes).

## 3. Assets the user must provide (put them in `Projects/<slug>/`)
| What | Where | Rule |
|---|---|---|
| Environment | `background/background.png` | island capture without characters, at least 1920 px wide |
| ONE character | `characters/character_01.png` | transparent PNG with a small margin; a render on a flat background works: `PY prepare_character.py <image> --project <slug>` |
| Gameplay recording | `captures/gameplay/<any name>.mp4` | 5+ minutes, 1080p, game UI visible; without it gameplay, trailer clips and screenshots are skipped |
| Own music (optional) | `audio/music.mp3` | otherwise the kit generates original music |
Originals the user gives you stay in `input/`; work on copies.

## 4. Verify
Run `PY intake.py --project <slug>` (add `--json` if you want to parse it). Fix every **BLOCK** with the user, mention every **WARN** (ComfyUI off = no AI artwork; start it with `PY services.py comfy` or use `--no-qwen`). Repeat until it prints **READY**, then hand back to `island-promo`.
