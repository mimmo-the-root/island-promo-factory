import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Shared helpers for the video scripts (ffmpeg / ffprobe lookup, probing)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("PROMO_DEBUG") == "1"


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
    local = ROOT / "Resources" / "bin" / (name + ".exe")
    if local.exists():
        return str(local)
    ff = os.environ.get("FFMPEG_PATH")
    if ff:
        sib = Path(ff).with_name(exe)
        if sib.exists():
            return str(sib)
    return None


def require_tools():
    ffmpeg = find_tool("ffmpeg", "FFMPEG_PATH")
    ffprobe = find_tool("ffprobe", "FFPROBE_PATH")
    if not ffmpeg or not ffprobe:
        print("ERROR: ffmpeg/ffprobe not found. Install: winget install Gyan.FFmpeg "
              "(then open a NEW terminal), or set FFMPEG_PATH, or copy both into Resources\\bin\\")
        sys.exit(1)
    return ffmpeg, ffprobe


def probe(ffprobe, path):
    """Return dict(duration, width, height, fps, has_audio, size_mb)."""
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print("ERROR: ffprobe could not read %s:\n%s" % (path, out.stderr.strip()))
        sys.exit(1)
    data = json.loads(out.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if v is None:
        print("ERROR: no video stream in %s" % path)
        sys.exit(1)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    duration = float(data.get("format", {}).get("duration") or v.get("duration") or 0)
    return {
        "duration": duration,
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": fps,
        "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
        "size_mb": float(data.get("format", {}).get("size", 0)) / 1048576.0,
    }


def fmt_time(t):
    t = int(round(t))
    return "%d:%02d" % (t // 60, t % 60)
