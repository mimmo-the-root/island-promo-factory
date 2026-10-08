import os
import sys
from pathlib import Path

from PIL import Image

# Native portrait source for Qwen. Epic portrait thumbnail = 1440x1920 (3:4).
# The old 1080x1920 (9:16) format is NOT an Epic Discover size.

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promo_project  # noqa: E402

PROJECT_DIR = promo_project.project_dir()

INPUT_FILE = PROJECT_DIR / "background" / "background.png"
OUTPUT_FILE = PROJECT_DIR / "background" / "background_vertical.png"

TARGET_WIDTH = 1440
TARGET_HEIGHT = 1920

# Horizontal crop position: 0.0 = left edge, 0.5 = centered, 1.0 = right edge.
# 0.72 keeps the main structure and drops the cropped starship / orphan
# beam fragment that appeared on the left with the centered crop.
ANCHOR_X = float(os.environ.get("VERTICAL_ANCHOR_X", "0.80"))


def crop_to_ratio(image, width, height, anchor_x):
    src_w, src_h = image.size
    target_ratio = width / height

    if src_w / src_h > target_ratio:
        crop_h = src_h
        crop_w = round(src_h * target_ratio)
        left = round((src_w - crop_w) * anchor_x)
        top = 0
    else:
        crop_w = src_w
        crop_h = round(src_w / target_ratio)
        left = 0
        top = (src_h - crop_h) // 2

    box = (left, top, left + crop_w, top + crop_h)
    return image.crop(box).resize((width, height), Image.Resampling.LANCZOS)


def main():
    print("=" * 40)
    print(" Island Promo Factory")
    print(" Vertical Background (3:4, 1440x1920)")
    print("=" * 40)

    if not INPUT_FILE.exists():
        print(f"ERROR: Background not found: {INPUT_FILE}")
        sys.exit(1)
    import promo_project as _pp
    _pp.normalize_background(INPUT_FILE)

    with Image.open(INPUT_FILE) as source:
        source = source.convert("RGB")
        print(f"Source: {source.width}x{source.height} | anchor_x={ANCHOR_X}")
        result = crop_to_ratio(source, TARGET_WIDTH, TARGET_HEIGHT, ANCHOR_X)

    result.save(OUTPUT_FILE, format="PNG")
    print(f"Output: {OUTPUT_FILE} ({result.width}x{result.height})")
    print("DONE")


if __name__ == "__main__":
    main()
