# Update

Run `update.bat`. It downloads the newest release (HTTPS, GitHub only), keeps the version you leave in `_releases\` and copies every replaced file to `_update_backup\` first. Your maps, brand files, badges, audio and models are never touched.

- `update.bat --check` only says whether a newer release exists.
- `update.bat --list` shows the stored copies; `update.bat --rollback` goes back one version.
- In Claude Code, `/promo-update` does it and summarises what changed.

After an update the live console restarts on its own (unless a run is in progress), and the next Claude Code session tells you "updated from vA to vB". Open a new session to load updated skills and agents.

> **Note** If the folder is a git clone, `update.bat` tells you to use `git pull` instead; the start-up message still reports the new version.
