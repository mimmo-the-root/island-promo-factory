import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Step 0 of every map: collect and verify the prerequisites, create or reuse the map project, say what is missing.

Usage:
  intake.py                                   list the existing maps
  intake.py --project SLUG                    check an existing map (read-only)
  intake.py --project SLUG --init --title "MAP TITLE" --island-code 1234-5678-9012 [--style SCI_FI] [--identity "..."]
                                              create the map (or reuse it) and write these values into config.json
  add --json for a machine-readable report.

Exit code: 0 = READY to run the pipeline, 1 = something blocks it (see the BLOCK lines), 2 = usage error.
BLOCK = the pipeline cannot start.  WARN = a feature is off.  OK = ready.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

import doctor
import promo_project as pp
import video_tools as vt

SCRIPTS = Path(__file__).resolve().parent
PLACEHOLDER = "DESCRIBE THE CHARACTER"
RECORDING_EXT = (".mp4", ".mkv", ".mov", ".webm")
ISLAND_CODE = re.compile(r"^\d{4}-\d{4}-\d{4}$")
rows = []


def add(level, what, fix=""):
    rows.append({"level": level, "what": what, "fix": fix})


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def check_config(proj, cfg):
    title = str(cfg.get("title", "")).strip()
    add("OK" if title else "BLOCK", "title: %s" % (title or "missing"), "ask the user for the map title (as shown in Discover)")
    code = str(cfg.get("island_code", "")).strip()
    if ISLAND_CODE.match(code):
        add("OK", "island code: %s" % code)
    else:
        add("BLOCK", "island code: %s" % (code or "missing"), "ask the user for the island code, format 1234-5678-9012")
    brand = json.loads((pp.ROOT / "Resources" / "brand" / "brand.json").read_text(encoding="utf-8"))
    styles = list(brand["typography"]["styles"])
    style = cfg.get("style", "")
    add("OK" if style in styles else "BLOCK", "title style: %s" % (style or "missing"), "choose one of: %s" % ", ".join(styles))
    chars = cfg.get("characters") or []
    if not chars:
        add("BLOCK", "no character defined in config.json", "add one entry under characters (file + identity)")
    for c in chars[:1]:
        ident = str(c.get("identity", "")).strip()
        if not ident or PLACEHOLDER in ident:
            add("BLOCK", "character identity is still the placeholder", "ask the user to describe the character in one sentence: helmet/face/hair, armor, weapon, companion")
        else:
            add("OK", "character identity written (%d chars)" % len(ident))
    if cfg.get("ip", {}).get("star_wars"):
        add("OK", "IP notice: Star Wars wording will be used in the island description")
    else:
        add("OK", "IP notice: generic Epic Games wording (set ip.disclaimer for your own text)")


def check_images(proj, cfg):
    bg = proj / (cfg.get("scene", {}).get("background") or "background/background.png")
    if not bg.exists():
        add("BLOCK", "background image missing: %s" % bg.relative_to(proj), "environment only (no characters), at least 1920 px wide: a UEFN capture of the island")
    else:
        w, h = Image.open(bg).size
        if w < 1280:
            add("BLOCK", "background is too small (%dx%d)" % (w, h), "use a capture at least 1920 px wide")
        elif w < 1920:
            add("WARN", "background is small (%dx%d), quality will suffer" % (w, h), "1920 px wide or more is recommended")
        else:
            add("OK", "background %dx%d" % (w, h))
    for c in (cfg.get("characters") or [])[:1]:
        f = proj / c.get("file", "characters/character_01.png")
        if not f.exists():
            add("BLOCK", "character image missing: %s" % f.relative_to(proj),
                "ONE character, transparent PNG. A render on a flat background works too:\npython scripts/prepare_character.py <image> --project %s" % proj.name)
            continue
        im = Image.open(f)
        if im.mode != "RGBA" or im.getchannel("A").getextrema()[0] == 255:
            add("BLOCK", "character %s has no transparency" % f.name, "run:  python scripts/prepare_character.py %s --project %s" % (f, proj.name))
        else:
            add("OK", "character %s %dx%d with transparency" % (f.name, im.size[0], im.size[1]))
    extra = [p.name for p in (proj / "characters").glob("*.png")] if (proj / "characters").is_dir() else []
    if len(extra) > 1:
        add("WARN", "%d files in characters/ (%s): only the first character in config.json is used" % (len(extra), ", ".join(sorted(extra))),
            "every thumbnail shows exactly ONE character")


def check_video(proj):
    gdir = proj / "captures" / "gameplay"
    recs = [p for p in gdir.iterdir() if p.suffix.lower() in RECORDING_EXT and not p.stem.startswith("gameplay")] if gdir.is_dir() else []
    if recs:
        big = max(recs, key=lambda p: p.stat().st_size)
        add("OK", "gameplay recording: %s (%.0f MB)" % (big.name, big.stat().st_size / 1048576.0))
    else:
        add("WARN", "no gameplay recording: gameplay, trailer clips and screenshots will be skipped",
            "record 5+ minutes in the island (1080p, game UI visible) and put it in Projects\\%s\\captures\\gameplay\\" % proj.name)
    ff, fp = vt.find_tool("ffmpeg", "FFMPEG_PATH"), vt.find_tool("ffprobe", "FFPROBE_PATH")
    add("OK" if ff and fp else "WARN", "ffmpeg + ffprobe %s" % ("found" if ff and fp else "not found"), "winget install Gyan.FFmpeg   (then open a NEW terminal)")
    audio = proj / "audio"
    own = [p.name for p in audio.iterdir() if p.stem.lower() == "music" and p.suffix.lower() != ".wav"] if audio.is_dir() else []  # music.wav = generated by the kit
    add("OK", "music: %s" % (own[0] + " (yours)" if own else "generated by the kit (nothing to provide)"))


def check_engine():
    import os
    if os.environ.get("PROMO_PROFILE", "").lower() == "light":
        add("OK", "light profile: ComfyUI not needed (run with --no-qwen)")
        return
    try:
        doctor.get(doctor.COMFY_URL + "/system_stats")
    except Exception:
        add("WARN", "ComfyUI not reachable at %s: the AI artwork is off" % doctor.COMFY_URL, "start_comfyui.bat, or run without AI: run_all.bat <map> --no-qwen")
        return
    add("OK", "ComfyUI reachable")
    for folder, name, where in doctor.MODELS:
        try:
            have = doctor.get("%s/models/%s" % (doctor.COMFY_URL, folder))
        except Exception:
            have = []
        add("OK" if name in have else "BLOCK", "model %s" % name, "put it in ComfyUI\\models\\%s\\ (%s)" % (folder, where))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--init", action="store_true", help="create the map if missing and write the given values")
    ap.add_argument("--title")
    ap.add_argument("--island-code")
    ap.add_argument("--style")
    ap.add_argument("--identity", help="one-sentence description of the character (what must be preserved)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not a.project:
        maps = pp.list_maps()
        print("Existing maps (%s): %s" % (pp.projects_dir(), ", ".join(maps) or "none yet"))
        print("Next: intake.py --project <slug> [--init --title \"TITLE\" --island-code 1234-5678-9012]")
        return 0
    slug = slugify(a.project)
    proj = pp.projects_dir() / slug
    created = False
    if not proj.exists():
        if not (a.init and a.title):
            print("Map '%s' does not exist. Create it with: intake.py --project %s --init --title \"TITLE\" --island-code 1234-5678-9012" % (slug, slug))
            return 2
        cmd = [sys.executable, str(SCRIPTS / "new_map.py"), slug, a.title] + (["--style", a.style] if a.style else [])
        r = subprocess.run(cmd, capture_output=True, text=True, env=dict(__import__("os").environ, PROMO_PROJECTS_DIR=str(pp.projects_dir())))
        if r.returncode != 0:
            print("ERROR creating the map:\n" + (r.stdout + r.stderr).strip())
            return 2
        created = True
    cfg_path = proj / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    changed = []
    if a.init or created:
        for key, val in (("title", a.title), ("island_code", a.island_code), ("style", a.style)):
            if val and cfg.get(key) != val:
                cfg[key] = val
                changed.append(key)
        if a.identity and cfg.get("characters"):
            cfg["characters"][0]["identity"] = a.identity
            changed.append("identity")
        if changed:
            cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    if created and not a.json:
        print("Map folder: %s" % proj)
        for sub, what in (("background", "the environment (no characters, >= 1920 px wide)"), ("characters", "ONE character, transparent PNG"),
                          ("captures/gameplay", "the gameplay recording (mp4, 5+ min, 1080p)"), ("audio", "optional music.mp3")):
            (proj / sub).mkdir(parents=True, exist_ok=True)
            print("  put here: %s  <- %s" % (proj / sub, what))
        print("(file names are examples: any name works, Claude renames the files for the kit)\n")
    import os
    os.environ["PROMO_PROJECT"] = slug
    check_config(proj, cfg)
    check_images(proj, cfg)
    check_video(proj)
    check_engine()

    blocks = [r for r in rows if r["level"] == "BLOCK"]
    report = {"project": slug, "path": str(proj), "created": created, "updated": changed, "ready": not blocks, "checks": rows}
    if a.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("Intake - %s%s%s\n" % (slug, " (created)" if created else "", " (updated: %s)" % ", ".join(changed) if changed else ""))
        for r in rows:
            print("%-5s %s" % (r["level"], r["what"]))
            if r["fix"] and r["level"] != "OK":
                for line in r["fix"].split("\n"):
                    print("      -> " + line)
        if blocks:
            print("\nNOT READY - %d item(s) block the pipeline (BLOCK lines above)." % len(blocks))
        else:
            print("\nREADY. Next:  run_all.bat %s --review-prompt" % slug)
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
