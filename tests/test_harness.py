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
check("--fix" in (ROOT / "scripts" / "doctor.py").read_text(encoding="utf-8"), "doctor has --fix")

print("\n%d check(s) failed" % len(fails))
sys.exit(1 if fails else 0)
