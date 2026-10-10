import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Claude Code SessionEnd hook (island_session_end): when you leave Claude Code (/exit, Ctrl+C twice, logout) the live console server is stopped.

Stops the console of every map (final/console.json -> services.stop_console). ComfyUI is NOT touched (other tools may use it).
Off with PROMO_KEEP_CONSOLE=1. Prints nothing, never fails the exit.
"""
import os
import sys

try:
    if os.environ.get("PROMO_KEEP_CONSOLE") != "1":
        import promo_project as pp
        import services

        stopped = 0
        root = pp.projects_dir()
        for cfg in sorted(root.glob("*/final/console.json")) if root.is_dir() else []:
            try:
                services.stop_console(cfg.parent.parent.name)
                stopped += 1
            except Exception:
                pass
except Exception:
    pass          # a hook must never break the exit
sys.exit(0)
