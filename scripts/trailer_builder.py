import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Trailer v1 builder (no AI video, no ComfyUI).

Ken Burns shots from the project's still images, crossfades, procedural embers,
vignette, end card with the island logo, optional age-rating (ESRB) / "Developed in Fortnite"
badges (video-only). Frames are rendered with Pillow and piped to ffmpeg
(libx264 + AAC). Output: Projects/<map>/final/trailer.mp4 (1920x1080, 30 fps).

Env: PROMO_PROJECT, PROMO_TRAILER_SECONDS (10-40, default 20),
     PROMO_BADGE_MODE=full|ends (default full), FFMPEG_PATH, PROMO_DEBUG=1.
"""
import json
import math
import os
import re
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import promo_project as pp
import title_composer as tc

W, H, FPS = 1920, 1080, 30
XFADE = 1.0            # crossfade length between shots (s)
LOGO_FADE_START = 4.0  # logo starts fading in this many seconds before the end
LOGO_FADE_LEN = 1.5
LOGO_WIDTH_FRAC = 0.60
BADGE_MAX_H_FRAC = 0.12
RATING_MAX_H_FRAC = 0.15      # the (tall) age-rating badge a little larger so its text stays legible
BADGE_MARGIN = 60
BADGE_END_SECONDS = 5.0
MAX_SOURCE_W = 3600    # larger sources are pre-shrunk for speed / alias-free sampling
CRF = 19
DEBUG = os.environ.get("PROMO_DEBUG") == "1"

# ---------------------------------------------------------------- shot list
# Data-driven: add / reorder shots here. "src" = candidates (first existing wins,
# relative to Projects/<map>). "weight" = relative duration (scaled to the total
# length). Camera = (cx, cy, zoom): centre in normalised source coords, zoom 1 =
# the biggest 16:9 box inside the source; "from" -> "to" is interpolated (eased).
# kind "endcard" = dark background + logo fading in during the last seconds.
SHOTS = [
    {"name": "lobby", "src": ["background/lobby_background.png"], "weight": 3.5,
     "from": (0.35, 0.50, 1.00), "to": (0.60, 0.50, 1.10)},
    {"name": "wide", "src": ["final/artwork_up.png", "final/artwork.png"], "weight": 4.5,
     "from": (0.50, 0.50, 1.00), "to": (0.50, 0.48, 1.14)},
    {"name": "closeup", "src": ["final/artwork_vertical_up.png", "final/artwork_vertical.png"], "weight": 4.5,
     "from": (0.50, 0.30, 1.00), "to": (0.50, 0.36, 1.18)},
    {"name": "wide2", "src": ["final/artwork_up.png", "final/artwork.png"], "weight": 3.5,
     "from": (0.30, 0.55, 1.35), "to": (0.55, 0.50, 1.10)},
    {"name": "endcard", "kind": "endcard", "weight": 7.0},
]

AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
LOG_LINES = []


def log(msg):
    print(msg, flush=True)
    LOG_LINES.append(str(msg))


def dbg(msg):
    if DEBUG:
        log("[debug] " + str(msg))


def die(msg):
    log("ERROR: " + str(msg))
    flush_log()
    sys.exit(1)


def flush_log():
    try:
        path = pp.project_dir() / "final" / "trailer_build.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(LOG_LINES) + "\n", encoding="utf-8")
    except Exception as exc:  # logging must never break the build
        print("WARNING: could not write trailer_build.log: %s" % exc)


# ---------------------------------------------------------------- tools
def find_tool(name, env_var=None):
    exe = name + (".exe" if os.name == "nt" else "")
    if env_var and os.environ.get(env_var):
        p = Path(os.environ[env_var])
        if p.is_dir():
            p = p / exe
        if p.exists():
            return str(p)
    found = shutil.which(name)
    if found:
        return found
    local = pp.ROOT / "Resources" / "bin" / (name + ".exe")
    if local.exists():
        return str(local)
    return None


def find_music(proj):
    """Trailer music, in order: your own file audio/music.<mp3|m4a|ogg|flac|...>, then the track generated for the
    gameplay video (audio/gameplay_music.wav, so trailer and gameplay share one sound), then audio/music.wav."""
    for base in (proj / "audio", pp.ROOT / "Resources" / "audio"):
        if base.is_dir():
            files = [f for f in sorted(base.iterdir()) if f.is_file() and f.suffix.lower() in AUDIO_EXT]
            own = [f for f in files if f.stem.lower() == "music" and f.suffix.lower() != ".wav"]
            if own:
                return own[0]
            house = [f for f in files if f.stem.lower() == "gameplay_music"]
            if house:
                return house[0]
            wav = [f for f in files if f.stem.lower() == "music"]
            if wav:
                return wav[0]
    return None


def find_rating_badge(proj):
    """The age-rating badge for the left corner: the map's own rating (ESRB, e.g. Teen) in Projects/<map>/badges/ first, then
    Resources/badges/. File name: rating.png, or any esrb*.png / rating*.png."""
    for bdir in (proj / "badges", pp.ROOT / "Resources" / "badges"):
        if not bdir.is_dir():
            continue
        for f in sorted(bdir.glob("*.png")):
            n = f.name.lower()
            if n == "rating.png" or n.startswith("esrb") or n.startswith("rating"):
                return f
    return None


def find_badge(proj, name):
    for p in (proj / "badges" / name, pp.ROOT / "Resources" / "badges" / name):
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------- imaging
def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def load_source(path):
    im = Image.open(path)
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (0, 0, 0))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[3])
        im = bg
    else:
        im = im.convert("RGB")
    if im.width > MAX_SOURCE_W:
        s = MAX_SOURCE_W / im.width
        im = im.resize((MAX_SOURCE_W, int(im.height * s)), Image.LANCZOS)
    return im


class KenBurns:
    def __init__(self, im, cam_from, cam_to):
        self.im, self.a, self.b = im, cam_from, cam_to
        sw, sh = im.size
        # biggest 16:9 box inside the source
        self.cw = min(sw, sh * 16.0 / 9.0)
        self.ch = self.cw * 9.0 / 16.0

    def frame(self, u):
        e = ease(u)
        cx, cy, z = (lerp(self.a[i], self.b[i], e) for i in range(3))
        sw, sh = self.im.size
        bw, bh = self.cw / z, self.ch / z
        x0 = min(max(cx * sw - bw / 2, 0), sw - bw)
        y0 = min(max(cy * sh - bh / 2, 0), sh - bh)
        return self.im.transform((W, H), Image.EXTENT, (x0, y0, x0 + bw, y0 + bh), Image.BICUBIC)


def make_vignette():
    # small radial gradient scaled up: cheap and smooth
    sw, sh = 192, 108
    m = Image.new("L", (sw, sh))
    px = m.load()
    for y in range(sh):
        for x in range(sw):
            dx, dy = (x - sw / 2) / (sw / 2), (y - sh / 2) / (sh / 2)
            d = math.sqrt(dx * dx * 0.8 + dy * dy)
            px[x, y] = int(max(0.0, min(1.0, (d - 0.55) / 0.85)) ** 1.6 * 200)
    return m.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))


def glow_sprite(size, level):
    s = max(3, int(size * 4))
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((s * 0.3, s * 0.3, s * 0.7, s * 0.7), fill=int(255 * level))
    d.ellipse((s * 0.42, s * 0.42, s * 0.58, s * 0.58), fill=min(255, int(255 * level * 1.3)))
    return m.filter(ImageFilter.GaussianBlur(max(1.0, size * 0.5)))


class Embers:
    def __init__(self, n=60, seed=7):
        rnd = random.Random(seed)
        self.p = []
        for _ in range(n):
            size = rnd.uniform(1.5, 4.5)
            self.p.append({
                "x": rnd.uniform(0, W), "ph": rnd.uniform(0, H + 80), "vy": rnd.uniform(25, 85),
                "sway": rnd.uniform(10, 45), "sf": rnd.uniform(0.4, 1.3), "sp": rnd.uniform(0, 6.28),
                "ff": rnd.uniform(2, 7), "fp": rnd.uniform(0, 6.28),
                "masks": [glow_sprite(size, lv) for lv in (0.35, 0.6, 0.85, 1.0)],
                "col": rnd.choice([(255, 150, 50), (255, 110, 30), (255, 200, 90)]),
            })

    def draw(self, img, t):
        for p in self.p:
            y = H + 40 - ((p["ph"] + t * p["vy"]) % (H + 80))
            x = p["x"] + math.sin(t * p["sf"] + p["sp"]) * p["sway"]
            fl = 0.5 + 0.5 * math.sin(t * p["ff"] + p["fp"])
            fade = min(1.0, max(0.0, y / 200.0))  # die out towards the top
            idx = int(fl * 3.99 * fade)
            m = p["masks"][idx]
            img.paste(p["col"], (int(x - m.width / 2), int(y - m.height / 2)), m)


def fit_badge(path, max_h):
    im = Image.open(path).convert("RGBA")
    s = min(max_h / im.height, (W * 0.28) / im.width)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def paste_rgba(img, sprite, pos, k=1.0):
    a = sprite.split()[3]
    if k < 1.0:
        a = a.point(lambda v: int(v * k))
    img.paste(sprite.convert("RGB"), pos, a)


CLIP_MAX = 4           # real-footage clips used in the trailer (captures/clips/clip_*.mp4)
CLIP_WEIGHT = 3.0
ISLAND_CODE_RE = re.compile(r"^\d{4}-\d{4}-\d{4}$")


class VideoShot:
    """Sequential reader of a real clip (ffmpeg rawvideo), cover-cropped to 1920x1080."""

    def __init__(self, ffmpeg, path, duration, clip_len, index=0, look=None):
        self.ffmpeg, self.path, self.duration = ffmpeg, path, duration
        self.look, self.index = look, index
        self.speed = look["speeds"][index % len(look["speeds"])] if look else 1.0
        need = (duration + 0.5) * self.speed  # source seconds consumed at this speed
        self.offset = max(0.0, (clip_len - need) / 2.0)  # use the middle of a longer clip
        self.proc = None
        self.idx = -1
        self.last = None

    def _open(self):
        import exposure
        g = exposure.video_gamma(self.ffmpeg, self.path, self.offset, (self.duration + 0.5) * self.speed)   # exposure.py rules
        if self.look:
            import gameplay_polish as gpol
            cmd = [self.ffmpeg, "-v", "error", "-ss", "%.3f" % self.offset, "-i", str(self.path),
                   "-t", "%.3f" % ((self.duration + 0.5) * self.speed), "-an",
                   "-filter_complex", gpol.clip_graph(exposure.with_gamma(self.look, g), self.speed, self.duration + 0.5, self.index % 2 == 0, letterbox=True),
                   "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        else:
            cmd = [self.ffmpeg, "-v", "error", "-ss", "%.3f" % self.offset, "-i", str(self.path),
                   "-t", "%.3f" % (self.duration + 0.5), "-an",
                   "-vf", exposure.eq_filter(g) + "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=%d" % (W, H, W, H, FPS),
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    def frame(self, lt):
        if self.proc is None:
            self._open()
        target = int(lt * FPS)
        size = W * H * 3
        while self.idx < target:
            raw = self.proc.stdout.read(size)
            if len(raw) < size:
                break  # clip ended: hold the last frame
            self.last = Image.frombytes("RGB", (W, H), raw)
            self.idx += 1
        return self.last.copy() if self.last is not None else Image.new("RGB", (W, H), (0, 0, 0))

    def close(self):
        if self.proc is not None:
            try:
                self.proc.stdout.close()
                self.proc.kill()
            except Exception:
                pass
            self.proc = None


def clip_length(ffmpeg, path):
    ffprobe = find_tool("ffprobe", "FFPROBE_PATH")
    if not ffprobe:
        return 0.0
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def island_code_sprite(code):
    """'PLAY NOW' + island code, white text with black outline, using the brand/fallback font."""
    brand = json.loads(tc.BRAND_FILE.read_text(encoding="utf-8"))
    font_path = tc.resolve_font_path(brand)
    if font_path is None:
        return None
    small = ImageFont.truetype(str(font_path), 54)
    big = ImageFont.truetype(str(font_path), 118)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    stroke = 6
    wb = probe.textbbox((0, 0), code, font=big, stroke_width=stroke)
    ws = probe.textbbox((0, 0), "PLAY NOW  -  ISLAND CODE", font=small, stroke_width=4)
    width = max(wb[2] - wb[0], ws[2] - ws[0]) + 40
    height = (ws[3] - ws[1]) + (wb[3] - wb[1]) + 70
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text(((width - (ws[2] - ws[0])) // 2 - ws[0], 10 - ws[1]), "PLAY NOW  -  ISLAND CODE", font=small,
           fill=(255, 205, 90), stroke_width=4, stroke_fill=(0, 0, 0))
    d.text(((width - (wb[2] - wb[0])) // 2 - wb[0], (ws[3] - ws[1]) + 40 - wb[1]), code, font=big,
           fill=(255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0))
    return im


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    proj = pp.project_dir()
    cfg = pp.load_config()
    log("Trailer builder v1 - map: %s (%s)" % (pp.project_name(), cfg.get("title", "?")))
    if not proj.is_dir():
        die("Project folder not found: %s" % proj)

    try:
        total = float(os.environ.get("PROMO_TRAILER_SECONDS", "20"))
    except ValueError:
        die("PROMO_TRAILER_SECONDS must be a number (10-40)")
    if not 10 <= total <= 40:
        die("PROMO_TRAILER_SECONDS=%s out of range (allowed 10-40)" % total)
    badge_mode = os.environ.get("PROMO_BADGE_MODE", "full").lower()
    if badge_mode not in ("full", "ends"):
        die("PROMO_BADGE_MODE must be 'full' or 'ends'")

    ffmpeg = find_tool("ffmpeg", "FFMPEG_PATH")
    if not ffmpeg:
        die("ffmpeg not found. Install it (winget install Gyan.FFmpeg), or set FFMPEG_PATH, "
            "or put ffmpeg.exe in PromoFactory\\Resources\\bin\\")
    log("ffmpeg: %s" % ffmpeg)

    # ---- island code (shown on the end card)
    island_code = str(cfg.get("island_code", "")).strip()
    if island_code and not ISLAND_CODE_RE.match(island_code):
        die("config.json island_code must look like 1234-5678-9012, got '%s'" % island_code)
    if not island_code:
        log("WARNING: no island_code in config.json: the end card will show the logo only")

    # ---- real clips from captures/clips (inserted after the first wide shot)
    shot_defs = list(SHOTS)
    clips = []
    if os.environ.get("PROMO_TRAILER_CLIPS", "1") != "0":
        cdir = proj / "captures" / "clips"
        if cdir.is_dir():
            clips = [c for c in sorted(cdir.iterdir()) if c.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")][:CLIP_MAX]
    if clips:
        # default: real clips only (+ end card). PROMO_TRAILER_STILLS=1 mixes the generated art stills back in.
        if os.environ.get("PROMO_TRAILER_STILLS", "0") == "1":
            pos = next((i for i, d in enumerate(shot_defs) if d["name"] == "wide"), 1) + 1
            for k, c in enumerate(clips):
                shot_defs.insert(pos + k, {"name": "clip%d" % (k + 1), "kind": "video", "path": c, "weight": CLIP_WEIGHT})
        else:
            shot_defs = [{"name": "clip%d" % (k + 1), "kind": "video", "path": c, "weight": CLIP_WEIGHT}
                         for k, c in enumerate(clips)] + [dict(d, weight=CLIP_WEIGHT * 1.75) for d in shot_defs if d.get("kind") == "endcard"]
        log("real clips: %s" % ", ".join(c.name for c in clips))
    else:
        log("no real clips in captures/clips: trailer built from stills only")

    # ---- resolve shots
    shots = []
    for s in shot_defs:
        if s.get("kind") == "video":
            shots.append(dict(s))
            continue
        if s.get("kind") == "endcard":
            shots.append(dict(s))
            continue
        src = next((proj / c for c in s["src"] if (proj / c).exists()), None)
        if src is None:
            log("WARNING: shot '%s' skipped, no image found (%s)" % (s["name"], ", ".join(s["src"])))
            continue
        d = dict(s)
        d["path"] = src
        shots.append(d)
    if not any(s.get("kind") not in ("endcard",) for s in shots):
        die("no source images found in %s" % proj)
    logo_path = proj / "final" / "island_logo.png"
    has_end = any(s.get("kind") == "endcard" for s in shots)
    if has_end and not logo_path.exists():
        die("end card needs %s (run the factory first)" % logo_path)

    # ---- timeline: sum(d) - (n-1)*XFADE = total
    n = len(shots)
    wsum = sum(s["weight"] for s in shots)
    pool = total + (n - 1) * XFADE
    t = 0.0
    for s in shots:
        s["dur"] = s["weight"] / wsum * pool
        s["start"] = t
        t += s["dur"] - XFADE
    if shots[-1].get("kind") == "endcard" and shots[-1]["dur"] < LOGO_FADE_START + 0.5:
        log("WARNING: end card shorter than the logo fade; raise its weight")
    for s in shots:
        dbg("shot %-8s start %.2f dur %.2f" % (s["name"], s["start"], s["dur"]))

    # ---- assets
    import gameplay_polish as gpol
    look_name = os.environ.get("PROMO_VIDEO_LOOK", "cinematic")
    look = None if look_name == "off" else gpol.LOOKS.get(look_name, gpol.LOOKS["cinematic"])
    idx_clip = 0
    for s in shots:
        if s.get("kind") == "video":
            log("shot %-8s <- %s (real footage)" % (s["name"], s["path"].relative_to(proj)))
            s["vs"] = VideoShot(ffmpeg, s["path"], s["dur"] + XFADE, clip_length(ffmpeg, s["path"]), idx_clip, look)
            idx_clip += 1
        elif s.get("kind") != "endcard":
            log("shot %-8s <- %s" % (s["name"], s["path"].relative_to(proj)))
            s["kb"] = KenBurns(load_source(s["path"]), s["from"], s["to"])
    code_sprite = island_code_sprite(island_code) if island_code else None
    logo = None
    if has_end:
        lg = Image.open(logo_path).convert("RGBA")
        lw = int(W * LOGO_WIDTH_FRAC)
        logo = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
        log("end card logo: %s (%dx%d on screen)" % (logo_path.name, logo.width, logo.height))
    end_bg = Image.new("RGB", (W, H), (8, 9, 14))
    # end card background: the map artwork (slow push-in), darkened as the title/code fade in.
    # PROMO_ENDCARD_BG=dark restores the plain dark card.
    end_art = None
    if os.environ.get("PROMO_ENDCARD_BG", "art") != "dark":
        art_path = next((proj / c for c in ("final/artwork_up.png", "final/artwork.png") if (proj / c).exists()), None)
        if art_path is not None:
            end_art = KenBurns(Image.open(art_path).convert("RGB"), (0.5, 0.5, 1.0), (0.5, 0.5, 1.10))
            log("end card background: %s" % art_path.name)

    missing = []
    badges = {}
    # Official "Developed in Fortnite" logos come as a white and a black variant (FNDV_*_White/Black_*.png):
    # when both exist the right badge switches per frame to whichever contrasts with the picture behind it.
    fndv = {}
    for bdir in (proj / "badges", pp.ROOT / "Resources" / "badges"):
        if bdir.is_dir():
            for f in sorted(bdir.glob("*.png")):
                n = f.name.lower()
                try:
                    with Image.open(f) as _im:
                        if "fndv" in n and _im.width < 2 * _im.height:
                            continue        # the wide "Developed in Fortnite" logo only: a tall file with an FNDV name is something else (e.g. a rating badge)
                except Exception:
                    continue
                if "fndv" in n and "white" in n:
                    fndv.setdefault("white", f)
                elif "fndv" in n and "black" in n:
                    fndv.setdefault("black", f)
    badge_dual = None
    if "white" in fndv and "black" in fndv:
        badge_dual = {k: fit_badge(v, int(H * BADGE_MAX_H_FRAC)) for k, v in fndv.items()}
        log("badge right (adaptive): %s / %s" % (fndv["white"].name, fndv["black"].name))
    for key, fname in (("left", "rating.png"), ("right", "developed_in_fortnite.png")):
        if key == "right" and badge_dual is not None:
            badges["right"] = badge_dual["white"]
            continue
        p = find_rating_badge(proj) if key == "left" else find_badge(proj, fname)
        if p is None:
            missing.append(fname)
        else:
            badges[key] = fit_badge(p, int(H * (RATING_MAX_H_FRAC if key == "left" else BADGE_MAX_H_FRAC)))
            log("badge %s: %s" % (key, p))
    if missing:
        log("WARNING: badge file(s) missing, trailer built WITHOUT them: %s" % ", ".join(missing))
        log("WARNING: put official transparent PNGs in %s (or per-map in %s)" % (
            pp.ROOT / "Resources" / "badges", proj / "badges"))
        log("WARNING: expected names: rating.png (or esrb_*.png) for the age rating, developed_in_fortnite.png (or the FNDV_*_White/Black_*.png pair)")

    music = find_music(proj)
    if music:
        log("music: %s (user-supplied)" % music)
    else:
        log("music: none found, audio track is silent (optional: Projects/%s/audio/music.mp3 or Resources/audio/music.mp3)" % pp.project_name())
    log("WARNING: use only music you are licensed to use (licensed-IP maps: follow the IP holder rules, no franchise music).")

    vignette = make_vignette()
    black = Image.new("RGB", (W, H), (0, 0, 0))
    embers = Embers()

    out_dir = proj / "final"
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = out_dir / "trailer_tmp.mp4"
    final = out_dir / "trailer.mp4"

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error" if not DEBUG else "info",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
    if music:
        cmd += ["-i", str(music)]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    af = "afade=t=in:st=0:d=1,afade=t=out:st=%.2f:d=2,alimiter=limit=0.89" % (total - 2) if music else "anull"
    cmd += ["-map", "0:v", "-map", "1:a", "-af", af, "-t", "%.3f" % total,
            *pp.h264_args(ffmpeg, CRF),
            "-r", str(FPS), "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-f", "mp4", str(scratch)]
    dbg(" ".join(cmd))
    # music shorter than the video: loop it
    if music:
        i = cmd.index(str(music)) - 1  # position of its "-i"
        cmd[i:i] = ["-stream_loop", "-1"]

    lum_ema, badge_pick = None, "white"
    nframes = int(round(total * FPS))
    log("rendering %d frames (%.0f s @ %d fps) ..." % (nframes, total, FPS))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for f in range(nframes):
            t = f / float(FPS)
            res = None
            video_active = False
            for i, s in enumerate(shots):
                if not (s["start"] <= t < s["start"] + s["dur"] + 1e-9):
                    continue
                lt = t - s["start"]
                if s.get("kind") == "endcard":
                    if end_art is not None:
                        img = end_art.frame(lt / s["dur"])
                        dk = 0.68 * ease((t - (total - LOGO_FADE_START - 0.6)) / 1.6)
                        if dk > 0:
                            img = Image.blend(img, end_bg, dk)
                    else:
                        img = end_bg.copy()
                elif s.get("kind") == "video":
                    img = s["vs"].frame(lt)
                    video_active = True
                else:
                    img = s["kb"].frame(lt / s["dur"])
                if res is None:
                    res = img
                else:
                    res = Image.blend(res, img, ease(lt / XFADE))
            if res is None:
                res = end_bg.copy()
            res.paste(black, mask=vignette)
            if not video_active:
                embers.draw(res, t)
            # logo fade-in during the last seconds
            if logo is not None:
                k = ease((t - (total - LOGO_FADE_START)) / LOGO_FADE_LEN)
                if k > 0:
                    ly = (H - logo.height) // 2 - (110 if code_sprite is not None else 0)
                    paste_rgba(res, logo, ((W - logo.width) // 2, ly), k)
                if code_sprite is not None:
                    kc = ease((t - (total - LOGO_FADE_START + 0.8)) / LOGO_FADE_LEN)
                    if kc > 0:
                        cy = (H - logo.height) // 2 - 110 + logo.height + 10
                        paste_rgba(res, code_sprite, ((W - code_sprite.width) // 2, min(cy, H - 200 - code_sprite.height)), kc)
            # badges
            if badges:
                if badge_mode == "full":
                    bk = 1.0
                else:
                    bk = min(1.0, (BADGE_END_SECONDS - t) / 0.4) if t < BADGE_END_SECONDS else 0.0
                    if t >= total - BADGE_END_SECONDS:
                        bk = min(1.0, (t - (total - BADGE_END_SECONDS)) / 0.4)
                if bk > 0:
                    if "left" in badges:
                        b = badges["left"]
                        paste_rgba(res, b, (BADGE_MARGIN, H - BADGE_MARGIN - b.height), bk)
                    if "right" in badges:
                        b = badges["right"]
                        if badge_dual is not None:
                            box = (W - BADGE_MARGIN - b.width - 20, H - BADGE_MARGIN - b.height - 20, W - BADGE_MARGIN + 20, H - BADGE_MARGIN + 20)
                            lum = res.crop(box).convert("L").resize((1, 1), Image.BOX).getpixel((0, 0))
                            lum_ema = lum if lum_ema is None else lum_ema + 0.12 * (lum - lum_ema)
                            if badge_pick == "white" and lum_ema > 150:
                                badge_pick = "black"
                            elif badge_pick == "black" and lum_ema < 105:
                                badge_pick = "white"
                            b = badge_dual[badge_pick]
                        paste_rgba(res, b, (W - BADGE_MARGIN - b.width, H - BADGE_MARGIN - b.height), bk)
            proc.stdin.write(res.tobytes())
            if f % 6 == 0:  # live preview for the dashboard (overwritten, tiny)
                try:
                    res.resize((640, 360), Image.BILINEAR).save(out_dir / "_live_frame.jpg", quality=78)
                except OSError:
                    pass
            if f % 100 == 0:
                log("  frame %d/%d (%.0f s elapsed)" % (f, nframes, time.time() - t0))
        proc.stdin.close()
        for sh in shots:
            if "vs" in sh:
                sh["vs"].close()
    except BrokenPipeError:
        proc.wait()
        die("ffmpeg closed the pipe early (exit %s)" % proc.returncode)
    rc = proc.wait()
    if rc != 0:
        die("ffmpeg failed with exit code %s" % rc)

    # move into place (never deletes other files; replaces an old trailer via _previous)
    if final.exists():
        prev = out_dir / "_previous" / time.strftime("%Y%m%d_%H%M%S")
        prev.mkdir(parents=True, exist_ok=True)
        shutil.move(str(final), str(prev / final.name))
        log("previous trailer moved to %s" % prev)
    shutil.move(str(scratch), str(final))
    size_mb = final.stat().st_size / 1048576.0
    log("trailer written: %s (%.1f MB, %.0f s build)" % (final, size_mb, time.time() - t0))
    if size_mb >= 400:
        log("ERROR: trailer is >= 400 MB, raise CRF in trailer_builder.py")
        flush_log()
        sys.exit(1)

    flush_log()
    log("--- validator ---")
    v = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "video_validate.py"),
                        str(final), "--kind", "trailer"], env=os.environ.copy())
    flush_log()
    sys.exit(0 if v.returncode == 0 else 1)


if __name__ == "__main__":
    main()
