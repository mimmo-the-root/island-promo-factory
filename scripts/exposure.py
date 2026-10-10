#!/usr/bin/env python3
"""Exposure rules: dark maps (night, horror, caves) get a gentle automatic lift so thumbnails, lobby background, trailer and
gameplay stay readable at small sizes (Discover shows thumbnails ~300 px wide on a phone).

RULES (one place, used by every generated image and video):
  1. Measure the mean luma (0-255) of the picture / of the video segment.
  2. Mean >= TRIGGER (85): leave it alone. Already bright enough.
  3. Otherwise raise it towards TARGET (95) with a gamma curve only: black stays black, white stays white, nothing clips,
     colours keep their hue. The gain is capped (images MAX_GAMMA_IMAGE, videos MAX_GAMMA_VIDEO) so a pitch-black scene gets
     lighter, not washed out, and a dark horror mood is lifted, never turned into daylight.
  4. Never touch the user's own finished art (conform landscape thumbnails 01/02, own title, own images).
  5. Switch: config.json "exposure": "off" (or PROMO_EXPOSURE=off) disables it; "exposure_target": 110 asks for brighter.

CLI:  python exposure.py <image-or-video> [...]   prints the measurement and the gamma the rules would apply.
"""
import os
import subprocess
import sys
from pathlib import Path

TRIGGER = 85.0
TARGET = 95.0
MAX_GAMMA_IMAGE = 1.9
MAX_GAMMA_VIDEO = 1.6


def _cfg():
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import promo_project as pp
        return pp.load_config() or {}
    except BaseException:      # no map selected (CLI use): defaults
        return {}


def enabled(cfg=None):
    v = os.environ.get("PROMO_EXPOSURE")
    if v is None:
        v = (cfg if cfg is not None else _cfg()).get("exposure", "auto")
    return str(v).strip().lower() not in ("off", "false", "0", "no")


def target(cfg=None):
    try:
        return float(os.environ.get("PROMO_EXPOSURE_TARGET") or (cfg if cfg is not None else _cfg()).get("exposure_target", TARGET))
    except (TypeError, ValueError):
        return TARGET


def _lift_mean(hist, g):
    n = sum(hist) or 1
    return sum(h * (255.0 * (i / 255.0) ** (1.0 / g)) for i, h in enumerate(hist)) / n


def gamma_for(hist, tgt=None, max_gamma=MAX_GAMMA_IMAGE):
    """Gamma (>= 1.0) that brings the histogram's mean luma to the target; 1.0 when no lift is needed."""
    tgt = target() if tgt is None else tgt
    n = sum(hist) or 1
    mean = sum(h * i for i, h in enumerate(hist)) / n
    if mean >= TRIGGER or mean >= tgt:
        return 1.0
    lo, hi = 1.0, max_gamma
    if _lift_mean(hist, hi) < tgt:
        return hi
    for _ in range(24):
        mid = (lo + hi) / 2
        if _lift_mean(hist, mid) < tgt:
            lo = mid
        else:
            hi = mid
    return round(hi, 3)


def measure(img):
    """(mean luma, share of pixels below 50) of a PIL image."""
    g = img.convert("L")
    h = g.histogram()
    n = sum(h) or 1
    return sum(i * c for i, c in enumerate(h)) / n, sum(h[:50]) / n


def lift_image(img, tgt=None, max_gamma=MAX_GAMMA_IMAGE, cfg=None):
    """Apply the rules to a PIL image. Returns (image, gamma); the image is returned unchanged when gamma == 1.0 or exposure is off."""
    if not enabled(cfg):
        return img, 1.0
    small = img.convert("L")
    small.thumbnail((512, 512))
    g = gamma_for(small.histogram(), tgt, max_gamma)
    if g <= 1.0:
        return img, 1.0
    lut = [min(255, int(round(255.0 * (i / 255.0) ** (1.0 / g)))) for i in range(256)]
    mode = img.mode
    if mode == "RGBA":
        r, gch, b, a = img.split()
        out = Image.merge("RGBA", (r.point(lut), gch.point(lut), b.point(lut), a))
    else:
        out = img.convert("RGB").point(lut * 3)
    return out, g


def sample_luma_hist(ffmpeg, path, start, dur, points=6):
    """Luma histogram of a few small frames spread over [start, start+dur] of a video (None when it cannot be read)."""
    hist = [0] * 256
    got = 0
    for k in range(points):
        t = start + dur * (k + 0.5) / points
        try:
            r = subprocess.run([str(ffmpeg), "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", str(path), "-frames:v", "1",
                                "-vf", "scale=128:72,format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=60)
        except Exception:
            continue
        if r.returncode == 0 and len(r.stdout) >= 128 * 72:
            for v in r.stdout[:128 * 72]:
                hist[v] += 1
            got += 1
    return hist if got else None


def video_gamma(ffmpeg, path, start, dur, cfg=None):
    """Gamma for ffmpeg's eq filter (eq=gamma=G brightens when G > 1) for this segment of a video; 1.0 = leave it."""
    if not enabled(cfg):
        return 1.0
    hist = sample_luma_hist(ffmpeg, path, start, dur)
    if not hist:
        return 1.0
    return gamma_for(hist, None, MAX_GAMMA_VIDEO)


def eq_filter(gamma):
    """ffmpeg filter text for the lift ('' when nothing to do)."""
    return "eq=gamma=%.3f," % gamma if gamma > 1.005 else ""


def with_gamma(look, gamma):
    """Copy of a gameplay_polish look whose grade starts with the exposure lift."""
    f = eq_filter(gamma)
    return dict(look, grade=f + look["grade"]) if f else look


try:
    from PIL import Image
except Exception:  # Pillow is a kit requirement; keep the CLI importable without it
    Image = None


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    import shutil
    ff = shutil.which("ffmpeg") or os.environ.get("FFMPEG_PATH")
    for f in argv:
        p = Path(f)
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            im = Image.open(p)
            m, dark = measure(im)
            g = gamma_for((lambda s: (s.thumbnail((512, 512)), s.histogram())[1])(im.convert("L")))
            print("%s: mean %.0f/255, %.0f%% of pixels < 50 -> image gamma %.2f" % (p.name, m, dark * 100, g))
        elif ff:
            import json
            dur = float(json.loads(subprocess.run([ff.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)],
                                                  capture_output=True, text=True).stdout)["format"]["duration"])
            h = sample_luma_hist(ff, p, 0, dur)
            if h:
                n = sum(h)
                print("%s: mean %.0f/255 -> video gamma %.2f" % (p.name, sum(i * c for i, c in enumerate(h)) / n, gamma_for(h, None, MAX_GAMMA_VIDEO)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
