# Security Policy

## Supported versions

Only the latest release of Island Promo Factory receives fixes. Please update to the newest
[GitHub Release](https://github.com/mimmo-the-root/island-promo-factory/releases) (`update.bat`) before reporting.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub:
[Report a vulnerability](https://github.com/mimmo-the-root/island-promo-factory/security/advisories/new).

Include: what is affected (script, `.bat` file, the live dashboard), steps to reproduce, and the impact you
expect. You can expect an acknowledgement within a few days and a fix or mitigation plan as soon as it is reproduced.

## Scope

In scope for this repo:

* The local dashboard (`scripts/dashboard.py`): it must only listen on `127.0.0.1`; e.g. path traversal, a way to
  trigger a run or variant from another web page, exposure beyond localhost, injection through displayed data.
* The updater (`scripts/update.py`, `update.bat`) and release tooling (`publish.ps1`, `.github/workflows`): e.g. unsafe
  extraction of a downloaded ZIP, overwriting user files (maps, brand files), running unverified code.
* Anything that could leak private data or protected material into the repo or a release: maps from `Projects/`,
  official badges or fonts, third-party artwork, API keys or tokens.
* Scripts that run on your machine (`.bat`, `scripts/*.py`) that could delete or overwrite files outside the project.

Out of scope: vulnerabilities in UEFN, Fortnite, ComfyUI, Qwen models, ffmpeg or other third-party software (report
those to their vendors), and issues in your own islands.

## Handling secrets

Never paste API keys, tokens, island codes you want to keep private or personal data into issues, pull requests
or screenshots. If you accidentally committed a secret, revoke it first, then tell us.
