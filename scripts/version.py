import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Version helpers: installed version, git commit, latest GitHub release, changelog sections.

The single source of truth is the VERSION file at the repo root (plain "X.Y.Z"). Git tags are "vX.Y.Z",
CHANGELOG.md entries are "## vX.Y.Z - title" (newest on top), commits start with "vX.Y.Z: ...".
Env: PROMO_FACTORY_REPO (default mimmo-the-root/island-promo-factory), PROMO_NO_UPDATE_CHECK=1 disables network checks.
"""
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("PROMO_FACTORY_REPO", "mimmo-the-root/island-promo-factory")
CACHE_FILE = ROOT / ".update_cache.json"
CACHE_AGE = 6 * 3600
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def read_version(root=ROOT):
    try:
        v = (Path(root) / "VERSION").read_text(encoding="utf-8").strip()
        return v if SEMVER.match(v) else "0.0.0"
    except OSError:
        return "0.0.0"


def parse(v):
    m = SEMVER.match(str(v).strip())
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def is_newer(a, b):
    """True when version a is newer than b."""
    return parse(a) > parse(b)


def git_commit(root=ROOT):
    if not (Path(root) / ".git").exists():
        return ""
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _get(url, timeout=6):
    if not url.startswith("https://api.github.com/"):
        raise ValueError("refusing non-GitHub URL")
    req = urllib.request.Request(url, headers={"User-Agent": "promo-factory-update", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(2_000_000))


def fetch_latest(repo=REPO, timeout=6):
    """Latest release as {"tag","zip","name"}; falls back to the highest vX.Y.Z tag. None on any failure."""
    try:
        rel = _get("https://api.github.com/repos/%s/releases/latest" % repo, timeout)
        return {"tag": rel["tag_name"], "zip": rel.get("zipball_url", ""), "name": rel.get("name") or rel["tag_name"]}
    except Exception:
        pass
    try:
        tags = [t["name"] for t in _get("https://api.github.com/repos/%s/tags?per_page=100" % repo, timeout) if SEMVER.match(t["name"])]
        if tags:
            tag = max(tags, key=parse)
            return {"tag": tag, "zip": "https://api.github.com/repos/%s/zipball/%s" % (repo, tag), "name": tag}
    except Exception:
        pass
    return None


def cached_latest():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8")).get("latest")
    except Exception:
        return None


def latest_release(force=False):
    """Network check at most every 6 h (cached); never raises, returns None when unknown/offline."""
    if os.environ.get("PROMO_NO_UPDATE_CHECK") == "1":
        return None
    try:
        c = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if not force and time.time() - c.get("checked", 0) < CACHE_AGE:
            return c.get("latest")
    except Exception:
        pass
    latest = fetch_latest()
    try:
        CACHE_FILE.write_text(json.dumps({"checked": time.time(), "latest": latest}), encoding="utf-8")
    except OSError:
        pass
    return latest


def info(check=False):
    cur = read_version()
    latest = latest_release() if check else cached_latest()
    tag = (latest or {}).get("tag", "")
    return {"version": cur, "commit": git_commit(), "latest": tag.lstrip("v") if tag else "",
            "newer": bool(tag) and is_newer(tag, cur)}


def changelog_sections(text):
    """[(version, heading, body)] from CHANGELOG.md text (headings '## vX.Y.Z - title' or '## X.Y.Z - title')."""
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+\.\d+)\s*[-—–:]*\s*(.*)$", line)
        if m:
            cur = [m.group(1), m.group(2).strip(), []]
            out.append(cur)
        elif cur is not None:
            cur[2].append(line)
    return [(v, t, "\n".join(b).strip()) for v, t, b in out]


def changelog_between(text, old, new):
    """Sections with old < version <= new, newest first."""
    return [s for s in changelog_sections(text) if is_newer(s[0], old) and not is_newer(s[0], new)]


if __name__ == "__main__":
    i = info(check="--check" in _sys.argv)
    print("Island Promo Factory v%s%s" % (i["version"], (" (" + i["commit"] + ")") if i["commit"] else ""))
    if i["latest"]:
        print("latest release: v%s%s" % (i["latest"], "  -> update available (run update.bat)" if i["newer"] else "  (up to date)"))
