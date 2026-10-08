"""End-to-end smoke test: synthetic map, mock ComfyUI, no GPU, no game assets.

Usage: python tests/smoke_test.py [--keep]
Copies the code to a temp folder, builds a fake map and runs: factory (with mock Qwen), vertical bust art,
video analyse/extract and the trailer (video steps run only if ffmpeg + ffprobe are installed).
Exit 0 = everything passed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import mock_comfyui  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


def run(py, args, env, cwd, timeout=600):
    r = subprocess.run([py, *args], env=env, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def synth_inputs(proj):
    bg = Image.new("RGB", (2400, 1200), (20, 24, 50))
    d = ImageDraw.Draw(bg)
    for i in range(0, 1200, 4):
        d.line([(0, i), (2400, i)], fill=(20 + i // 12, 24 + i // 20, 50 + i // 10))
    d.ellipse((1500, 100, 2200, 800), fill=(120, 120, 130))
    d.rectangle((0, 950, 2400, 1200), fill=(60, 50, 45))
    (proj / "background").mkdir(parents=True, exist_ok=True)
    bg.save(proj / "background" / "background.png")
    ch = Image.new("RGBA", (522, 1080), (0, 0, 0, 0))
    cd = ImageDraw.Draw(ch)
    cd.ellipse((180, 60, 340, 220), fill=(180, 180, 190, 255))      # head
    cd.rounded_rectangle((140, 220, 380, 640), 40, fill=(150, 70, 50, 255))   # torso
    cd.rectangle((170, 640, 350, 1040), fill=(60, 60, 80, 255))      # legs
    (proj / "characters").mkdir(parents=True, exist_ok=True)
    ch.save(proj / "characters" / "character_01.png")
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    cfg["island_code"] = "1234-5678-9012"
    cfg["characters"][0]["identity"] = "a synthetic test character"
    (proj / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def synth_video(path, seconds=70):
    # calm colour + one loud, busy burst in the middle (10 s) so the analyser has something to find
    c = seconds // 2 - 5
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "lavfi", "-i", "color=c=0x203040:s=640x360:r=30:d=%d" % c,
           "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=10",
           "-f", "lavfi", "-i", "color=c=0x302020:s=640x360:r=30:d=%d" % (seconds - c - 10),
           "-f", "lavfi", "-i", "sine=f=100:d=%d:sample_rate=48000" % c,
           "-f", "lavfi", "-i", "anoisesrc=d=10:c=white:a=0.8:r=48000",
           "-f", "lavfi", "-i", "sine=f=110:d=%d:sample_rate=48000" % (seconds - c - 10),
           "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[3:a]volume=0.05[a0];[5:a]volume=0.05[a2];[a0][4:a][a2]concat=n=3:v=0:a=1[a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
           "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def main():
    keep = "--keep" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="promo_smoke_"))
    root = tmp / "pf"
    for name in ("scripts", "Resources", "workflows"):
        shutil.copytree(REPO / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
    py = sys.executable
    server, port = mock_comfyui.start()
    env = dict(os.environ, PROMO_PROJECT="smoke", COMFY_URL="http://127.0.0.1:%d" % port, PYTHONIOENCODING="utf-8",
               PROMO_TRAILER_SECONDS="12")
    env.pop("PROMO_PLAN_B", None)
    t0 = time.time()
    print("temp copy: %s | mock ComfyUI on port %d" % (root, port))

    rc, out = run(py, ["scripts/new_map.py", "smoke", "SMOKE TEST MAP"], env, root)
    check(rc == 0, "new_map.py creates the project")
    proj = root / "Projects" / "smoke"
    synth_inputs(proj)

    rc, out = run(py, ["scripts/factory.py", "--project", "smoke"], env, root)
    check(rc == 0, "factory.py full run with mock Qwen exits 0")
    if rc != 0:
        print(out[-2500:])
    for f in ("final/artwork.png", "final/artwork_vertical.png", "final/island_logo.png",
              "final/thumbnail_horizontal.png", "final/thumbnail_horizontal_title.png",
              "final/thumbnail_vertical.png", "final/thumbnail_vertical_title.png",
              "promo_pack/01_landscape_with_text_1920x1080.png", "promo_pack/03_portrait_with_text_1440x1920.png",
              "promo_pack/05_logo_1440x608.png", "promo_pack/06_lobby_background_2048x1024.png"):
        check((proj / f).exists(), "output exists: " + f)
    if (proj / "final" / "thumbnail_vertical_title.png").exists():
        check(Image.open(proj / "final" / "thumbnail_vertical_title.png").size == (1440, 1920), "portrait thumbnail is 1440x1920")
    if (proj / "final" / "island_logo.png").exists():
        im = Image.open(proj / "final" / "island_logo.png")
        check(im.size == (1440, 608) and im.mode == "RGBA", "logo is 1440x608 RGBA")

    env_b = dict(env, PROMO_PLAN_B="bust")
    rc, out = run(py, ["scripts/qwen_run.py", "vertical"], env_b, root)
    check(rc == 0 and "plan B bust" in out, "vertical Plan B (bust) builds without Qwen")
    rc, out = run(py, ["scripts/factory.py", "--project", "smoke", "--no-qwen"], env, root)
    check(rc == 0, "factory.py --no-qwen recomposes everything")

    have_ff = shutil.which("ffmpeg") and shutil.which("ffprobe")
    if not have_ff:
        print("SKIP  video steps (ffmpeg/ffprobe not installed)")
    else:
        vid = tmp / "synthetic.mp4"
        check(synth_video(vid), "synthetic gameplay video created")
        rc, out = run(py, ["scripts/video_analyze.py", str(vid), "--top", "2", "--window", "6", "--skip-start", "5"], env, root)
        check(rc == 0 and (proj / "captures" / "analysis" / "candidates.json").exists(), "video_analyze finds moments")
        if (proj / "captures" / "analysis" / "candidates.json").exists():
            c0 = json.loads((proj / "captures" / "analysis" / "candidates.json").read_text())["candidates"][0]
            check(25 <= c0["start"] <= 36, "top moment is the busy burst (start=%.1f s)" % c0["start"])
        rc, out = run(py, ["scripts/video_extract.py", str(vid), "--auto", "--clips", "2", "--gameplay-seconds", "12"], env, root)
        check((proj / "captures" / "clips" / "clip_01.mp4").exists(), "video_extract cuts clips")
        check((proj / "captures" / "screenshots" / "screenshot_01.png").exists(), "video_extract grabs screenshots")
        check((proj / "captures" / "gameplay" / "gameplay.mp4").exists(), "video_extract cuts the gameplay segment")
        rc, out = run(py, ["scripts/trailer_builder.py"], env, root, timeout=900)
        check(rc == 0 and (proj / "final" / "trailer.mp4").exists(), "trailer_builder builds trailer.mp4 with clips + island code")
        if rc != 0:
            print(out[-2500:])
        rc, out = run(py, ["scripts/video_validate.py", str(proj / "final" / "trailer.mp4"), "--kind", "trailer"], env, root)
        check(rc == 0, "trailer passes video_validate")

    # demo map + maps stored OUTSIDE the repo (PROMO_PROJECTS_DIR), the layout real users have
    pdir = Path(tmp) / "outside_projects"
    env2 = dict(env, PROMO_PROJECTS_DIR=str(pdir))
    rc, out = run(py, ["scripts/make_demo.py"], env2, root)
    check(rc == 0 and (pdir / "demo" / "final" / "artwork_vertical.png").exists(), "make_demo builds the demo map outside the repo")
    rc, out = run(py, ["scripts/factory.py", "--project", "demo", "--no-qwen"], env2, root)
    check(rc == 0 and (pdir / "demo" / "final" / "thumbnail_vertical_title.png").exists(), "demo map runs end to end without Qwen")
    if rc != 0:
        print(out[-2000:])
    rc, out = run(py, ["scripts/variant.py", "--project", "demo", "--name", "B", "--no-qwen"], env2, root)
    vb = pdir / "demo" / "variants" / "B"
    check(rc == 0 and (vb / "promo_pack" / "01_landscape_with_text_1920x1080.png").exists() and not (pdir / "_variant_demo_B").exists(),
          "variant B is generated in isolation (A untouched, temp copy removed)")
    if rc != 0:
        print(out[-2000:])
    rc, out = run(py, ["scripts/doctor.py"], env2, root)
    check(rc == 0 and "READY" in out, "doctor.py reports no FAIL")

    server.shutdown()
    print("\n%d check(s) failed, %.0f s" % (len(FAILS), time.time() - t0))
    if keep:
        print("kept: %s" % tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
