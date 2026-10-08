"""Island Name Logo: 1440x608 PNG with alpha (Epic spec), rendered at NATIVE size.

Epic composes art + logo at display time, so the logo must be crisp: the title
is rendered directly with the brand font at the size needed to fill the
1440x608 canvas (no upscaling of a small raster). It reuses the drawing code
of title_composer.py, so logo and thumbnail title look identical.

Usage: python logo_composer.py ["TITLE TEXT"]   (default title like title_composer.py)
Output: final/island_logo.png
Env: PROMO_DEBUG=1 for extra logging.
"""
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import title_composer as tc  # noqa: E402

DEBUG = os.environ.get("PROMO_DEBUG") == "1"

OUTPUT = tc.PROJECT_DIR / "final" / "island_logo.png"

LOGO_SIZE = (1440, 608)
PAD_X = 72
PAD_Y = 40
CANVAS = (4200, 2200)
ORIGIN = (300, 200)

BASE = {
    "FONT_1_SIZE": tc.FONT_1_SIZE,
    "FONT_2_SIZE": tc.FONT_2_SIZE,
    "STROKE_WIDTH": tc.STROKE_WIDTH,
    "SHADOW_OFFSET_X": tc.SHADOW_OFFSET_X,
    "SHADOW_OFFSET_Y": tc.SHADOW_OFFSET_Y,
}


def log(msg):
    if DEBUG:
        print(f"[logo] {msg}")


def render(title, font_path, style, k):
    """Render the title with every size multiplied by k; return the cropped RGBA."""
    for name, value in BASE.items():
        setattr(tc, name, max(1, round(value * k)))

    image = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    lines = tc.split_title(title)
    colors = (tuple(style["gradient_top"]), tuple(style["gradient_bottom"]),
              tuple(style["outline"]), tuple(style["shadow"]))

    from PIL import ImageDraw
    draw = ImageDraw.Draw(image)
    y = ORIGIN[1]
    for index, line in enumerate(lines):
        size = tc.FONT_2_SIZE if (len(lines) == 1 or index == len(lines) - 1) else tc.FONT_1_SIZE
        font = ImageFont.truetype(str(font_path), size)
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=tc.STROKE_WIDTH)
        x = (CANVAS[0] - (bbox[2] - bbox[0])) // 2
        tc.draw_gradient_text(image, (x, y), line, font, *colors)
        y += size

    box = image.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box is None:
        print("ERROR: rendered logo is empty.")
        sys.exit(1)
    return image.crop(box)


def main():
    print("=== LOGO COMPOSER (1440x608 alpha, native render) ===")

    if not tc.BRAND_FILE.exists():
        print(f"ERROR: brand file not found: {tc.BRAND_FILE}")
        sys.exit(1)

    brand = json.loads(tc.BRAND_FILE.read_text(encoding="utf-8"))
    font_path = tc.resolve_font_path(brand)
    if font_path is None:
        print("ERROR: no usable font found (Resources/brand/font or Resources/fonts).")
        sys.exit(1)

    style = brand["typography"]["styles"][tc.STYLE]
    title = tc.get_title()
    print(f"Title: {title}")

    max_w = LOGO_SIZE[0] - 2 * PAD_X
    max_h = LOGO_SIZE[1] - 2 * PAD_Y

    probe = render(title, font_path, style, 1.0)
    k = min(max_w / probe.width, max_h / probe.height)
    log(f"probe {probe.size} -> k={k:.3f}")

    logo = render(title, font_path, style, k)
    # Rounding of font sizes can leave a tiny excess: shrink only if needed.
    if logo.width > max_w or logo.height > max_h:
        s = min(max_w / logo.width, max_h / logo.height)
        logo = logo.resize((round(logo.width * s), round(logo.height * s)), Image.Resampling.LANCZOS)
        log(f"final fit shrink x{s:.4f}")
    log(f"logo {logo.size}")

    canvas = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(
        logo, ((LOGO_SIZE[0] - logo.width) // 2, (LOGO_SIZE[1] - logo.height) // 2))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT, "PNG", optimize=True)
    print(f"OK: {OUTPUT} {LOGO_SIZE[0]}x{LOGO_SIZE[1]} RGBA ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
