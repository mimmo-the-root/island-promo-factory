---
name: island-promo
description: Orchestrates Island Promo Factory for ONE UEFN map end to end - intake, ComfyUI and live console start, images, video, review, portal checklist. Use when the user wants to prepare or redo the Discover assets (thumbnails, logo, gameplay, trailer, screenshots) of a map, or asks for a new package.
---

# Island Promo - orchestrator

You drive the whole pipeline for ONE map at a time. Never start a second map before the user reports the Creator Portal result of the first.
Chat with the user in their language; code and comments in English. Iterate one change at a time and say clearly when a fix is incomplete.
**You run every command yourself. The user must never be asked to double-click a .bat file or open a terminal.**

## How to run a kit script
`PY` below means: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/py.ps1` (it finds the right Python). Example:
`PY intake.py --project my-map`. Run from the repo root. Long jobs (full run: about 2 minutes without Qwen, 6-8 with it): start them in the background and
poll `last_run_all.log` every 20-30 s, telling the user briefly what stage it is in; do not block silently.

## Which case?
For a NEW map ask, right after island code and title (plain text, one question): **make new artwork** from separate images (the order below), or **make my existing thumbnail conform** (the user already has a finished thumbnail)? For the second load `island-conform` instead and continue there (the map is already created). For an existing map the case is already known from what it contains (`input/thumbnail_original.*` = conform case).

## Order (do not skip, do not reorder)
0. **Version**: run `PY update.py --check` FIRST (do not rely on the start-up hook, its message may not be visible) and tell the user the result in one line. If a newer release exists, offer `/promo-update` (one question), then continue.
1. **Step 0 - intake**: load `island-intake`. FIRST list the existing maps (`PY intake.py`) and ask in plain text, as the very first question: continue one of these maps, or start a new one? (Do not use a question widget for this; a normal message is enough.) For an existing map skip to the checks and ask what the user wants to redo. For a new map ask only for island code and title, create the map, **open the live console immediately** (`PY services.py console --project <slug>`; tell the user it stays open and updates live), say where each input file goes, wait for the files, decide style and character description from the images, run `PY intake.py --project <slug>` until READY. Nothing else starts before that.
2. **ComfyUI** (only if the run uses AI art, after READY): `PY services.py comfy` - opens its own window and waits until it answers. If it cannot start, say why and offer `--no-qwen`.
3. **Images**: load `island-images`.
4. **Video**: load `island-video`.
5. **Review**: load `island-review` (look at every output, write `RUN_REPORT.md`, hand over the pack and the upload checklist).
6. Wait for the user's portal result. Only then offer the next map.

## Ground rules
- **The live console must show what is happening.** A full run (`run_all`) is tracked by itself. Any other long step (a Qwen run, a video cut, an upscale) goes through `PY activity.py run --project <slug> --label "What it does" --expected <seconds> -- <script.py> [args]`: it shows the step, progress and the map's own log in the console. Never leave the console empty while you work.
- Every stage must exit 0 AND create or update its output. On failure: read `last_run_all.log`, fix ONE thing, rerun that stage only.
- Never delete the user's files: move them to a `_to_delete_*` folder and say so.
- Debug output behind `PROMO_DEBUG=1`.
- Legal: never add Epic/Fortnite/third-party art, fonts or badges to the repo; the age-rating (ESRB) and "Developed in Fortnite" badges are video-only and never distorted; music is the generated one or the user's own.
- The portal's gameplay slot may require real, unedited gameplay. The default look is cinematic (edited); `--gameplay-look off` gives the unedited cut. Tell the user which one is in the pack.
- Versioning: when you change kit code, bump `VERSION` (`PY release.py bump patch|minor`), fill the CHANGELOG entry, run `PY release.py check` and `PY ../tests/smoke_test.py` before telling the user it is done.
