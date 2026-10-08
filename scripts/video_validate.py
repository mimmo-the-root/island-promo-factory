import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Validate a video against the Epic Creator Portal specs (read-only, uses ffprobe).

Usage: video_validate.py <file> [--kind trailer|gameplay]
Checks: container mp4/mkv/webm/mov, 1920x1080, duration 10-40 s, size < 400 MB,
video stream present. Reports fps / codec / audio. Exit 1 on any failed check.
The file is NEVER modified. Gameplay must be real, unedited footage with in-game UI.
Env: PROMO_DEBUG=1 prints the raw ffprobe JSON; FFPROBE_PATH overrides the binary.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("PROMO_DEBUG") == "1"
OK_FORMATS = {"mp4", "mov", "matroska", "webm"}  # ffprobe format_name tokens
OK_EXT = {".mp4", ".mkv", ".webm", ".mov"}


def find_ffprobe():
    env = os.environ.get("FFPROBE_PATH")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffprobe")
    if found:
        return found
    ff = os.environ.get("FFMPEG_PATH")
    if ff:
        sib = Path(ff).with_name("ffprobe" + (".exe" if os.name == "nt" else ""))
        if sib.exists():
            return str(sib)
    local = ROOT / "Resources" / "bin" / "ffprobe.exe"
    return str(local) if local.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--kind", choices=["trailer", "gameplay"], default="trailer")
    a = ap.parse_args()

    path = Path(a.file)
    if not path.is_file():
        print("ERROR: file not found: %s" % path)
        sys.exit(1)
    probe = find_ffprobe()
    if not probe:
        print("ERROR: ffprobe not found (install ffmpeg: winget install Gyan.FFmpeg, "
              "or set FFPROBE_PATH, or put ffprobe.exe in PromoFactory\\Resources\\bin\\)")
        sys.exit(1)
    r = subprocess.run([probe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if r.returncode != 0:
        print("ERROR: ffprobe failed: %s" % r.stderr.strip())
        sys.exit(1)
    if DEBUG:
        print("[debug] raw ffprobe output:\n" + r.stdout)
    info = json.loads(r.stdout)
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    print("Validating (%s): %s" % (a.kind, path))
    failed = 0

    def check(ok, label, detail=""):
        nonlocal failed
        print("%s  %s%s" % ("PASS" if ok else "FAIL", label, (" - " + detail) if detail else ""))
        if not ok:
            failed += 1

    names = set(str(fmt.get("format_name", "")).split(","))
    check(bool(names & OK_FORMATS) and path.suffix.lower() in OK_EXT, "container mp4/mkv/webm/mov",
          "format=%s ext=%s" % (fmt.get("format_name"), path.suffix))
    check(video is not None, "has a video stream")
    if video is not None:
        w, h = video.get("width"), video.get("height")
        check((w, h) == (1920, 1080), "resolution exactly 1920x1080", "%sx%s" % (w, h))
    try:
        dur = float(fmt.get("duration") or (video or {}).get("duration") or 0)
    except ValueError:
        dur = 0.0
    check(10.0 <= dur <= 40.0, "duration 10-40 s", "%.2f s" % dur)
    size_mb = path.stat().st_size / 1048576.0
    check(size_mb < 400, "size < 400 MB", "%.1f MB" % size_mb)

    if video is not None:
        num, _, den = str(video.get("avg_frame_rate", "0/1")).partition("/")
        try:
            fps = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        print("INFO  video: codec=%s pix_fmt=%s fps=%.2f" % (video.get("codec_name"), video.get("pix_fmt"), fps))
    if audio is not None:
        print("INFO  audio: codec=%s %s Hz, %s ch" % (audio.get("codec_name"), audio.get("sample_rate"), audio.get("channels")))
    else:
        print("INFO  audio: none")

    if a.kind == "gameplay":
        print("REMINDER: gameplay video must be REAL, UNEDITED gameplay footage including the in-game UI. "
              "No cuts, effects, overlays or badges. This script only validates and never modifies the file.")

    print("VERDICT: %s" % ("FAIL (%d check(s) failed)" % failed if failed else "PASS"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
