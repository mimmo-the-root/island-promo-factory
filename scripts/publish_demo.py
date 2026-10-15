import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Turns the finished demo map into small files that are versioned in docs/demo/ and published with the manual on GitHub Pages.

Usage: publish_demo.py [--project demo]
Reads <Projects>/demo/promo_pack/ (run demo.bat first). Writes docs/demo/: jpg previews of the images, 720p / 540p low-bitrate
previews of the videos (the real 1080p files stay on the maker's PC: they are large and the *.mp4 rule of .gitignore keeps them out),
and a self-contained index.html. The demo is fictional: own art, own character, script-made gameplay.
"""
import argparse
import html
import subprocess
from pathlib import Path

from PIL import Image

import promo_project as pp
import video_tools as vt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo"

IMAGES = [   # (source glob, output name, caption, max width)
    ("01_landscape_with_text_*.png", "thumbnail-landscape.jpg", "Landscape thumbnail, with title (1920x1080)", 1280),
    ("03_portrait_with_text_*.png", "thumbnail-portrait.jpg", "Portrait thumbnail, with title (1440x1920)", 720),
    ("05_logo_*.png", "logo.png", "Island logo (transparent PNG)", 720),
    ("06_lobby_background_*.png", "lobby.jpg", "Lobby background (2048x1024)", 1280),
    ("lightbox.png", "lightbox.jpg", "The lightbox: the whole kit on one sheet", 1400),
]
VIDEOS = [   # (source glob, output name, caption, output width)
    ("08_trailer_1920x1080.mp4", "trailer-preview.mp4", "Trailer (preview, 720p)", 1280),
    ("07_gameplay_*.mp4", "gameplay-preview.mp4", "Portal gameplay video (preview, 720p)", 1280),
    ("social/social_A_*.mp4", "social-preview.mp4", "Social video 9:16 (optional extra, preview)", 540),
]


def first(folder, pattern):
    hits = sorted(folder.glob(pattern))
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="demo")
    a = ap.parse_args()
    pack = pp.projects_dir() / a.project / "promo_pack"
    if not pack.is_dir():
        raise SystemExit("no promo_pack in %s: run demo.bat first" % pack.parent)
    ffmpeg, _ = vt.require_tools()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        if old.is_file():
            old.unlink()
    figs = []
    for pat, name, cap, mw in IMAGES:
        src = first(pack, pat)
        if not src:
            print("skip (missing): " + pat)
            continue
        im = Image.open(src)
        if im.width > mw:
            im = im.resize((mw, round(im.height * mw / im.width)), Image.LANCZOS)
        if name.endswith(".jpg"):
            im.convert("RGB").save(OUT / name, quality=82, optimize=True)
        else:
            im.save(OUT / name, optimize=True)
        figs.append(("img", name, cap))
    for pat, name, cap, w in VIDEOS:
        src = first(pack, pat)
        if not src:
            print("skip (missing): " + pat)
            continue
        cmd = [ffmpeg, "-y", "-v", "error", "-i", str(src), "-vf", "scale=%d:-2" % w, "-c:v", "libx264", "-preset", "slow", "-crf", "32",
               "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "64k",
               "-movflags", "+faststart", str(OUT / name)]
        if subprocess.run(cmd).returncode != 0:
            raise SystemExit("ffmpeg failed on " + src.name)
        figs.append(("vid", name, cap))
    body = []
    for kind, name, cap in figs:
        tag = ('<img src="%s" alt="%s">' if kind == "img" else '<video src="%s" controls preload="none" playsinline aria-label="%s"></video>') % (name, html.escape(cap))
        body.append("<figure>%s<figcaption>%s</figcaption></figure>" % (tag, html.escape(cap)))
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>Island Promo Factory demo</title><style>body{margin:0;background:#0b0d14;color:#e8ecf5;font:16px/1.6 system-ui,sans-serif;padding:24px;max-width:1100px;margin:auto}"
            "a{color:#22e1ff}img,video{max-width:100%;border-radius:10px;border:1px solid #2a2f45}figure{margin:0 0 28px}figcaption{color:#9aa3bd;font-size:14px;margin-top:6px}</style></head><body>"
            "<h1>Demo: what the kit makes</h1><p>A fictional map (own art, own character, script-made gameplay) run through the whole kit, offline, with no AI models. "
            'These are small previews; the real files are full size. <a href="../">Back to the manual</a>.</p>' + "".join(body) +
            "</body></html>")
    (OUT / "index.html").write_text(page, encoding="utf-8")
    mb = sum(f.stat().st_size for f in OUT.iterdir()) / 1e6
    print("docs/demo written: %d files, %.1f MB" % (len(list(OUT.iterdir())), mb))


if __name__ == "__main__":
    main()
