import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Per-stage cache for run_all: a stage is redone only when something upstream of it changed.

A stage's key is the SHA-256 of its inputs (file contents; for files over 64 MB: size + three 4 MB samples), the kit version and the
flags that change its result. After a successful run the key is stored in Projects/<map>/final/stage_cache.json together with the
output files. Next run: same key AND every output still exists and is not empty -> the stage is skipped.
Ignored (always redone): --redo-all, --no-cache, a changed input, a missing output, another kit version.
Usage: stage_cache.py [--project SLUG] [--clear]       shows the stored stages (or forgets them with --clear)
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIG = 64 * 1024 * 1024
SAMPLE = 4 * 1024 * 1024

# stage -> input patterns (relative to the map; "@" = relative to the kit) and outputs (relative to the map)
STAGES = {
    "images": {"in": ["config.json", "input/**/*", "background/background.*", "characters/**/*", "title/**/*", "@Resources/brand/**/*", "@Resources/prompts/**/*", "@workflows/**/*"],
               "out": ["final/thumbnail_horizontal_title.png", "final/thumbnail_vertical_title.png", "final/island_logo.png"]},
    "trailer": {"in": ["config.json", "captures/clips/**/*", "audio/music.*", "final/artwork.png", "final/artwork_vertical.png", "final/island_logo.png",
                       "badges/**/*", "@Resources/badges/**/*"],
                "out": ["final/trailer.mp4"]},
    "promo pack": {"in": ["config.json", "final/*.png", "background/lobby_background.png", "final/trailer.mp4", "captures/gameplay/gameplay.mp4",
                          "captures/screenshots/**/*", "badges/**/*"],
                   "out": ["promo_pack/UPLOAD_CHECKLIST.md"]},
    "lightbox": {"in": ["promo_pack/*"], "out": ["promo_pack/lightbox.png"]},
}
EXCLUDE = {"lightbox.png"}      # an output of the lightbox stage is not one of its inputs


def file_digest(p):
    h = hashlib.sha256()
    size = p.stat().st_size
    h.update(str(size).encode())
    with open(p, "rb") as f:
        if size <= BIG:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        else:
            for pos in (0, size // 2 - SAMPLE // 2, size - SAMPLE):
                f.seek(max(0, pos))
                h.update(f.read(SAMPLE))
    return h.hexdigest()


def expand(proj, patterns, root=ROOT):
    files = set()
    for pat in patterns:
        base, pat = (root, pat[1:]) if pat.startswith("@") else (Path(proj), pat)
        for f in base.glob(pat):
            if f.is_file() and f.name not in EXCLUDE and "__pycache__" not in f.parts:
                files.add(f)
    return sorted(files)


def stage_key(proj, stage, extra="", root=ROOT):
    spec = STAGES[stage]
    h = hashlib.sha256()
    h.update(("%s|%s|" % (stage, extra)).encode())
    try:
        h.update((Path(root) / "VERSION").read_bytes())
    except OSError:
        pass
    for f in expand(proj, spec["in"], root):
        base = root if str(f).startswith(str(root)) and not str(f).startswith(str(proj)) else proj
        try:
            rel = f.relative_to(base).as_posix()
        except ValueError:
            rel = f.name
        h.update(("\n%s:%s" % (rel, file_digest(f))).encode())
    return h.hexdigest()


def cache_path(proj):
    return Path(proj) / "final" / "stage_cache.json"


def load(proj):
    try:
        return json.loads(cache_path(proj).read_text(encoding="utf-8"))
    except Exception:
        return {}


def hit(proj, stage, key):
    """True when this exact input set already produced this stage's outputs and they are all still there."""
    entry = load(proj).get(stage)
    if not entry or entry.get("key") != key:
        return False
    return all((Path(proj) / o).is_file() and (Path(proj) / o).stat().st_size > 0 for o in STAGES[stage]["out"])


def store(proj, stage, key):
    d = load(proj)
    d[stage] = {"key": key, "when": time.strftime("%Y-%m-%d %H:%M:%S"), "outputs": STAGES[stage]["out"]}
    Path(proj, "final").mkdir(exist_ok=True)
    cache_path(proj).write_text(json.dumps(d, indent=2), encoding="utf-8")


def forget(proj, stage=None):
    d = load(proj)
    if stage:
        d.pop(stage, None)
    else:
        d = {}
    cache_path(proj).write_text(json.dumps(d, indent=2), encoding="utf-8")


def main():
    import promo_project as pp
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    if a.clear:
        forget(proj)
        print("stage cache cleared for %s" % proj.name)
        return
    d = load(proj)
    for st in STAGES:
        e = d.get(st)
        print("%-11s %s" % (st, ("stored %s" % e["when"]) if e else "not stored (runs next time)"))


if __name__ == "__main__":
    main()
