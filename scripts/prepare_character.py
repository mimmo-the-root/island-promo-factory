import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Turns a character render into a clean characters/character_01.png: tight crop + margin, sane size, no colour halos.

Usage: prepare_character.py <image> [--project SLUG] [--out PATH] [--max-height 2400] [--margin 0.06]
- A PNG with transparency is used as it is. Colours hidden under fully transparent pixels (green/white screens left by some
  exporters) are neutralised by resizing in premultiplied alpha, so no fringe appears on the edges.
- A fully opaque image on a flat background (all four corners the same colour) gets that colour keyed out.
Output: Projects/<map>/characters/character_01.png (or --out).
"""
import argparse
import os
from pathlib import Path

import numpy as np
from PIL import Image

import promo_project as pp


def key_flat_background(im, tol=38):
    a = np.array(im.convert("RGBA")).astype(np.int16)
    h, w = a.shape[:2]
    corners = [a[0, 0, :3], a[0, w - 1, :3], a[h - 1, 0, :3], a[h - 1, w - 1, :3]]
    if max(np.abs(c - corners[0]).max() for c in corners) > 12:
        return im, False
    dist = np.abs(a[..., :3] - corners[0]).max(axis=2)
    alpha = np.clip((dist - tol) * 255 / max(1, tol), 0, 255).astype(np.uint8)   # soft edge
    a[..., 3] = alpha
    return Image.fromarray(a.astype(np.uint8), "RGBA"), True


def prepare(src, dest, max_height=2400, margin=0.06):
    im = Image.open(src).convert("RGBA")
    alpha = np.array(im)[..., 3]
    note = "kept the existing transparency"
    if (alpha > 250).mean() > 0.995:                      # no real transparency
        im, keyed = key_flat_background(im)
        note = "keyed out the flat background" if keyed else "WARNING: no transparency and no flat background - cut the character out first"
        alpha = np.array(im)[..., 3]
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        raise SystemExit("the image is fully transparent")
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    m = int(max(x1 - x0, y1 - y0) * margin)
    canvas = Image.new("RGBA", (x1 - x0 + 2 * m, y1 - y0 + 2 * m), (0, 0, 0, 0))
    canvas.paste(im.crop((x0, y0, x1, y1)), (m, m))
    pm = canvas.convert("RGBa")                             # premultiplied: transparent pixels carry no colour
    if pm.height > max_height:
        s = max_height / pm.height
        pm = pm.resize((max(1, int(pm.width * s)), max_height), Image.LANCZOS)
    out = pm.convert("RGBA")
    out.save(dest)
    return out.size, note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--project", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-height", type=int, default=2400)
    ap.add_argument("--margin", type=float, default=0.06)
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    dest = Path(a.out) if a.out else pp.project_dir() / "characters" / "character_01.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    size, note = prepare(a.image, dest, a.max_height, a.margin)
    print("character ready: %s (%dx%d) - %s" % (dest, size[0], size[1], note))


if __name__ == "__main__":
    main()
