import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""First-run check: what works, what is missing and exactly what to do about it.

Usage: doctor.py [--quiet]
OK   = ready.   WARN = a feature is off (the kit still runs without it).   FAIL = nothing will run until you fix it.
Exit code 0 unless something FAILed.
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import promo_project as pp
import video_tools as vt

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
MODELS = [  # (ComfyUI models endpoint, file name, where to download)
    ("diffusion_models", "qwen_image_edit_2511_int8_convrot.safetensors", "docs/INSTALL.md step 4"),
    ("text_encoders", "qwen_2.5_vl_7b_fp8_scaled.safetensors", "docs/INSTALL.md step 4"),
    ("vae", "qwen_image_vae.safetensors", "docs/INSTALL.md step 4"),
]
results = []


def report(level, what, hint=""):
    results.append(level)
    print("%-5s %s" % (level, what))
    if hint and level != "OK":
        for line in hint.split("\n"):
            print("      -> " + line)


def get(url, timeout=4):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    print("Island Promo Factory - doctor (%s)\n" % (pp.ROOT / "VERSION").read_text().strip() if (pp.ROOT / "VERSION").exists() else "Island Promo Factory - doctor\n")

    # --- required ---
    v = sys.version_info
    report("OK" if v >= (3, 9) else "FAIL", "Python %d.%d.%d (%s)" % (v[0], v[1], v[2], sys.executable), "install Python 3.10+ or install ComfyUI portable next to this folder")
    for mod, pipname in (("PIL", "pillow"), ("numpy", "numpy")):
        try:
            __import__(mod)
            report("OK", "%s installed" % pipname)
        except ImportError:
            report("FAIL", "%s is missing" % pipname, "run:  %s -m pip install %s" % (sys.executable, pipname))

    # --- video (trailer, clips): WARN only, images work without it ---
    ffmpeg, ffprobe = vt.find_tool("ffmpeg", "FFMPEG_PATH"), vt.find_tool("ffprobe", "FFPROBE_PATH")
    if ffmpeg and ffprobe:
        try:
            enc = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
            if " libx264 " in enc:
                report("OK", "ffmpeg + ffprobe found, libx264 available (%s)" % ffmpeg)
            else:
                report("WARN", "ffmpeg found but without libx264 (%s)" % ffmpeg,
                       "an alternative H.264 encoder will be used if present; for best results use the GPL build:\nwinget install Gyan.FFmpeg   (then open a NEW terminal)")
        except Exception as e:
            report("WARN", "ffmpeg found but does not run (%s)" % e, "reinstall it: winget install Gyan.FFmpeg")
    else:
        report("WARN", "ffmpeg / ffprobe not found: trailer and video cutting are skipped",
               "winget install Gyan.FFmpeg   (then open a NEW terminal)\nor copy ffmpeg.exe and ffprobe.exe into Resources\\bin\\")

    # --- brand files (optional) ---
    fonts = list((pp.ROOT / "Resources" / "brand" / "font").glob("*.[ot]tf"))
    report("OK" if fonts else "WARN", "brand font: %s" % (fonts[0].name if fonts else "none, the bundled open font is used"),
           "optional: put your licensed title font in Resources\\brand\\font\\ (see the README there)")
    badges = [p for p in (pp.ROOT / "Resources" / "badges").glob("*.png")]
    report("OK" if badges else "WARN", "video badges (PEGI / Developed in Fortnite): %s" % ("%d file(s)" % len(badges) if badges else "none, the trailer has no badges"),
           "optional: download the official badges and put them in Resources\\badges\\ (see the README there)")

    # --- projects ---
    pd = pp.projects_dir()
    maps = pp.list_maps()
    report("OK" if pd.is_dir() else "WARN", "Projects folder: %s (%s)" % (pd, ", ".join(maps) if maps else "no maps yet"),
           "create the demo map:  python scripts\\make_demo.py     or your own:  new_map.bat my-map \"MY TITLE\"")

    # --- ComfyUI + models: WARN only, --no-qwen works without them ---
    try:
        get(COMFY_URL + "/system_stats")
        report("OK", "ComfyUI reachable at %s" % COMFY_URL)
        for folder, name, where in MODELS:
            try:
                have = get("%s/models/%s" % (COMFY_URL, folder))
            except Exception:
                have = []
            report("OK" if name in have else "WARN", "model %s%s" % (name, "" if name in have else " (missing)"),
                   "put it in ComfyUI\\models\\%s\\ - download links: %s" % (folder, where))
        try:
            ups = get("%s/models/upscale_models" % COMFY_URL)
        except Exception:
            ups = []
        report("OK" if ups else "WARN", "AI upscale model: %s" % (ups[0] if ups else "none (optional)"),
               "optional: RealESRGAN_x4plus.pth in ComfyUI\\models\\upscale_models\\")
    except Exception:
        report("WARN", "ComfyUI not reachable at %s: the AI horizontal art is off, everything else works" % COMFY_URL,
               "start it with start_comfyui.bat (or set COMFY_URL if it runs elsewhere)\nwithout it use:  run_all.bat <map> --no-qwen")

    fails, warns = results.count("FAIL"), results.count("WARN")
    print("\n%s" % ("READY - everything is in place." if not fails and not warns else
                    "NOT READY - fix the FAIL lines above." if fails else
                    "READY with %d optional item(s) missing (see WARN lines)." % warns))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
