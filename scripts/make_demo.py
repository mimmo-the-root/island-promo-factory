import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Creates the `demo` map: original, procedurally drawn art (no AI models, no third-party IP, no downloads).

Usage: make_demo.py [--force] [--background FILE --character FILE] [--title "MY TITLE"]
With --background/--character your own images are used instead of the drawn ones (the character is cleaned by prepare_character.py).
Result: <Projects>/demo with background, one character, a ready horizontal artwork and config.json, so a fresh install can run
    run_all.bat demo --no-qwen
and see the whole kit (thumbnails, logo, trailer, promo pack, lightbox) in about two minutes, with or without a GPU.
"""
import json
import math
import random
import shutil
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import promo_project as pp

W, H = 2060, 1151


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background():
    rnd = random.Random(7)
    y = np.linspace(0, 1, H)[:, None, None]
    top, mid, low = np.array([10, 8, 38]), np.array([120, 40, 120]), np.array([255, 120, 90])
    t = np.clip(y / 0.62, 0, 1)
    sky = np.where(t < 0.55, top + (mid - top) * (t / 0.55), mid + (low - mid) * ((t - 0.55) / 0.45))
    img = Image.fromarray(np.repeat(sky, W, axis=1).astype("uint8"), "RGB")
    d = ImageDraw.Draw(img)
    for _ in range(420):                                     # stars
        x, yy = rnd.randrange(W), rnd.randrange(int(H * 0.5))
        r = rnd.choice((1, 1, 1, 2))
        c = rnd.randrange(150, 255)
        d.ellipse([x, yy, x + r, yy + r], fill=(c, c, 255))
    glow = Image.new("RGB", (W, H), (0, 0, 0))              # moon + glow
    g = ImageDraw.Draw(glow)
    mx, my, mr = int(W * 0.72), int(H * 0.30), 150
    g.ellipse([mx - mr * 2, my - mr * 2, mx + mr * 2, my + mr * 2], fill=(90, 60, 140))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = ImageChops.add(img, glow)
    d = ImageDraw.Draw(img)
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 226, 200))
    for cx, cy, cr in ((mx - 50, my - 40, 34), (mx + 55, my + 30, 24), (mx + 10, my - 70, 16)):
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(236, 200, 180))
    for k, (base, amp, col) in enumerate(((0.62, 90, (58, 30, 92)), (0.68, 120, (40, 22, 74)), (0.74, 90, (24, 14, 52)))):
        ph = rnd.random() * 10
        pts = [(0, H)]
        for x in range(0, W + 20, 20):
            v = math.sin(x / 210 + ph) * 0.6 + math.sin(x / 83 + ph * 2) * 0.4
            pts.append((x, int(H * base + v * amp)))
        pts.append((W, H))
        d.polygon(pts, fill=col)
    floor_y = int(H * 0.80)                                  # arena floor with perspective grid
    d.rectangle([0, floor_y, W, H], fill=(20, 12, 40))
    vx = W * 0.5
    for i in range(-14, 15):
        d.line([(vx + i * 40, floor_y), (vx + i * 330, H)], fill=(120, 70, 190), width=2)
    for j in range(1, 9):
        yy = floor_y + (H - floor_y) * (j / 8) ** 1.7
        d.line([(0, yy), (W, yy)], fill=(120, 70, 190), width=2)
    glow = Image.new("RGB", (W, H), (0, 0, 0))              # glowing floor cracks
    g = ImageDraw.Draw(glow)
    for _ in range(9):
        x, yy = rnd.randrange(W), rnd.randrange(floor_y + 40, H - 10)
        pts = [(x, yy)]
        for _ in range(5):
            x += rnd.randrange(-60, 60)
            yy += rnd.randrange(-14, 14)
            pts.append((x, yy))
        g.line(pts, fill=(255, 150, 60), width=4)
    img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(5)))
    for _ in range(7):                                       # floating crystals
        cx, cy = rnd.randrange(int(W * 0.45), W - 80), rnd.randrange(int(H * 0.45), int(H * 0.76))
        s = rnd.randrange(24, 58)
        cg = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(cg).ellipse([cx - s * 2, cy - s * 2, cx + s * 2, cy + s * 2], fill=(30, 120, 160))
        img = ImageChops.add(img, cg.filter(ImageFilter.GaussianBlur(26)))
        d = ImageDraw.Draw(img)
        d.polygon([(cx, cy - s * 1.6), (cx + s * 0.7, cy), (cx, cy + s * 1.6), (cx - s * 0.7, cy)], fill=(120, 230, 255))
        d.polygon([(cx, cy - s * 1.6), (cx + s * 0.7, cy), (cx, cy)], fill=(190, 250, 255))
    return img


def character():
    """An original armoured sentinel with a glowing visor and an energy blade, transparent PNG with margins."""
    S = 2                                                     # draw at 2x, then downscale for smooth edges
    w, h = 760 * S, 1320 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w // 2
    metal, dark, edge, glow = (74, 96, 126), (36, 46, 66), (14, 18, 30), (80, 255, 230)

    def shape(pts, fill, width=7 * S):
        d.polygon(pts, fill=fill, outline=edge, width=width)

    def box(x0, y0, x1, y1, fill, r=26 * S):
        d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill, outline=edge, width=7 * S)

    for sx in (-1, 1):                                        # legs
        box(cx + sx * 40 * S - 62 * S, 760 * S, cx + sx * 40 * S + 62 * S, 1040 * S, metal)
        box(cx + sx * 40 * S - 56 * S, 1040 * S, cx + sx * 40 * S + 56 * S, 1230 * S, dark)
        shape([(cx + sx * 40 * S - 78 * S, 1230 * S), (cx + sx * 40 * S + 78 * S, 1230 * S), (cx + sx * 40 * S + sx * 40 * S, 1296 * S), (cx + sx * 40 * S - 78 * S, 1296 * S)], metal)
    box(cx - 170 * S, 560 * S, cx + 170 * S, 790 * S, metal, 40 * S)   # torso + belt
    box(cx - 128 * S, 600 * S, cx + 128 * S, 700 * S, dark, 28 * S)
    d.ellipse([cx - 34 * S, 618 * S, cx + 34 * S, 686 * S], fill=glow, outline=edge, width=6 * S)
    box(cx - 176 * S, 760 * S, cx + 176 * S, 826 * S, dark, 22 * S)
    for sx in (-1, 1):                                        # shoulders + arms
        shape([(cx + sx * 150 * S, 520 * S), (cx + sx * 300 * S, 560 * S), (cx + sx * 330 * S, 690 * S), (cx + sx * 190 * S, 660 * S)], metal)
        box(cx + sx * 250 * S - 54 * S, 660 * S, cx + sx * 250 * S + 54 * S, 880 * S, dark)
        d.ellipse([cx + sx * 250 * S - 58 * S, 870 * S, cx + sx * 250 * S + 58 * S, 960 * S], fill=metal, outline=edge, width=7 * S)
    d.rectangle([cx + 300 * S - 12 * S, 330 * S, cx + 300 * S + 12 * S, 930 * S], fill=(210, 220, 235), outline=edge, width=5 * S)   # energy blade
    blade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(blade).rectangle([cx + 300 * S - 22 * S, 300 * S, cx + 300 * S + 22 * S, 900 * S], fill=glow + (200,))
    im = Image.alpha_composite(im, blade.filter(ImageFilter.GaussianBlur(14 * S)))
    d = ImageDraw.Draw(im)
    d.rectangle([cx + 300 * S - 7 * S, 330 * S, cx + 300 * S + 7 * S, 900 * S], fill=(235, 255, 252))
    box(cx - 54 * S, 470 * S, cx + 54 * S, 570 * S, dark, 20 * S)       # neck + helmet
    shape([(cx - 130 * S, 300 * S), (cx - 96 * S, 170 * S), (cx, 120 * S), (cx + 96 * S, 170 * S), (cx + 130 * S, 300 * S), (cx + 100 * S, 470 * S), (cx - 100 * S, 470 * S)], metal)
    shape([(cx - 4 * S, 120 * S), (cx + 4 * S, 120 * S), (cx + 28 * S, 60 * S), (cx - 28 * S, 60 * S)], dark)  # crest
    visor = [(cx - 100 * S, 270 * S), (cx + 100 * S, 270 * S), (cx + 84 * S, 340 * S), (cx - 84 * S, 340 * S)]
    d.polygon(visor, fill=glow, outline=edge, width=6 * S)
    # light shading: bright top-left rim, darker lower-right
    a = im.split()[3]
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(0, w, 6):
        sd.line([(i, 0), (i - h // 3, h)], fill=(0, 0, 0, int(70 * i / w)), width=7)
    shade.putalpha(ImageChops.multiply(shade.split()[3], a))
    im = Image.alpha_composite(im, shade)
    return im.resize((w // S, h // S), Image.LANCZOS)


def compose_artwork(bg, ch):
    bw, bh = bg.size
    if bw / bh < 16 / 9 - 0.02 or bw / bh > 16 / 9 + 0.02:   # artwork is 16:9: centre-crop wider/taller backgrounds
        if bw / bh < 16 / 9:
            tw, th = bw, int(bw * 9 / 16)
        else:
            tw, th = int(bh * 16 / 9), bh
        bg = bg.crop(((bw - tw) // 2, (bh - th) // 2, (bw - tw) // 2 + tw, (bh - th) // 2 + th))
    aw, ah = bg.size
    art = bg.convert("RGBA")
    c = ch.copy()
    scale = 0.90 * ah / c.height
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    x, y = int(aw * 0.07), int(ah * 0.07)
    shadow = Image.new("RGBA", art.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([x + 20, y + c.height - 46, x + c.width - 20, y + c.height + 26], fill=(0, 0, 0, 150))
    art = Image.alpha_composite(art, shadow.filter(ImageFilter.GaussianBlur(18)))
    art.alpha_composite(c, (x, y))
    return art.convert("RGB")


REC_NAME = "demo_recording.mp4"
REC_SECONDS, REC_FPS, REC_W, REC_H = 60, 24, 1280, 720
BURSTS = (14.0, 32.0, 48.0)          # seconds where the fictional fight peaks: lots of motion and loud audio


def recording(project):
    """A short fictional gameplay recording made by a script (no game, no third-party content): the sentinel runs through the
    arena and three fights burst with sparks, flashes and a camera shake. It gives the demo a real source video, so the whole pack
    (portal gameplay cut, trailer moments, screenshots, social videos) is produced offline."""
    import subprocess
    import tempfile
    import wave

    import video_tools as vt
    ffmpeg, _ = vt.require_tools()
    out_dir = project / "captures" / "gameplay"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / REC_NAME
    bg = Image.open(project / "background" / "background.png").convert("RGB")
    ch = Image.open(project / "characters" / "character_01.png").convert("RGBA")
    ch = ch.crop(ch.getbbox())
    ph = int(REC_H * 0.62)
    ch = ch.resize((int(ch.width * ph / ch.height), ph), Image.LANCZOS)
    pad = 240                                                  # extra width so the camera can pan
    bg = bg.resize((REC_W + pad, REC_H), Image.LANCZOS)
    rnd = random.Random(11)
    sr = 22050
    n = REC_SECONDS * sr
    t = np.arange(n) / sr
    audio = 0.10 * np.sin(2 * math.pi * 55 * t) + 0.05 * np.sin(2 * math.pi * 110 * t + np.sin(t))
    audio += 0.03 * np.sin(2 * math.pi * 220 * t) * (np.sin(2 * math.pi * 0.5 * t) > 0)
    noise = np.random.RandomState(3).uniform(-1, 1, n)
    for b in BURSTS:
        env = np.clip(1 - np.abs(t - (b + 3)) / 3.2, 0, 1) ** 1.5
        audio += 0.55 * noise * env
    audio = np.clip(audio, -1, 1)
    with tempfile.TemporaryDirectory() as td:
        wav = _P(td) / "a.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((audio * 32000).astype("<i2").tobytes())
        cmd = [ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (REC_W, REC_H), "-r", str(REC_FPS),
               "-i", "-", "-i", str(wav)] + pp.h264_args(ffmpeg, crf=22) + ["-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        sparks = []
        for f in range(REC_SECONDS * REC_FPS):
            tt = f / REC_FPS
            near = max([max(0.0, 1 - abs(tt - (b + 3)) / 3.2) for b in BURSTS])          # 0 calm .. 1 fight peak
            sx = int(rnd.uniform(-1, 1) * 22 * near)
            sy = int(rnd.uniform(-1, 1) * 14 * near)
            pan = int((math.sin(tt / 4.0) * 0.5 + 0.5) * pad)
            frame = bg.crop((pan, 0, pan + REC_W, REC_H)).copy()
            d = ImageDraw.Draw(frame)
            for k in range(7):                                  # floor lines rushing toward the camera
                yy = int(REC_H * 0.80 + ((tt * (2.2 + near * 2) + k / 7) % 1) ** 1.6 * REC_H * 0.2)
                d.line([(0, yy), (REC_W, yy)], fill=(150, 90, 220), width=2)
            bob = int(math.sin(tt * (7 + near * 5)) * (8 + near * 10))
            cx = int(REC_W * (0.30 + 0.22 * math.sin(tt / 6.0) + 0.12 * near))
            frame.paste(ch, (cx - ch.width // 2, int(REC_H * 0.34) + bob), ch)
            if near > 0.15:
                for _ in range(int(14 * near)):
                    sparks.append([cx + 60, REC_H * 0.5, rnd.uniform(-9, 9), rnd.uniform(-12, 2), 1.0])
            nxt = []
            for sp in sparks:
                sp[0] += sp[2]
                sp[1] += sp[3]
                sp[3] += 0.8
                sp[4] -= 0.07
                if sp[4] > 0:
                    r = 3 + int(5 * sp[4])
                    d.ellipse([sp[0] - r, sp[1] - r, sp[0] + r, sp[1] + r], fill=(255, int(120 + 120 * sp[4]), 80))
                    nxt.append(sp)
            sparks = nxt
            if near > 0.8 and f % 6 < 2:                       # flashes
                frame = Image.blend(frame, Image.new("RGB", frame.size, (255, 240, 220)), 0.35)
            if sx or sy:
                frame = ImageChops.offset(frame, sx, sy)
            pr.stdin.write(frame.tobytes())
        pr.stdin.close()
        if pr.wait() != 0 or not out.exists():
            raise SystemExit("could not make the demo recording")
    return out


def main():
    def arg(name):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None

    force = "--force" in sys.argv
    project = pp.projects_dir() / "demo"
    if project.exists() and not force:
        if (project / "background" / "background.png").exists() and not (project / "captures" / "gameplay" / REC_NAME).exists():
            recording(project)                                  # maps made by an older demo: only add the recording
            print("demo recording added: %s" % (project / "captures" / "gameplay" / REC_NAME))
        else:
            print("%s already exists (use --force to rebuild the art)." % project)
        return
    for sub in ("input", "background", "characters", "final", "title"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    if arg("--background") and arg("--character"):
        _src = Image.open(arg("--background"))
        bg = Image.new("RGB", _src.size)
        bg.paste(_src.convert("RGB"))                         # plain RGB: drops any colour-key transparency
        import prepare_character
        prepare_character.prepare(arg("--character"), project / "characters" / "character_01.png")
        ch = Image.open(project / "characters" / "character_01.png")
        bg.save(project / "background" / "background.png")
    else:
        bg, ch = background(), character()
        bg.save(project / "background" / "background.png")
        ch.save(project / "characters" / "character_01.png")
    compose_artwork(bg, ch).save(project / "final" / "artwork.png")
    cfg = {
        "project": {"name": "demo"},
        "title": arg("--title") or "NEON SENTINEL",
        "island_code": "1234-5678-9012",
        "style": "SCI_FI",
        "scene": {"background": "background/background.png"},
        "characters": [{
            "file": "characters/character_01.png", "side": "left",
            "identity": "the character from the reference image, keep it exactly" if arg("--character") else "armoured sentinel with a glowing teal visor and an energy blade",
            "pose": "keep the original pose from the reference, only slightly turned toward the center", "facing": "center"}],
        "qwen": {"max_characters": 1},
    }
    (project / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    # vertical art without AI (deterministic half-body composite, "plan B bust"): needs no ComfyUI
    import os
    import subprocess
    env = dict(os.environ, PROMO_PROJECT="demo", PROMO_PLAN_B="bust", PROMO_PROJECTS_DIR=str(pp.projects_dir()))
    here = _P(__file__).resolve().parent
    subprocess.run([sys.executable, str(here / "prepare_vertical_background.py")], env=env, capture_output=True, text=True)
    r = subprocess.run([sys.executable, str(here / "qwen_run.py"), "vertical"], env=env, capture_output=True, text=True)
    if r.returncode != 0 or not (project / "final" / "artwork_vertical.png").exists():
        print((r.stdout + r.stderr)[-1500:])
        raise SystemExit("could not build the vertical art for the demo")
    recording(project)
    print("demo map created: %s" % project)
    print("next: run_all.bat demo --no-qwen   (no GPU or models needed)")


if __name__ == "__main__":
    main()
