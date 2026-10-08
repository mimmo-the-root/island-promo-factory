import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Keep a map's work folders small: old archives pile up in final/_previous, final/_runs and background/_runs.

Usage: cleanup.py [--project SLUG] [--keep 3] [--apply]
Dry run by default (lists what would go and how much space it frees). With --apply the older items are MOVED to
Projects/<map>/_to_delete/ (nothing is erased; delete that folder yourself when you are happy).
"""
import argparse
import shutil
from datetime import datetime
from pathlib import Path

import promo_project as pp

ARCHIVES = ["final/_previous", "final/_runs", "background/_runs"]


def size(p):
    p = Path(p)
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--keep", type=int, default=3, help="newest items to keep in each archive folder")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.project:
        import os
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    trash = proj / "_to_delete" / datetime.now().strftime("%Y%m%d_%H%M%S")
    total = 0
    for rel in ARCHIVES:
        d = proj / rel
        if not d.is_dir():
            continue
        items = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime)
        old = items[:-a.keep] if a.keep > 0 else items
        for it in old:
            total += size(it)
            print("%s %s/%s (%.1f MB)" % ("MOVE" if a.apply else "would move", rel, it.name, size(it) / 1048576.0))
            if a.apply:
                dest = trash / rel
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(it), str(dest / it.name))
    print("%s %.0f MB%s" % ("freed" if a.apply else "would free", total / 1048576.0, "" if a.apply else "  (run again with --apply)"))


if __name__ == "__main__":
    main()
