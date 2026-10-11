import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Default skin: a map with NO character of its own gets a random one from Resources/Characters/.

Rules (one place):
  - Only when the map has no character: characters/character_01.png is missing AND characters/ holds no other picture.
    A skin you provide is never replaced.
  - The pick is random among Resources/Characters/*.png, cut to a workable size (prepare_character.py), saved as
    characters/character_01.png and remembered in config.json ("default_skin": "<file>"), so every later run keeps the same hero.
  - If characters[0].identity is still the placeholder it is written from the skin's name ("Skull Trooper").
  - Another one: python scripts/default_skin.py --project <map> --reroll   (or --skin "part of the file name" for a chosen one).
  - PROMO_SKINS_DIR points at another folder; PROMO_SKIN_SEED makes the pick repeatable.
Resources/Characters/ is never published (Epic Games artwork): only your own copy.
"""
import argparse
import json
import os
import random
import re
from pathlib import Path

import promo_project as pp

PLACEHOLDER = "DESCRIBE THE CHARACTER"
EXT = (".png", ".webp", ".jpg", ".jpeg")


def skins_dir():
    env = os.environ.get("PROMO_SKINS_DIR")
    if env:
        return Path(env)
    res = pp.ROOT / "Resources"
    if res.is_dir():
        for d in res.iterdir():                      # Windows is case-insensitive, other systems are not
            if d.is_dir() and d.name.lower() == "characters":
                return d
    return res / "Characters"


def list_skins():
    d = skins_dir()
    return sorted(p for p in d.iterdir() if p.suffix.lower() in EXT and not p.name.startswith((".", "_"))) if d.is_dir() else []


def skin_name(path):
    """'FN 01 Outfit (Funk Ops)(New Glasses).png' -> ('Funk Ops', 'New Glasses')."""
    groups = [g.strip() for g in re.findall(r"\(([^)]*)\)", Path(path).stem)]
    if groups:
        return groups[0], groups[1:]
    return re.sub(r"^FN\s*\d+\s*(Outfit)?\s*", "", Path(path).stem).strip() or Path(path).stem, []


def identity_for(path):
    name, extra = skin_name(path)
    more = (" (%s)" % ", ".join(extra)) if extra else ""
    return ('Fortnite outfit "%s"%s, full body: keep the head/helmet/face, the outfit, its colours and every accessory exactly as in the reference' % (name, more))


def has_character(proj, cfg):
    chars = proj / "characters"
    if not chars.is_dir():
        return False
    cfile = proj / ((cfg.get("characters") or [{}])[0].get("file") or "characters/character_01.png")
    if cfile.is_file():
        return True
    return any(p.suffix.lower() in EXT and not p.name.startswith("_") for p in chars.iterdir())


def _pick(skins, hint=None, avoid=None):
    pool = skins
    if hint:
        pool = [s for s in skins if hint.lower() in s.name.lower()] or skins
    if avoid and len(pool) > 1:
        pool = [s for s in pool if s.name != avoid] or pool
    seed = os.environ.get("PROMO_SKIN_SEED")
    return (random.Random(seed) if seed else random).choice(pool)


def apply(proj, cfg, skin):
    import prepare_character as pc
    dest = Path(proj) / "characters" / "character_01.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    size, _ = pc.prepare(skin, dest)
    chars = cfg.setdefault("characters", [{}])
    if not chars:
        chars.append({})
    c = chars[0]
    c["file"] = "characters/character_01.png"
    c.setdefault("side", "left")
    c.setdefault("pose", "keep the original pose from the reference, only slightly turned toward the center")
    c.setdefault("facing", "center")
    if not str(c.get("identity", "")).strip() or PLACEHOLDER in str(c.get("identity", "")) or c.get("default_skin"):
        c["identity"] = identity_for(skin)
    c.pop("complete", None)                          # judged again from the new cut-out
    c["default_skin"] = skin.name
    cfg["default_skin"] = skin.name
    (Path(proj) / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return size


def ensure(proj=None, log=print):
    """Gives the map a random default skin when it has no character. Returns the skin file name used, or None."""
    proj = Path(proj) if proj else pp.project_dir()
    try:
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    if has_character(proj, cfg):
        return None
    skins = list_skins()
    if not skins:
        return None
    skin = _pick(skins)
    size = apply(proj, cfg, skin)
    log("Default skin: this map has no character of its own, picked %s at random from %s (%dx%d). "
        "Another one: python scripts/default_skin.py --project %s --reroll" % (skin.name, skins_dir().name, size[0], size[1], proj.name))
    return skin.name


def main(argv=None):
    ap = argparse.ArgumentParser(description="random default skin from Resources/Characters")
    ap.add_argument("--project", default=None)
    ap.add_argument("--reroll", action="store_true", help="replace the map's character with another random skin")
    ap.add_argument("--skin", default=None, help="part of a skin's file name: use that one")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    skins = list_skins()
    if a.list or not (a.project or os.environ.get("PROMO_PROJECT")):
        print("%d skins in %s" % (len(skins), skins_dir()))
        for s in skins:
            print("  " + s.name)
        return 0
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
    if a.reroll or a.skin:
        if not skins:
            print("No skins in %s" % skins_dir())
            return 1
        skin = _pick(skins, a.skin, avoid=cfg.get("default_skin"))
        old = proj / "characters" / "character_01.png"
        if old.is_file():
            prev = proj / "characters" / "_previous"
            prev.mkdir(exist_ok=True)
            import time
            old.replace(prev / ("character_01_%s.png" % time.strftime("%Y%m%d_%H%M%S")))
        size = apply(proj, cfg, skin)
        print("Skin: %s (%dx%d). Rebuild the images: run_all %s --no-qwen --redo-portrait --skip-video (or without --no-qwen for new artwork)" % (skin.name, size[0], size[1], proj.name))
        return 0
    name = ensure(proj)
    print("Skin: %s" % (name or cfg.get("default_skin") or "the map already has its own character"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
