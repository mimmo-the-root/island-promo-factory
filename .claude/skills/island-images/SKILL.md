---
name: island-images
description: Island Promo Factory image stage - review the Qwen prompt, run the image pipeline (art, title, logo, thumbnails), handle quality-gate failures and generate A/B variants.
---

# Images

Prerequisite: intake says READY. ComfyUI must be running for AI art (you start it: `PY services.py comfy`, it waits until ComfyUI answers); otherwise use `--no-qwen`.

1. **Prompt control**: `PY run_all.py --project <slug> --review-prompt` shows the final Qwen prompt before anything is generated. The user may edit it (saved as `Projects/<slug>/qwen_prompt_custom.txt`). Per-map additions live in `config.json` under `prompt.extra` (do this) and `prompt.avoid` (never add this).
2. **Run**: `PY run_all.py --project <slug>` (everything) or `PY factory.py --project <slug>` (images only). One character per thumbnail; landscape = full body, portrait = half bust.
3. **Quality gate**: Qwen output is rejected and retried (new seed, up to 3 tries) when it contains invented text, extra objects or creatures, or the character leaves the left zone. If all tries fail, read `last_qwen.log`, adjust `prompt.avoid`/identity in `config.json`, rerun. `PROMO_SEED=N` fixes the seed; `PROMO_DEBUG=1` adds diagnostics.
4. **Variants B/C** (different seed, A is never touched): dashboard buttons (the live console) or `PY variant.py --project <slug> --name B [--seed N]`. Results land in `Projects/<slug>/variants/<name>/`.
5. Validate with `PY validate_project.py --project <slug>`; sizes and the 200 px safe area must pass.

Output: `final/` (art, thumbnails, logo) and, after the promo pack stage, `promo_pack/01..06`.
