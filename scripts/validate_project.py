import os
import sys
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promo_project  # noqa: E402

PROJECT = promo_project.project_dir()
BACKGROUND = PROJECT / "background"
TITLE = PROJECT / "title"
FINAL = PROJECT / "final"

SAFE_MARGIN = 200
MAX_FILE_MB = 5.0

# (path, exact size or None, (min_ratio, max_ratio) or None, min_width)
# Raw Qwen artworks are ~1 MP and have their own ratio: only the ratio
# range is checked. Epic deliverables are checked at the exact size.
CHECKS = [
    (BACKGROUND / "lobby_background.png", (2048, 1024), None, 0),
    (BACKGROUND / "background_vertical.png", (1440, 1920), None, 0),
    (TITLE / "title.png", (1920, 1080), None, 0),
    (FINAL / "artwork.png", None, (1.6, 2.0), 1200),
    (FINAL / "artwork_vertical.png", None, (0.68, 0.80), 800),
    (FINAL / "thumbnail_horizontal.png", (1920, 1080), None, 0),
    (FINAL / "thumbnail_horizontal_title.png", (1920, 1080), None, 0),
    (FINAL / "thumbnail_vertical.png", (1440, 1920), None, 0),
    (FINAL / "thumbnail_vertical_title.png", (1440, 1920), None, 0),
]

# (art only, art + title): the title must stay inside the safe area.
TITLE_PAIRS = [
    (FINAL / "thumbnail_horizontal.png", FINAL / "thumbnail_horizontal_title.png"),
    (FINAL / "thumbnail_vertical.png", FINAL / "thumbnail_vertical_title.png"),
]

DELIVERABLES = [
    FINAL / "thumbnail_horizontal.png",
    FINAL / "thumbnail_horizontal_title.png",
    FINAL / "thumbnail_vertical.png",
    FINAL / "thumbnail_vertical_title.png",
    FINAL / "island_logo.png",
]


def rel(path):
    return path.relative_to(PROJECT)


def check_image(path, size, ratio_range, min_width):
    if not path.exists():
        return f"MISSING: {rel(path)}"

    try:
        with Image.open(path) as image:
            actual = image.size
            if image.mode != "RGBA" and "transparency" in image.info:
                return f"COLOUR-KEY TRANSPARENCY: {path.name} has a hidden transparent colour (white/solid pixels would vanish on the portal)"
    except Exception as exc:
        return f"INVALID IMAGE: {path.name} -> {exc}"

    if size and actual != size:
        return f"WRONG SIZE: {path.name} -> {actual}, expected {size}"

    if ratio_range:
        ratio = actual[0] / actual[1]

        if not (ratio_range[0] <= ratio <= ratio_range[1]) or actual[0] < min_width:
            return (
                f"WRONG FORMAT: {path.name} -> {actual} "
                f"(ratio {ratio:.3f}, expected {ratio_range}, width >= {min_width})"
            )

    print(f"OK: {rel(path)} {actual[0]}x{actual[1]}")
    return None


def check_title_in_safe_area(art_only, with_title):
    if not art_only.exists() or not with_title.exists():
        return None

    with Image.open(art_only) as a, Image.open(with_title) as b:
        a = a.convert("RGB")
        b = b.convert("RGB")

        if a.size != b.size:
            return f"SIZE MISMATCH: {art_only.name} / {with_title.name}"

        diff = ImageChops.difference(a, b).convert("L").point(
            lambda v: 255 if v > 24 else 0
        )

        bbox = diff.getbbox()
        height = a.height

    if bbox is None:
        return f"NO TITLE FOUND: {with_title.name}"

    top, bottom = bbox[1], bbox[3]

    if top < SAFE_MARGIN or bottom > height - SAFE_MARGIN:
        return (
            f"TITLE OUTSIDE SAFE AREA: {with_title.name} "
            f"y={top}..{bottom}, allowed {SAFE_MARGIN}..{height - SAFE_MARGIN}"
        )

    print(f"OK: title safe area {with_title.name} y={top}..{bottom}")
    return None


def check_logo(path):
    """Island Name Logo: exactly 1440x608, RGBA, transparent, content off the edges."""
    if not path.exists():
        return f"MISSING {rel(path)}"

    with Image.open(path) as img:
        if img.size != (1440, 608):
            return f"WRONG SIZE {rel(path)} -> {img.size}, expected (1440, 608)"
        if img.mode != "RGBA":
            return f"NO ALPHA CHANNEL {rel(path)} (mode {img.mode})"
        alpha = img.getchannel("A")

    low, high = alpha.getextrema()
    if low != 0:
        return f"LOGO HAS NO TRANSPARENT AREA: {path.name}"
    bbox = alpha.point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox is None:
        return f"LOGO IS EMPTY: {path.name}"
    left, top, right, bottom = bbox
    if left < 20 or top < 10 or right > 1440 - 20 or bottom > 608 - 10:
        return f"LOGO TOO CLOSE TO EDGE: {path.name} bbox={bbox}"

    print(f"OK: logo {path.name} 1440x608 RGBA bbox={bbox}")
    return None


def check_file_size(path, limit_mb=None):
    if not path.exists():
        return None

    size_mb = path.stat().st_size / (1024 * 1024)

    limit = limit_mb or MAX_FILE_MB

    if size_mb > limit:
        return f"OVER {limit} MB: {path.name} ({size_mb:.2f} MB)"

    print(f"OK: {path.name} {size_mb:.2f} MB (<= {limit} MB)")
    return None


def main():
    print()
    print("=" * 40)
    print(" FINAL OUTPUT VALIDATION")
    print("=" * 40)

    errors = []

    for path, size, ratio_range, min_width in CHECKS:
        error = check_image(path, size, ratio_range, min_width)
        if error:
            errors.append(error)

    for art_only, with_title in TITLE_PAIRS:
        if os.environ.get("PROMO_CONFORM") == "1" and with_title.name == "thumbnail_horizontal_title.png":
            print("SKIP: title position of %s (conform case: the title is the user's own design)" % with_title.name)
            continue
        error = check_title_in_safe_area(art_only, with_title)
        if error:
            errors.append(error)

    error = check_logo(FINAL / "island_logo.png")
    if error:
        errors.append(error)

    for path in DELIVERABLES:
        # Creator Portal: logo PNG < 3 MB, thumbnails < 5 MB.
        error = check_file_size(path, 3 if path.name == "island_logo.png" else None)
        if error:
            errors.append(error)

    if errors:
        print()
        print("VALIDATION FAILED:")
        for error in errors:
            print(f" - {error}")
        sys.exit(1)

    print()
    print("ALL REQUIRED OUTPUTS ARE VALID")


if __name__ == "__main__":
    main()
