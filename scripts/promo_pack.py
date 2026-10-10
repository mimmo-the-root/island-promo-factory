"""Build the Promo Pack for the active map: Creator Portal-ready files + checklist.

Usage: python promo_pack.py            (map = PROMO_PROJECT / factory.py --project)
Output: Projects/<map>/promo_pack/
  01_landscape_with_text_1920x1080.png   (portal: Immagine di anteprima orizzontale - Con testo, REQUIRED)
  02_landscape_art_only_1920x1080.png    (orizzontale - Solo immagine)
  03_portrait_with_text_1440x1920.png    (verticale - Con testo)
  04_portrait_art_only_1440x1920.png     (verticale - Solo immagine)
  05_logo_1440x608.png                   (Logo, transparent PNG < 3 MB)
  06_lobby_background_2048x1024.png      (Sfondo lobby)
  island_description_disclaimer.txt      (Star Wars maps: Disney text; every other map: Epic Games text; config ip.disclaimer overrides both)
  UPLOAD_CHECKLIST.md                    (what is ready, what must be captured/recorded by hand)
Exit code 1 if a required file is missing or has the wrong size/limit.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promo_project as pp  # noqa: E402

EPIC_DISCLAIMER = (
    "Fortnite and Unreal Editor for Fortnite are trademarks and/or copyrighted works of Epic Games, Inc. "
    "All rights reserved by Epic Games. "
    "This island was created with Unreal Editor for Fortnite. It is not official and is not endorsed by Epic Games."
)

DISCLAIMER = (
    "Portions of the materials used are trademarks and/or copyrighted works of The Walt Disney Company. "
    "All rights reserved by Disney. "
    "This material is not official and is not endorsed by Disney."
)

# (output name, source relative to project, size, max MB, mode or None, required)
ITEMS = [
    ("01_landscape_with_text_1920x1080.png", "final/thumbnail_horizontal_title.png", (1920, 1080), 5, None, True),
    ("02_landscape_art_only_1920x1080.png", "final/thumbnail_horizontal.png", (1920, 1080), 5, None, False),
    ("03_portrait_with_text_1440x1920.png", "final/thumbnail_vertical_title.png", (1440, 1920), 5, None, False),
    ("04_portrait_art_only_1440x1920.png", "final/thumbnail_vertical.png", (1440, 1920), 5, None, False),
    ("05_logo_1440x608.png", "final/island_logo.png", (1440, 608), 3, "RGBA", False),
    ("06_lobby_background_2048x1024.png", "background/lobby_background.png", (2048, 1024), 10, None, False),
]


def make_prores(src, dest, ffmpeg, ffprobe):
    """ProRes 422 .mov next to the H.264 .mp4 (Epic's recommended delivery format): 10-bit 4:2:2, stereo uncompressed PCM audio, native frame rate.
    LT when it stays well under the portal's 400 MB limit, else Proxy. Returns (size_mb, profile name) or None."""
    import json as _json
    import subprocess
    dur = 30.0
    if ffprobe:
        try:
            r = subprocess.run([str(ffprobe), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(src)], capture_output=True, text=True)
            dur = float(_json.loads(r.stdout)["format"]["duration"])
        except Exception:
            pass
    for prof, pname, mb_s in ((1, "LT", 13.5), (0, "Proxy", 6.0)):
        if prof == 1 and dur * mb_s > 330:
            continue
        # write to a temp file and move it in place only when it is complete and readable (an interrupted encode must never leave a half file)
        tmp = dest.with_name(dest.stem + ".part.mov")
        cmd = [str(ffmpeg), "-y", "-v", "error", "-i", str(src), "-c:v", "prores_ks", "-profile:v", str(prof), "-vendor", "apl0",
               "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = r.returncode == 0 and tmp.exists()
        if ok and ffprobe:
            pr = subprocess.run([str(ffprobe), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(tmp)], capture_output=True, text=True)
            try:
                ok = abs(float(_json.loads(pr.stdout)["format"]["duration"]) - dur) < 0.5
            except Exception:
                ok = False
        if not ok:
            print("WARNING: ProRes export failed for %s: %s" % (dest.name, (r.stderr or "").strip()[-200:]))
            try:
                tmp.unlink()
            except OSError:
                pass
            return None
        mb = tmp.stat().st_size / 1048576
        if mb < 395:
            if dest.exists():
                dest.unlink()
            tmp.replace(dest)
            return mb, pname
        tmp.unlink()
    return None


def copy_with_retry(src, dst, attempts=5):
    """Copy a file, retrying on transient Windows errors (file briefly locked)."""
    import time
    for i in range(attempts):
        try:
            shutil.copyfile(src, dst)
            return
        except OSError:
            if i == attempts - 1:
                raise
            time.sleep(1.5)


def main():
    project = pp.project_dir()
    cfg = pp.load_config()
    out = project / "promo_pack"
    print(f"=== PROMO PACK | map: {pp.project_name()} ===")

    errors, ready = [], []
    out.mkdir(parents=True, exist_ok=True)

    for name, rel, size, max_mb, mode, required in ITEMS:
        src = project / rel
        if not src.exists():
            errors.append(f"MISSING {rel}")
            continue
        mb = src.stat().st_size / (1024 * 1024)
        with Image.open(src) as im:
            if im.size != size:
                errors.append(f"WRONG SIZE {rel}: {im.size}, expected {size}")
                continue
            if mode and im.mode != mode:
                errors.append(f"WRONG MODE {rel}: {im.mode}, expected {mode}")
                continue
        if mb >= max_mb:
            errors.append(f"TOO BIG {rel}: {mb:.2f} MB, limit < {max_mb} MB")
            continue
        copy_with_retry(src, out / name)
        ready.append((name, size, mb, required))
        print(f"OK: {name} ({mb:.2f} MB)")

    # leftovers of older versions (separate cinematic video): move aside, never delete
    for old in list(out.glob("09_gameplay_cinematic*")) + list(out.glob("10_gameplay_cinematic*")):
        aside = out.parent / "_to_delete_stale"
        aside.mkdir(exist_ok=True)
        shutil.move(str(old), str(aside / old.name))
        print(f"NOTE: old file {old.name} moved to {aside.name}/ (the cinematic gameplay is now 07)")

    # ---- video + screenshots (optional: only when they exist; videos are validated first)
    import subprocess
    import video_tools as vt
    manual, unvalidated = [], []
    skip_video = "--no-video" in sys.argv  # factory.py runs this before the video stages exist
    have_probe = vt.find_tool("ffprobe", "FFPROBE_PATH") is not None
    for name, rel, kind in (("07_gameplay_1920x1080.mp4", "captures/gameplay/gameplay.mp4", "gameplay"),
                            ("08_trailer_1920x1080.mp4", "final/trailer.mp4", "trailer")):
        src = project / rel
        if skip_video:
            continue
        if not src.exists():
            manual.append(kind)
            continue
        mb = src.stat().st_size / (1024 * 1024)
        if have_probe:
            res = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "video_validate.py"), str(src), "--kind", kind],
                                 capture_output=True, text=True)
            if res.returncode != 0:
                bad = [l.strip() for l in (res.stdout + res.stderr).splitlines() if l.startswith(("FAIL", "ERROR"))]
                errors.append(f"VIDEO FAILED validation {rel}: " + ("; ".join(bad) if bad else "see: python scripts/video_validate.py %s --kind %s" % (rel, kind)))
                continue
        else:
            unvalidated.append(name)
            print(f"WARNING: ffprobe not found - {name} copied WITHOUT validation (install ffmpeg: winget install Gyan.FFmpeg)")
        copy_with_retry(src, out / name)
        ready.append((name, (1920, 1080), mb, False))
        print(f"OK: {name} ({mb:.1f} MB, validated)")
        # ProRes MOV twin (Epic recommends ProRes for trailer/gameplay): config "video_formats" (default both) or PROMO_VIDEO_FORMATS=mp4|prores|both
        fmts = str(__import__("os").environ.get("PROMO_VIDEO_FORMATS") or cfg.get("video_formats") or "both").lower()
        ff = vt.find_tool("ffmpeg", "FFMPEG_PATH")
        if fmts in ("both", "prores") and ff:
            mov = out / (name[:-4] + "_prores.mov")
            res = make_prores(src, mov, ff, vt.find_tool("ffprobe", "FFPROBE_PATH"))
            if res:
                ready.append((mov.name, (1920, 1080), res[0], False))
                print(f"OK: {mov.name} ({res[0]:.0f} MB, ProRes 422 {res[1]}, 10-bit, PCM audio)")
        if fmts == "prores" and (out / name).exists():
            (out / name).unlink()
    shots = sorted((project / "captures" / "screenshots").glob("screenshot_*.png"))[:3] if (project / "captures" / "screenshots").is_dir() else []
    if not shots:
        manual.append("screenshots")
    for k, src in enumerate(shots, 1):
        with Image.open(src) as im:
            sz = im.size
        mb = src.stat().st_size / (1024 * 1024)
        if sz != (1920, 1080) or mb >= 5:
            errors.append(f"SCREENSHOT {src.name}: {sz}, {mb:.2f} MB (need 1920x1080, < 5 MB)")
            continue
        name = f"09_screenshot_{k}_1920x1080.png"
        copy_with_retry(src, out / name)
        ready.append((name, sz, mb, False))
        print(f"OK: {name} ({mb:.2f} MB)")

    star_wars = bool(cfg.get("ip", {}).get("star_wars"))
    custom = str(cfg.get("ip", {}).get("disclaimer", "")).strip()
    text = custom or (DISCLAIMER if star_wars else EPIC_DISCLAIMER)
    (out / "island_description_disclaimer.txt").write_text(text + "\n", encoding="utf-8")
    print("OK: island_description_disclaimer.txt (%s)" % ("custom" if custom else "Disney / Star Wars" if star_wars else "Epic Games"))

    lines = [f"# Upload checklist - {cfg.get('title', pp.project_name())}", "",
             "Creator Portal > Media promozionali. Files are in this folder.", "",
             "## Ready (generated)"]
    for name, size, mb, required in ready:
        lines.append(f"- [x] {name} - {size[0]}x{size[1]}, {mb:.2f} MB" + (" - REQUIRED" if required else ""))
    todo = {"gameplay": "- [ ] Gameplay video: 1920x1080, MP4/MKV/WEBM/MOV, < 400 MB, 10-40 s, REAL unedited gameplay incl. game UI "
                        "(put a recording in captures/gameplay/ and run scripts/video_extract.py)",
            "screenshots": "- [ ] In-game screenshots (up to 3): 1920x1080, PNG/JPEG, < 5 MB, real gameplay",
            "trailer": "- [ ] Trailer (optional): run scripts/trailer_builder.py"}
    lines += ["", "## Manual (real captures, cannot be generated)"]
    lines += [todo[k] for k in ("gameplay", "screenshots", "trailer") if k in manual]
    lines += [f"- [ ] NOT VALIDATED (ffprobe missing): {n} - install ffmpeg and rerun the promo pack" for n in unvalidated]
    lines += ["- [ ] Check the gameplay and screenshots really show the game (the portal requires real footage, in-game UI visible)"]
    if not star_wars:
        lines += ["", "## Island description", "- [ ] Optional: paste island_description_disclaimer.txt (Epic Games notice) at the end of the island description",
                  "- Suggested wording, not an official Epic text: if your island uses licensed IP, follow that IP holder's brand rules instead (set ip.disclaimer in config.json)"]
    if star_wars:
        lines += ["", "## Star Wars island",
                  "- [ ] Paste island_description_disclaimer.txt into the island description",
                  "- [ ] Only UEFN-provided Star Wars assets; no Star Wars/Disney logos or film imagery; no Star Wars music in promo videos",
                  "- Rules: https://dev.epicgames.com/documentation/fortnite/star-wars-brand-rules-in-fortnite"]
    try:
        gmeta = __import__("json").loads((project / "captures" / "gameplay" / "gameplay.json").read_text(encoding="utf-8"))
    except Exception:
        gmeta = {}
    if gmeta.get("polished"):
        lines += ["", "## Gameplay video note",
                  f"- 07_gameplay is an EDITED {gmeta.get('style', 'cinematic')} montage of {len(gmeta.get('segments', []))} real segments "
                  "(colour grade, zoom, speed changes, transitions) with music generated by Island Promo Factory; the original audio is removed.",
                  "- The portal gameplay slot asks for real, unedited gameplay: if it is rejected, rebuild with `run_all.bat <map> --redo-video --skip-images --gameplay-look off` for an unedited cut."]
    elif gmeta.get("mode") == "montage":

        lines += ["", "## Gameplay video note",
                  f"- 07_gameplay is a MONTAGE of {len(gmeta.get('segments', []))} real segments of one recording (hard cuts, no effects, original audio).",
                  "- The portal asks for real gameplay: check Epic's current rules for joined footage before uploading it."]
    code = str(cfg.get("island_code", "")).strip()
    if code:
        lines += ["", "## Island code", f"- {code}"]
    lines += ["", "## Optional", "- [ ] Create an A/B test with a variant of the thumbnail (new Qwen seed / other title style)"]
    (out / "UPLOAD_CHECKLIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:                                   # people open final/ and look for the deliverables: say where they are
        (project / "final").mkdir(exist_ok=True)
        (project / "final" / "README.txt").write_text(
            "This folder holds the WORKING files of the kit (art, cuts, logs). Do not upload from here.\n"
            "The numbered files for the Creator Portal (01_ ... 09_, gameplay and trailer included) are in:\n  %s\n" % out, encoding="utf-8")
    except OSError:
        pass

    if errors:
        print("\nPROMO PACK INCOMPLETE:")
        for e in errors:
            print(f" - {e}")
        sys.exit(1)
    print(f"\nPROMO PACK READY: {out}")


if __name__ == "__main__":
    main()
