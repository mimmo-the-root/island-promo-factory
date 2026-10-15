import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""One small image with every picture of a map's promo pack, so a reviewer looks at ONE file instead of many big ones.

Usage: contact_sheet.py [--project SLUG] [--out FILE] [--width 1600] [--cols 3] [FILE ...]
Default inputs: Projects/<map>/promo_pack/*.png|jpg (lightbox.png excluded). Output: Projects/<map>/final/contact_sheet.jpg
Each tile is labelled with its file name and original size. Nothing is modified.
"""
import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import promo_project as pp

EXT = {".png", ".jpg", ".jpeg"}


def build(files, out, width=1600, cols=3):
    files = [Path(f) for f in files]
    if not files:
        raise ValueError("no images to show")
    cols = max(1, min(cols, len(files)))
    gap, label_h = 8, 18
    tile_w = (width - gap * (cols + 1)) // cols
    tiles = []
    for f in files:
        with Image.open(f) as im:
            size = im.size
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (40, 40, 40, 255))
            bg.alpha_composite(im)           # transparent logo shown on dark grey
            im = bg.convert("RGB")
        r = tile_w / im.width
        im = im.resize((tile_w, max(1, int(im.height * r))))
        tiles.append((f.name, size, im))
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    row_h = [max(t[2].height for t in r) + label_h for r in rows]
    sheet = Image.new("RGB", (width, sum(row_h) + gap * (len(rows) + 1)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = gap
    for r, h in zip(rows, row_h):
        x = gap
        for name, size, im in r:
            sheet.paste(im, (x, y + label_h))
            d.text((x, y + 3), "%s  %dx%d" % (name, size[0], size[1]), fill=(230, 230, 230))
            x += tile_w + gap
        y += h + gap
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=85)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    files = a.files or sorted(f for f in (proj / "promo_pack").glob("*") if f.suffix.lower() in EXT and f.name != "lightbox.png")
    out = a.out or str(proj / "final" / "contact_sheet.jpg")
    try:
        build(files, out, a.width, a.cols)
    except Exception as e:
        print("contact_sheet: %s" % e)
        sys.exit(1)
    print("contact sheet (%d images): %s" % (len(files), out))


if __name__ == "__main__":
    main()
