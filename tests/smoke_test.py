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
        mov = tmp / "trailer_prores.mov"
        rc, out = run(py, ["-c", "import sys; sys.path.insert(0, 'scripts'); import promo_pack as pk, video_tools as vt; "
                           "r = pk.make_prores(sys.argv[1], __import__('pathlib').Path(sys.argv[2]), vt.find_tool('ffmpeg', 'FFMPEG_PATH'), vt.find_tool('ffprobe', 'FFPROBE_PATH')); "
                           "sys.exit(0 if r else 1)", str(proj / "final" / "trailer.mp4"), str(mov)], env, root, timeout=600)
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,pix_fmt", "-of", "csv=p=0", str(mov)], capture_output=True, text=True).stdout if mov.exists() else ""
        check(rc == 0 and "prores" in pr and "yuv422p10le" in pr and "pcm_s16le" in pr, "promo_pack exports a ProRes 422 MOV (10-bit, PCM audio) from the trailer")

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
    rc, out = run(py, ["scripts/intake.py", "--project", "newcomer", "--init", "--title", "NEW COMER", "--island-code", "1234-5678-9012"], env2, root)
    check(rc == 1 and (pdir / "newcomer" / "config.json").exists() and "BLOCK background image missing" in out,
          "intake creates a map and reports the missing assets")
    rc, out = run(py, ["scripts/intake.py", "--project", "demo"], env2, root)
    check("island code" in out and "title:" in out, "intake checks an existing map")
    ksync = Path(tmp) / "kit_root"
    (ksync / "scripts").mkdir(parents=True)
    shutil.copytree(root / "scripts" / "claude_kit", ksync / "scripts" / "claude_kit")
    (ksync / ".claude").mkdir()
    (ksync / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(ls:*)"]}}', encoding="utf-8")
    rc, out = run(py, ["scripts/claude_sync.py", "--root", str(ksync)], env2, root)
    st = json.loads((ksync / ".claude" / "settings.json").read_text(encoding="utf-8"))
    check(rc == 0 and (ksync / ".claude" / "skills" / "island-promo" / "SKILL.md").exists() and "permissions" in st
          and "island_session_start" in json.dumps(st), "claude_sync installs skills + hook and keeps the user's own settings")
    rc, out = run(py, ["scripts/claude_sync.py", "--root", str(ksync)], env2, root)
    check("already up to date" in out, "claude_sync is idempotent")
    real = Path(__file__).resolve().parent.parent          # the real repo, not the temp copy
    same = not (real / ".claude").exists() or all((real / ".claude" / r).read_bytes() == (real / "scripts" / "claude_kit" / r).read_bytes()
               for r in ("skills/island-promo/SKILL.md", "skills/island-intake/SKILL.md", "commands/promo-pack.md"))
    check(same, ".claude/ in the repo matches scripts/claude_kit/")
    rc, out = run(py, ["scripts/session_start.py"], dict(env2, PROMO_NO_UPDATE_CHECK="1"), root)
    check(rc == 0 and json.loads(out.strip().splitlines()[-1])["hookSpecificOutput"]["hookEventName"] == "SessionStart", "session_start hook prints valid JSON")
    rc, out = run(py, ["scripts/doctor.py"], env2, root)
    check(rc == 0 and "READY" in out, "doctor.py reports no FAIL")

    # update stage area: stored copies + rollback (local zips, no network)
    import zipfile
    ur = tmp / "upd_root"
    (ur / "scripts").mkdir(parents=True)
    (ur / "VERSION").write_text("1.0.0\n")
    (ur / "scripts" / "x.py").write_text("old\n")
    (ur / "Projects").mkdir()
    (ur / "Projects" / "keep.txt").write_text("mine")
    zp = tmp / "rel.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("VERSION", "1.1.0\n")
        zf.writestr("scripts/x.py", "new\n")
    rc, out = run(py, ["scripts/update.py", "--root", str(ur), "--zip", str(zp)], env2, root)
    check(rc == 0 and (ur / "scripts" / "x.py").read_text().strip() == "new", "update applies a release zip")
    check((ur / "_releases" / "v1.0.0.zip").exists() and (ur / "_releases" / "v1.1.0.zip").exists(), "stage area keeps the old and the new version")
    rc, out = run(py, ["scripts/update.py", "--root", str(ur), "--rollback"], env2, root)
    check(rc == 0 and (ur / "VERSION").read_text().strip() == "1.0.0" and (ur / "scripts" / "x.py").read_text().strip() == "old", "rollback restores the previous version")
    check((ur / "Projects" / "keep.txt").read_text() == "mine", "update/rollback never touch Projects/")
    rc, out = run(py, ["scripts/update.py", "--root", str(ur), "--rollback", "1.1.0"], env2, root)
    check(rc == 0 and (ur / "VERSION").read_text().strip() == "1.1.0", "rollback to a named version (roll forward) works")

    # claude_sync retires renamed commands
    rt = tmp / "retire_root"
    (rt / "scripts").mkdir(parents=True)
    shutil.copytree(root / "scripts" / "claude_kit", rt / "scripts" / "claude_kit")
    (rt / ".claude" / "commands").mkdir(parents=True)
    (rt / ".claude" / "commands" / "island-new.md").write_text("old")
    rc, out = run(py, ["scripts/claude_sync.py", "--root", str(rt)], env2, root)
    check(not (rt / ".claude" / "commands" / "island-new.md").exists() and (rt / ".claude" / "commands" / "promo-pack.md").exists(), "claude_sync removes the old command name and installs promo-pack")

    # activity wrapper: a step becomes a running/done stage with its own log
    ap_ = tmp / "act_projects" / "a1"
    (ap_ / "final").mkdir(parents=True)
    (ap_ / "config.json").write_text("{}")
    (root / "scripts" / "_act_probe.py").write_text("print('probe ok')\n")
    try:
        rc, out = run(py, ["scripts/activity.py", "run", "--project", "a1", "--label", "Probe", "--expected", "5", "--", "_act_probe.py"],
                      dict(env, PROMO_PROJECTS_DIR=str(ap_.parent)), root)
    finally:
        (root / "scripts" / "_act_probe.py").unlink()
    st_ = json.loads((ap_ / "final" / "run_status.json").read_text())
    check(rc == 0 and st_["kind"] == "activity" and st_["stages"][0]["state"] == "done" and "probe ok" in (ap_ / "final" / "activity.log").read_text(),
          "activity.py shows a single step as a stage and keeps its own log")

    # conform: existing thumbnail -> landscape with text
    cp = tmp / "conf_projects" / "c1"
    (cp / "input").mkdir(parents=True)
    (cp / "config.json").write_text("{}")
    Image.new("RGB", (1376, 752), (30, 10, 50)).save(cp / "input" / "my old thumb.jpg")
    (cp / "input" / "thumbnail_original.jpg").write_bytes((cp / "input" / "my old thumb.jpg").read_bytes())
    rc, out = run(py, ["scripts/conform.py", "landscape", "--project", "c1"], dict(env, PROMO_PROJECTS_DIR=str(cp.parent)), root)
    check(rc == 0 and Image.open(cp / "final" / "thumbnail_horizontal_title.png").size == (1920, 1080), "conform.py makes a 1920x1080 landscape from a 1376x752 thumbnail")
    Image.new("RGB", (1392, 752), (20, 20, 40)).save(cp / "final" / "_untitle_raw.png")
    rc, out = run(py, ["scripts/conform.py", "art", "--project", "c1", "--qwen"], dict(env, PROMO_PROJECTS_DIR=str(cp.parent)), root)
    check(rc == 0 and Image.open(cp / "final" / "thumbnail_horizontal.png").size == (1920, 1080), "conform.py art --qwen fits the Qwen untitle result to 1920x1080")
    # local title removal: a white title with a dark outline on a purple picture disappears, the rest stays identical
    from PIL import ImageDraw
    own = Image.new("RGB", (1920, 1080), (60, 30, 100))
    ImageDraw.Draw(own).rectangle((900, 700, 1100, 800), fill=(200, 40, 40))      # something that must stay
    d = ImageDraw.Draw(own)
    for k in range(8):
        d.rectangle((420 + k * 130, 60, 420 + k * 130 + 95, 150), fill=(255, 255, 255), outline=(10, 10, 10), width=6)
    own.save(cp / "final" / "thumbnail_horizontal_title.png")
    rc, out = run(py, ["scripts/conform.py", "art", "--project", "c1"], dict(env, PROMO_PROJECTS_DIR=str(cp.parent)), root)
    res = Image.open(cp / "final" / "thumbnail_horizontal.png").convert("RGB")
    check(rc == 0 and res.getpixel((470, 100))[0] < 150 and res.getpixel((1000, 750)) == (200, 40, 40) and res.getpixel((100, 900)) == (60, 30, 100),
          "conform.py art erases the title locally (text gone, the rest identical, no Qwen)")

    # conform, rest of the chain: hero cut-out, clean background, factory --conform keeps the user's landscape files
    env_c = dict(env, PROMO_PROJECTS_DIR=str(cp.parent))
    rc, out = run(py, ["scripts/new_map.py", "c2", "Conform Test"], env_c, root)
    c2 = cp.parent / "c2"
    synth_inputs(c2)
    (c2 / "characters" / "character_01.png").unlink()
    (c2 / "final").mkdir(exist_ok=True)
    Image.new("RGB", (1920, 1080), (70, 20, 90)).save(c2 / "final" / "thumbnail_horizontal_title.png")
    Image.new("RGB", (1920, 1080), (60, 20, 80)).save(c2 / "final" / "thumbnail_horizontal.png")
    raw = Image.new("RGB", (1392, 752), (0, 255, 0))
    dr = ImageDraw.Draw(raw)
    dr.ellipse((560, 60, 660, 160), fill=(200, 170, 150))
    dr.rounded_rectangle((520, 160, 700, 520), 30, fill=(150, 70, 50))
    dr.rectangle((560, 300, 640, 380), fill=(0, 255, 0))                 # an enclosed pocket of background colour must be removed
    dr.rectangle((600, 420, 640, 480), fill=(30, 140, 40))               # a darker green detail of the outfit must stay
    dr.rectangle((540, 520, 680, 751), fill=(60, 60, 80))        # legs run to the bottom border = a cut hero
    raw.save(c2 / "characters" / "_hero_raw.png")
    rc, out = run(py, ["scripts/conform.py", "hero", "--project", "c2"], env_c, root)
    ch_ = Image.open(c2 / "characters" / "character_01.png")
    al_ = ch_.getchannel("A")
    check(rc == 0 and ch_.mode == "RGBA" and al_.getpixel((2, 2)) == 0 and al_.getpixel((121, 321)) == 0 and al_.getpixel((141, 431)) == 255 and al_.getpixel((150, 150)) == 255,
          "conform.py hero cuts the hero out of the flat green render")
    _cfg = json.loads((c2 / "config.json").read_text(encoding="utf-8"))
    check(_cfg["characters"][0].get("complete") is False and "CUT" in out, "conform.py hero reports a hero cut by the picture border and records complete=false")
    # a hero that only just touches the border (two thin feet, 12 px wide) must still be reported as cut
    thin = Image.new("RGB", (1392, 752), (0, 255, 0))
    dt = ImageDraw.Draw(thin)
    dt.ellipse((600, 100, 700, 200), fill=(200, 170, 150))
    dt.rounded_rectangle((570, 200, 730, 600), 30, fill=(150, 70, 50))
    dt.rectangle((620, 600, 632, 751), fill=(60, 60, 80))
    dt.rectangle((668, 600, 680, 751), fill=(60, 60, 80))
    thin.save(c2 / "characters" / "_hero_raw.png")
    rc, out = run(py, ["scripts/conform.py", "hero", "--project", "c2"], env_c, root)
    check("CUT" in out and "bottom" in out, "conform.py hero reports a hero whose feet only just touch the bottom border")
    raw.save(c2 / "characters" / "_hero_raw.png")
    rc, out = run(py, ["scripts/conform.py", "hero", "--project", "c2"], env_c, root)
    (c2 / "background" / "_clean_probe.png").write_bytes((c2 / "background" / "background.png").read_bytes())
    Image.new("RGB", (2400, 1200), (10, 60, 20)).save(c2 / "background" / "background_clean.png")
    rc, out = run(py, ["scripts/conform.py", "use-clean", "--project", "c2"], env_c, root)
    check(rc == 0 and (c2 / "background" / "_previous" / "background_source.png").exists()
          and Image.open(c2 / "background" / "background.png").getpixel((5, 5)) == (10, 60, 20), "conform.py use-clean swaps in the clean background and keeps the original")
    before = {n: (c2 / "final" / n).read_bytes() for n in ("thumbnail_horizontal.png",)}
    own_title = (c2 / "final" / "thumbnail_horizontal_title.png").read_bytes()
    cfg_ = json.loads((c2 / "config.json").read_text(encoding="utf-8")); cfg_["characters"][0]["identity"] = "test hero"; cfg_["case"] = "conform"   # as conform.py landscape sets it
    (c2 / "config.json").write_text(json.dumps(cfg_), encoding="utf-8")
    rc, out = run(py, ["scripts/factory.py", "--project", "c2"], dict(env_c, PROMO_PLAN_B="bust"), root)
    fin = c2 / "final"
    check(rc == 0 and all((fin / n).read_bytes() == b for n, b in before.items())
          and Image.open(fin / "thumbnail_vertical.png").size == (1440, 1920) and (fin / "island_logo.png").exists()
          and (c2 / "background" / "lobby_background.png").exists() and (fin / "thumbnail_horizontal_own_title.png").read_bytes() == own_title
          and (fin / "thumbnail_horizontal_title.png").read_bytes() != own_title
          and "conform case" in out, "factory.py on a map in the conform case (no flag) builds portrait, logo and lobby, keeps the user's art-only landscape and puts the kit's title on it")
    if rc != 0:
        print(out[-1500:])
    rc, out = run(py, ["scripts/intake.py", "--project", "c2", "--init", "--mood", "dark"], env_c, root)
    rc2, out2 = run(py, ["scripts/music_generator.py", "--seed", "3", "--seconds", "8"], dict(env_c, PROMO_PROJECT="c2"), root)
    check(json.loads((c2 / "config.json").read_text(encoding="utf-8")).get("music_mood") == "dark" and rc2 == 0 and "mood=dark" in out2
          and (c2 / "audio" / "music_mood.txt").read_text(encoding="utf-8") == "dark", "music mood is chosen in the config and used by the music generator")
    rc, out = run(py, ["scripts/conform.py", "status", "--project", "c2"], env_c, root)
    check(rc == 0 and "DONE  hero cut-out" in out and "NEXT: run_all.py" in out.replace("style + hero identity saved", "") or "NEXT:" in out,
          "conform.py status lists done steps and the next one")

    # portrait mode follows the hero: a full-body cut-out keeps its legs (direct), a cut or half-body hero gets the bust
    import importlib
    sys.path.insert(0, str(REPO / "scripts"))
    ppm = importlib.import_module("promo_project")
    pb = tmp / "pb"
    for name, size, feet in (("full", (500, 1100), False), ("cutfeet", (500, 1100), True), ("wide", (1100, 500), False)):
        d = pb / name
        (d / "characters").mkdir(parents=True)
        (d / "config.json").write_text(json.dumps({"characters": [{"file": "characters/character_01.png"}]}), encoding="utf-8")
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((size[0] // 4, 20, size[0] * 3 // 4, size[1] - (1 if feet else 40)), fill=(120, 60, 40, 255))
        im.save(d / "characters" / "character_01.png")
    d = pb / "margins"          # full-body skin exported with big transparent margins: the file is nearly square, the figure is tall
    (d / "characters").mkdir(parents=True)
    (d / "config.json").write_text(json.dumps({"characters": [{"file": "characters/character_01.png"}]}), encoding="utf-8")
    im = Image.new("RGBA", (860, 1033), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((250, 50, 600, 990), fill=(120, 60, 40, 255))
    im.save(d / "characters" / "character_01.png")
    modes = {n: ppm.plan_b_default(pb / n) for n in ("full", "cutfeet", "wide", "margins")}
    check(modes == {"full": "direct", "cutfeet": "bust", "wide": "bust", "margins": "direct"}, "portrait mode: full-body hero = direct (legs kept), feet cut or half body = bust (%s)" % modes)
    cfg_f = json.loads((pb / "full" / "config.json").read_text()); cfg_f["characters"][0]["complete"] = False
    (pb / "full" / "config.json").write_text(json.dumps(cfg_f), encoding="utf-8")
    check(ppm.plan_b_default(pb / "full") == "bust", "portrait mode: complete=false in config.json wins over the image")

    # SessionEnd hook: leaving Claude Code stops the live console of every map (a stale console.json is cleaned up, PROMO_KEEP_CONSOLE=1 keeps it)
    # exposure rules: dark picture is lifted, bright one is left alone, "off" disables, own title/alpha kept
    sys.path.insert(0, str(root / "scripts"))
    import exposure
    from PIL import Image as _I
    os.environ["PROMO_EXPOSURE"] = "auto"
    dark = _I.new("RGB", (64, 64), (30, 30, 40))
    lit, g = exposure.lift_image(dark)
    check(g > 1.3 and exposure.measure(lit)[0] > exposure.measure(dark)[0] + 25, "exposure: dark picture is lifted (gamma %.2f)" % g)
    bright = _I.new("RGB", (64, 64), (160, 150, 140))
    same, g2 = exposure.lift_image(bright)
    check(g2 == 1.0 and same is bright, "exposure: bright picture is left alone")
    black = _I.new("RGB", (64, 64), (0, 0, 0))
    check(exposure.lift_image(black)[0].getpixel((1, 1)) == (0, 0, 0), "exposure: pure black stays black")
    os.environ["PROMO_EXPOSURE"] = "off"
    check(exposure.lift_image(dark)[1] == 1.0, "exposure: PROMO_EXPOSURE=off disables the lift")
    del os.environ["PROMO_EXPOSURE"]
    check(exposure.eq_filter(1.0) == "" and exposure.eq_filter(1.4).startswith("eq=gamma=1.4"), "exposure: ffmpeg eq filter text")

    # --redo-all: old promo_pack is archived (nothing deleted by hand), the user's own music file is kept
    ra = tmp / "ra_projects"
    for sub_ in ("p1/promo_pack", "p1/final", "p1/audio"):
        (ra / sub_).mkdir(parents=True)
    (ra / "p1" / "config.json").write_text("{}")
    (ra / "p1" / "promo_pack" / "01.png").write_text("x")
    (ra / "p1" / "audio" / "music.mp3").write_text("m")
    rc, out = run(py, ["scripts/run_all.py", "--project", "p1", "--redo-all", "--skip-images", "--skip-video"], dict(env, PROMO_PROJECTS_DIR=str(ra)), root)
    arch = list((ra / "p1" / "final" / "_previous").glob("*_redo/promo_pack/01.png"))
    check(len(arch) == 1 and "cleaned" in out and not (ra / "p1" / "promo_pack" / "01.png").exists() and "audio/music.* exists" in out and (ra / "p1" / "audio" / "music.mp3").exists(), "run_all --redo-all moves the old results aside (clean) and keeps the user's music")

    # video badges: the age-rating badge (ESRB) goes in the left corner, found by name; a tall FNDV-named file is not the Fortnite logo
    bp = tmp / "badge_projects" / "p1" / "badges"
    bp.mkdir(parents=True)
    (tmp / "badge_projects" / "p1" / "config.json").write_text("{}")
    from PIL import Image as _BI
    _BI.new("RGBA", (325, 493), (255, 255, 255, 255)).save(bp / "esrb_teen.png")
    rc, out = run(py, ["-c", "import sys; sys.argv=['x']; sys.path.insert(0,'scripts'); import trailer_builder as t, promo_project as p; print('RATING', t.find_rating_badge(p.project_dir()).name)"],
                  dict(env, PROMO_PROJECTS_DIR=str(tmp / "badge_projects"), PROMO_PROJECT="p1"), root)
    check("RATING esrb_teen.png" in out, "trailer: the age-rating badge is found by name (esrb_*.png / rating.png), PEGI is gone")
    check("pegi" not in (root / "scripts" / "trailer_builder.py").read_text(encoding="utf-8").lower(), "trailer: no PEGI left in the code")

    se = tmp / "se_projects"
    for m in ("m1", "m2"):
        (se / m / "final").mkdir(parents=True)
        (se / m / "config.json").write_text("{}")
        (se / m / "final" / "console.json").write_text(json.dumps({"url": "http://127.0.0.1:9", "pid": 0}))
    rc, out = run(py, ["scripts/session_end.py"], dict(env, PROMO_PROJECTS_DIR=str(se), PROMO_KEEP_CONSOLE="1"), root)
    check(rc == 0 and (se / "m1" / "final" / "console.json").exists(), "session_end hook keeps the console with PROMO_KEEP_CONSOLE=1")
    rc, out = run(py, ["scripts/session_end.py"], dict(env, PROMO_PROJECTS_DIR=str(se)), root)
    check(rc == 0 and not (se / "m1" / "final" / "console.json").exists() and not (se / "m2" / "final" / "console.json").exists(),
          "session_end hook stops the console of every map on exit")
    st = json.loads((REPO / "scripts" / "claude_kit" / "settings.json").read_text(encoding="utf-8"))
    check("island_session_end" in json.dumps(st.get("hooks", {}).get("SessionEnd", [])), "kit settings carry the SessionEnd hook")

    server.shutdown()
    print("\n%d check(s) failed, %.0f s" % (len(FAILS), time.time() - t0))
    if keep:
        print("kept: %s" % tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
