---
description: Update Island Promo Factory to the newest GitHub release (code, docs and the Claude kit; maps and brand files are never touched)
allowed-tools: Bash(powershell:*), Bash(python:*), Bash(python3:*)
---

Run, from the repo root: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/py.ps1 update.py` (add `--check` first if the user only wants to know).
If the folder is a git clone it will say so: then run `git pull` instead (tell the user what you are doing).
Report in one or two lines: the old and the new version and what changed (the updater prints the CHANGELOG sections).
If files changed, remind the user to open a NEW Claude session so the updated skills load. Do not change anything else.
