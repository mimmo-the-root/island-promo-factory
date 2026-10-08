import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Install the Claude Code kit of this repo (skills, slash commands, start-up hook) into .claude/.

The reference copy lives in scripts/claude_kit/ (it travels with every update); this script mirrors it into .claude/:
  claude_kit/skills/*/SKILL.md   -> .claude/skills/...      (replaced when different; the old file goes to _update_backup/)
  claude_kit/commands/*.md       -> .claude/commands/...
  claude_kit/settings.json       -> MERGED into .claude/settings.json (your own settings are kept; only our hook entry is added)
Usage: claude_sync.py [--quiet] [--root DIR]      Prints one line per change; with --quiet only when something changed.
Run automatically by update.py and by the start-up hook, so a new kit version needs no manual step.
"""
import argparse
import json
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARK = "island_session_start"      # identifies our hook entry inside settings.json


def sync(root, quiet=False):
    root = Path(root)
    kit = root / "scripts" / "claude_kit"
    dst = root / ".claude"
    if not kit.is_dir():
        return []
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = root / "_update_backup" / ("claude_" + stamp)
    changes = []
    for sub in ("skills", "commands"):
        for f in sorted((kit / sub).rglob("*")) if (kit / sub).is_dir() else []:
            if not f.is_file():
                continue
            rel = f.relative_to(kit)
            target = dst / rel
            data = f.read_bytes()
            if target.exists():
                if target.read_bytes() == data:
                    continue
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup / rel)
                changes.append("updated %s" % rel.as_posix())
            else:
                changes.append("added %s" % rel.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    ours = json.loads((kit / "settings.json").read_text(encoding="utf-8")) if (kit / "settings.json").exists() else {}
    if ours:
        st_path = dst / "settings.json"
        try:
            cur = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
        except ValueError:
            cur = None
        if cur is None:
            changes.append("skipped settings.json (not valid JSON, left untouched)")
        else:
            before = json.dumps(cur, sort_keys=True)
            hooks = cur.setdefault("hooks", {})
            for event, entries in ours.get("hooks", {}).items():
                have = hooks.setdefault(event, [])
                for entry in entries:
                    blob = json.dumps(entry)
                    existing = [i for i, e in enumerate(have) if MARK in json.dumps(e)]
                    if existing:
                        have[existing[0]] = entry          # refresh our own entry
                    else:
                        have.append(entry)
                    assert MARK in blob
            if json.dumps(cur, sort_keys=True) != before:
                if st_path.exists():
                    (backup).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(st_path, backup / "settings.json")
                dst.mkdir(exist_ok=True)
                st_path.write_text(json.dumps(cur, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                changes.append("hook installed/updated in settings.json")
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--root", default=str(HERE.parent))
    a = ap.parse_args()
    ch = sync(a.root, a.quiet)
    if ch:
        print("Claude kit: %d change(s): %s" % (len(ch), "; ".join(ch)))
    elif not a.quiet:
        print("Claude kit: already up to date.")


if __name__ == "__main__":
    main()
