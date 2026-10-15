import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Similarity pre-check: does this map's thumbnail look too much like another of YOUR maps (or reuse the same skin)?

Epic compares new thumbnails with others' and your own live ones and refuses copies; this is a cheap local pre-check against your
other maps in Projects/. It never blocks: it prints OK / NOTE / WARN, and writes final/visual_profile.json + final/similarity.json.
Usage: similarity.py [--project SLUG] [--warn 0.18] [--note 0.28]
Profile of a map = perceptual hash (dHash 16x16 of the art-only landscape thumbnail), brightness, 3 dominant colours, skin, style.
Distance 0 = identical picture, ~0.5 = unrelated. Not a guarantee about Epic's own check (it also compares with other creators' islands).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import promo_project as pp


def thumb_of(proj):
    pack = proj / "promo_pack"
    for pat in ("02_landscape_art_only*", "01_landscape_with_text*"):
        f = next(iter(sorted(pack.glob(pat))), None) if pack.is_dir() else None
        if f:
            return f
    f = proj / "final" / "thumbnail_horizontal.png"
    return f if f.exists() else None


def dhash(im, n=16):
    g = im.convert("L").resize((n + 1, n), Image.LANCZOS)
    px = np.asarray(g).ravel().tolist()
    bits = []
    for y in range(n):
        for x in range(n):
            bits.append(1 if px[y * (n + 1) + x] > px[y * (n + 1) + x + 1] else 0)
    return "".join(map(str, bits))


def profile(proj):
    f = thumb_of(proj)
    if f is None:
        return None
    with Image.open(f) as im:
        im = im.convert("RGB")
        small = im.resize((96, 54))
        pal = small.quantize(3, method=Image.MEDIANCUT).convert("RGB").getcolors(96 * 54)
        top = [("#%02x%02x%02x" % c[1]) for c in sorted(pal, reverse=True)[:3]]
        luma = float(np.asarray(small.convert("L")).mean())
        h = dhash(im)
    try:
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    return {"map": proj.name, "file": f.name, "hash": h, "luma": round(luma, 1), "palette": top,
            "skin": cfg.get("default_skin") or "", "style": cfg.get("style", "")}


def distance(a, b):
    return sum(x != y for x, y in zip(a["hash"], b["hash"])) / float(len(a["hash"]))


def compare(me, others, warn=0.18, note=0.28):
    """[(level, message)] - level in WARN / NOTE."""
    out = []
    for o in others:
        d = distance(me, o)
        if d < warn:
            out.append(("WARN", "thumbnail of '%s' looks very similar to '%s' (distance %.2f): change pose, framing, colours or background" % (me["map"], o["map"], d)))
        elif d < note:
            out.append(("NOTE", "thumbnail resembles '%s' somewhat (distance %.2f)" % (o["map"], d)))
        if me["skin"] and o["skin"] and me["skin"] == o["skin"]:
            out.append(("NOTE", "same skin as '%s' (%s): consider another hero so the maps do not look alike" % (o["map"], me["skin"])))
        if me["style"] and me["style"] == o["style"] and me["palette"][:1] == o["palette"][:1]:
            out.append(("NOTE", "same title style and main colour as '%s'" % o["map"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--warn", type=float, default=0.18)
    ap.add_argument("--note", type=float, default=0.28)
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    me = profile(proj)
    if me is None:
        print("similarity: no thumbnail yet - nothing to compare")
        return
    (proj / "final").mkdir(exist_ok=True)
    (proj / "final" / "visual_profile.json").write_text(json.dumps(me, indent=2), encoding="utf-8")
    others = []
    for name in pp.list_maps():
        if name == proj.name:
            continue
        p = profile(pp.projects_dir() / name)
        if p:
            others.append(p)
    res = compare(me, others, a.warn, a.note)
    for lvl, msg in res:
        print("%-4s  %s" % (lvl, msg))
    if not res:
        print("OK    no look-alike among your %d other map(s) with a thumbnail" % len(others))
    (proj / "final" / "similarity.json").write_text(json.dumps({"compared_with": [o["map"] for o in others], "findings": res,
                                                                 "profile": me}, indent=2), encoding="utf-8")
    print("(local pre-check only: Epic also compares with other creators' islands)")


if __name__ == "__main__":
    main()
