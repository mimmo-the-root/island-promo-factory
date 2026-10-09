import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Lightbox: one board with numbered previews of what the kit produced, sizes underneath (a photographer's proof sheet).

Usage: lightbox.py [--cols 3] [--width 2000] [--out PATH]
Reads Projects/<map>/promo_pack/ (images + videos; the 3 screenshots become ONE tile numbered like their files, e.g. 09),
each tile carries the number of its file (01..09) so you can say "upload 01, 03, 07",
writes promo_pack/lightbox.png. Same look as the live console. Use it to show the results without publishing the full-size
files, or to pick the numbers you want to upload.
"""
import argparse
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import promo_project as pp
import version as V
import video_tools as vt

BG = (7, 8, 13)
PANEL = (15, 17, 26)
LINE = (34, 38, 57)
TXT = (233, 235, 245)
DIM = (124, 130, 156)
C1, C2, C3 = (34, 225, 255), (164, 91, 255), (255, 79, 163)
OK = (55, 230, 160)


def font(size):
    cands = sorted((pp.ROOT / "Resources" / "brand" / "font").glob("*.[ot]tf")) + [pp.ROOT / "Resources" / "fonts" / "LilitaOne-Regular.ttf"]
    for p in cands:
        try:
            return ImageFont.truetype(str(p), size)
        except OSError:
            continue
    return ImageFont.load_default()


def mono(size):
    for n in ("DejaVuSansMono-Bold.ttf", "consolab.ttf", "Menlo.ttc", "cour.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return font(size)


def gradient(w, h, stops=(C1, C2, C3)):
    xs = np.linspace(0, 1, max(w, 2))
    seg = xs * (len(stops) - 1)
    i = np.minimum(seg.astype(int), len(stops) - 2)
    t = (seg - i)[:, None]
    a, b = np.array(stops, dtype=np.float32)[i], np.array(stops, dtype=np.float32)[i + 1]
    row = (a + (b - a) * t).astype(np.uint8)
    return Image.fromarray(np.broadcast_to(row[None, :, :], (h, len(xs), 3)).copy(), "RGB").resize((w, h))


def gradient_text(img, xy, text, f, anchor="la"):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255, anchor=anchor)
    box = mask.getbbox()
    if box:
        g = gradient(box[2] - box[0], box[3] - box[1])
        img.paste(g, (box[0], box[1]), mask.crop(box))


def checker(size, step=16):
    im = Image.new("RGB", size, (30, 33, 46))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(44, 48, 66))
    return im


def label(name):
    parts = Path(name).stem.split("_")
    if parts and parts[0].isdigit():
        parts = parts[1:]
    parts = [p for p in parts if not (p[:1].isdigit() and "x" in p)]
    return " ".join(parts).upper()


def rounded_mask(size, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=r, fill=255)
    return m


def number_of(f, fallback):
    """Tile number = the number at the start of the file name (01_..., 09_...)."""
    head = f.name.split("_", 1)[0]
    return int(head) if head.isdigit() else fallback


def screenshot_tile(shots):
    """One preview image for all screenshots: the first big on the left, the others stacked on the right."""
    ims = [Image.open(s).convert("RGB") for s in shots[:3]]
    bw, bh = 1102, 620
    sw, sh = 550, 309
    canvas = Image.new("RGB", (bw + 10 + sw, bh), (15, 17, 26))
    canvas.paste(ims[0].resize((bw, bh), Image.LANCZOS), (0, 0))
    for k, im in enumerate(ims[1:3]):
        canvas.paste(im.resize((sw, sh), Image.LANCZOS), (bw + 10, k * (sh + 2)))
    out = Path(tempfile.gettempdir()) / "lb_screenshots.png"
    canvas.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--width", type=int, default=2000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    pack = pp.project_dir() / "promo_pack"
    allf = sorted([f for f in list(pack.glob("*.png")) + list(pack.glob("*.mp4")) if f.name != "lightbox.png"])
    shots = [f for f in allf if "screenshot" in f.name.lower()]
    files = [f for f in allf if f not in shots]
    over = {}                                   # tile overrides: number, caption, size text
    if shots:
        tri = screenshot_tile(shots)
        files.append(tri)
        over[tri] = {"num": number_of(shots[0], len(files)), "label": "SCREENSHOTS (%d)" % len(shots),
                     "dims": "%d x 1920 x 1080 px" % len(shots), "mb": sum(s.stat().st_size for s in shots) / 1048576.0}
    files.sort(key=lambda f: over[f]["num"] if f in over else number_of(f, 0))
    if not files:
        raise SystemExit("no files in %s - run the promo pack first" % pack)
    cfg = pp.load_config()
    title = str(cfg.get("title", pp.project_name())).upper()

    W, pad, gap, head = a.width, 48, 30, 210
    cell_w = (W - 2 * pad - gap * (a.cols - 1)) // a.cols
    box_h = int(cell_w * 0.70)
    cap_h = 104
    cell_h = box_h + cap_h
    rows = (len(files) + a.cols - 1) // a.cols
    H = head + rows * cell_h + (rows - 1) * gap + pad + 40

    sheet = Image.new("RGB", (W, H), BG)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for x in range(0, W, 44):  # faint grid, fading downwards
        od.line([(x, 0), (x, H)], fill=(34, 38, 57, 70))
    for y in range(0, H, 44):
        od.line([(0, y), (W, y)], fill=(34, 38, 57, 70))
    fade = Image.linear_gradient("L").resize((W, H))
    ov.putalpha(Image.eval(Image.composite(Image.new("L", (W, H), 255), Image.new("L", (W, H), 0), fade.point(lambda v: 255 - v)), lambda v: v).point(lambda v: int(v * 0.55)))
    for cx, col in ((int(W * 0.12), C2), (int(W * 0.9), C1)):  # soft colour glows behind the header
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([cx - 520, -420, cx + 520, 300], fill=col + (46,))
        from PIL import ImageFilter
        sheet.paste(Image.alpha_composite(sheet.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(120))).convert("RGB"))
    sheet.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(sheet)

    # header
    gradient_text(sheet, (pad, 40), "ISLAND PROMO FACTORY", mono(24))
    d.text((pad, 84), title, font=font(78), fill=TXT)
    n_vid = sum(1 for f in files if f.suffix == ".mp4")
    right = "KIT LIGHTBOX"
    gradient_text(sheet, (W - pad, 44), right, font(40), anchor="ra")
    d.text((W - pad, 98), "%d assets  -  %d video  -  v%s  -  %s" % (len(allf), n_vid, V.read_version(), time.strftime("%Y-%m-%d")),
           font=mono(22), fill=DIM, anchor="ra")
    d.text((W - pad, 130), "pick the numbers you want to upload", font=mono(20), fill=DIM, anchor="ra")
    sheet.paste(gradient(W - 2 * pad, 3), (pad, head - 28))

    for i, f in enumerate(files):
        r, c = divmod(i, a.cols)
        x, y = pad + c * (cell_w + gap), head + r * (cell_h + gap)
        card = Image.new("RGB", (cell_w, cell_h), PANEL)
        cd = ImageDraw.Draw(card)
        is_vid = f.suffix.lower() == ".mp4"
        extra = ""
        if is_vid:
            ffmpeg, ffprobe = vt.find_tool("ffmpeg", "FFMPEG_PATH"), vt.find_tool("ffprobe", "FFPROBE_PATH")
            info = vt.probe(ffprobe, f)
            tmp = Path(tempfile.gettempdir()) / ("lb_%s.png" % f.stem)
            subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", "%.2f" % (info["duration"] * 0.3), "-i", str(f), "-frames:v", "1", str(tmp)])
            im = Image.open(tmp).convert("RGB")
            im.load()
            extra = "  |  %d s" % round(info["duration"])
            w, h = info["width"], info["height"]
        else:
            im = Image.open(f)
            w, h = im.size
        ov_ = over.get(f, {})
        mb = ov_.get("mb", f.stat().st_size / 1048576.0)
        scale = min((cell_w - 28) / w, (box_h - 28) / h)
        tw, th = max(1, int(w * scale)), max(1, int(h * scale))
        t_im = im.convert("RGBA").resize((tw, th), Image.LANCZOS)
        base = checker((tw, th)) if (im.mode == "RGBA" and not is_vid) else Image.new("RGB", (tw, th))
        base.paste(t_im, (0, 0), t_im)
        if is_vid:
            pd = ImageDraw.Draw(base, "RGBA")
            cx, cy, rr = tw // 2, th // 2, max(22, th // 7)
            pd.ellipse([cx - rr - 4, cy - rr - 4, cx + rr + 4, cy + rr + 4], outline=C1 + (230,), width=3)
            pd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(5, 8, 14, 170))
            pd.polygon([(cx - rr // 3, cy - rr // 2), (cx - rr // 3, cy + rr // 2), (cx + rr // 2, cy)], fill=(255, 255, 255, 240))
        px, py = (cell_w - tw) // 2, 14 + (box_h - 28 - th) // 2
        shadow = Image.new("RGBA", (tw + 40, th + 40), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle([20, 26, tw + 20, th + 26], fill=(0, 0, 0, 150))
        from PIL import ImageFilter
        card.paste(shadow.filter(ImageFilter.GaussianBlur(10)), (px - 20, py - 20), shadow.filter(ImageFilter.GaussianBlur(10)))
        card.paste(base, (px, py))
        cd.rectangle([px - 1, py - 1, px + tw, py + th], outline=(52, 58, 84))
        # number pill (gradient) + caption
        pill = gradient(64, 34)
        pm = rounded_mask((64, 34), 17)
        card.paste(pill, (14, 14), pm)
        cd.text((14 + 32, 14 + 17), "%02d" % ov_.get("num", number_of(f, i + 1)), font=mono(20), fill=(6, 8, 14), anchor="mm")
        cd.text((cell_w // 2, box_h + 12), ov_.get("label", label(f.name)), font=font(30), fill=TXT, anchor="ma")
        cd.text((cell_w // 2, box_h + 56), ("%s  |  %.2f MB" % (ov_["dims"], mb)) if ov_ else "%d x %d px%s  |  %.2f MB" % (w, h, extra, mb), font=mono(20), fill=DIM, anchor="ma")
        cd.ellipse([cell_w - 34, 20, cell_w - 22, 32], fill=OK)  # portal spec checked by the promo pack
        # top accent bar and rounded card with border
        card.paste(gradient(cell_w, 4), (0, 0))
        m = rounded_mask((cell_w, cell_h), 18)
        sheet.paste(card, (x, y), m)
        ImageDraw.Draw(sheet).rounded_rectangle([x, y, x + cell_w - 1, y + cell_h - 1], radius=18, outline=LINE, width=2)

    d = ImageDraw.Draw(sheet)
    d.text((W // 2, H - 34), "made with Island Promo Factory  -  open source, free  -  github.com/mimmo-the-root/island-promo-factory",
           font=mono(18), fill=DIM, anchor="mm")
    out = Path(a.out) if a.out else pack / "lightbox.png"
    for attempt in range(5):  # a file briefly locked (antivirus, cloud sync) must not fail the whole run
        try:
            sheet.save(out)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1.5)
    print("lightbox: %s (%dx%d, %d assets)" % (out, sheet.width, sheet.height, len(allf)))


if __name__ == "__main__":
    main()
