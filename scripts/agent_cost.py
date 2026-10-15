import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Where did the tokens go? Reads the Claude Code transcripts of this folder (no prices, only token counts).

Usage: agent_cost.py [--json] [--days N] [--root DIR]
Groups by model and by main session vs sub-agents. Needs no network. Console: /costs
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def transcripts_dir(root=ROOT):
    """~/.claude/projects/<folder path with separators turned into '-'>"""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    name = re.sub(r"[^A-Za-z0-9]", "-", str(Path(root).resolve()))
    return home / "projects" / name


def scan(root=ROOT, days=None, tdir=None):
    tdir = Path(tdir) if tdir else transcripts_dir(root)
    out = {"dir": str(tdir), "models": {}, "kinds": {}, "total": 0, "files": 0}
    if not tdir.is_dir():
        return out
    cutoff = time.time() - days * 86400 if days else 0
    seen = set()
    for f in tdir.rglob("*.jsonl"):
        try:
            if f.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        kind = "sub-agent" if "subagent" in f.as_posix().lower() or f.name.startswith("agent-") else "main"
        out["files"] += 1
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            m = d.get("message") if isinstance(d, dict) else None
            if not isinstance(m, dict) or not isinstance(m.get("usage"), dict):
                continue
            key = (m.get("id"), d.get("requestId"), d.get("uuid"))
            if key in seen:
                continue
            seen.add(key)
            u = m["usage"]
            n = {k: int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
            for bucket, name in ((out["models"], m.get("model") or "unknown"), (out["kinds"], kind)):
                b = bucket.setdefault(name, {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "calls": 0})
                for k, v in n.items():
                    b[k] += v
                b["calls"] += 1
            out["total"] += sum(n.values())
    return out


def render(r):
    lines = ["Tokens (no prices) - %s  [%d transcript file(s)]" % (r["dir"], r["files"])]
    for title, bucket in (("By model", r["models"]), ("By role", r["kinds"])):
        lines.append("\n" + title)
        for k, b in sorted(bucket.items(), key=lambda x: -(x[1]["input_tokens"] + x[1]["output_tokens"])):
            lines.append("  %-34s calls %5d  in %10d  out %9d  cache-read %11d" % (k, b["calls"], b["input_tokens"], b["output_tokens"], b["cache_read_input_tokens"]))
    if not r["files"]:
        lines.append("\nNo transcripts found for this folder yet.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args()
    r = scan(a.root, a.days)
    print(json.dumps(r, indent=2) if a.json else render(r))


if __name__ == "__main__":
    main()
