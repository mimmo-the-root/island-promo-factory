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
    latest = V.latest_release()
    tag = (latest or {}).get("tag", "")
    if tag and V.is_newer(tag, cur):
        msgs.append("Island Promo Factory %s is available (you have v%s). Type /island-update to install it." % (tag, cur))
        ctx.append("A newer Island Promo Factory release (%s) exists; the installed version is v%s. Offer the user to run /island-update before starting a map." % (tag, cur))
    ctx.append("Island Promo Factory v%s. For a new or existing map follow the island-promo skill (step 0 = island-intake). "
               "You run every command yourself: the user must never have to double-click .bat files." % cur)
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(ctx)}}
    if msgs:
        out["systemMessage"] = " ".join(msgs)
    print(json.dumps(out))
except Exception:
    pass          # a hook must never break the session
sys.exit(0)
