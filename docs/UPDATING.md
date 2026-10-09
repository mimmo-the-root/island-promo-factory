# Versions and updates

## With Claude Code (recommended)
Open this folder in Claude Code. At every start the kit mirrors its skills into `.claude/` and checks GitHub (cached 6 h, silent offline):
if a newer release exists Claude tells you and offers `/promo-update`. That command runs `scripts/update.py` for you. Same technique as the UEFN dream
bot team kit: a reference copy (`scripts/claude_kit/`) travels with every update, the start-up hook syncs it into `.claude/`, your own settings are kept.
First time after upgrading from v1.0.0: run `update.bat` once more (or `python scripts/claude_sync.py`) so the hook and skills are installed.

## For users: get the newest version
- The console (opened by `run_all.bat`) shows your version next to the title and an amber banner when a newer release exists.
- **Update:** double-click `update.bat` (or `python scripts/update.py`). It downloads the newest GitHub Release, replaces the
  code and docs, and prints what changed. Check only: `update.bat --check`.
- Safe by design: it **never touches** `Projects/`, `Resources/brand/`, `Resources/badges/`, `Resources/audio/`, your models or logs.
  Every replaced file is first copied to `_update_backup/<timestamp>/`.
- **Stage area and rollback:** each update keeps the downloaded release and the version you leave in `_releases/` (last 5, never overwritten). `update.bat --list` shows them; `update.bat --rollback` returns to the previous one, `update.bat --rollback 1.1.1` to a named one (also to move forward again). Maps and brand files are never touched.
- If you installed with `git clone`, use `git pull` instead (the updater tells you so).
- Offline? Download the release zip from GitHub and run `python scripts/update.py --zip that-file.zip`.
- No network checks at all: set `PROMO_NO_UPDATE_CHECK=1`.

## For maintainers: ship a version
One scheme, enforced by CI: `VERSION` (X.Y.Z) -> CHANGELOG entry `## vX.Y.Z - title` -> commit `vX.Y.Z: title` -> tag `vX.Y.Z` -> Release.
1. `python scripts/release.py bump patch|minor|major` (raises `VERSION`, adds an empty CHANGELOG entry).
2. Fill in the CHANGELOG entry (one line per change).
3. `python scripts/release.py check` (VERSION and CHANGELOG agree).
4. Commit as `vX.Y.Z: title`, push, tag `vX.Y.Z`, push the tag (`python scripts/release.py ship` prints the commands, `publish.ps1` runs them).
5. GitHub Actions runs the tests; only if they pass it creates the GitHub Release with the zip and the notes from the CHANGELOG.
Semver: patch = fixes, minor = new features that keep working maps working, major = something users must change.
