import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Case "make my thumbnail conform": start from a thumbnail you already have instead of generating the artwork.

Usage: conform.py landscape|art|background --project SLUG [--source FILE]
  landscape   input/thumbnail_original.* (or --source) -> final/thumbnail_horizontal_title.png  (portal: landscape WITH text, 1920x1080 PNG < 5 MB)
  art         final/_untitle_raw.png (qwen_run.py untitle) -> final/thumbnail_horizontal.png    (portal: landscape art only, no text, 1920x1080)
  background  background/background_clean.png (qwen_run.py clean) -> fitted to 1920x1080 in place; the raw file is kept in background/_previous/
Rules: the image is never stretched. A 16:9 image of any size is scaled (LANCZOS); another ratio is centre-cropped to 16:9 first
(the crop is reported). Smaller than 1920 px wide: it is upscaled and a WARN says the detail will be soft. The original stays in input/.
Exit code 0 = written and valid, 1 = problem (reason printed), 2 = usage.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

import promo_project as pp

W, H = 1920, 1080
MAX_MB = 5
EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def find_source(proj, given=None):
    if given:
        f = Path(given)
        return f if f.is_file() else None
    for f in sorted((proj / "input").glob("thumbnail_original*")) if (proj / "input").is_dir() else []:
        if f.suffix.lower() in EXT:
            return f
    return None


def fit_16_9(im):
    """Return (image of exactly 1920x1080, note). Never stretches."""
    w, h = im.size
    notes = []
    target = W / H
    if abs(w / h - target) > 0.002:
        if w / h > target:
            nw = round(h * target)
            x0 = (w - nw) // 2
            im = im.crop((x0, 0, x0 + nw, h))
            notes.append("cropped %d px from the sides to reach 16:9" % (w - nw))
        else:
            nh = round(w / target)
            y0 = (h - nh) // 2
            im = im.crop((0, y0, w, y0 + nh))
            notes.append("cropped %d px from top/bottom to reach 16:9" % (h - nh))
    if im.size != (W, H):
        if im.size[0] < W:
            notes.append("upscaled from %d px wide: detail is softer than a native 1920 px image" % im.size[0])
        im = im.resize((W, H), Image.LANCZOS)
    return im, notes


def landscape(proj, source=None):
    src = find_source(proj, source)
    if src is None:
        print("BLOCK no thumbnail found: put it in %s as thumbnail_original.png (any image format)" % (proj / "input"))
        return 1
    im = Image.open(src)
    im.load()
    print("source: %s (%dx%d, %s)" % (src.name, im.size[0], im.size[1], im.mode))
    if im.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", im.size, (0, 0, 0))
        flat.paste(im.convert("RGBA"), mask=im.convert("RGBA").getchannel("A"))
        im = flat
    else:
        im = im.convert("RGB")
    out, notes = fit_16_9(im)
    dest = proj / "final" / "thumbnail_horizontal_title.png"
    dest.parent.mkdir(exist_ok=True)
    out.save(dest, "PNG", optimize=True)
    mb = dest.stat().st_size / 1048576
    for n in notes:
        print("WARN  " + n)
    if mb >= MAX_MB:
        print("BLOCK %s is %.1f MB (limit %d MB)" % (dest.name, mb, MAX_MB))
        return 1
    print("OK    %s %dx%d, %.1f MB  (landscape WITH text)" % (dest.relative_to(proj).as_posix(), W, H, mb))
    return 0


def _fit_file(src, dest, label):
    if not src.is_file():
        print("BLOCK missing %s" % src)
        return 1
    im = Image.open(src)
    im.load()
    print("source: %s (%dx%d)" % (src.name, im.size[0], im.size[1]))
    out, notes = fit_16_9(im.convert("RGB"))
    for n in notes:
        print("WARN  " + n)
    dest.parent.mkdir(exist_ok=True)
    out.save(dest, "PNG", optimize=True)
    mb = dest.stat().st_size / 1048576
    if mb >= MAX_MB:
        print("BLOCK %s is %.1f MB (limit %d MB)" % (dest.name, mb, MAX_MB))
        return 1
    print("OK    %s %dx%d, %.1f MB  (%s)" % (dest.parent.name + "/" + dest.name, W, H, mb, label))
    return 0


def art(proj):
    return _fit_file(proj / "final" / "_untitle_raw.png", proj / "final" / "thumbnail_horizontal.png", "landscape art only, no text")


def background(proj):
    import shutil
    src = proj / "background" / "background_clean.png"
    if not src.is_file():
        print("BLOCK missing %s" % src)
        return 1
    keep = proj / "background" / "_previous"
    keep.mkdir(exist_ok=True)
    raw = keep / "background_clean_raw.png"
    if not raw.exists():
        shutil.copy2(src, raw)
    return _fit_file(raw, src, "clean background, no characters")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["landscape", "art", "background"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--source")
    a = ap.parse_args()
    proj = pp.projects_dir() / a.project
    if not (proj / "config.json").exists():
        print("map '%s' not found in %s" % (a.project, pp.projects_dir()))
        return 2
    if a.what == "art":
        return art(proj)
    if a.what == "background":
        return background(proj)
    return landscape(proj, a.source)


if __name__ == "__main__":
    sys.exit(main())
