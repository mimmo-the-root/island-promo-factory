---
description: Rebuild the whole promo package of a map from scratch - first cleans (old results are moved to final/_previous, nothing is lost), then runs the pipeline again
allowed-tools: Bash(powershell:*), Bash(python:*), Bash(python3:*)
---

Rebuild everything for the map named in $ARGUMENTS (if none is given: the only map, or list them with `py.ps1 intake.py` and ask which).

1. Say in one line what will happen: the previous results (promo pack, trailer, logo, lobby background, gameplay cut, screenshots, generated music) are MOVED to `final/_previous/<time>_redo/` and everything is built again. The user's inputs, art, characters, own music file and source recordings are never touched.
2. Decide the artwork: a map in the conform case or whenever the user says "keep the art" -> add `--no-qwen`. A standard map that should get NEW AI artwork -> no `--no-qwen` (takes several minutes, ComfyUI must be running: `PY services.py comfy`). If the user did not say, keep the art (`--no-qwen`) and mention that new artwork needs "with new artwork".
3. Run, from the repo root: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/py.ps1 run_all.py --project <slug> --redo-all [--no-qwen] --ui`
   (`--skip-video` leaves the video stages out.) Never delete anything yourself.
4. When it ends, report in two lines: what was rebuilt (see `promo_pack/`), anything that failed, and where the old results are. Offer to open the console (`/promo-console`).
