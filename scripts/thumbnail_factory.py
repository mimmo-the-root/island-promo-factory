import os
import sys
from pathlib import Path

from PIL import Image, ImageFilter

# ============================================================
# ISLAND PROMO FACTORY - Thumbnail Factory
#
# Inputs  (Projects/<map>):
#   final/artwork.png            horizontal Qwen artwork (2 characters)
#   final/artwork_vertical.png   native portrait Qwen artwork (1 character)
#   title/title.png              1920x1080 transparent title layer
#
# Outputs (final/), Epic Discover sizes:
#   thumbnail_horizontal.png         1920x1080  art only
#   thumbnail_horizontal_title.png   1920x1080  art + title
#   thumbnail_vertical.png           1440x1920  art only
#   thumbnail_vertical_title.png     1440x1920  art + title
# ============================================================

DEBUG = os.environ.get("PROMO_DEBUG", "0") == "1"

PROMO_FACTORY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import promo_project  # noqa: E402

PROJECT_DIR = promo_project.project_dir()

ARTWORK_FILE = PROJECT_DIR / "final" / "artwork.png"
ARTWORK_VERTICAL_FILE = PROJECT_DIR / "final" / "artwork_vertical.png"
TITLE_FILE = PROJECT_DIR / "title" / "title.png"
OUTPUT_DIR = PROJECT_DIR / "final"

HORIZONTAL_FILE = OUTPUT_DIR / "thumbnail_horizontal.png"
HORIZONTAL_TITLE_FILE = OUTPUT_DIR / "thumbnail_horizontal_title.png"
VERTICAL_FILE = OUTPUT_DIR / "thumbnail_vertical.png"
VERTICAL_TITLE_FILE = OUTPUT_DIR / "thumbnail_vertical_title.png"

HORIZONTAL_SIZE = (1920, 1080)
VERTICAL_SIZE = (1440, 1920)

# Epic: keep ~200 px (15%) free at the top and bottom (tags, CCU).
SAFE_MARGIN = 200
MAX_FILE_MB = 5.0

# Epic examples: portrait logo sits in the lower third, ~75-80% of the width.
VERTICAL_TITLE_WIDTH_RATIO = float(os.environ.get("PROMO_VTITLE_W", "0.78"))
VERTICAL_TITLE_CENTER_Y = float(os.environ.get("PROMO_VTITLE_CY", "0.78"))
# Horizontal: the character stands in the left third, the title goes in the
# right two thirds (center x as a fraction of the width).
HORIZONTAL_TITLE_CENTER_X = float(os.environ.get("PROMO_TITLE_CX", "0.70"))
VERTICAL_TITLE_TOP = SAFE_MARGIN + 15

# Qwen outputs ~1 MP; the upscale to Discover size is soft without this.
SHARPEN = ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2)


def log(message):
    if DEBUG:
        print(f"[debug] {message}")


def fail(message):
    print()
    print(f"ERROR: {message}")
    sys.exit(1)


def resize_cover(image, target_width, target_height):
    """Scale until the target is covered, then center-crop. Sharpen if upscaled."""

    source_width, source_height = image.size

    scale = max(
        target_width / source_width,
        target_height / source_height,
    )

    new_width = max(target_width, round(source_width * scale))
    new_height = max(target_height, round(source_height * scale))

    log(f"cover {image.size} -> {(new_width, new_height)} (x{scale:.3f})")

    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2

    cropped = resized.crop((left, top, left + target_width, top + target_height))

    if scale > 1.05:
        cropped = cropped.filter(SHARPEN)

    return cropped


def create_horizontal(artwork):
    return resize_cover(artwork, *HORIZONTAL_SIZE)


def create_vertical(artwork_vertical):
    """Native portrait artwork -> 1440x1920. No letterbox, no blur bands."""
    return resize_cover(artwork_vertical, *VERTICAL_SIZE)


def place_title_least_busy(thumbnail, cropped):
    """Conform case: the artwork is a finished picture (no empty space reserved for a title). The title is scaled to ~42% of the width and
    put in the least busy spot INSIDE the safe area (top row just under the 200 px margin, or the bottom row above it)."""
    import numpy as np
    from PIL import ImageFilter
    W, H = HORIZONTAL_SIZE
    tw = int(W * float(os.environ.get("PROMO_FIT_TITLE_W", "0.42")))
    th = max(1, int(cropped.height * tw / cropped.width))
    t = cropped.resize((tw, th), Image.Resampling.LANCZOS)
    g = thumbnail.convert("L")
    edges = np.array(g.filter(ImageFilter.FIND_EDGES)).astype(np.float32)
    lum = np.array(g).astype(np.float32)
    best = None
    rows = {"top": SAFE_MARGIN + 12, "bottom": H - SAFE_MARGIN - 12 - th}
    for name, y in rows.items():
        for cx in np.arange(0.26, 0.741, 0.02):
            x = int(round(W * cx - tw / 2))
            x = max(SAFE_MARGIN // 2, min(x, W - tw - SAFE_MARGIN // 2))
            reg_e, reg_l = edges[y:y + th, x:x + tw], lum[y:y + th, x:x + tw]
            score = float(reg_e.mean()) + 0.25 * float(reg_l.std()) + (0.0 if name == "top" else 4.0)   # the top row is preferred
            if best is None or score < best[0]:
                best = (score, x, y, name)
    _, x, y, name = best
    log(f"horizontal title fitted: {tw}x{th} at x={x} y={y} ({name} row, least busy spot)")
    result = thumbnail.copy()
    result.alpha_composite(t, (x, y))
    return result


def apply_title_horizontal(thumbnail, title):
    if title.size != HORIZONTAL_SIZE:
        title = title.resize(HORIZONTAL_SIZE, Image.Resampling.LANCZOS)

    bbox = title.getchannel("A").getbbox()

    if bbox is None:
        fail("title.png is fully transparent.")

    cropped = title.crop(bbox)
    if os.environ.get("PROMO_FIT_TITLE") == "1":
        return place_title_least_busy(thumbnail, cropped)
    # Keep the original vertical position, move the title horizontally.
    x = round(HORIZONTAL_SIZE[0] * HORIZONTAL_TITLE_CENTER_X - cropped.width / 2)
    x = max(SAFE_MARGIN // 2, min(x, HORIZONTAL_SIZE[0] - cropped.width - SAFE_MARGIN // 2))
    log(f"horizontal title bbox={bbox} x={x}")

    result = thumbnail.copy()
    result.alpha_composite(cropped, (x, bbox[1]))
    return result


def apply_title_vertical(thumbnail, title):
    """
    Crop the title layer to its visible bounds, scale it proportionally to
    a fraction of the portrait width and place it in the lower third
    (as in Epic's portrait examples), inside the safe area.
    """

    bbox = title.getchannel("A").getbbox()

    if bbox is None:
        fail("title.png is fully transparent.")

    title = title.crop(bbox)

    target_width = round(VERTICAL_SIZE[0] * VERTICAL_TITLE_WIDTH_RATIO)
    scale = target_width / title.width
    target_height = round(title.height * scale)

    title = title.resize((target_width, target_height), Image.Resampling.LANCZOS)

    x = (VERTICAL_SIZE[0] - target_width) // 2
    y = round(VERTICAL_SIZE[1] * VERTICAL_TITLE_CENTER_Y - target_height / 2)
    # Keep the title fully inside the safe area (200 px top and bottom).
    y = max(SAFE_MARGIN + 10, min(y, VERTICAL_SIZE[1] - SAFE_MARGIN - 10 - target_height))

    if y + target_height > VERTICAL_SIZE[1] - SAFE_MARGIN:
        fail("Vertical title does not fit inside the safe area.")

    log(f"vertical title {title.size} at {(x, y)}")

    result = thumbnail.copy()
    result.alpha_composite(title, (x, y))
    return result


def save_png(image, output_file):
    """Discover thumbnails are opaque: store RGB PNG, check the 5 MB cap."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    image.convert("RGB").save(str(output_file), format="PNG", optimize=True)

    size_mb = output_file.stat().st_size / (1024 * 1024)

    print(f"Created: {output_file.name} ({size_mb:.2f} MB)")

    if size_mb > MAX_FILE_MB:
        print(
            f"WARNING: {output_file.name} is above {MAX_FILE_MB} MB "
            "(Epic limit). Export as JPG for upload."
        )


def pick_artwork(raw, upscaled):
    """Use the AI-upscaled artwork only if it exists and is not older than the raw one."""
    if upscaled.exists() and upscaled.stat().st_mtime >= raw.stat().st_mtime - 2:
        log(f"using upscaled artwork: {upscaled.name}")
        return upscaled
    return raw


def main():
    print("=" * 40)
    print(" Island Promo Factory")
    print(" Thumbnail Factory")
    print("=" * 40)
    print()

    for label, path in (
        ("artwork.png", ARTWORK_FILE),
        ("artwork_vertical.png", ARTWORK_VERTICAL_FILE),
        ("title.png", TITLE_FILE),
    ):
        if not path.exists():
            fail(f"{label} not found: {path}")

    artwork_file = pick_artwork(ARTWORK_FILE, ARTWORK_FILE.with_name("artwork_up.png"))
    artwork_vertical_file = pick_artwork(
        ARTWORK_VERTICAL_FILE, ARTWORK_VERTICAL_FILE.with_name("artwork_vertical_up.png"))
    artwork = Image.open(artwork_file).convert("RGBA")
    artwork_vertical = Image.open(artwork_vertical_file).convert("RGBA")
    title = Image.open(TITLE_FILE).convert("RGBA")

    print(f"Artwork horizontal: {artwork.width}x{artwork.height} ({artwork_file.name})")
    print(f"Artwork vertical:   {artwork_vertical.width}x{artwork_vertical.height} ({artwork_vertical_file.name})")
    print(f"Title layer:        {title.width}x{title.height}")
    print()

    # exposure rules (exposure.py): dark artwork gets a gentle gamma lift BEFORE the title goes on; a conform map keeps the
    # user's own landscape untouched
    import exposure
    import promo_project as _pp
    if (_pp.load_config() or {}).get("case") != "conform":
        artwork, g_h = exposure.lift_image(artwork)
        if g_h > 1.0:
            print(f"Exposure: horizontal artwork lifted (gamma {g_h:.2f})")
    artwork_vertical, g_v = exposure.lift_image(artwork_vertical)
    if g_v > 1.0:
        print(f"Exposure: vertical artwork lifted (gamma {g_v:.2f})")

    horizontal = create_horizontal(artwork)
    save_png(horizontal, HORIZONTAL_FILE)
    save_png(apply_title_horizontal(horizontal, title), HORIZONTAL_TITLE_FILE)

    vertical = create_vertical(artwork_vertical)
    save_png(vertical, VERTICAL_FILE)
    save_png(apply_title_vertical(vertical, title), VERTICAL_TITLE_FILE)

    print()

    expected = (
        (HORIZONTAL_FILE, HORIZONTAL_SIZE),
        (HORIZONTAL_TITLE_FILE, HORIZONTAL_SIZE),
        (VERTICAL_FILE, VERTICAL_SIZE),
        (VERTICAL_TITLE_FILE, VERTICAL_SIZE),
    )

    ok = True

    for file, size in expected:
        if not file.exists():
            print(f"ERROR: missing output: {file}")
            ok = False
            continue

        with Image.open(file) as image:
            if image.size != size:
                print(f"ERROR: wrong size {file.name}: {image.size}, expected {size}")
                ok = False
            else:
                print(f"OK: {file.name} {image.width}x{image.height}")

    if not ok:
        fail("THUMBNAIL FACTORY FAILED")

    print()
    print("THUMBNAIL FACTORY SUCCESS (4 thumbnails)")


if __name__ == "__main__":
    main()
