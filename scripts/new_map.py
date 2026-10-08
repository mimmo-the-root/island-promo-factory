import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Create the folder structure for a new map (one map at a time).

Usage: python new_map.py <slug> "MAP TITLE" [--style SCI_FI]
Creates Projects/<slug>/ with config.json and empty input folders, then tells
you which files to place before running:  factory.py --project <slug>
"""
import json
import promo_project as pp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLES = ("WHITE", "SCI_FI", "FIRE")  # see Resources/brand/brand.json for all styles


def main():
    args = sys.argv[1:]
    style = "SCI_FI"
    if "--style" in args:
        i = args.index("--style")
        style = args[i + 1]
        del args[i:i + 2]
    if len(args) < 2:
        raise SystemExit('usage: new_map.py <slug> "MAP TITLE" [--style SCI_FI]')

    slug, title = args[0], args[1]
    if not slug.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("slug must contain only letters, digits, - and _")

    brand = json.loads((ROOT / "Resources" / "brand" / "brand.json").read_text(encoding="utf-8"))
    if style not in brand["typography"]["styles"]:
        raise SystemExit(f"unknown style {style}; available: {', '.join(brand['typography']['styles'])}")

    project = pp.projects_dir() / slug
    if project.exists():
        raise SystemExit(f"Projects/{slug} already exists - nothing changed.")

    for sub in ("input", "background", "characters", "final", "title"):
        (project / sub).mkdir(parents=True)

    config = {
        "project": {"name": slug},
        "title": title,
        "island_code": "",   # e.g. 1234-5678-9012 - shown on the trailer end card and in the upload checklist
        "style": style,
        "scene": {"background": "background/background.png"},
        "characters": [{
            "file": "characters/character_01.png",
            "side": "left",
            "identity": "DESCRIBE THE CHARACTER: what must be preserved exactly (helmet/face/hair, armor, weapon, companion)",
            "pose": "keep the original pose from the reference, only slightly turned toward the center",
            "facing": "center",
        }],
        "qwen": {"max_characters": 1},
    }
    (project / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Created Projects/{slug}")
    print("Now place (UEFN/in-island captures only for licensed IP):")
    print(f"  Projects/{slug}/background/background.png      environment only (no characters), >= 1920 px wide")
    print(f"  Projects/{slug}/characters/character_01.png    ONE character, transparent PNG (RGBA)")
    print(f"  edit Projects/{slug}/config.json -> characters[0].identity")
    print("Then run:")
    print(f"  run_all.bat {slug}      (everything)   or   run_factory.bat {slug}      (images only)")


if __name__ == "__main__":
    main()
