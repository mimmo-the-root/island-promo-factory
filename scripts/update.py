import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Update Island Promo Factory to the newest GitHub release (code and docs only; your maps and brand files are never touched).

Usage: update.py [--check] [--zip FILE] [--force] [--root DIR] [--list] [--rollback [VERSION]]
  --check   print installed and latest version, change nothing
  --zip     use a release zip you already downloaded (offline / tests)
  --force   apply even if the release is not newer, or when this folder is a git clone (normally: use `git pull`)
  --root    install folder to update (default: this one; used by the tests)
  --list    show the stored copies in _releases/
  --rollback [VERSION]  go back to a stored copy (default: the newest one older than the installed version)
Stage area: every release you download is kept as _releases/v<version>.zip, and the version you are leaving is stored there
too before an update replaces it, so you can always roll back (last 5 copies kept; never overwritten, never deleted below that).
Replaced: scripts/, workflows/, docs/, tests/, Resources/prompts/, Resources/fonts/, the root .bat files and docs (README, CHANGELOG, VERSION...).
NEVER replaced: Projects/, Resources/brand/, Resources/badges/, Resources/audio/, models, logs.
Every replaced file is first copied to _update_backup/<timestamp>/. Download: HTTPS to api.github.com only, 80 MB cap, zip paths checked.
"""
import argparse
import io
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import version as V

CAP = 80 * 1024 * 1024
MANAGED_DIRS = ("scripts/", "workflows/", "docs/", "tests/", "Resources/prompts/", "Resources/fonts/")
MANAGED_FILES = {"README.md", "LICENSE", "NOTICE.md", "CHANGELOG.md", "CONTRIBUTING.md", "CLAUDE.md", "VERSION",
                 "run_all.bat", "run_factory.bat", "run_trailer.bat", "run_vertical.bat", "new_map.bat", "update.bat"}


KEEP = 5


def releases_dir(root):
    return Path(root) / "_releases"


def stage_zip(root, version, data):
    """Keep a release zip in the stage area (_releases/v<version>.zip). An existing copy is never overwritten."""
    d = releases_dir(root)
    d.mkdir(exist_ok=True)
    f = d / ("v%s.zip" % version)
    if not f.exists():
        f.write_bytes(data)
    return f


def snapshot_installed(root, cur):
    """Store the installed managed files as _releases/v<cur>.zip (if that copy is not there yet), so a rollback is always possible."""
    root = Path(root)
    f = releases_dir(root) / ("v%s.zip" % cur)
    if f.exists():
        return f
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if managed(rel) and "__pycache__" not in rel:
                z.write(p, rel)
    return stage_zip(root, cur, buf.getvalue())


def stored(root):
    """[(version, path)] newest first."""
    out = []
    d = releases_dir(root)
    for f in d.glob("v*.zip") if d.is_dir() else []:
        v = f.stem[1:]
        if V.SEMVER.match(v):
            out.append((v, f))
    out.sort(key=lambda x: tuple(int(i) for i in x[0].split(".")), reverse=True)
    return out


def prune(root, keep=KEEP):
    for v, f in stored(root)[keep:]:
        try:
            f.unlink()
        except OSError:
            pass


def managed(rel):
    return rel in MANAGED_FILES or rel.startswith(MANAGED_DIRS)


def download(url):
    if not url.startswith("https://api.github.com/"):
        raise ValueError("refusing non-GitHub URL")
    req = urllib.request.Request(url, headers={"User-Agent": "promo-factory-update"})
    with urllib.request.urlopen(req, timeout=60) as r:  # GitHub redirects to its own codeload host
        data = r.read(CAP + 1)
    if len(data) > CAP:
        raise ValueError("download larger than %d MB" % (CAP // 1048576))
    return data


def members(z):
    """[(zip name, relative path)] for the managed files; strips the single top folder GitHub adds."""
    names = [n for n in z.namelist() if not n.endswith("/")]
    for n in names:
        p = Path(n)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("unsafe path in zip: %s" % n)
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    strip = len(tops) == 1 and not any("/" not in n for n in names)
    out = []
    for n in names:
        rel = n.split("/", 1)[1] if strip else n
        if managed(rel):
            out.append((n, rel))
    return out


def apply_zip(data, root, version_hint=""):
    root = Path(root)
    z = zipfile.ZipFile(io.BytesIO(data))
    mem = members(z)
    if not any(r == "VERSION" for _, r in mem):
        raise ValueError("this zip has no VERSION file: not a Island Promo Factory release")
    new_ver = z.read(next(n for n, r in mem if r == "VERSION")).decode("utf-8").strip()
    if not V.SEMVER.match(new_ver):
        raise ValueError("bad VERSION in the zip: %r" % new_ver)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = root / "_update_backup" / stamp
    changed = added = 0
    for n, rel in mem:
        content = z.read(n)
        dst = root / rel
        if dst.exists():
            if dst.read_bytes() == content:
                continue
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup / rel)
            changed += 1
        else:
            added += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(content)
    return new_ver, changed, added, (backup if changed else None), z


def _sync_claude(root):
    """Mirror scripts/claude_kit/ into .claude/ (skills, commands, start-up hook)."""
    try:
        import claude_sync
        ch = claude_sync.sync(root)
        if ch:
            print("Claude kit: %d change(s) - open a NEW Claude session to load them." % len(ch))
    except Exception as e:
        print("Claude kit sync skipped (%s)" % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--zip", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--root", default=str(V.ROOT))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--rollback", nargs="?", const="", default=None, metavar="VERSION")
    a = ap.parse_args()
    root = Path(a.root)
    cur = V.read_version(root)
    print("Installed: Island Promo Factory v%s" % cur)

    if a.list or a.rollback is not None:
        have = stored(root)
        if a.list or not have:
            print("Stored copies (_releases/): %s" % (", ".join("v" + v for v, _ in have) or "none yet - they are created by the next update"))
            return
        want = a.rollback.lstrip("vV")
        if want:
            pick = [x for x in have if x[0] == want]
        else:
            pick = [x for x in have if V.is_newer("v" + cur, x[0])]
            pick = pick[:1]
        if not pick:
            print("No stored copy to go back to (have: %s)." % ", ".join("v" + v for v, _ in have))
            sys.exit(1)
        if (root / ".git").exists() and not a.force:
            print("This folder is a git clone: go back with `git checkout v%s` (or use --force to overwrite the managed files)." % pick[0][0])
            return
        snapshot_installed(root, cur)
        new_ver, changed, added, backup, z = apply_zip(pick[0][1].read_bytes(), root)
        print("\nROLLED BACK to v%s: %d file(s) replaced, %d added. v%s stays in _releases/ (re-apply with --rollback %s)." % (new_ver, changed, added, cur, cur))
        if backup:
            print("The files you had before: %s" % backup)
        _sync_claude(root)
        return

    if a.zip:
        data, tag = Path(a.zip).read_bytes(), "(local zip)"
    else:
        latest = V.latest_release(force=True)
        if not latest:
            print("Could not reach GitHub (offline, or no release published yet). Nothing changed.")
            sys.exit(0 if a.check else 1)
        tag = latest["tag"]
        print("Latest release: %s" % tag)
        if not V.is_newer(tag, cur) and not a.force:
            print("You are up to date.")
            _sync_claude(root)
            return
        if a.check:
            print("Update available. Run update.bat (or: python scripts/update.py).")
            return
        data = None
    if (root / ".git").exists() and not a.force:
        print("This folder is a git clone: update it with `git pull` (or `git fetch --tags && git checkout %s`)." % tag)
        print("Use --force to overwrite the managed files from the release zip anyway.")
        _sync_claude(root)
        return
    if data is None:
        print("Downloading %s ..." % tag)
        data = download(latest["zip"])
    try:
        snapshot_installed(root, cur)       # stage area: the version we leave, for --rollback
        pv = zipfile.ZipFile(io.BytesIO(data))
        pm = members(pv)
        stage_zip(root, pv.read(next(n for n, rr in pm if rr == "VERSION")).decode("utf-8").strip(), data)
        prune(root)
    except Exception as e:
        print("Stage area skipped (%s)" % e)
    new_ver, changed, added, backup, z = apply_zip(data, root)
    if not V.is_newer(new_ver, cur) and not a.force:
        print("The zip holds v%s, which is not newer than v%s. Nothing applied beyond identical files." % (new_ver, cur))
    print("\nUPDATED to v%s: %d file(s) replaced, %d added." % (new_ver, changed, added))
    if backup:
        print("Previous versions of the replaced files: %s" % backup)
    print("Not touched: Projects/, Resources/brand/, Resources/badges/, models, logs.")
    print("Roll back any time: update.bat --rollback   (stored copies: update.bat --list)")
    _sync_claude(root)
    try:
        text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        for v, title, body in V.changelog_between(text, cur, new_ver):
            print("\n== v%s - %s ==\n%s" % (v, title, body))
    except OSError:
        pass
    print("\nRestart the dashboard / close this window before the next run.")


if __name__ == "__main__":
    main()
