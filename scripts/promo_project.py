import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Per-map project resolution for Island Promo Factory (one map at a time).

The active map is selected with the PROMO_PROJECT environment variable
(factory.py --project <slug> sets it). With no selection, the only map under Projects/ is used.
Maps live in ..\\Projects (or PROMO_PROJECTS_DIR, or Projects\\ inside the repo). Layout: <Projects>/<slug>/{input,background,characters,final,title,config.json}
Shared defaults (prompts, workflow) live in Resources/prompts and workflows/;
a file with the same name inside the project folder overrides the shared one.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "Resources" / "prompts"
WORKFLOWS_DIR = ROOT / "workflows"


CONSOLE_PORT_DEFAULT = 8791      # the live console (was 8765, used by another local console); PROMO_CONSOLE_PORT or --port overrides


def console_port():
    try:
        return int(os.environ.get("PROMO_CONSOLE_PORT", CONSOLE_PORT_DEFAULT))
    except ValueError:
        return CONSOLE_PORT_DEFAULT


def projects_dir():
    """Where the map folders live: PROMO_PROJECTS_DIR, else a sibling folder ..\\Projects if it exists, else Projects\\ inside this repo."""
    env = os.environ.get("PROMO_PROJECTS_DIR")
    if env:
        return Path(env)
    sibling = ROOT.parent / "Projects"
    return sibling if sibling.is_dir() else ROOT / "Projects"


def list_maps():
    base = projects_dir()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "config.json").exists())


def project_name():
    name = os.environ.get("PROMO_PROJECT")
    if name:
        return name
    maps = list_maps()
    if len(maps) == 1:
        return maps[0]
    raise SystemExit("Which map? Pass --project <slug> (or set PROMO_PROJECT). Available: %s" % (", ".join(maps) or "none - run new_map.bat first"))


def find_python():
    """Interpreter for child scripts: PROMO_PYTHON, then ComfyUI's embedded python (the sibling folder
    ..\\ComfyUI_windows_portable, else inside this folder, else the legacy ..\\python_embeded), else the interpreter running this script."""
    import sys
    env = os.environ.get("PROMO_PYTHON")
    if env and Path(env).exists():
        return Path(env)
    if os.name == "nt":
        for c in (ROOT.parent / "ComfyUI_windows_portable" / "python_embeded" / "python.exe", ROOT / "ComfyUI_windows_portable" / "python_embeded" / "python.exe", ROOT.parent / "python_embeded" / "python.exe"):
            if c.exists():
                return c
    return Path(sys.executable)


def plan_b_default(proj=None):
    """Portrait mode for the map's hero: "direct" (full figure, legs included) when the character is complete, else "bust" (half body fading
    into the scene). complete in config.json (set by conform.py hero) wins; otherwise the cut-out is judged: it must not touch the bottom
    border (feet) and must be taller than wide (a standing figure). A map used to get "bust" always, which cut the legs of every full-body hero."""
    proj = Path(proj) if proj else project_dir()
    try:
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
        chars = cfg.get("characters") or [{}]
        flag = chars[0].get("complete")
        if isinstance(flag, bool):
            return "direct" if flag else "bust"
        f = proj / chars[0].get("file", "characters/character_01.png")
        from PIL import Image
        import numpy as np
        al = np.array(Image.open(f).convert("RGBA").getchannel("A")) > 128
        h, w = al.shape
        ys, xs = np.where(al)
        if len(ys) == 0:
            return "bust"
        # judge the FIGURE (its bounding box), not the file: skins are often exported with big transparent margins (860x1033 file, 350x950 figure)
        fh, fw = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
        feet_cut = int(al[-3:].sum()) >= 8
        return "direct" if (not feet_cut and fh / fw >= 1.6) else "bust"
    except Exception:
        return "bust"


def project_dir():
    return projects_dir() / project_name()


def load_config():
    path = project_dir() / "config.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def shared_or_project(name, shared_dir):
    """Project file wins; otherwise the shared default."""
    own = project_dir() / name
    return own if own.exists() else shared_dir / name


def prompt_path(name):
    return shared_or_project(name, PROMPTS_DIR)


def load_prompt(name):
    path = prompt_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def workflow_path(name="qwen_workflow_api.json"):
    return shared_or_project(name, WORKFLOWS_DIR)


_H264_CACHE = {}


def h264_args(ffmpeg, crf=18):
    """Video encoder arguments: libx264 when this ffmpeg build has it, else the best H.264 encoder available.
    (LGPL ffmpeg builds have no libx264.) Always yuv420p."""
    import subprocess
    key = str(ffmpeg)
    if key not in _H264_CACHE:
        try:
            out = subprocess.run([key, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
        except Exception:
            out = ""
        names = [e for e in ("libx264", "h264_nvenc", "libopenh264", "h264_mf", "h264_qsv", "h264_amf") if (" %s " % e) in out]
        _H264_CACHE[key] = names[0] if names else "libx264"
        if _H264_CACHE[key] != "libx264":
            print("    note: libx264 not in this ffmpeg build, using %s" % _H264_CACHE[key])
    enc = _H264_CACHE[key]
    if enc == "libx264":
        return ["-c:v", enc, "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if enc == "h264_nvenc":
        return ["-c:v", enc, "-preset", "p5", "-rc", "vbr", "-cq", str(crf + 4), "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", enc, "-b:v", "16M", "-pix_fmt", "yuv420p"]


def normalize_background(path=None):
    """Makes background/background.png a plain RGB image. Palette PNGs with a 'transparent colour' (tRNS) and RGBA files with
    holes are the classic trap: white pixels (lightning, sun, snow) silently turn transparent in every derived file. The original
    is kept as input/background_source.png before the first rewrite. Returns True if the file was changed."""
    from PIL import Image
    path = Path(path) if path else project_dir() / "background" / "background.png"
    if not path.exists():
        return False
    with Image.open(path) as im:
        im.load()
        risky = im.mode != "RGB" or "transparency" in im.info
        if not risky:
            return False
        if im.mode in ("RGBA", "LA", "PA"):
            base = Image.new("RGB", im.size, (0, 0, 0))
            base.paste(im.convert("RGBA"), mask=im.convert("RGBA").getchannel("A"))
            flat = base
        else:
            flat = Image.new("RGB", im.size)
            flat.paste(im.convert("RGB"))                   # colours only: the colour-key info is not carried over
    keep = path.parent.parent / "input" / "background_source.png"
    if not keep.exists():
        keep.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copyfile(str(path), str(keep))
    flat.save(path)
    print("  note: background.png was a %s image (colour-key / alpha trap): rewritten as plain RGB, original kept in input/background_source.png" % im.mode)
    return True
