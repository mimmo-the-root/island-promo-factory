import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Font check: can the title font draw every character of the title and the island code? (empty boxes on a thumbnail are rejected)

Usage: font_check.py [--project SLUG]      exit 1 when a character of the island code or title cannot be drawn.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from PIL import ImageFont

import promo_project as pp

ROOT = Path(__file__).resolve().parent.parent


def font_files():
    out = []
    for d in (ROOT / "Resources" / "brand" / "font", ROOT / "Resources" / "fonts"):
        if d.is_dir():
            out += [p for p in sorted(d.iterdir()) if p.suffix.lower() in (".ttf", ".otf")]
    return out


def missing(font_file, text):
    font = ImageFont.truetype(str(font_file), 48)
    return sorted({c for c in text if not c.isspace() and not font.getmask(c).getbbox()})


def check(title, code, fonts=None):
    """(font name or None, missing characters) for the first font that works, else for the first font."""
    fonts = fonts if fonts is not None else font_files()
    if not fonts:
        return None, ["<no font file found>"]
    first = None
    for f in fonts:
        m = missing(f, title + code)
        if first is None:
            first = (f.name, m)
        if not m:
            return f.name, []
    return first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    cfg = pp.load_config()
    name, miss = check(str(cfg.get("title", "")), str(cfg.get("island_code", "")))
    if miss:
        print("WARN  font %s cannot draw: %s - change the title or put a font with these characters in Resources/brand/font/" % (name, " ".join(miss)))
        sys.exit(1)
    print("OK    font %s draws the whole title and the island code" % name)


if __name__ == "__main__":
    main()
