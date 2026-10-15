import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Claude Code SessionStart hook (island_session_start): keeps the kit current and tells Claude / the user what is new.

1. mirrors scripts/claude_kit/ into .claude/ (new skills and commands appear without a manual step)
2. checks GitHub for a newer release (cached 6 h, silent when offline, off with PROMO_NO_UPDATE_CHECK=1)
Prints ONE line of JSON for Claude Code ({"systemMessage": ..., "hookSpecificOutput": {...}}) or nothing. Never fails the session.
"""
import json
import sys

try:
    import claude_sync
    import version as V

    msgs, ctx = [], []
    changes = claude_sync.sync(V.ROOT, quiet=True)
    if changes:
        msgs.append("Island Promo Factory kit synced (%d file(s)); open a new session to load updated skills." % len(changes))
    cur = V.read_version()
    mk = V.ROOT / ".post-update"
    if mk.exists():
        try:
            m = json.loads(mk.read_text(encoding="utf-8"))
            msgs.append("Island Promo Factory updated from v%s to v%s: %s file(s)." % (m.get("from"), m.get("to"), m.get("files")))
            mk.unlink()
        except Exception:
            pass
    seen = V.ROOT / ".last_seen_version"
    try:
        prev = seen.read_text(encoding="utf-8").strip()
    except OSError:
        prev = ""
    if prev and prev != cur and not any("updated from" in m for m in msgs):
        msgs.append("Island Promo Factory updated from v%s to v%s." % (prev, cur))     # git pull / manual copy: no update.bat marker
    try:
        seen.write_text(cur, encoding="utf-8")
    except OSError:
        pass
    latest = V.latest_release()
    tag = (latest or {}).get("tag", "")
    if tag and V.is_newer(tag, cur):
        msgs.append("Island Promo Factory %s is available (you have v%s). Type /promo-update to install it." % (tag, cur))
        ctx.append("A newer Island Promo Factory release (%s) exists; the installed version is v%s. Offer the user to run /promo-update before starting a map." % (tag, cur))
    if not any("available" in m for m in msgs):
        msgs.append("Island Promo Factory v%s - up to date." % cur)
    ctx.append("Island Promo Factory v%s. For a new or existing map follow the island-promo skill (step 0 = island-intake). "
               "You run every command yourself: the user must never have to double-click .bat files." % cur)
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(ctx)}}
    if msgs:
        out["systemMessage"] = " ".join(msgs)
    print(json.dumps(out))
except Exception:
    pass          # a hook must never break the session
sys.exit(0)
