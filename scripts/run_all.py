import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Full run for one map: images -> video cut -> music -> trailer -> promo pack -> lightbox, with timings.

Usage: run_all.py [--project SLUG] [--no-qwen] [--redo-video] [--skip-video] [--skip-images] [--seed N]
Stages (each is a separate script, so any of them can also be run alone):
  1 images        factory.py            Qwen art, title, logo, thumbnails (skipped Qwen with --no-qwen)
  2 video cut     video_analyze/extract  only if captures/gameplay holds a source recording
                                         (uses captures/selection.json if present, else --auto)
  3 music         music_generator.py    only if audio/music.* is missing (--seed N to pick a track)
  4 trailer       trailer_builder.py
  5 promo pack    promo_pack.py         validates and collects everything for the Creator Portal
  6 lightbox      lightbox.py           the numbered preview board of the pack
Log: last_run_all.log (overwritten each run). Timings: Projects/<map>/final/run_timings.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm")


class Tee:
    def __init__(self, *s):
        self.s = s

    def write(self, d):
        for x in self.s:
            x.write(d)
            x.flush()

    def flush(self):
        for x in self.s:
            x.flush()


def fmt(sec):
    return "%d:%02d" % divmod(int(round(sec)), 60)


def run(cmd, env):
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", cwd=str(ROOT))
    for line in p.stdout:
        print("    " + line.rstrip())
    return p.wait()


def review_prompt(proj):
    """Build the Qwen prompt, let the user edit it, keep the edit as qwen_prompt_custom.txt (used until deleted)."""
    import promo_project as pp
    builder = Path(__file__).resolve().parent / "qwen_prompt_builder.py"
    env = dict(os.environ, PROMO_PROJECT=pp.project_name())
    subprocess.run([sys.executable, str(builder)], env=env, check=False)
    final, custom = proj / "qwen_prompt_final.txt", proj / "qwen_prompt_custom.txt"
    if not custom.exists() and final.exists():
        custom.write_text(final.read_text(encoding="utf-8"), encoding="utf-8")
    print("\n" + "=" * 64)
    print(" PROMPT REVIEW - this text is sent to Qwen:")
    print("=" * 64)
    print(custom.read_text(encoding="utf-8") if custom.exists() else "(prompt not found)")
    print("=" * 64)
    print(" Edit: %s" % custom)
    print(" (delete that file to go back to the automatic prompt)")
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(custom))
    except Exception:
        pass
    try:
        input(" Save your changes, then press Enter to start (Ctrl+C cancels)... ")
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--no-qwen", action="store_true")
    ap.add_argument("--standard", action="store_true", help="force the normal generated artwork even if the map is in the conform case")
    ap.add_argument("--conform", action="store_true",
                    help="case 'make my thumbnail conform': keep the user's own landscape thumbnails (01/02) and build portrait, logo and lobby "
                         "from the clean background + extracted hero (no Qwen in this stage)")
    ap.add_argument("--redo-video", action="store_true")
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--skip-images", action="store_true", help="keep the current images (no Qwen run); redo only the video stages, promo pack and lightbox")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--gameplay-look", choices=["cinematic", "hype", "off"], default="cinematic",
                    help="extra EDITED gameplay video (>=4 real moments, grade, zoom, speed, beat-synced cuts, our own music, original audio removed); "
                         "off = only the unedited portal cut. The portal gameplay.mp4 is always one real, unedited cut.")
    ap.add_argument("--gameplay-scenes", type=int, default=3, metavar="N",
                    help="gameplay video (slot 07) = N (2 or 3) real scenes from the best moments, soft dissolves, our music instead of the original audio "
                         "(default 3; 0 = the longer beat-synced montage of >=4 moments; ignored with --gameplay-look off = one unedited cut with its own audio)")
    ap.add_argument("--review-prompt", action="store_true",
                    help="build the Qwen prompt, open it for editing and wait for Enter before anything starts")
    ap.add_argument("--ui", action="store_true", help="open the live web dashboard (stays open after the run)")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    import promo_project as pp
    log = open(ROOT / "last_run_all.log", "w", encoding="utf-8", errors="replace")
    sys.stdout = Tee(sys.__stdout__, log)
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    env.setdefault("PROMO_PLAN_B", "bust")
    py = sys.executable
    proj = pp.project_dir()
    try:
        if json.loads((proj / "config.json").read_text(encoding="utf-8")).get("case") == "conform" and not a.standard and not a.conform:
            a.conform = True
            print("This map is in the conform case: keeping your own landscape art, no new Qwen artwork (--standard forces the normal flow).")
    except Exception:
        pass
    caps = proj / "captures" / "gameplay"
    print("=" * 64)
    import version as V
    print(" ISLAND PROMO FACTORY v%s%s - FULL RUN | map: %s" % (V.read_version(), (" (" + V.git_commit() + ")") if V.git_commit() else "", pp.project_name()))
    print("=" * 64)

    stages = []  # (name, [cmd], reason-to-skip or None)
    img = [py, str(SCRIPTS / "factory.py"), "--project", pp.project_name()] + (["--no-qwen"] if a.no_qwen else []) + (["--conform"] if a.conform else []) + (["--standard"] if a.standard else [])
    stages.append(("images", None if a.skip_images else img, "--skip-images" if a.skip_images else None))

    src = None
    if caps.is_dir():
        cands = [f for f in caps.iterdir() if f.suffix.lower() in VIDEO_EXT and f.stem.lower() != "gameplay"]
        if cands:
            src = max(cands, key=lambda f: f.stat().st_size)
    gp = caps / "gameplay.mp4"
    need_cut = src is not None and (a.redo_video or not gp.exists() or src.stat().st_mtime > gp.stat().st_mtime)
    if a.skip_video:
        stages.append(("video cut", None, "--skip-video"))
    elif src is None:
        stages.append(("video cut", None, "no source recording in captures/gameplay"))
    elif not need_cut:
        stages.append(("video cut", None, "gameplay.mp4 is up to date (--redo-video to redo)"))
    else:
        sel = proj / "captures" / "selection.json"
        if a.gameplay_look == "off":
            style = []
        elif a.gameplay_scenes > 0:
            style = ["--gameplay-scenes", str(a.gameplay_scenes), "--gameplay-look", a.gameplay_look]
        else:
            style = ["--gameplay-polish", "--gameplay-look", a.gameplay_look]
        stages.append(("video analyse", [py, str(SCRIPTS / "video_analyze.py"), str(src)], None))
        if sel.exists():
            stages.append(("video cut", [py, str(SCRIPTS / "video_extract.py"), "--selection", str(sel), str(src)] + style, None))
        else:
            stages.append(("video cut", [py, str(SCRIPTS / "video_extract.py"), "--auto", str(src)] + style, None))

    audio = proj / "audio"
    has_music = audio.is_dir() and any(f.stem.lower() == "music" for f in audio.iterdir())
    mood_now = None
    try:
        mood_now = json.loads((proj / "config.json").read_text(encoding="utf-8")).get("music_mood")
        side = audio / "music_mood.txt"
        if has_music and mood_now and side.exists() and side.read_text(encoding="utf-8").strip() != mood_now and any(f.name == "music.wav" for f in audio.iterdir()):
            print("music mood changed (%s -> %s): the generated track is made again" % (side.read_text(encoding="utf-8").strip(), mood_now))
            has_music = False      # only our own generated music.wav is replaced; a user's music.mp3 is never touched
    except Exception:
        pass
    if has_music:
        stages.append(("music", None, "audio/music.* exists"))
    else:
        stages.append(("music", [py, str(SCRIPTS / "music_generator.py")] + (["--seed", str(a.seed)] if a.seed is not None else []), None))
    os.environ["PROMO_VIDEO_LOOK"] = a.gameplay_look
    stages.append(("trailer", [py, str(SCRIPTS / "trailer_builder.py")], None))
    stages.append(("promo pack", [py, str(SCRIPTS / "promo_pack.py")], None))
    stages.append(("lightbox", [py, str(SCRIPTS / "lightbox.py")], None))

    # expected duration per stage: last successful run of the same kind, else a rough default
    defaults = {"images": 30 if (a.no_qwen or a.conform) else 300, "video analyse": 25, "video cut": 30, "music": 4,
                "trailer": 50, "promo pack": 10, "lightbox": 4}
    prev = {}
    try:
        old_run = json.loads((proj / "final" / "run_timings.json").read_text(encoding="utf-8"))
        if bool(old_run.get("qwen")) == (not (a.no_qwen or a.conform)):
            for t in old_run.get("stages", []):
                if t.get("status") == "ok" and t.get("seconds", 0) > 0:
                    prev[t["stage"]] = t["seconds"]
    except Exception:
        pass
    # video tools: without ffmpeg/ffprobe the video stages cannot run - say so now, not after 15 minutes of Qwen
    import video_tools as vt
    def _runs(tool):
        try:
            return subprocess.run([tool, "-version"], capture_output=True, timeout=30).returncode == 0
        except Exception:
            return False
    _ff, _fp = vt.find_tool("ffmpeg", "FFMPEG_PATH"), vt.find_tool("ffprobe", "FFPROBE_PATH")
    if _ff and _fp and not (_runs(_ff) and _runs(_fp)):
        print("\n*** WARNING: ffmpeg was found (%s) but does not start (blocked by antivirus/SmartScreen, or a damaged file). ***" % _ff)
        _ff = None
    if not (_ff and _fp):
        print("\n*** WARNING: ffmpeg / ffprobe NOT FOUND - the video cut and the trailer will be SKIPPED. ***")
        print("*** Install once:  winget install Gyan.FFmpeg   (then open a NEW terminal) - or copy ffmpeg.exe + ffprobe.exe into Resources\\bin\\ ***\n")
        stages = [(n, None, "ffmpeg not installed (winget install Gyan.FFmpeg)") if n in ("video analyse", "video cut", "trailer") else (n, c, sk)
                  for n, c, sk in stages]
    if a.review_prompt and not a.no_qwen:
        review_prompt(proj)
    status_path = proj / "final" / "run_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    t_all = time.time()
    status = {"map": pp.project_name(), "version": V.read_version(), "state": "running", "started": t_all,
              "qwen": not (a.no_qwen or a.conform),
              "stages": [{"name": n, "state": "skipped" if c is None else "pending", "note": sk or "", "seconds": 0,
                          "expected": prev.get(n, defaults.get(n, 30))} for n, c, sk in stages]}

    def save():
        status_path.write_text(json.dumps(status), encoding="utf-8")

    save()
    if a.ui:
        import services
        services.start_console(proj.name, a.port, open_browser=True)   # separate background process: it outlives this run
    timings = []
    failed = None
    for idx, (name, cmd, skip) in enumerate(stages):
        if cmd is None:
            print("\n--- %s: skipped (%s)" % (name, skip))
            timings.append({"stage": name, "seconds": 0.0, "status": "skipped: " + skip})
            continue
        print("\n--- %s ..." % name)
        t0 = time.time()
        status["stages"][idx].update(state="running", t0=t0)
        save()
        rc = run(cmd, env)
        dt = time.time() - t0
        status["stages"][idx].update(state="done" if rc == 0 else "failed", seconds=round(dt, 1))
        save()
        timings.append({"stage": name, "seconds": round(dt, 1), "status": "ok" if rc == 0 else "FAILED (exit %d)" % rc})
        print("--- %s: %s in %s" % (name, "done" if rc == 0 else "FAILED", fmt(dt)))
        if rc != 0:
            failed = name
            break
    total = time.time() - t_all

    print("\n" + "=" * 64)
    print(" TIMINGS")
    print("=" * 64)
    for t in timings:
        print(" %-14s %7s  %s" % (t["stage"], fmt(t["seconds"]) if t["seconds"] else "-", t["status"]))
    print(" %-14s %7s" % ("TOTAL", fmt(total)))
    (proj / "final").mkdir(parents=True, exist_ok=True)
    if not failed:  # keep the last good timings as the baseline for ETA estimates
      (proj / "final" / "run_timings.json").write_text(json.dumps({"map": pp.project_name(), "total_seconds": round(total, 1), "version": V.read_version(), "qwen": not (a.no_qwen or a.conform),
                                                                 "stages": timings}, indent=2), encoding="utf-8")
    status.update(state="failed" if failed else "done", total=round(total, 1), failed=failed)
    save()
    if failed:
        print("\nFULL RUN FAILED at stage '%s' - see last_run_all.log (and last_run.log for the images stage)" % failed)
        sys.exit(1)
    print("\nFULL RUN COMPLETE. Upload files: %s" % (proj / "promo_pack"))
    if a.ui:
        print("The live console stays open in your browser (it closes by itself after 30 idle minutes).")
        print("Reopen it any time: dashboard.bat %s   |   close it now: python scripts/services.py stop --project %s" % (proj.name, proj.name))


if __name__ == "__main__":
    main()
