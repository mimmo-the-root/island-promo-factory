import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Polished gameplay montage: colour grade, zoom punches, speed changes, beat-synced transitions, our own music.

Used by video_extract.py (--gameplay-montage --gameplay-polish [--gameplay-look cinematic|hype]). The footage is still real gameplay, but it is
edited: the original audio is removed and replaced by a track synthesised by music_generator.py (no third-party
material). Check Epic's current rules before uploading edited footage as the portal gameplay video.

build(ffmpeg, video, moments, total_seconds, dest, music_path, seed, source_duration, style='cinematic') -> info dict
build_scenes(..., n=3, style=...)  -> 2-3 real scenes, soft dissolves, same grade, music instead of the original audio
"""
import subprocess
import sys
import shutil
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
    import exposure
    g = exposure.video_gamma(ffmpeg, video, st, need)     # dark segment -> gentle gamma lift (exposure.py rules)
    if g > 1.0:
        print("  exposure: gamma %.2f" % g)
        look = exposure.with_gamma(look, g)
    chain = clip_graph(look, speed, out_len, zoom_in)
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % st, "-t", "%.3f" % need, "-i", str(video), "-an",
           "-filter_complex", chain, "-map", "[v]", "-t", "%.3f" % out_len] + pp.h264_args(ffmpeg, 15) + ["-r", "30", str(dest)]
    _run(cmd)


def _ai_montage_track(total, seed, music_path):
    """AI music for the beat-synced montage: returns the MEASURED bpm and writes the trimmed track (first downbeat at t=0) to music_path,
    or returns None when AI music is off / not available / fails (the caller then uses the synthesiser)."""
    try:
        import music_ai
        import music_beats
        import music_generator as mg
        if music_ai.engine_setting() == "synth":
            return None
        ok, why = music_ai.ai_ready()
        if not ok:
            print("polish: AI music not used (%s) -> synthesiser" % why)
            return None
        need_s = min(total, 38.0) + 8.0
        shared = music_path.parent / "music.wav"          # the track of the run's "music" stage: same sound as the trailer, no new generation
        info, raw = None, None
        try:
            if (music_path.parent / "music_engine.txt").read_text(encoding="utf-8").strip() == "ai" and shared.is_file():
                import wave as _wave
                with _wave.open(str(shared), "rb") as _w:
                    if _w.getnframes() / float(_w.getframerate()) >= need_s:
                        raw, info = shared, {"bpm": music_ai.MOODS.get(mg.config_mood(), music_ai.MOODS["action"])[1]}
                        print("polish: using the AI track %s (same as the trailer)" % shared.name)
        except Exception:
            raw = None
        if raw is None:
            raw = music_path.parent / "_candidates" / "montage_raw.wav"
            info = music_ai.generate_ai(mg.config_mood(), min(total, 38.0) + 14.0, seed, raw, music_ai.candidates_setting())
        bpm, first, conf = music_beats.detect(raw, info["bpm"])
        print("polish: tempo %.2f bpm, first downbeat at %.2f s (confidence %.2f)" % (bpm, first, conf))
        import video_tools as vt
        ff = vt.find_tool("ffmpeg", "FFMPEG_PATH")
        r = subprocess.run([str(ff), "-y", "-v", "error", "-ss", "%.3f" % first, "-i", str(raw), "-c:a", "pcm_s16le", str(music_path)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not music_path.exists():
            raise RuntimeError("could not trim the track: %s" % (r.stderr or "")[-200:])
        return bpm
    except (Exception, SystemExit) as e:
        print("polish: AI music failed (%s) -> synthesiser" % e)
        return None


def build(ffmpeg, video, moments, total, dest, music_path, seed, source_duration, style="cinematic"):
    look = LOOKS[style]
    import music_generator as mg
    music_path = Path(music_path)
    music_path.parent.mkdir(parents=True, exist_ok=True)
    # 1) the music first: its tempo drives the edit. AI music (ACE-Step): measure its real tempo and first downbeat, trim the track so
    #    the first bar starts at t=0, and plan every cut on that measured beat grid. Synth (or any AI problem): the old way, exact tempo known.
    bpm = _ai_montage_track(total, seed, music_path)
    if bpm is not None:
        segs, seg_len, ov, n, out_total = plan(moments, total, bpm, source_duration, look)
        print("polish: AI music, measured %.2f bpm -> %s" % (bpm, music_path.name))
    else:
        probe_buf, bpm, key, prog = mg.generate(seed, 8.0, "action")
        segs, seg_len, ov, n, out_total = plan(moments, total, bpm, source_duration, look)
        buf, bpm, key, prog = mg.generate(seed, out_total + 1.0, "action")
        mg.write_wav(music_path, buf)
        print("polish: music seed=%d bpm=%d -> %s" % (seed, bpm, music_path.name))
    beat = 60.0 / bpm
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
        cmd += pp.h264_args(ffmpeg, 20) + ["-r", "30", "-af", "afade=t=in:st=0:d=0.1,afade=t=out:st=%.3f:d=1.2,apad" % (out_total - 1.2),
                                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "%.3f" % out_total,
                                           "-movflags", "+faststart", str(dest)]
        _run(cmd)
    return {"segments": [{"start": s, "end": round(s + nd, 3), "speed": sp} for s, nd, sp in segs], "bpm": bpm,
            "seed": seed, "style": style, "seconds": round(out_total, 2), "music": music_path.name}


def build_scenes(ffmpeg, video, moments, total, dest, music_path, seed, source_duration, n=3, style="cinematic"):
    """The portal gameplay video as 2-3 REAL scenes (the best moments), played at normal speed with the look's grade,
    joined by short dissolves; our generated music replaces the original audio. No speed ramps, no zoom, no bars."""
    import music_generator as mg
    n = 2 if int(n) <= 2 else 3
    look = dict(LOOKS[style], speeds=[1.0], zoom=0.0, letterbox=0, pulse=0.0, grain=min(4, LOOKS[style]["grain"]))
    total = max(10.0, min(38.0, float(total)))
    if len(moments) < n:
        print("ERROR: %d scenes need %d moments, only %d found (run video_analyze.py on a longer recording)" % (n, n, len(moments)))
        sys.exit(1)
    ov = 0.6
    seg_len = (total - ov) / n
    need = min(seg_len + ov, source_duration)
    chosen = sorted(moments[:n], key=lambda m: m[0])
    segs = []
    for a, b in chosen:
        centre = (a + b) / 2.0
        st = max(0.0, min(centre - need / 2.0, source_duration - need))
        segs.append((round(st, 3), round(need, 3)))
    music_path = Path(music_path)
    music_path.parent.mkdir(parents=True, exist_ok=True)
    gen = music_path.parent / "music.wav"
    reuse = False
    if gen.is_file() and (music_path.parent / "music_engine.txt").exists():
        try:
            import wave as _wave
            with _wave.open(str(gen), "rb") as _w:
                reuse = _w.getnframes() / float(_w.getframerate()) >= total + 1.0       # long enough: gameplay and trailer share ONE track
        except Exception:
            reuse = False
    if reuse:
        shutil.copyfile(str(gen), str(music_path))
        bpm = 0
        print("polish: music: reusing %s (same track as the trailer)" % gen.name)
    else:
        import music_ai
        bpm = music_ai.make_track(mg.config_mood(), total + 1.0, seed, music_path).get("bpm", 0)   # mood chosen for the map (dark for horror, epic, calm, action)
    print("scenes: %d real scenes x %.1f s, dissolves %.1f s, total %.1f s, music seed=%d bpm=%d" % (n, seg_len, ov, total, seed, bpm))
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, (st, nd) in enumerate(segs):
            part = Path(td) / ("part%02d.mp4" % i)
            _render_part(ffmpeg, video, st, nd, 1.0, seg_len + ov, part, True, look)
            parts.append(part)
            print("  scene %d/%d  src %.1f-%.1f s" % (i + 1, n, st, st + nd))
        chain, last = [], "[0:v]"
        for k in range(1, n):
            chain.append("%s[%d:v]xfade=transition=dissolve:duration=%.3f:offset=%.3f[x%d]" % (last, k, ov, k * seg_len, k))
            last = "[x%d]" % k
        chain.append("%sfade=t=in:st=0:d=0.4,fade=t=out:st=%.3f:d=0.8,format=yuv420p[v]" % (last, total - 0.8))
        cmd = [ffmpeg, "-v", "error", "-y"]
        for p_ in parts:
            cmd += ["-i", str(p_)]
        cmd += ["-i", str(music_path), "-filter_complex", ";".join(chain), "-map", "[v]", "-map", "%d:a" % n]
        cmd += pp.h264_args(ffmpeg, 20) + ["-r", "30", "-af", "afade=t=in:st=0:d=0.1,afade=t=out:st=%.3f:d=1.2" % (total - 1.2),
                                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "%.3f" % total,
                                           "-movflags", "+faststart", str(dest)]
        _run(cmd)
    return {"segments": [{"start": s, "end": round(s + nd, 3), "speed": 1.0} for s, nd in segs], "bpm": bpm, "seed": seed,
            "style": style, "seconds": round(total, 2), "music": music_path.name, "scenes": n}
