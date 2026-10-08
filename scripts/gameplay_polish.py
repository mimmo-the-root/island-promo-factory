import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Polished gameplay montage: colour grade, zoom punches, speed changes, beat-synced transitions, our own music.

Used by video_extract.py (--gameplay-montage --gameplay-polish [--gameplay-look cinematic|hype]). The footage is still real gameplay, but it is
edited: the original audio is removed and replaced by a track synthesised by music_generator.py (no third-party
material). Check Epic's current rules before uploading edited footage as the portal gameplay video.

build(ffmpeg, video, moments, total_seconds, dest, music_path, seed, source_duration, style='cinematic') -> info dict
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import promo_project as pp

VF_FIT = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
LOOKS = {
    # cinematic: 2.39:1 letterbox, soft warm grade, soft bloom, film grain, slow push-ins, dissolves, gentle speed changes
    "cinematic": {
        "transitions": ["fade", "dissolve", "smoothleft", "fadeblack", "dissolve"],
        "speeds": [1.15, 0.85, 1.3, 0.9, 1.2, 0.85],
        "grade": ("eq=contrast=1.05:saturation=1.08:gamma=1.0,"
                  "colorbalance=rh=0.03:bh=-0.02,"      # warm highlights only: blue shadows + red highlights read as purple
                  "curves=preset=medium_contrast"),
        "bloom": 0.12, "grain": 7, "zoom": 0.06, "pulse": 0.025, "letterbox": 140, "ov_beats": 1.5,
    },
    # hype: faster, punchier, white flashes, no bars
    "hype": {
        "transitions": ["fadewhite", "slideleft", "smoothleft", "circleopen", "radial"],
        "speeds": [1.25, 1.0, 1.6, 1.1, 1.4, 1.0],
        "grade": ("eq=contrast=1.12:saturation=1.45:gamma=1.04,"
                  "colorbalance=rs=-0.06:bs=0.08:rh=0.10:gh=0.02:bh=-0.08,unsharp=5:5:0.7:5:5:0.0"),
        "bloom": 0.0, "grain": 0, "zoom": 0.10, "pulse": 0.05, "letterbox": 0, "ov_beats": 0.75,
    },
}
MIN_SEGMENTS = 4


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: ffmpeg failed:\n%s" % r.stderr.strip()[-1800:])
        sys.exit(1)


def plan(moments, total, bpm, source_duration, look):
    """Beat-aligned plan: n >= 4 segments of L seconds (a multiple of 4 beats) joined by transitions of ov seconds.
    Returns [(src_start, src_len, speed)], L, ov, n, final length."""
    beat = 60.0 / bpm
    total = max(10.0, min(38.0, float(total)))
    n = max(MIN_SEGMENTS, int(round(total / 6.2)))
    if len(moments) < n:
        print("ERROR: the montage needs at least %d moments, only %d found (run video_analyze.py on a longer recording)" % (
            n, len(moments)))
        sys.exit(1)
    bar4 = 4 * beat
    seg_len = max(bar4, round((total / n) / bar4) * bar4)
    ov = look["ov_beats"] * beat
    chosen = sorted(moments[:n], key=lambda m: m[0])
    segs = []
    for i, (a, b) in enumerate(chosen):
        speed = look["speeds"][i % len(look["speeds"])]
        need = (seg_len + ov) * speed
        if need > source_duration:
            need = source_duration
        centre = (a + b) / 2.0
        st = max(0.0, min(centre - need / 2.0, source_duration - need))
        segs.append((round(st, 3), round(need, 3), speed))
    return segs, seg_len, ov, n, n * seg_len + ov


def clip_graph(look, speed, out_len, zoom_in, letterbox=False):
    """filter_complex string ([0:v] -> [v]): speed, 1920x1080 fit, slow push-in/out, grade, vignette, bloom, grain
    (and the letterbox bars when asked). Shared by the gameplay montage and the trailer's real clips."""
    d = max(0.1, out_len)
    z = look["zoom"]
    if zoom_in:
        w = "trunc(1920*(1+%.3f*t/%.3f)/2)*2" % (z, d)
        h = "trunc(1080*(1+%.3f*t/%.3f)/2)*2" % (z, d)
    else:
        w = "trunc(1920*(1+%.3f*(1-t/%.3f))/2)*2" % (z, d)
        h = "trunc(1080*(1+%.3f*(1-t/%.3f))/2)*2" % (z, d)
    chain = ("[0:v]setpts=(PTS-STARTPTS)/%.3f,fps=30,%s,scale=w='%s':h='%s':eval=frame,crop=1920:1080,%s,vignette=PI/6,"
             "format=yuv420p") % (speed, VF_FIT, w, h, look["grade"])
    if look["bloom"] > 0:
        chain += (",split[a][b];[b]gblur=sigma=18[g];[a][g]blend=c0_mode=screen:c0_opacity=%.2f:c1_opacity=0:c2_opacity=0") % look["bloom"]
    if look["grain"] > 0:
        chain += ",noise=alls=%d:allf=t" % look["grain"]
    if letterbox and look["letterbox"]:
        lb = look["letterbox"]
        chain += ",crop=1920:%d:0:%d,pad=1920:1080:0:%d:black" % (1080 - 2 * lb, lb, lb)
    return chain + ",format=yuv420p[v]"


def still_graph(look):
    """filter_complex string ([0:v] -> [v]) for ONE screenshot: same grade, vignette and bloom as the videos
    (no grain-heavy noise, no letterbox: the portal needs a full 1920x1080 frame)."""
    chain = "[0:v]%s,%s,vignette=PI/7,format=yuv420p" % (VF_FIT, look["grade"])
    if look["bloom"] > 0:
        chain += ",split[a][b];[b]gblur=sigma=18[g];[a][g]blend=c0_mode=screen:c0_opacity=%.2f:c1_opacity=0:c2_opacity=0" % look["bloom"]
    else:
        chain += ",unsharp=5:5:0.5:5:5:0.0"
    return chain + ",format=yuv420p[v]"


def _render_part(ffmpeg, video, st, need, speed, out_len, dest, zoom_in, look):
    chain = clip_graph(look, speed, out_len, zoom_in)
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % st, "-t", "%.3f" % need, "-i", str(video), "-an",
           "-filter_complex", chain, "-map", "[v]", "-t", "%.3f" % out_len] + pp.h264_args(ffmpeg, 15) + ["-r", "30", str(dest)]
    _run(cmd)


def build(ffmpeg, video, moments, total, dest, music_path, seed, source_duration, style="cinematic"):
    look = LOOKS[style]
    import music_generator as mg
    # 1) our own music first: its tempo drives the edit
    probe_buf, bpm, key, prog = mg.generate(seed, 8.0, "action")
    segs, seg_len, ov, n, out_total = plan(moments, total, bpm, source_duration, look)
    buf, bpm, key, prog = mg.generate(seed, out_total + 1.0, "action")
    music_path = Path(music_path)
    music_path.parent.mkdir(parents=True, exist_ok=True)
    mg.write_wav(music_path, buf)
    beat = 60.0 / bpm
    print("polish: music seed=%d bpm=%d -> %s" % (seed, bpm, music_path.name))
    print("polish: %d segments x %.2f s (speeds %s), transitions %.2f s, total %.1f s" % (
        n, seg_len, ", ".join("%.2gx" % s[2] for s in segs), ov, out_total))

    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, (st, need, speed) in enumerate(segs):
            part = Path(td) / ("part%02d.mp4" % i)
            _render_part(ffmpeg, video, st, need, speed, seg_len + ov, part, (i % 2 == 0), look)
            parts.append(part)
            print("  part %d/%d  src %.1f-%.1f s  speed %.2gx" % (i + 1, n, st, st + need, speed))
        # 2) join with beat-aligned transitions, pulse on every beat, fades; our music replaces the original audio
        chain, last = [], "[0:v]"
        for k in range(1, n):
            tr = look["transitions"][(k - 1) % len(look["transitions"])]
            chain.append("%s[%d:v]xfade=transition=%s:duration=%.3f:offset=%.3f[x%d]" % (last, k, tr, ov, k * seg_len, k))
            last = "[x%d]" % k
        tail = ("%seq=brightness='%.3f*exp(-7*mod(t,%.4f))':saturation='1+0.10*exp(-7*mod(t,%.4f))':eval=frame"
                % (last, look["pulse"], beat, beat))
        if look["letterbox"]:
            lb = look["letterbox"]
            tail += ",crop=1920:%d:0:%d,pad=1920:1080:0:%d:black" % (1080 - 2 * lb, lb, lb)
        tail += ",fade=t=in:st=0:d=0.4,fade=t=out:st=%.3f:d=0.8,format=yuv420p[v]" % (out_total - 0.8)
        chain.append(tail)
        graph = ";".join(chain)  # inline: newer ffmpeg builds dropped -filter_complex_script
        cmd = [ffmpeg, "-v", "error", "-y"]
        for p in parts:
            cmd += ["-i", str(p)]
        cmd += ["-i", str(music_path), "-filter_complex", graph, "-map", "[v]", "-map", "%d:a" % n]
        cmd += pp.h264_args(ffmpeg, 20) + ["-r", "30", "-af", "afade=t=in:st=0:d=0.1,afade=t=out:st=%.3f:d=1.2" % (out_total - 1.2),
                                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "%.3f" % out_total,
                                           "-movflags", "+faststart", str(dest)]
        _run(cmd)
    return {"segments": [{"start": s, "end": round(s + nd, 3), "speed": sp} for s, nd, sp in segs], "bpm": bpm,
            "seed": seed, "style": style, "seconds": round(out_total, 2), "music": music_path.name}
