import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Epic's media rules in ONE place (epic_specs.json): sizes, limits, video length, what is forbidden, where each rule comes from.

promo_pack.py, video_validate.py, trailer_builder.py, the upload checklist and the docs read it, so a change of Epic's rules is one edit here.
CLI:  python epic_specs.py        prints the rules, the date they were checked and the links.
"""
import json
from pathlib import Path

_FILE = Path(__file__).with_name("epic_specs.json")
SPECS = json.loads(_FILE.read_text(encoding="utf-8"))


def image(name):
    """{'size': (w, h), 'max_mb': n, ...} for landscape / portrait / logo / lobby."""
    d = dict(SPECS["images"][name])
    d["size"] = tuple(d["size"])
    return d


def video():
    return dict(SPECS["video"])


def video_seconds():
    v = SPECS["video"]
    return float(v["min_s"]), float(v["max_s"])


def main():
    print("Epic media rules, checked on %s (mandatory thumbnail types from %s)" % (SPECS["verified"], SPECS["mandatory_from"]))
    for k, v in SPECS["images"].items():
        print("  image %-9s %s" % (k, v))
    print("  video: %s" % SPECS["video"])
    for k, u in SPECS["sources"].items():
        print("  %s: %s" % (k, u))


if __name__ == "__main__":
    main()
