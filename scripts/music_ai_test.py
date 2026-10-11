import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))
"""Listening test for the AI music (kept for convenience): same as `music_ai.py --test`."""
import music_ai

if __name__ == "__main__":
    raise SystemExit(music_ai.main(["--test"] + _sys.argv[1:]))
