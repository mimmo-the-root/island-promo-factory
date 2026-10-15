"""Quick tests (a few seconds, no ffmpeg/ComfyUI): agents, cost rules, contact sheet, agent_cost, kit sync, console kit bar.
Run: python tests/test_harness.py     (the long end-to-end test is tests/smoke_test.py)"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
fails = []


def check(ok, name):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


# --- agents: valid front matter, cheap models only
agents = sorted((ROOT / "scripts" / "claude_kit" / "agents").glob("*.md"))
check(len(agents) == 7, "7 agents in the kit")
ok_models = True
for f in agents:
    t = f.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    fm = dict(l.split(": ", 1) for l in m.group(1).splitlines()) if m else {}
    if not (fm.get("name") == f.stem and fm.get("description") and fm.get("model") in ("haiku", "sonnet") and fm.get("tools")):
        ok_models = False
        print("   bad agent:", f.name, fm)
check(ok_models, "agents: name = file, description, tools, model haiku or sonnet (never opus)")
check("Cost rules" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8"), "CLAUDE.md has the cost rules")

# --- kit sync copies agents, keeps the user's own settings and agents
import claude_sync  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    shutil.copytree(ROOT / "scripts" / "claude_kit", d / "scripts" / "claude_kit")
    (d / ".claude").mkdir()
    (d / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
    (d / ".claude" / "agents").mkdir()
    (d / ".claude" / "agents" / "mine.md").write_text("mine", encoding="utf-8")
    ch = claude_sync.sync(d, quiet=True)
    check((d / ".claude" / "agents" / "art-director.md").exists(), "sync installs the agents")
    check((d / ".claude" / "agents" / "mine.md").exists(), "sync keeps the user's own agent")
    st = json.loads((d / ".claude" / "settings.json").read_text(encoding="utf-8"))
    check(st.get("permissions", {}).get("allow") == ["Bash(ls)"] and "SessionStart" in st.get("hooks", {}), "sync merges hooks and keeps the user's settings")
    check(claude_sync.sync(d, quiet=True) == [], "second sync changes nothing")
    # CRLF copy is not a change
    f = d / ".claude" / "agents" / "art-director.md"
    f.write_bytes(f.read_bytes().replace(b"\n", b"\r\n"))
    check(claude_sync.sync(d, quiet=True) == [], "CRLF-only difference is not a change")

# --- contact sheet
from PIL import Image  # noqa: E402
import contact_sheet  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    files = []
    for i, (w, h) in enumerate(((1920, 1080), (1440, 1920), (1440, 608))):
        p = d / ("img%d.png" % i)
        Image.new("RGBA", (w, h), (200, 30 * i, 30, 255 if i < 2 else 0)).save(p)
        files.append(p)
    out = contact_sheet.build(files, d / "sheet.jpg", 1200, 3)
    with Image.open(out) as im:
        check(im.width == 1200 and im.height < 1200 and (d / "sheet.jpg").stat().st_size < 400_000, "contact sheet: one small image of 3 pictures")

# --- agent_cost reads transcripts, counts a message once
import agent_cost  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "sub" / "subagents").mkdir(parents=True)
    line = lambda mid, model, i, o: json.dumps({"uuid": mid, "message": {"id": mid, "model": model, "usage": {"input_tokens": i, "output_tokens": o}}})
    (d / "s1.jsonl").write_text("\n".join([line("a", "claude-sonnet-5-5", 100, 10), line("a", "claude-sonnet-5-5", 100, 10)]), encoding="utf-8")
    (d / "sub" / "subagents" / "agent-1.jsonl").write_text(line("b", "claude-haiku-4-5", 50, 5), encoding="utf-8")
    r = agent_cost.scan(tdir=d)
    check(r["models"]["claude-sonnet-5-5"]["input_tokens"] == 100 and r["kinds"]["sub-agent"]["calls"] == 1 and r["total"] == 165,
          "agent_cost: per model and role, duplicates counted once")
    check(agent_cost.scan(tdir=d / "none")["files"] == 0, "agent_cost: no transcripts is not an error")

# --- console: kit bar + costs page exist, doctor --fix exists
dash = (ROOT / "scripts" / "dashboard.py").read_text(encoding="utf-8")
check("/api/kit" in dash and "START_VERSION" in dash and '"/costs"' in dash, "console has the kit-updated bar and the costs page")
check("/social.zip" in dash and "d[\"social\"]" in dash and "NOT for the Creator Portal" in dash, "console separates Creator Portal files from social files")
check("--fix" in (ROOT / "scripts" / "doctor.py").read_text(encoding="utf-8"), "doctor has --fix")

# --- v1.1.22: similarity, font check, heartbeat, licensed music, unedited gameplay slot, latest-result.json
import similarity  # noqa: E402
import font_check  # noqa: E402
import promo_project as _pp  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    import numpy as _np
    rng = _np.random.RandomState(1)
    base = (rng.rand(54, 96, 3) * 255).astype("uint8")
    other = (rng.rand(54, 96, 3) * 255).astype("uint8")
    Image.fromarray(base).resize((960, 540)).save(d / "a.png")
    Image.fromarray(base).resize((1920, 1080)).save(d / "a2.png")      # same picture, other size
    Image.fromarray(other).resize((960, 540)).save(d / "b.png")
    def prof(name, f, skin):
        pr = d / name
        (pr / "promo_pack").mkdir(parents=True)
        shutil.copy(d / f, pr / "promo_pack" / "02_landscape_art_only_1920x1080.png")
        (pr / "config.json").write_text(json.dumps({"default_skin": skin, "style": "NEON"}), encoding="utf-8")
        return similarity.profile(pr)
    pa, pa2, pb = prof("m1", "a.png", "Skin X"), prof("m2", "a2.png", "Skin X"), prof("m3", "b.png", "Skin Y")
    res = similarity.compare(pa, [pa2, pb])
    check(any(l == "WARN" and "m2" in m for l, m in res) and not any("m3" in m and l == "WARN" for l, m in res), "similarity: the same picture is a WARN, an unrelated one is not")
    check(any("same skin" in m for l, m in res), "similarity: the same skin on two maps is reported")
ff = font_check.font_files()
check(bool(ff) and font_check.check("Crazy Race", "4194-7202-1504")[1] == [], "font_check: title and island code can be drawn")
check(font_check.check("Crazy \u9f8d", "1234", ff[-1:])[1] == ["\u9f8d"], "font_check: a character the font cannot draw is reported")
import io as _io, contextlib as _cl
_buf = _io.StringIO()
with _cl.redirect_stdout(_buf):
    _r = _pp.run_alive([sys.executable, "-c", "import time; time.sleep(1.3)"], "test", every=0.4)
check(_r.returncode == 0 and "still working" in _buf.getvalue(), "run_alive: a long command prints a heartbeat")
ra_src = (ROOT / "scripts" / "run_all.py").read_text(encoding="utf-8")
check("music_source" in ra_src and "licensed" in ra_src and "latest-result.json" in ra_src and '"similarity"' in ra_src, "run_all: licensed music, similarity stage, latest-result.json")
ve_src = (ROOT / "scripts" / "video_extract.py").read_text(encoding="utf-8")
check("gameplay_montage.mp4" in ve_src and '"unedited": True' in ve_src, "video_extract: slot 07 is the unedited cut, the montage is a separate file")
check("gameplay_montage_1920x1080.mp4" in (ROOT / "scripts" / "promo_pack.py").read_text(encoding="utf-8"), "promo_pack puts the montage in social/, not in the portal files")

# --- social is optional: not in the kit run, a console button, the bot asks after the kit
check('"--social"' in ra_src and "optional: add --social" in ra_src and "not a.social" in ra_src, "run_all: social content is optional (--social), the kit holds the unedited cut only")
check("/api/social" in dash and "mkSocial" in dash and "CREATE SOCIAL VIDEOS" in dash, "console: button to create the social videos")
check("Optional social step" in (ROOT / "scripts" / "claude_kit" / "skills" / "island-review" / "SKILL.md").read_text(encoding="utf-8"), "island-review: asks about the social videos AFTER the kit")

# --- v1.1.23: per-stage cache
import stage_cache as sc  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    for sub in ("input", "final", "promo_pack", "characters", "title", "background"):
        (d / sub).mkdir()
    (d / "config.json").write_text("{}", encoding="utf-8")
    (d / "input" / "a.png").write_bytes(b"one")
    for o in sc.STAGES["images"]["out"]:
        (d / o).write_bytes(b"x")
    k1 = sc.stage_key(d, "images", "q=1")
    check(not sc.hit(d, "images", k1), "stage cache: nothing stored yet is a miss")
    sc.store(d, "images", k1)
    check(sc.hit(d, "images", sc.stage_key(d, "images", "q=1")), "stage cache: same inputs and outputs present is a hit")
    check(not sc.hit(d, "images", sc.stage_key(d, "images", "q=0")), "stage cache: a changed flag is a miss")
    (d / "input" / "a.png").write_bytes(b"two")
    check(not sc.hit(d, "images", sc.stage_key(d, "images", "q=1")), "stage cache: a changed input file is a miss")
    (d / "input" / "a.png").write_bytes(b"one")
    check(sc.hit(d, "images", sc.stage_key(d, "images", "q=1")), "stage cache: restoring the input is a hit again")
    (d / sc.STAGES["images"]["out"][0]).unlink()
    check(not sc.hit(d, "images", sc.stage_key(d, "images", "q=1")), "stage cache: a missing output is a miss")
    (d / "promo_pack" / "01.png").write_bytes(b"p")
    (d / "promo_pack" / "lightbox.png").write_bytes(b"l1")
    kl = sc.stage_key(d, "lightbox")
    (d / "promo_pack" / "lightbox.png").write_bytes(b"l2")
    check(sc.stage_key(d, "lightbox") == kl, "stage cache: the lightbox's own output is not one of its inputs")
    big = d / "big.bin"
    with open(big, "wb") as f:
        f.truncate(sc.BIG + 1024)
    check(len(sc.file_digest(big)) == 64, "stage cache: files over 64 MB are sampled, not read whole")
ra2 = (ROOT / "scripts" / "run_all.py").read_text(encoding="utf-8")
check("--no-cache" in ra2 and "sc.hit(" in ra2 and "sc.store(" in ra2, "run_all uses the stage cache (--no-cache forces)")

# v1.1.24: manual, console route, footer, demo recording
import subprocess as _sp
_r = _sp.run([sys.executable, str(ROOT / "scripts" / "build_manual.py"), "--check"], capture_output=True, text=True)
check(_r.returncode == 0, "manual: committed HTML is current and passes the lint (links, anchors, images, no external resources, version)\n" + (_r.stdout + _r.stderr)[-600:])
_ver = (ROOT / "VERSION").read_text().strip()
check("v" + _ver in (ROOT / "docs" / "manual-html" / "index.html").read_text(encoding="utf-8"), "manual: footer carries the current version")
_db = (ROOT / "scripts" / "dashboard.py").read_text(encoding="utf-8")
check('"/manual"' in _db and "whatsnew" in _db and "not affiliated" in _db and 'id="fver"' in _db, "console: /manual/ route and footer (repo, MIT, disclaimer, version)")
_md = (ROOT / "scripts" / "make_demo.py").read_text(encoding="utf-8")
check("def recording(" in _md and "demo_recording.mp4" in _md, "demo: makes a script-made gameplay recording")
check((ROOT / ".github" / "workflows" / "pages.yml").exists() and "build_manual.py" in (ROOT / "publish.ps1").read_text(encoding="utf-8"), "pages workflow exists and publish.ps1 rebuilds the manual")

print("\n%d check(s) failed" % len(fails))
sys.exit(1 if fails else 0)
