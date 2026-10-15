# Run and rerun

`run_all.bat my-map` runs every stage and prints the timings: images, music, video cut, trailer, promo pack, lightbox, similarity check. Add `--no-qwen` if you have no ComfyUI.

## Reruns are cheap

A stage is redone only when something upstream changed. The kit hashes each stage's inputs (your files, the kit version, the options that matter) and skips the stage when nothing changed and its outputs are still there. Change the title and only the stages after it run again. `python scripts\stage_cache.py --project my-map` shows what is stored.

## Flags you will use

| Flag | Effect |
|---|---|
| `--no-cache` | Redo every stage, even if nothing changed |
| `--redo-all` | Move the old results aside (nothing is deleted) and rebuild everything |
| `--redo-portrait` | Rebuild the portrait art |
| `--redo-video` | Rebuild the gameplay cut and what depends on it |
| `--skip-images`, `--skip-video` | Leave those stages alone |
| `--social` | Also make the optional social media content ([Social videos](ch:social-videos)) |
| `--review-prompt` | Show and edit the Qwen prompt before generating |

> **Tip** In Claude Code, `/promo-redo my-map` does the clean rebuild for you.

## When a stage fails

The run stops at the failed stage and says which. Read `last_run_all.log`, fix that one thing and run again: the stages before it are skipped by the cache.
