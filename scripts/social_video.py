import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Vertical 9:16 social videos (TikTok, Reels, Shorts) with English promotional subtitles, made from the finished trailer.

Usage: social_video.py [--project SLUG] [--only A] [--seconds 24]
Input : final/trailer.mp4 (real clips, music, badges, island code), Projects/<map>/social.json (optional)
Output: promo_pack/social/social_<A|B>_1080x1920.mp4 (+ .srt), promo_pack/social/captions.txt   (NOT for the Creator Portal)
social.json: {"variants": [{"name": "A", "hook": "...", "lines": ["...", "..."], "cta": "Island code: 1234-5678-9012"}]}
Without social.json two neutral DRAFT variants are written from config.json; the social-copywriter agent can improve them and the
user approves them. Layout: blurred full-screen background, sharp 16:9 clip below the top safe area, subtitles in the middle band
(clear of the app's bottom bar and right-hand button column). Cuts snap to the music's beats when the tempo is reliable.
Encoded BT.709 tagged, 15-30 s, 1080x1920.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import epic_specs
import promo_project as pp
import video_tools as vt

W, H = 1080, 1920
CLIP_Y = 380                    # sharp 16:9 clip: y 380..988 (top 250 px stay free for the app's header)
CAP_Y, CAP_W = 1050, 840        # subtitle band: y 1050..1450, 120 px margins (the right column of buttons stays free)
HOOK_T = (0.4, 3.4)
ROOT = Path(__file__).resolve().parent.parent


def font_path():
    for d in (ROOT / "Resources" / "brand" / "font", ROOT / "Resources" / "fonts"):
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.suffix.lower() in (".ttf", ".otf"):
                    return p
    return None


def clean(text, font):
    """Keep only characters the font can draw (no empty boxes in a burned-in subtitle)."""
    out = []
    for ch in str(text):
        if ch.isspace() or font.getmask(ch).getbbox():
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def drafts(cfg):
    title = str(cfg.get("title") or "this island").strip()
    code = str(cfg.get("island_code") or "").strip()
    cta = "Island code: %s" % code if code else "Search for %s in Fortnite" % title
    return {"draft": True, "variants": [
        {"name": "A", "hook": "Play %s" % title, "lines": ["Only in Fortnite", "Bring your squad"], "cta": cta},
        {"name": "B", "hook": "Ready for %s?" % title, "lines": ["Jump in now", "Challenge your friends"], "cta": cta}]}


def load_social(proj, cfg):
    f = proj / "social.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        if not d.get("variants"):
            raise ValueError("social.json has no variants")
        return d
    d = drafts(cfg)
    f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("social: wrote DRAFT texts to %s - edit them or ask the social-copywriter agent, then rerun" % f)
    return d


def schedule(variant, total, beats=None):
    """[(start, end, text, kind)] hook first, selling points spread out, call to action in the last seconds."""
    lines = [l for l in variant.get("lines", []) if l]
    cta_start = total - 4.6
    seg = [(HOOK_T[0], HOOK_T[1], variant["hook"], "hook")]
    if lines:
        span = (cta_start - 0.4) - 3.9
        step = span / len(lines)
        for i, l in enumerate(lines):
            seg.append((3.9 + i * step, 3.9 + i * step + min(3.0, step - 0.3), l, "line"))
    seg.append((cta_start, total - 0.3, variant["cta"], "cta"))
    if beats:
        t0, per = beats
        snap = lambda t: t0 + round((t - t0) / per) * per
        seg = [(a if k == "hook" else max(0.2, snap(a)), b, t, k) for a, b, t, k in seg]
        seg = [(a, b if b > a + 0.8 else a + 0.8, t, k) for a, b, t, k in seg]
    return seg


def caption_png(text, kind, font_file, dest):
    from PIL import Image, ImageDraw, ImageFont
    size = {"hook": 84, "line": 64, "cta": 62}[kind]
    font = ImageFont.truetype(str(font_file), size)
    text = clean(text, font)
    words, rows, cur = text.split(), [], ""
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    for w in words:
        t = (cur + " " + w).strip()
        if probe.textlength(t, font=font) <= CAP_W or not cur:
            cur = t
        else:
            rows.append(cur)
            cur = w
    if cur:
        rows.append(cur)
    lh = int(size * 1.18)
    im = Image.new("RGBA", (W, lh * len(rows) + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = (255, 214, 64, 255) if kind == "cta" else (255, 255, 255, 255)
    for i, r in enumerate(rows):
        x = (W - probe.textlength(r, font=font)) / 2 - 40       # centred in the band left of the button column
        d.text((max(60, x), 8 + i * lh), r, font=font, fill=fill, stroke_width=max(4, size // 14), stroke_fill=(0, 0, 0, 255))
    im.save(dest)
    return im.height


def srt(seg, dest):
    def ts(t):
        return "%02d:%02d:%02d,%03d" % (t // 3600, t % 3600 // 60, t % 60, int(round((t % 1) * 1000)) % 1000)
    dest.write_text("\n".join("%d\n%s --> %s\n%s\n" % (i + 1, ts(a), ts(b), t) for i, (a, b, t, k) in enumerate(seg)), encoding="utf-8")


def beats_for(proj):
    try:
        import music_beats
        m = next((f for f in (proj / "audio").iterdir() if f.stem.lower() == "music" and f.suffix.lower() == ".wav"), None)
        if m:
            bpm, t0, conf = music_beats.detect(m)
            if conf >= 0.5:
                return t0, 60.0 / bpm * 2          # every second beat: one caption change per bar half
    except Exception:
        pass
    return None


def render(ffmpeg, src, seg, total, dest, tmp, font_file):
    pngs = []
    for i, (a, b, t, k) in enumerate(seg):
        p = Path(tmp) / ("cap%d.png" % i)
        caption_png(t, k, font_file, p)
        pngs.append(p)
    fc = ["[0:v]split[a][b]",
          "[a]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=36:6,eq=brightness=-0.10[bg]" % (W, H, W, H),
          "[b]scale=%d:-2[fg]" % W,
          "[bg][fg]overlay=0:%d[v0]" % CLIP_Y]
    cmd = [ffmpeg, "-v", "error", "-y", "-i", str(src)]
    for i, (p, (a, b, t, k)) in enumerate(zip(pngs, seg)):
        cmd += ["-loop", "1", "-t", "%.2f" % total, "-i", str(p)]
        fc.append("[%d:v]format=rgba[c%d]" % (i + 1, i))
        fc.append("[v%d][c%d]overlay=0:%d:enable='between(t,%.3f,%.3f)':format=auto[v%d]" % (i, i, CAP_Y, a, b, i + 1))
    fc.append("[v%d]format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv[vo]" % len(seg))
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "0:a?", "-t", "%.2f" % total, "-r", "30"]
    cmd += pp.h264_args(ffmpeg, 18) + ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                                       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not Path(dest).exists():
        raise RuntimeError("ffmpeg failed: %s" % r.stderr.strip()[-600:])


def validate(ffprobe, dest, code):
    """[(ok, message)] - the same spirit as video_validate, for 9:16."""
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,color_space,color_primaries,color_transfer,color_range:format=duration", "-of", "json", str(dest)],
                         capture_output=True, text=True)
    d = json.loads(out.stdout or "{}")
    s = (d.get("streams") or [{}])[0]
    dur = float((d.get("format") or {}).get("duration") or 0)
    lo, hi = epic_specs.video_seconds()
    return [(s.get("width") == W and s.get("height") == H, "size %sx%s (need %dx%d)" % (s.get("width"), s.get("height"), W, H)),
            (lo <= dur <= hi + 0.2, "duration %.1f s (%d-%d)" % (dur, lo, hi)),
            (s.get("color_space") == "bt709" and s.get("color_primaries") == "bt709" and s.get("color_range") == "tv", "BT.709 tv tags")]


def captions_txt(cfg, variant):
    title, code = cfg.get("title", ""), cfg.get("island_code", "")
    tag = re.sub(r"[^A-Za-z0-9]", "", title)
    base = "%s - %s. Play it in Fortnite%s." % (variant["hook"], ", ".join(variant.get("lines", [])), (": island code %s" % code) if code else "")
    tags = " ".join(h for h in ("#Fortnite", "#UEFN", "#FortniteCreative", "#" + tag if tag else "", "#Gaming") if h)
    return "TIKTOK / INSTAGRAM REELS\n%s\n%s\n\nYOUTUBE SHORTS\nTitle: %s | Fortnite island %s\n%s\n" % (base, tags, title, code, base)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--only", default=None, help="only this variant name (A, B ...)")
    ap.add_argument("--seconds", type=float, default=None)
    a = ap.parse_args()
    if a.project:
        import os
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    cfg = pp.load_config()
    src = proj / "final" / "trailer.mp4"
    if not src.exists():
        print("social: no final/trailer.mp4 yet - nothing to do (run the trailer stage first)")
        return
    ffmpeg, ffprobe = vt.find_tool("ffmpeg", "FFMPEG_PATH"), vt.find_tool("ffprobe", "FFPROBE_PATH")
    if not (ffmpeg and ffprobe):
        print("social: ffmpeg/ffprobe not found - skipped")
        return
    font_file = font_path()
    if font_file is None:
        print("ERROR: no font in Resources/brand/font or Resources/fonts")
        sys.exit(1)
    info = vt.probe(ffprobe, src)
    lo, hi = epic_specs.video_seconds()
    total = a.seconds or min(info["duration"], hi)
    if total < lo:
        print("ERROR: the trailer is %.1f s, shorter than %d s" % (info["duration"], lo))
        sys.exit(1)
    social = load_social(proj, cfg)
    out_dir = proj / "promo_pack" / "social"
    out_dir.mkdir(parents=True, exist_ok=True)
    beats = beats_for(proj)
    bad = 0
    for v in social["variants"]:
        if a.only and v["name"] != a.only:
            continue
        seg = schedule(v, total, beats)
        dest = out_dir / ("social_%s_1080x1920.mp4" % v["name"])
        tmp_dest = dest.with_suffix(".part.mp4")
        with tempfile.TemporaryDirectory() as tmp:
            try:
                render(ffmpeg, src, seg, total, tmp_dest, tmp, font_file)
            except Exception as e:
                print("ERROR: variant %s: %s" % (v["name"], e))
                tmp_dest.unlink(missing_ok=True)
                sys.exit(1)
        tmp_dest.replace(dest)                      # a broken encode never replaces a good file
        srt(seg, dest.with_suffix(".srt"))
        res = validate(ffprobe, dest, cfg.get("island_code"))
        code = str(cfg.get("island_code") or "")
        res.append((not code or code in v["cta"], "island code in the call to action"))
        for ok, msg in res:
            print("%s  social %s: %s" % ("PASS" if ok else "FAIL", v["name"], msg))
            bad += 0 if ok else 1
    first = next((v for v in social["variants"] if not a.only or v["name"] == a.only), None)
    if first:
        (out_dir / "captions.txt").write_text(captions_txt(cfg, first), encoding="utf-8")
    if social.get("draft"):
        print("NOTE: the texts are DRAFTS (social.json 'draft': true). Edit them, remove the flag, rerun.")
    print("social: %s" % out_dir)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
