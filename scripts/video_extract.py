import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Cut clips, the portal gameplay video and screenshots out of a long recording.

Usage:
  video_extract.py <video> --auto [--clips 4] [--gameplay-seconds 25]
  video_extract.py <video> --selection selection.json
  add --gameplay-montage to build the gameplay video as a montage of the best moments (default: one continuous cut)

selection.json (times in seconds):
  {"clips":      [{"start": 62.0, "end": 68.0}, ...],        # extra shots for the trailer (may be edited)
   "gameplay":   {"start": 120.0, "end": 148.0},            # ONE continuous segment, 10-40 s
                 or {"montage": true, "seconds": 25}        # MONTAGE of the best moments, hard cuts, total 10-40 s
                 or {"montage": true, "segments": [{"start": 62, "end": 68}, ...]}
   "screenshots": [75.0, 133.5, 201.0]}                      # up to 3 in-game frames

Output in Projects/<map>/captures/: clips/clip_NN.mp4, gameplay/gameplay.mp4, screenshots/screenshot_NN.png|jpg.
Gameplay modes: "single" (default) = ONE continuous cut, only trimmed (and scaled to 1920x1080 if needed, with a warning);
"montage" = several real segments joined with hard cuts (no effects, no overlays, original audio), total length as requested.
The portal asks for real gameplay: montage footage is real, but check Epic's current rules before uploading a joined video.
The mode is recorded in captures/gameplay/gameplay.json and shown in UPLOAD_CHECKLIST.md. Existing files are moved to
captures/_previous/<timestamp>/ (never deleted). --auto needs captures/analysis/candidates.json (video_analyze.py).
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

import promo_project as pp
import video_tools as vt

VF_FIT = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: ffmpeg failed:\n%s" % r.stderr.strip()[-1500:])
        sys.exit(1)


def cut(ffmpeg, video, start, end, dest, fps=None, crf=18):
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % start, "-i", str(video), "-t", "%.3f" % (end - start),
           "-vf", VF_FIT] + pp.h264_args(ffmpeg, crf)
    if fps:
        cmd += ["-r", str(fps)]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dest)]
    run(cmd)


def sharpness(ffmpeg, video, t):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "f.png"
        subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=480:-1", str(p)], capture_output=True)
        if not p.exists():
            return -1.0
        g = np.asarray(Image.open(p).convert("L"), dtype=np.float32)
        lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
        return float(lap.var())


def screenshot(ffmpeg, video, t, dest_stem, look=None):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.png"
        if look:
            import gameplay_polish as gpol
            run([ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % t, "-i", str(video), "-frames:v", "1",
                 "-filter_complex", gpol.still_graph(gpol.LOOKS[look]), "-map", "[v]", str(p)])
        else:
            run([ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % t, "-i", str(video), "-frames:v", "1", "-vf", VF_FIT, str(p)])
        if not p.exists():
            print("ERROR: could not grab a frame at %.1f s" % t)
            sys.exit(1)
        if p.stat().st_size < 4.8 * 1048576:
            out = dest_stem.with_suffix(".png")
            shutil.copyfile(p, out)
        else:  # portal limit is 5 MB: use a high-quality JPEG instead
            out = dest_stem.with_suffix(".jpg")
            Image.open(p).convert("RGB").save(out, quality=95, subsampling=0)
        return out


def archive(folder, pattern, stamp):
    old = [f for f in folder.glob(pattern) if f.is_file()]
    if old:
        target = folder.parent / "_previous" / stamp / folder.name
        target.mkdir(parents=True, exist_ok=True)
        for f in old:
            shutil.move(str(f), str(target / f.name))


def auto_selection(cap, info, n_clips, gp_seconds):
    path = cap / "analysis" / "candidates.json"
    if not path.exists():
        print("ERROR: %s not found - run video_analyze.py first, or pass --selection" % path)
        sys.exit(1)
    cands = json.loads(path.read_text(encoding="utf-8"))["candidates"]
    best = cands[0]
    centre = (best["start"] + best["end"]) / 2
    gp = max(10.0, min(40.0, gp_seconds))
    start = max(0.0, min(centre - gp / 2, info["duration"] - gp))
    sel = {
        "clips": [{"start": c["start"], "end": c["end"]} for c in cands[:n_clips]],
        "gameplay": {"start": round(start, 2), "end": round(start + gp, 2)},
        "screenshots": [],
    }
    return sel, cands


def montage_segments(sel, cands, total, info):
    """Equal-length segments centred on the best moments, in chronological order. total = seconds of the montage."""
    total = max(10.0, min(40.0, float(total)))
    gp = sel.get("gameplay") or {}
    src = gp.get("segments")
    if src:
        return [(float(x["start"]), float(x["end"])) for x in src]
    moments = [(c["start"], c["end"]) for c in (sel.get("clips") or [])] or [(c["start"], c["end"]) for c in (cands or [])]
    if not moments:
        print("ERROR: montage needs moments: run video_analyze.py first, or give gameplay.segments / clips in the selection")
        sys.exit(1)
    n = max(2, min(len(moments), int(round(total / 6.0))))
    each = total / n
    out = []
    for a, b in moments[:n]:
        centre = (a + b) / 2
        st = max(0.0, min(centre - each / 2, info["duration"] - each))
        out.append((round(st, 2), round(st + each, 2)))
    return sorted(out)


def build_montage(ffmpeg, video, segs, dest):
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, (a, b) in enumerate(segs, 1):
            part = Path(td) / ("p%02d.mp4" % i)
            cmd = [ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % a, "-i", str(video), "-t", "%.3f" % (b - a), "-vf", VF_FIT,
                   "-r", "30"] + pp.h264_args(ffmpeg, 16) + [
                   "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(part)]
            run(cmd)
            parts.append(part)
        lst = Path(td) / "list.txt"
        lst.write_text("".join("file '%s'\n" % str(x).replace("\\", "/") for x in parts), encoding="utf-8")
        run([ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)] + pp.h264_args(ffmpeg, 16) + [
             "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dest)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--selection")
    ap.add_argument("--clips", type=int, default=4)
    ap.add_argument("--gameplay-seconds", type=float, default=25.0)
    ap.add_argument("--gameplay-montage", action="store_true", help="join the best moments into the gameplay video")
    ap.add_argument("--gameplay-polish", action="store_true",
                    help="montage with colour grade, zoom, speed changes, beat-synced transitions and our own music (original audio removed)")
    ap.add_argument("--gameplay-look", choices=["cinematic", "hype"], default="cinematic", help="look of the polished montage")
    ap.add_argument("--music-seed", type=int, default=None, help="seed of the generated gameplay music (default: from the map name)")
    args = ap.parse_args()
    if bool(args.auto) == bool(args.selection):
        print("ERROR: use exactly one of --auto or --selection <file>")
        sys.exit(1)

    video = Path(args.video)
    if not video.is_file():
        print("ERROR: video not found: %s" % video)
        sys.exit(1)
    ffmpeg, ffprobe = vt.require_tools()
    info = vt.probe(ffprobe, video)
    print("source: %s | %.0f s | %dx%d | %.1f fps" % (video.name, info["duration"], info["width"], info["height"], info["fps"]))
    if (info["width"], info["height"]) != (1920, 1080):
        print("WARNING: source is %dx%d, not 1920x1080: output is scaled/padded. Record at 1080p for the portal." % (
            info["width"], info["height"]))

    cap = pp.project_dir() / "captures"
    cands = None
    if args.auto:
        sel, cands = auto_selection(cap, info, args.clips, args.gameplay_seconds)
    else:
        sel = json.loads(Path(args.selection).read_text(encoding="utf-8"))

    polish = bool(args.gameplay_polish or (sel.get("gameplay") or {}).get("polish"))
    montage = bool(args.gameplay_montage or (sel.get("gameplay") or {}).get("montage"))
    mont_segs = None
    polish_moments = None
    if polish:
        # best moments first: the selection's clips, then the other analysed candidates that do not overlap them
        cfile = cap / "analysis" / "candidates.json"
        allc = cands or (json.loads(cfile.read_text(encoding="utf-8"))["candidates"] if cfile.exists() else [])
        polish_moments = [(c["start"], c["end"]) for c in (sel.get("clips") or [])]
        for c in allc:
            if all(c["end"] <= a or c["start"] >= b for a, b in polish_moments):
                polish_moments.append((c["start"], c["end"]))
        polish_seconds = (sel.get("gameplay") or {}).get("seconds", args.gameplay_seconds)
        sel["gameplay"] = {"polish": True, "seconds": polish_seconds}
        montage = False
    elif montage:
        total = (sel.get("gameplay") or {}).get("seconds", args.gameplay_seconds)
        mont_segs = montage_segments(sel, cands or (json.loads((cap / "analysis" / "candidates.json").read_text(encoding="utf-8"))["candidates"]
                                                    if (cap / "analysis" / "candidates.json").exists() else None), total, info)
        sel["gameplay"] = {"montage": True, "segments": [{"start": a, "end": b} for a, b in mont_segs]}

    # ---- validate times
    def check(a, b, what, lo=1.0, hi=None):
        if not (0 <= a < b <= info["duration"] + 0.01):
            print("ERROR: %s %.1f-%.1f is outside the video (0-%.1f s)" % (what, a, b, info["duration"]))
            sys.exit(1)
        if b - a < lo or (hi and b - a > hi):
            print("ERROR: %s length %.1f s out of range (%.0f-%s s)" % (what, b - a, lo, hi or "inf"))
            sys.exit(1)

    for i, c in enumerate(sel.get("clips", []), 1):
        check(c["start"], c["end"], "clip %d" % i, lo=2.0, hi=20.0)
    gp = sel.get("gameplay")
    if gp and mont_segs:
        for i, (a, b) in enumerate(mont_segs, 1):
            check(a, b, "montage segment %d" % i, lo=1.5, hi=20.0)
        tot = sum(b - a for a, b in mont_segs)
        if not 10.0 <= tot <= 40.0:
            print("ERROR: montage length %.1f s is outside 10-40 s" % tot)
            sys.exit(1)
    elif gp and polish:
        pass  # the polished montage plans its own segments from the moments
    elif gp:
        check(gp["start"], gp["end"], "gameplay", lo=10.0, hi=40.0)
    shots = sel.get("screenshots", [])
    if len(shots) > 3:
        print("ERROR: at most 3 screenshots")
        sys.exit(1)
    for t in shots:
        if not 0 <= t <= info["duration"]:
            print("ERROR: screenshot time %.1f outside the video" % t)
            sys.exit(1)
    if args.auto and cands:
        # sharpest frame of the first 3 distinct candidates
        for c in cands[:3]:
            ts = [c["start"] + (c["end"] - c["start"]) * f for f in (0.2, 0.4, 0.6, 0.8)]
            shots.append(max(ts, key=lambda t: sharpness(ffmpeg, video, t)))
        sel["screenshots"] = [round(t, 2) for t in shots]

    stamp = time.strftime("%Y%m%d_%H%M%S")
    (cap / "analysis").mkdir(parents=True, exist_ok=True)
    (cap / "analysis" / "selection_used.json").write_text(json.dumps(sel, indent=2), encoding="utf-8")

    if sel.get("clips"):
        d = cap / "clips"
        d.mkdir(parents=True, exist_ok=True)
        archive(d, "clip_*.mp4", stamp)
        for i, c in enumerate(sel["clips"], 1):
            dest = d / ("clip_%02d.mp4" % i)
            cut(ffmpeg, video, c["start"], c["end"], dest, fps=30)
            print("clip %d: %s-%s -> %s" % (i, vt.fmt_time(c["start"]), vt.fmt_time(c["end"]), dest.name))
    if gp:
        d = cap / "gameplay"
        d.mkdir(parents=True, exist_ok=True)
        archive(d, "gameplay.*", stamp)  # also moves the old gameplay.json
        dest = d / "gameplay.mp4"
        if polish and polish_moments:
            import gameplay_polish as gpol
            seed = args.music_seed if args.music_seed is not None else sum(map(ord, pp.project_name())) % 100000
            info_p = gpol.build(ffmpeg, video, polish_moments, polish_seconds, dest,
                                pp.project_dir() / "audio" / "gameplay_music.wav", seed, info["duration"], args.gameplay_look)
            print("gameplay: %s MONTAGE of %d real segments (grade, zoom, speed changes, beat-synced cuts), original audio "
                  "replaced by our generated music -> %s" % (args.gameplay_look.upper(), len(info_p["segments"]), dest))
            meta = {"mode": "montage", "polished": True, "source": video.name, **info_p}
        elif mont_segs:
            build_montage(ffmpeg, video, mont_segs, dest)
            print("gameplay: MONTAGE of %d real segments (%s), hard cuts, no effects -> %s" % (
                len(mont_segs), ", ".join("%s-%s" % (vt.fmt_time(a), vt.fmt_time(b)) for a, b in mont_segs), dest))
            meta = {"mode": "montage", "segments": [{"start": a, "end": b} for a, b in mont_segs], "source": video.name}
        else:
            cut(ffmpeg, video, gp["start"], gp["end"], dest, crf=16)
            print("gameplay: %s-%s (one continuous cut, no effects) -> %s" % (vt.fmt_time(gp["start"]), vt.fmt_time(gp["end"]), dest))
            meta = {"mode": "single", "segments": [{"start": gp["start"], "end": gp["end"]}], "source": video.name}
        (d / "gameplay.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if shots:
        d = cap / "screenshots"
        d.mkdir(parents=True, exist_ok=True)
        archive(d, "screenshot_*.*", stamp)
        for i, t in enumerate(shots, 1):
            out = screenshot(ffmpeg, video, t, d / ("screenshot_%02d" % i), args.gameplay_look if polish else None)
            print("screenshot %d: %.1f s -> %s (%.1f MB)" % (i, t, out.name, out.stat().st_size / 1048576.0))

    rc = 0
    if gp:
        print("\n--- validator (gameplay) ---")
        rc = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "video_validate.py"),
                             str(cap / "gameplay" / "gameplay.mp4"), "--kind", "gameplay"]).returncode
    print("\nDone. Selection saved in %s" % (cap / "analysis" / "selection_used.json"))
    sys.exit(rc)


if __name__ == "__main__":
    main()
