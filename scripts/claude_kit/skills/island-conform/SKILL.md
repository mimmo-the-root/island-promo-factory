---
name: island-conform
description: Case "make my thumbnail conform" - the user already has a finished thumbnail and wants the portal-ready files made from it instead of generating new artwork. Use when the user says they already have a thumbnail / old thumb and wants it made compliant.
---

# Make my thumbnail conform

The user brings a finished thumbnail (usually WITH the title drawn in). Goal: the files the Creator Portal asks for, made from it.
Same rules as `island-promo` (you run every command, one change at a time, English release text). Use `PY` as defined there.

Entry points: `/island-conform`, or `/island-new` -> new map -> "make my existing thumbnail conform".

## Steps
1. **Map**: list maps (`PY intake.py`); ask in plain text: continue a map or new? New: ask only island code + title, create it with `PY intake.py --project <slug> --init --title "..." --island-code ...`, open the live console (`PY services.py console --project <slug>`).
2. **Thumbnail**: tell the user to put it in `Projects/<slug>/input/` (any file name and image format; say the folder's absolute path). Wait, or let them come back later (`/island-new` or `/island-conform` -> continue the map). Copy/rename it to `input/thumbnail_original.<ext>`; never edit the original.
3. **Look at it** (Read tool): which text is the title, who is the hero (the player character, equipped, usually facing the centre) and who is the enemy / creature, what is the environment. If it is unclear who the hero is, ask ONE question.
4. **Landscape WITH text** (available now): `PY conform.py landscape --project <slug>` -> `final/thumbnail_horizontal_title.png`, 1920x1080 PNG < 5 MB. 16:9 images are scaled, other ratios are centre-cropped (reported), small images are upscaled with a WARN (detail will be soft). Show the result to the user.
5. **Not built yet - say so plainly, do not fake it**: landscape WITHOUT text (title removed), portrait with/without text (needs the clean background and the hero extracted from the thumbnail), logo, lobby background. If the user asks for them, explain what is missing and offer the normal case (`island-promo`) with a separate background and character image.

Limits to tell the user: a character cut by the image border has hard edges when extracted; removing the title and the characters from a finished image and rebuilding what is behind them has to be judged on the real image.
