import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Find the most salient moments of a long gameplay recording (3-20 min).

Usage: video_analyze.py <video> [--top 8] [--window 8] [--skip-start 10] [--skip-end 5]
Project: PROMO_PROJECT (or the only map). Output in Projects/<map>/captures/analysis/:
  candidates.json        ranked windows (start, end, score, motion, audio)
  contact_sheet_N.png    3 frames per candidate: review them and pick (an AI agent can read the sheet)
Method: motion energy (frame differences at 2 fps) + audio loudness and sudden loudness rises
(explosions, hits), robust z-scores, sliding window, non-overlapping top-K.
The source video is only read, never modified.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import promo_project as pp
import video_tools as vt

SAMPLE_FPS = 2.0


def read_motion(ffmpeg, video):
    cmd = [ffmpeg, "-v", "error", "-i", str(video), "-vf", "fps=%s,scale=160:90,format=gray" % SAMPLE_FPS,
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (160 * 90)
    if n < 4:
        return None
    frames = np.frombuffer(raw[: n * 160 * 90], dtype=np.uint8).reshape(n, 90, 160).astype(np.float32)
    diff = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    return np.concatenate([[0.0], diff])


def read_audio(ffmpeg, video, n_bins):
    cmd = [ffmpeg, "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    if len(raw) < 16000:
        return None
    pcm = np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    per_bin = int(8000 / SAMPLE_FPS)
    n = min(n_bins, len(pcm) // per_bin)
    if n < 4:
        return None
    rms = np.sqrt((pcm[: n * per_bin].reshape(n, per_bin) ** 2).mean(axis=1))
    rise = np.maximum(0.0, np.diff(rms, prepend=rms[0]))
    out = np.zeros(n_bins, dtype=np.float32)
    out[:n] = rms + 2.0 * rise
    return out


def robust_z(x):
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826
    return np.clip((x - med) / (mad + 1e-6), 0.0, 6.0)


def pick_windows(score, window, top, skip_start, skip_end):
    n = len(score)
    w = max(2, int(window * SAMPLE_FPS))
    cs = np.concatenate([[0.0], np.cumsum(score)])
    sums = (cs[w:] - cs[:-w]) / w
    lo = int(skip_start * SAMPLE_FPS)
    hi = max(lo + 1, n - w - int(skip_end * SAMPLE_FPS))
    sums[:lo] = -1
    sums[hi:] = -1
    picks = []
    for _ in range(top):
        i = int(np.argmax(sums))
        if sums[i] <= 0:
            break
        picks.append((i, float(sums[i])))
        sums[max(0, i - w): i + w] = -1
    return w, picks


def grab(ffmpeg, video, t, path, width=480):
    subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=%d:-1" % width, str(path)], capture_output=True)


def contact_sheets(ffmpeg, video, cands, out_dir, per_sheet=4):
    tw, th, pad, label_w = 480, 270, 6, 150
    tmp = out_dir / "_thumbs"
    tmp.mkdir(exist_ok=True)
    sheets = []
    for s0 in range(0, len(cands), per_sheet):
        group = cands[s0: s0 + per_sheet]
        sheet = Image.new("RGB", (label_w + 3 * (tw + pad), len(group) * (th + pad)), (20, 20, 24))
        d = ImageDraw.Draw(sheet)
        for r, c in enumerate(group):
            y = r * (th + pad)
            d.text((8, y + 8), "#%d" % c["id"], fill=(255, 220, 90))
            d.text((8, y + 28), "%s - %s" % (vt.fmt_time(c["start"]), vt.fmt_time(c["end"])), fill=(255, 255, 255))
            d.text((8, y + 48), "score %.2f" % c["score"], fill=(180, 220, 255))
            d.text((8, y + 68), "motion %.1f" % c["motion"], fill=(160, 160, 160))
            d.text((8, y + 88), "audio %.1f" % c["audio"], fill=(160, 160, 160))
            for k, frac in enumerate((0.1, 0.5, 0.9)):
                t = c["start"] + (c["end"] - c["start"]) * frac
                p = tmp / ("c%d_%d.png" % (c["id"], k))
                grab(ffmpeg, video, t, p, tw)
                if p.exists():
                    im = Image.open(p).convert("RGB").resize((tw, th))
                    sheet.paste(im, (label_w + k * (tw + pad), y))
        path = out_dir / ("contact_sheet_%d.png" % (len(sheets) + 1))
        sheet.save(path)
        sheets.append(path)
    return sheets


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--window", type=float, default=8.0, help="seconds per candidate window")
    ap.add_argument("--skip-start", type=float, default=10.0, help="ignore the first N s (menus, loading)")
    ap.add_argument("--skip-end", type=float, default=5.0)
    args = ap.parse_args()

    video = Path(args.video)
    if not video.is_file():
        print("ERROR: video not found: %s" % video)
        sys.exit(1)
    ffmpeg, ffprobe = vt.require_tools()
    info = vt.probe(ffprobe, video)
    print("video: %s | %.0f s (%s) | %dx%d | %.1f fps | audio=%s" % (
        video.name, info["duration"], vt.fmt_time(info["duration"]), info["width"], info["height"], info["fps"], info["has_audio"]))
    if info["duration"] < 20:
        print("ERROR: video shorter than 20 s, nothing to analyse")
        sys.exit(1)

    t0 = time.time()
    motion = read_motion(ffmpeg, video)
    if motion is None:
        print("ERROR: could not decode frames from %s" % video)
        sys.exit(1)
    audio = read_audio(ffmpeg, video, len(motion)) if info["has_audio"] else None
    print("analysed %d samples in %.0f s (audio: %s)" % (len(motion), time.time() - t0, "yes" if audio is not None else "no"))
    mz = robust_z(motion)
    if audio is not None:
        az = robust_z(audio)
        score = 0.45 * mz + 0.55 * az
    else:
        az = np.zeros_like(mz)
        score = mz

    w, picks = pick_windows(score, args.window, args.top, args.skip_start, args.skip_end)
    if not picks:
        print("ERROR: no salient window found (video too static or too short for the skip settings)")
        sys.exit(1)
    cands = []
    for k, (i, sc) in enumerate(sorted(picks, key=lambda p: -p[1]), 1):
        cands.append({
            "id": k,
            "start": round(i / SAMPLE_FPS, 2),
            "end": round((i + w) / SAMPLE_FPS, 2),
            "score": round(sc, 3),
            "motion": round(float(motion[i:i + w].mean()), 2),
            "audio": round(float(az[i:i + w].mean()), 2),
        })

    out_dir = pp.project_dir() / "captures" / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {"video": str(video), "duration": info["duration"], "window": args.window, "candidates": cands}
    (out_dir / "candidates.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    sheets = contact_sheets(ffmpeg, video, cands, out_dir)
    print("\nTop moments (best first):")
    for c in cands:
        print("  #%d  %s - %s  score %.2f (motion %.1f, audio %.1f)" % (
            c["id"], vt.fmt_time(c["start"]), vt.fmt_time(c["end"]), c["score"], c["motion"], c["audio"]))
    print("\nOutput: %s" % out_dir)
    for s in sheets:
        print("  %s" % s.name)
    print("Next: review the contact sheets, then run video_extract.py (--auto or --selection).")


if __name__ == "__main__":
    main()
