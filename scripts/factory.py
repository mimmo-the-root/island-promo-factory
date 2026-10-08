import os
import shutil
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ============================================================
# ISLAND PROMO FACTORY - complete image pipeline
#
# Usage:
#   python factory.py                 full run (needs ComfyUI)
#   python factory.py --title "NAME"  override the map title
#   python factory.py --no-qwen       skip Qwen: rebuild lobby, vertical
#                                     background, title and thumbnails from
#                                     the existing final/artwork*.png
#
# Every stage must succeed AND produce its file, otherwise the run stops.
# Previous results are archived in final/_previous/<timestamp>/ and are
# never deleted.
# ============================================================

PROJECT = Path(__file__).resolve().parent.parent

# --project <slug>: work on one map at a time (or the only map under Projects/).
if "--project" in sys.argv:
    _i = sys.argv.index("--project")
    if _i + 1 >= len(sys.argv):
        raise SystemExit("--project needs a map slug (folder name under Projects/).")
    os.environ["PROMO_PROJECT"] = sys.argv[_i + 1]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promo_project  # noqa: E402
ROOT = PROJECT.parent
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")

PYTHON = promo_project.find_python()

SCRIPTS = PROJECT / "scripts"
TEST_PROJECT = promo_project.project_dir()

PROMPT_BUILDER = SCRIPTS / "qwen_prompt_builder.py"
QWEN_RUN = SCRIPTS / "qwen_run.py"
PREPARE_VERTICAL_BACKGROUND = SCRIPTS / "prepare_vertical_background.py"
LOBBY_BACKGROUND = SCRIPTS / "lobby_background.py"
TITLE_COMPOSER = SCRIPTS / "title_composer.py"
THUMBNAIL_FACTORY = SCRIPTS / "thumbnail_factory.py"
LOGO_COMPOSER = SCRIPTS / "logo_composer.py"
UPSCALE = SCRIPTS / "upscale.py"
PROMO_PACK = SCRIPTS / "promo_pack.py"
VALIDATOR = SCRIPTS / "validate_project.py"

FINAL_DIR = TEST_PROJECT / "final"
TITLE_DIR = TEST_PROJECT / "title"
BACKGROUND_DIR = TEST_PROJECT / "background"

QWEN_OUTPUTS = ["artwork.png", "artwork_vertical.png", "artwork_up.png", "artwork_vertical_up.png"]

THUMBNAIL_OUTPUTS = [
    "thumbnail_horizontal.png",
    "thumbnail_horizontal_title.png",
    "thumbnail_vertical.png",
    "thumbnail_vertical_title.png",
]


def fail(message):
    raise RuntimeError(message)


def run_script(script, *args, expect=()):
    print("\n" + "=" * 64)
    print(f" RUNNING: {script.name} {' '.join(args)}")
    print("=" * 64)

    if not script.exists():
        fail(f"Script not found: {script}")

    started = time.time()

    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")

    proc = subprocess.Popen(
        [str(PYTHON), str(script), *args],
        cwd=str(PROJECT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    for line in proc.stdout:
        print(line, end="")

    returncode = proc.wait()

    if returncode != 0:
        fail(f"{script.name} failed with exit code {returncode}")

    # A script that exits 0 without producing its file is a failure too.
    for path in expect:
        if not path.exists():
            fail(f"{script.name} finished but did not create: {path}")

        if path.stat().st_mtime < started - 2:
            fail(f"{script.name} finished but did not update: {path}")


def check_comfyui():
    print("\nChecking ComfyUI...")

    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=5) as response:
            if response.status != 200:
                fail("ComfyUI returned a non-200 response.")
    except Exception:
        fail(f"ComfyUI is not running on {COMFY_URL}")

    print("ComfyUI: OK")


def validate_inputs():
    background = BACKGROUND_DIR / "background.png"
    characters_dir = TEST_PROJECT / "characters"

    if not background.exists():
        fail(f"Missing source background: {background}")

    if not characters_dir.exists():
        fail(f"Missing characters directory: {characters_dir}")

    character = characters_dir / "character_01.png"

    if not character.exists():
        fail(f"Missing character: {character}")

    print("Source background: OK")
    print("Character asset: OK (character_01.png, one character for all formats)")


def archive_previous(filenames):
    """Move previous results to final/_previous/<timestamp>/ (never delete)."""

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    TITLE_DIR.mkdir(parents=True, exist_ok=True)

    existing = [FINAL_DIR / n for n in filenames if (FINAL_DIR / n).exists()]

    if not existing:
        return

    target = FINAL_DIR / "_previous" / datetime.now().strftime("%Y%m%d_%H%M%S")
    target.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 64)
    print(f" ARCHIVING PREVIOUS RESULTS -> {target.relative_to(TEST_PROJECT)}")
    print("=" * 64)

    for path in existing:
        shutil.move(str(path), str(target / path.name))
        print(f"MOVED: {path.name}")


def check_required_scripts(no_qwen):
    scripts = [
        PREPARE_VERTICAL_BACKGROUND,
        LOBBY_BACKGROUND,
        TITLE_COMPOSER,
        LOGO_COMPOSER,
        THUMBNAIL_FACTORY,
        VALIDATOR,
        PROMO_PACK,
    ]

    if not no_qwen:
        scripts += [PROMPT_BUILDER, QWEN_RUN, UPSCALE]

    missing = [str(p) for p in scripts if not p.exists()]

    if missing:
        for item in missing:
            print(f" - missing: {item}")
        fail("Pipeline is incomplete.")


class _Tee:
    """Mirror stdout/stderr to a log file (overwritten each run)."""

    def __init__(self, stream, log):
        self.stream = stream
        self.log = log

    def write(self, text):
        try:
            self.stream.write(text)
        except Exception:
            pass
        self.log.write(text)
        self.log.flush()

    def flush(self):
        try:
            self.stream.flush()
        except Exception:
            pass
        self.log.flush()


def start_log():
    log_path = Path(__file__).resolve().parent.parent / "last_run.log"
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    sys.stdout = _Tee(sys.__stdout__, log)
    sys.stderr = _Tee(sys.__stderr__, log)
    return log_path


def main():
    start_log()
    promo_project.normalize_background()
    args = sys.argv[1:]
    no_qwen = "--no-qwen" in args

    title_args = []

    if "--title" in args:
        index = args.index("--title")

        if index + 1 >= len(args):
            fail("--title needs a value.")

        title_args = [args[index + 1]]

    print("=" * 64)
    print(" ISLAND PROMO FACTORY - IMAGE PIPELINE")
    print(f" Map:  {promo_project.project_name()}")
    print(f" Mode: {'COMPOSE ONLY (--no-qwen)' if no_qwen else 'FULL (Qwen + compose)'}")
    print("=" * 64)

    validate_inputs()
    check_required_scripts(no_qwen)

    if not no_qwen:
        check_comfyui()
        archive_previous(QWEN_OUTPUTS + THUMBNAIL_OUTPUTS + ["island_logo.png"])
    else:
        archive_previous(THUMBNAIL_OUTPUTS + ["island_logo.png"])

    # 1. Lobby background 2048x1024 (environment only).
    run_script(LOBBY_BACKGROUND, expect=[BACKGROUND_DIR / "lobby_background.png"])

    # 2. Native portrait background 1440x1920 (3:4).
    run_script(
        PREPARE_VERTICAL_BACKGROUND,
        expect=[BACKGROUND_DIR / "background_vertical.png"],
    )

    if not no_qwen:
        # 3. Prompt file from config.json + template.
        run_script(
            PROMPT_BUILDER,
            expect=[TEST_PROJECT / "qwen_prompt_final.txt"],
        )

        # 3b. One-time clean horizontal background (removes unwanted objects, per-map prompt).
        #     Skipped when it already exists; PROMO_REFRESH_BG=1 forces it.
        #     Only for maps that define Projects/<map>/qwen_prompt_clean_background.txt
        #     (+ qwen_negative_clean_background.txt): it is map-specific.
        clean_bg = BACKGROUND_DIR / "background_clean.png"
        clean_prompt = TEST_PROJECT / "qwen_prompt_clean_background.txt"
        if not clean_prompt.exists():
            print("\nNo qwen_prompt_clean_background.txt in this map: background cleanup skipped.")
        elif os.environ.get("PROMO_REFRESH_BG") == "1" or not clean_bg.exists():
            run_script(QWEN_RUN, "clean", expect=[clean_bg])
        else:
            print("\nbackground_clean.png exists: skipping cleanup (PROMO_REFRESH_BG=1 to redo)")

        # 4. Horizontal artwork: ONE character (same as vertical).
        run_script(QWEN_RUN, "horizontal", expect=[FINAL_DIR / "artwork.png"])

        # 5. Native portrait artwork: 1 character (the portrait fits only one).
        run_script(QWEN_RUN, "vertical", expect=[FINAL_DIR / "artwork_vertical.png"])

        # 5b. Optional AI upscale (skips itself when no upscale model is installed).
        run_script(UPSCALE)

    # 6. Title layer.
    run_script(TITLE_COMPOSER, *title_args, expect=[TITLE_DIR / "title.png"])

    # 6b. Island Name Logo 1440x608 (PNG alpha) from the same title layer.
    run_script(LOGO_COMPOSER, *title_args, expect=[FINAL_DIR / "island_logo.png"])

    # 7. Four thumbnails.
    run_script(
        THUMBNAIL_FACTORY,
        expect=[FINAL_DIR / name for name in THUMBNAIL_OUTPUTS],
    )

    # 8. Validate every required output.
    run_script(VALIDATOR)

    # 9. Promo Pack: Creator Portal-ready files + upload checklist.
    run_script(PROMO_PACK, "--no-video", expect=[TEST_PROJECT / "promo_pack" / "UPLOAD_CHECKLIST.md"])

    print("\n" + "=" * 64)
    print(" PROMO FACTORY SUCCESS")
    print("=" * 64)
    print(f"Project: {TEST_PROJECT}")
    print(f"Final:   {FINAL_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n" + "=" * 64)
        print(" PROMO FACTORY FAILED")
        print("=" * 64)
        print(str(exc))
        print("\nPrevious results (if any) are in final/_previous/.")
        sys.exit(1)
