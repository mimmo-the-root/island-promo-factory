import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Case "make my thumbnail conform": start from a thumbnail you already have instead of generating the artwork.

Usage: conform.py landscape|art|background|hero|use-clean|status --project SLUG [--source FILE]
  status      which conform steps are done, and the NEXT one (run it first when you resume a map; never redo a finished Qwen step by accident)
  landscape   input/thumbnail_original.* (or --source) -> final/thumbnail_horizontal_title.png  (portal: landscape WITH text, 1920x1080 PNG < 5 MB)
  art         title erased locally from final/thumbnail_horizontal_title.png -> final/thumbnail_horizontal.png (portal: art only, no text). --qwen uses final/_untitle_raw.png instead
  background  background/background_clean.png (qwen_run.py clean) -> fitted to 1920x1080 in place; the raw file is kept in background/_previous/
  hero        characters/_hero_raw.png (qwen_run.py hero: the hero on flat green) -> characters/character_01.png (cut out, green removed)
  use-clean   background/background_clean.png -> background/background.png (the original goes to background/_previous/background_source.png),
              so lobby background, portrait and the rest of the pipeline use the background WITHOUT title and characters
Rules: the image is never stretched. A 16:9 image of any size is scaled (LANCZOS); another ratio is centre-cropped to 16:9 first
(the crop is reported). Smaller than 1920 px wide: it is upscaled and a WARN says the detail will be soft. The original stays in input/.
Exit code 0 = written and valid, 1 = problem (reason printed), 2 = usage.
"""
import argparse
import json
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


def mark_case(proj):
    """The map is in the conform case: run_all / factory then keep your own landscape art and never regenerate the artwork with Qwen."""
    f = proj / "config.json"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8"))
        if cfg.get("case") != "conform":
            cfg["case"] = "conform"
            f.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def landscape(proj, source=None):
    mark_case(proj)
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


def find_title_box(a):
    import numpy as np
    h, w, _ = a.shape
    band = a[: int(h * 0.30)]
    white = band.min(axis=2) > 228
    cols = white.sum(axis=0)
    on = cols >= 3
    # merge gaps < 70 px into spans, keep the widest
    spans, s, gap = [], None, 0
    for x in range(w):
        if on[x]:
            if s is None: s = x
            gap = 0; e = x
        elif s is not None:
            gap += 1
            if gap > 70:
                spans.append((s, e)); s = None
    if s is not None: spans.append((s, e))
    spans = [sp for sp in spans if sp[1] - sp[0] >= w * 0.22]
    if not spans: return None
    x0, x1 = max(spans, key=lambda sp: sp[1] - sp[0])
    rows = white[:, x0:x1 + 1].sum(axis=1) >= 0.04 * (x1 - x0)
    best, cs, gap = None, None, 0
    runs = []
    for y in range(len(rows)):
        if rows[y]:
            if cs is None: cs = y
            gap = 0; ce = y
        elif cs is not None:
            gap += 1
            if gap > 12: runs.append((cs, ce)); cs = None
    if cs is not None: runs.append((cs, ce))
    if not runs: return None
    y0, y1 = max(runs, key=lambda r: r[1] - r[0])
    return x0, y0, x1, y1

def _up(est, shape):
    import numpy as np
    ch = [np.asarray(Image.fromarray(est[..., i].astype(np.float32), "F").resize((shape[1], shape[0]), Image.BILINEAR)) for i in range(3)]
    return np.stack(ch, axis=-1)


def push_pull_fill(img, mask):
    import numpy as np
    """Fill the masked pixels from their surroundings (multi-scale weighted average, smooth upsampling)."""
    wgt = (~mask).astype(np.float32)
    levels = []
    cur, cw = img * wgt[..., None], wgt
    while min(cur.shape[:2]) > 4:
        levels.append((cur, cw))
        hh, ww = cur.shape[0] // 2 * 2, cur.shape[1] // 2 * 2
        cur = cur[:hh, :ww].reshape(hh // 2, 2, ww // 2, 2, 3).sum((1, 3))
        cw = cw[:hh, :ww].reshape(hh // 2, 2, ww // 2, 2).sum((1, 3))
    tot = max(float(cw.sum()), 1e-6)
    mean = cur.sum((0, 1)) / tot
    est = np.where(cw[..., None] > 0, cur / np.maximum(cw[..., None], 1e-6), mean)
    for cur, cw in reversed(levels):
        up = _up(est, cur.shape[:2])
        est = np.where(cw[..., None] > 0.5, cur / np.maximum(cw[..., None], 1e-6), up)
    return est


def untitle_local(im):
    import numpy as np
    from PIL import ImageFilter
    a = np.asarray(im.convert("RGB"))
    box = find_title_box(a)
    if box is None: return None, None
    x0, y0, x1, y1 = box
    pad = 26
    X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad)
    sub = a[Y0:Y1, X0:X1].astype(np.float32)
    white = sub.min(axis=2) > 200
    dark = sub.max(axis=2) < 70
    core = Image.fromarray((white * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(21))
    near = np.asarray(core) > 128
    m = Image.fromarray((((white | dark) & near) * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MaxFilter(5))
    mask = np.asarray(m) > 128
    fill = push_pull_fill(sub, mask)
    # soft texture: add mild noise matching the surroundings
    rng = np.random.default_rng(1)
    out = np.where(mask[..., None], fill + rng.normal(0, 2.0, fill.shape), sub)
    soft = np.asarray(m.filter(ImageFilter.GaussianBlur(3))).astype(np.float32)[..., None] / 255
    res = sub * (1 - soft) + out * soft
    b = a.copy(); b[Y0:Y1, X0:X1] = np.clip(res, 0, 255).astype(np.uint8)
    return Image.fromarray(b), (X0, Y0, X1, Y1)


def art(proj, qwen=False):
    """Landscape art only. Default: the title is erased LOCALLY from your own landscape (everything else stays pixel-identical to your picture).
    --qwen: use final/_untitle_raw.png from qwen_run.py untitle (Qwen repaints the whole scene: moon, buildings and faces can change)."""
    dest = proj / "final" / "thumbnail_horizontal.png"
    if qwen:
        return _fit_file(proj / "final" / "_untitle_raw.png", dest, "landscape art only, no text (Qwen untitle)")
    # the user's OWN landscape: the saved copy first (the factory later rewrites final/thumbnail_horizontal_title.png with the kit title)
    cands = [proj / "final" / "_conform_keep" / "thumbnail_horizontal_title.png", proj / "final" / "thumbnail_horizontal_own_title.png",
             proj / "final" / "thumbnail_horizontal_title.png"]
    src = next((c for c in cands if c.is_file()), None)
    if src is None:
        print("BLOCK missing final/thumbnail_horizontal_title.png (run conform.py landscape first)")
        return 1
    im = Image.open(src).convert("RGB")
    out, box = untitle_local(im)
    if out is None:
        print("WARN  no title found in %s: the picture is used as it is (art only = your landscape)" % src.name)
        out = im
    else:
        print("title erased locally in the box %s" % (box,))
    dest.parent.mkdir(exist_ok=True)
    out.save(dest, "PNG", optimize=True)
    print("OK    final/thumbnail_horizontal.png %dx%d  (landscape art only, no text; the rest of the picture is untouched)" % out.size)
    return 0


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


def hero(proj):
    """Cuts the hero out of the flat-green Qwen render: flood fill from the border (green clothes inside the hero stay), soft edge, green spill removed."""
    import numpy as np
    from PIL import ImageDraw, ImageFilter
    import prepare_character as pc
    raw = proj / "characters" / "_hero_raw.png"
    if not raw.is_file():
        print("BLOCK missing %s (run qwen_run.py hero first)" % raw)
        return 1
    im = Image.open(raw).convert("RGB")
    w, h = im.size
    mark = (1, 2, 3)
    work = im.copy()
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)] + [(x, 0) for x in range(0, w, max(1, w // 24))] + \
            [(x, h - 1) for x in range(0, w, max(1, w // 24))] + [(0, y) for y in range(0, h, max(1, h // 24))] + \
            [(w - 1, y) for y in range(0, h, max(1, h // 24))]
    corners = np.array([im.getpixel(c) for c in seeds[:4]]).astype(np.int16)
    ref0 = np.median(corners, axis=0)
    for s in seeds:
        # only border pixels that look like the background: a hero cut by the border has its own pixels there
        if work.getpixel(s) != mark and np.abs(np.array(im.getpixel(s)).astype(np.int16) - ref0).max() <= 50:
            ImageDraw.floodfill(work, s, mark, thresh=70)
    bg = (np.array(work) == np.array(mark)).all(axis=2)
    # pockets of the same background colour ENCLOSED by the figure (between hair and an object, under an arm): the border flood fill misses them
    if bg.any():
        ref = np.array(im)[bg].mean(axis=0)
        near = (np.abs(np.array(im).astype(np.int16) - ref).max(axis=2) < 34) & ~bg
        near_img = Image.fromarray(near.astype(np.uint8) * 255, "L").filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
        pockets = 0
        tag = 128
        for _ in range(300):
            arr = np.array(near_img)
            pts = np.argwhere(arr == 255)
            if len(pts) == 0:
                break
            y0, x0 = pts[0]
            before = int((arr == tag).sum())
            ImageDraw.floodfill(near_img, (int(x0), int(y0)), tag)
            area = int((np.array(near_img) == tag).sum()) - before
            if area >= 600:                 # a real pocket, not a green detail of the outfit
                bg |= np.array(near_img.point(lambda v: 255 if v == tag else 0)) > 0
                pockets += 1
                near_img = near_img.point(lambda v: 0 if v == tag else v)
            else:
                near_img = near_img.point(lambda v: 0 if v == tag else v)
        if pockets:
            print("      removed %d enclosed pocket(s) of background colour" % pockets)
    if bg.mean() < 0.15:
        print("BLOCK the background is not a flat colour (only %.0f%% removed): the hero render is unusable, run qwen_run.py hero again" % (bg.mean() * 100))
        return 1
    mask = Image.fromarray((~bg).astype(np.uint8) * 255, "L").filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    a = np.array(im).astype(np.int16)
    edge = np.array(mask.filter(ImageFilter.MinFilter(15))) < 250         # band (about 7 px) near the border of the cut-out
    g_cap = np.maximum(a[..., 0], a[..., 2])
    spill = edge & (a[..., 1] > g_cap)
    # edge pixels that are still clearly the key colour (green fringe, glow mixed with green): drop them from the cut-out
    hard = edge & (a[..., 1] - g_cap > 35)
    mk = np.array(mask)
    mk[hard] = 0
    mask = Image.fromarray(mk, "L").filter(ImageFilter.GaussianBlur(0.8))
    a[..., 1] = np.where(spill, g_cap, a[..., 1])
    rgba = np.dstack([a.astype(np.uint8), np.array(mask)])
    cut = Image.fromarray(rgba, "RGBA")
    tmp = proj / "characters" / "_hero_cut.png"
    cut.save(tmp)
    size, note = pc.prepare(tmp, proj / "characters" / "character_01.png")
    try:
        tmp.unlink()
    except OSError:
        pass
    al = np.array(mask) > 128
    ys, xs = np.where(al)
    print("OK    characters/character_01.png %dx%d  (%s; hero fills %.0f%% of the render's height)" % (size[0], size[1], note, 100.0 * (ys.max() - ys.min()) / h))
    cut_sides = [n for n, v in (("left", xs.min() <= 4), ("right", xs.max() >= w - 5), ("top", ys.min() <= 4), ("bottom", ys.max() >= h - 5)) if v]
    cfgp = proj / "config.json"
    try:
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        if cfg.get("characters"):
            cfg["characters"][0]["complete"] = not cut_sides
            cfgp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    if cut_sides:
        print("CUT   the hero touches the %s border of the render: the figure is NOT complete. Rebuild it: add to qwen_prompt_hero.txt that the missing parts must be redrawn "
              "(full body, head to feet, whole figure inside the picture) and run qwen_run.py hero + conform.py hero again (keep the first result in characters/_previous/). "
              "If it is still cut, the portrait falls back to the bust version." % "/".join(cut_sides))
    else:
        print("OK    the hero is complete (not cut by the picture): the portrait uses the full figure")
    if al.mean() < 0.03:
        print("WARN  the hero is very small in the render, check it")
    return 0


def use_clean(proj):
    import shutil
    clean = proj / "background" / "background_clean.png"
    if not clean.is_file():
        print("BLOCK missing %s (run qwen_run.py clean + conform.py background first)" % clean)
        return 1
    bgf = proj / "background" / "background.png"
    keep = proj / "background" / "_previous"
    keep.mkdir(exist_ok=True)
    if bgf.exists() and not (keep / "background_source.png").exists():
        shutil.copy2(bgf, keep / "background_source.png")
    shutil.copy2(clean, bgf)
    print("OK    background/background.png = the clean background (original kept in background/_previous/background_source.png)")
    return 0


def status(proj):
    f = lambda *p: proj.joinpath(*p)
    has_thumb = any((proj / "input").glob("thumbnail_original*")) if (proj / "input").is_dir() else False
    steps = [
        ("thumbnail in input/", has_thumb, "put the thumbnail in input/"),
        ("landscape WITH text (conform.py landscape)", f("final", "thumbnail_horizontal_title.png").is_file(), "conform.py landscape"),
        ("landscape art only (conform.py art, local title removal, no Qwen)", f("final", "thumbnail_horizontal.png").is_file(), "conform.py art"),
        ("clean background (qwen_run.py clean + conform.py background)", f("background", "_previous", "background_clean_raw.png").is_file(), "qwen_run.py clean, then conform.py background"),
        ("hero cut-out (qwen_run.py hero + conform.py hero)", f("characters", "character_01.png").is_file(), "write qwen_prompt_hero.txt, qwen_run.py hero, then conform.py hero"),
        ("clean background is the working background (conform.py use-clean)", f("background", "_previous", "background_source.png").is_file(), "conform.py use-clean"),
        ("style + hero identity saved (intake.py --init --style --identity)", (json.loads(f("config.json").read_text(encoding="utf-8")).get("style_chosen") is True), "intake.py --init --style STYLE --identity \"...\""),
        ("package built (run_all.py --conform): promo_pack/ with the numbered files", f("promo_pack", "UPLOAD_CHECKLIST.md").is_file(), "run_all.py --project SLUG --conform --ui"),
    ]
    nxt = None
    for name, ok, how in steps:
        print("%-5s %s" % ("DONE" if ok else "TODO", name))
        if not ok and nxt is None:
            nxt = how
    print("\nNEXT: " + (nxt if nxt else "everything is done - hand over to the review step"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["landscape", "art", "background", "hero", "use-clean", "status"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--source")
    ap.add_argument("--qwen", action="store_true", help="art: use the Qwen untitle result instead of the local title removal")
    a = ap.parse_args()
    proj = pp.projects_dir() / a.project
    if not (proj / "config.json").exists():
        print("map '%s' not found in %s" % (a.project, pp.projects_dir()))
        return 2
    if a.what == "status":
        return status(proj)
    if a.what == "art":
        return art(proj, a.qwen)
    if a.what == "background":
        return background(proj)
    if a.what == "hero":
        return hero(proj)
    if a.what == "use-clean":
        return use_clean(proj)
    return landscape(proj, a.source)


if __name__ == "__main__":
    sys.exit(main())
