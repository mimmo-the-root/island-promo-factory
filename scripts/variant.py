import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Generate an A/B test variant (B, C, ...) of a map's images with a NEW seed, without touching version A.

Usage: variant.py --project SLUG --name B [--seed N] [--no-qwen]

Works in a throw-away copy of the inputs (Projects/_variant_<slug>_<name>), runs the image pipeline there
(Qwen artwork with a new seed, title, logo, thumbnails, promo pack images) and moves the result to
Projects/<slug>/variants/<name>/. Your current final/ and promo_pack/ (variant A) are never modified.
Progress for the dashboard: variants/<name>/status.json and variants/<name>/log.txt.
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import promo_project as pp

SCRIPTS = Path(__file__).resolve().parent
COPY_DIRS = ("background", "characters", "input")
COPY_FILES = ("config.json", "qwen_prompt_custom.txt")
KEEP_FINAL = ("artwork.png", "artwork_up.png", "artwork_vertical.png", "artwork_vertical_up.png",
              "thumbnail_horizontal.png", "thumbnail_horizontal_title.png", "thumbnail_vertical.png",
              "thumbnail_vertical_title.png", "island_logo.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-qwen", action="store_true")
    a = ap.parse_args()
    name = "".join(ch for ch in a.name.upper() if ch.isalnum())[:4]
    if not name or name == "A":
        sys.exit("ERROR: variant name must be B, C, D... (A is the main version)")
    os.environ["PROMO_PROJECT"] = a.project
    src = pp.project_dir()
    if not (src / "config.json").exists():
        sys.exit("ERROR: map not found: %s" % src)
    out = src / "variants" / name
    out.mkdir(parents=True, exist_ok=True)
    seed = a.seed if a.seed is not None else random.randint(1, 2 ** 48)
    status_file, log_file = out / "status.json", out / "log.txt"

    def status(state, **kw):
        status_file.write_text(json.dumps({"name": name, "state": state, "seed": seed, "started": started, **kw}), encoding="utf-8")

    started = time.time()
    status("running", stage="preparing")
    tmp = pp.projects_dir() / ("_variant_%s_%s" % (a.project, name))
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for d in COPY_DIRS:
        if (src / d).is_dir():
            shutil.copytree(src / d, tmp / d)
    for f in COPY_FILES:
        if (src / f).exists():
            shutil.copyfile(src / f, tmp / f)
    if a.no_qwen:  # without Qwen the existing artwork is the input
        (tmp / "final").mkdir(exist_ok=True)
        for f in (src / "final").glob("artwork*.png"):
            shutil.copyfile(f, tmp / "final" / f.name)
    cfg = json.loads((tmp / "config.json").read_text(encoding="utf-8"))
    cfg.setdefault("project", {})["name"] = tmp.name
    (tmp / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    env = dict(os.environ, PROMO_SEED=str(seed), PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PROMO_PROJECT=tmp.name,
               PROMO_PROJECTS_DIR=str(pp.projects_dir()))
    env.setdefault("PROMO_PLAN_B", pp.plan_b_default(src))
    cmd = [sys.executable, str(SCRIPTS / "factory.py"), "--project", tmp.name] + (["--no-qwen"] if a.no_qwen else [])
    status("running", stage="images (seed %d)" % seed)
    with open(log_file, "w", encoding="utf-8", errors="replace") as log:
        log.write("variant %s of %s | seed %d\n" % (name, a.project, seed))
        log.flush()
        rc = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        status("failed", stage="images", error="the image pipeline failed - see log.txt", seconds=round(time.time() - started, 1))
        shutil.rmtree(tmp, ignore_errors=True)
        print("VARIANT %s FAILED (see %s)" % (name, log_file))
        sys.exit(1)

    # move the results next to A, never over it
    for old in list(out.iterdir()):
        if old.name not in ("status.json", "log.txt"):
            shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink()
    (out / "final").mkdir(exist_ok=True)
    for f in KEEP_FINAL:
        if (tmp / "final" / f).exists():
            shutil.copyfile(tmp / "final" / f, out / "final" / f)
    if (tmp / "promo_pack").is_dir():
        shutil.copytree(tmp / "promo_pack", out / "promo_pack")
    (out / "variant.json").write_text(json.dumps({"name": name, "seed": seed, "map": a.project,
                                                   "created": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    status("done", stage="done", seconds=round(time.time() - started, 1))
    print("VARIANT %s READY (seed %d): %s" % (name, seed, out))


if __name__ == "__main__":
    main()
