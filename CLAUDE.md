# Island Promo Factory — instructions for an AI coding agent

Goal: produce Creator-Portal-ready media for one UEFN map at a time. The user supplies inputs and checks the portal result.
Language: answer the user in their language; code and comments in English. Iterate one change at a time, say clearly when a fix is incomplete.

## Layout
- `scripts/` — `factory.py` (orchestrator), `qwen_run.py` (horizontal|vertical|clean), `upscale.py`, `title_composer.py`, `logo_composer.py`,
  `thumbnail_factory.py`, `validate_project.py`, `promo_pack.py`, `new_map.py`, `promo_project.py`, `comfy_common.py`,
  `lobby_background.py`, `prepare_vertical_background.py`, `qwen_prompt_builder.py`, `trailer_builder.py`, `video_validate.py`.
- `Resources/prompts/`, `Resources/brand/brand.json`, `Resources/fonts/`, `workflows/qwen_workflow_api.json`.
- `Projects/<map>/` — `input`, `background`, `characters`, `final`, `title`, `promo_pack`, `config.json`.

## Per map
1. `new_map.bat <slug> "TITLE"`; the user adds `background/background.png` and `characters/character_01.png` (transparent, with margin).
2. `run_factory.bat <slug>` (needs ComfyUI) or `python scripts/factory.py --project <slug> --no-qwen`.
3. `run_vertical.bat <slug>`; `run_trailer.bat <slug>`.
4. Read `last_run.log`, `last_qwen.log`, `last_trailer.log`. On failure fix ONE thing and rerun.
5. Review the images (one character, nothing floating or cut, title readable, bottom corners free, sizes valid) and write `Projects/<slug>/RUN_REPORT.md`.
6. Only after the user reports the portal result, start another map. No batch generation.

## Rules
- Never delete user files: move to `final/_previous/` or a `_to_delete_*` folder.
- Every stage must exit 0 AND create/update its output; scripts exit 1 with a clear message otherwise.
- Embedded Python ignores the script dir: scripts insert their own dir in `sys.path` first.
- Gameplay video is real and unedited: validate only (`video_validate.py --kind gameplay`).
- PEGI and "Developed in Fortnite" are video-only. Do not redistribute fonts/badges/franchise art you cannot license.
- Debug output behind `PROMO_DEBUG=1`. Run `python tests/smoke_test.py` after changes.

## Versioning (keep it consistent)
- Single source: `VERSION` (X.Y.Z). Every user-visible change: add a line to the top `CHANGELOG.md` entry (or `python scripts/release.py bump ...` for a new version).
- Commit `vX.Y.Z: summary`, tag `vX.Y.Z`; CI builds the Release. Run `python scripts/release.py check` and `python tests/test_version.py` before committing.
- `update.py` replaces only scripts/, workflows/, docs/, tests/, Resources/prompts+fonts, root docs/.bat files. If you add a new top-level folder that ships to users, add it to `MANAGED_DIRS` in `scripts/update.py`.
