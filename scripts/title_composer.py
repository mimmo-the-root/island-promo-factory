import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json
import sys


PROMO_FACTORY_DIR = Path(__file__).resolve().parent.parent

import promo_project  # noqa: E402

PROJECT_DIR = promo_project.project_dir()
_CONFIG = promo_project.load_config()

BRAND_FILE = (
    PROMO_FACTORY_DIR
    / "Resources"
    / "brand"
    / "brand.json"
)

OUTPUT_DIR = PROJECT_DIR / "title"
OUTPUT_FILE = OUTPUT_DIR / "title.png"


# ---------------------------------------------------------
# DEFAULTS
# ---------------------------------------------------------

DEFAULT_TITLE = _CONFIG.get("title", "MY MAP TITLE")

STYLE = _CONFIG.get("style", "SCI_FI")

FONT_1_SIZE = 135
FONT_2_SIZE = 210

STROKE_WIDTH = 10

SHADOW_OFFSET_X = 12
SHADOW_OFFSET_Y = 16

START_Y = 520


# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------


def resolve_font_path(brand):
    """Brand font if present, else any font in Resources/brand/font, else the bundled
    OFL fallback (Resources/fonts/LilitaOne-Regular.ttf). Returns a Path or None."""
    base = PROMO_FACTORY_DIR / "Resources"
    candidates = [base / "brand" / brand["typography"]["font"]]
    font_dir = base / "brand" / "font"
    if font_dir.exists():
        candidates += sorted(p for p in font_dir.iterdir() if p.suffix.lower() in (".otf", ".ttf"))
    candidates.append(base / "fonts" / "LilitaOne-Regular.ttf")
    for path in candidates:
        if path.exists():
            if path != candidates[0]:
                print(f"NOTE: brand font not found, using {path.name}")
            return path
    return None


def get_title():

    if len(sys.argv) > 1:

        title = " ".join(
            sys.argv[1:]
        ).strip()

        if title:
            return title

    return DEFAULT_TITLE


def split_title(title):

    # "MAIN TITLE | Subtitle": the bar is a separator, not a drawn character
    if "|" in title:
        parts = [p.strip() for p in title.split("|") if p.strip()]
        if len(parts) >= 2:
            return [parts[0], " ".join(parts[1:])]

    words = title.split()

    if len(words) <= 2:
        return [
            " ".join(words)
        ]

    midpoint = len(words) // 2

    return [
        " ".join(words[:midpoint]),
        " ".join(words[midpoint:])
    ]


# ---------------------------------------------------------
# GRADIENT TEXT
# ---------------------------------------------------------

def draw_gradient_text(
    base,
    position,
    text,
    font,
    top_color,
    bottom_color,
    outline_color,
    shadow_color
):

    x, y = position

    # -----------------------------------------------------
    # SHADOW
    # -----------------------------------------------------

    shadow = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    shadow_draw = ImageDraw.Draw(
        shadow
    )

    shadow_draw.text(
        (
            x + SHADOW_OFFSET_X,
            y + SHADOW_OFFSET_Y
        ),
        text,
        font=font,
        fill=shadow_color,
        stroke_width=STROKE_WIDTH,
        stroke_fill=shadow_color
    )

    base.alpha_composite(
        shadow
    )

    # -----------------------------------------------------
    # OUTLINE
    # -----------------------------------------------------

    outline = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    outline_draw = ImageDraw.Draw(
        outline
    )

    outline_draw.text(
        (x, y),
        text,
        font=font,
        fill=outline_color,
        stroke_width=STROKE_WIDTH,
        stroke_fill=outline_color
    )

    base.alpha_composite(
        outline
    )

    # -----------------------------------------------------
    # TEXT MASK
    #
    # IMPORTANT:
    # NO STROKE HERE.
    #
    # This prevents the gradient from covering
    # the black outline.
    # -----------------------------------------------------

    mask = Image.new(
        "L",
        base.size,
        0
    )

    mask_draw = ImageDraw.Draw(
        mask
    )

    mask_draw.text(
        (x, y),
        text,
        font=font,
        fill=255,
        stroke_width=0
    )

    # -----------------------------------------------------
    # GRADIENT
    # -----------------------------------------------------

    gradient = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    gradient_draw = ImageDraw.Draw(
        gradient
    )

    bbox = font.getbbox(
        text
    )

    # glyphs are drawn from y + bbox[1] (ascender offset) down to y + bbox[3]
    glyph_top = y + bbox[1]
    glyph_bottom = y + bbox[3]
    text_height = max(1, glyph_bottom - glyph_top)

    start_y = max(0, glyph_top)
    end_y = min(base.height, glyph_bottom + 1)

    for py in range(start_y, end_y):

        ratio = max(0.0, min(1.0, (py - glyph_top) / text_height))

        color = tuple(
            int(
                top_color[i]
                * (1.0 - ratio)
                +
                bottom_color[i]
                * ratio
            )
            for i in range(3)
        )

        gradient_draw.line(
            (
                0,
                py,
                base.width,
                py
            ),
            fill=(
                color[0],
                color[1],
                color[2],
                255
            )
        )

    # -----------------------------------------------------
    # APPLY GRADIENT ONLY INSIDE LETTERS
    # -----------------------------------------------------

    gradient_text = Image.composite(
        gradient,
        Image.new(
            "RGBA",
            base.size,
            (0, 0, 0, 0)
        ),
        mask
    )

    base.alpha_composite(
        gradient_text
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    with open(
        BRAND_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        brand = json.load(f)

    width = brand["thumbnail"]["width"]
    height = brand["thumbnail"]["height"]

    # -----------------------------------------------------
    # FONT
    # -----------------------------------------------------

    font_path = resolve_font_path(brand)

    if font_path is None:

        print()
        print("ERROR: no usable font found (Resources/brand/font or Resources/fonts).")
        print()

        sys.exit(1)

    styles = brand[
        "typography"
    ][
        "styles"
    ]

    style = styles[
        STYLE
    ]

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    title = get_title()

    lines = split_title(
        title
    )

    print("========================================")
    print(" Island Promo Factory")
    print(" Title Composer")
    print("========================================")
    print()

    print(
        f"Title: {title}"
    )

    print(
        f"Style: {STYLE}"
    )

    print(
        f"Font: {font_path}"
    )

    print(
        f"Stroke: {STROKE_WIDTH}px"
    )

    print()

    # -----------------------------------------------------
    # CANVAS
    # -----------------------------------------------------

    image = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        image
    )

    # -----------------------------------------------------
    # ONE LINE
    # -----------------------------------------------------

    if len(lines) == 1:

        font = ImageFont.truetype(
            str(font_path),
            FONT_2_SIZE
        )

        bbox = draw.textbbox(
            (0, 0),
            lines[0],
            font=font,
            stroke_width=STROKE_WIDTH
        )

        text_width = (
            bbox[2] - bbox[0]
        )

        x = (
            width - text_width
        ) // 2

        y = START_Y

        draw_gradient_text(
            image,
            (x, y),
            lines[0],
            font,
            tuple(
                style["gradient_top"]
            ),
            tuple(
                style["gradient_bottom"]
            ),
            tuple(
                style["outline"]
            ),
            tuple(
                style["shadow"]
            )
        )

    # -----------------------------------------------------
    # TWO LINES
    # -----------------------------------------------------

    else:

        font1 = ImageFont.truetype(
            str(font_path),
            FONT_1_SIZE
        )

        font2 = ImageFont.truetype(
            str(font_path),
            FONT_2_SIZE
        )

        bbox1 = draw.textbbox(
            (0, 0),
            lines[0],
            font=font1,
            stroke_width=STROKE_WIDTH
        )

        bbox2 = draw.textbbox(
            (0, 0),
            lines[1],
            font=font2,
            stroke_width=STROKE_WIDTH
        )

        width1 = (
            bbox1[2] - bbox1[0]
        )

        width2 = (
            bbox2[2] - bbox2[0]
        )

        x1 = (
            width - width1
        ) // 2

        x2 = (
            width - width2
        ) // 2

        draw_gradient_text(
            image,
            (
                x1,
                START_Y
            ),
            lines[0],
            font1,
            tuple(
                style["gradient_top"]
            ),
            tuple(
                style["gradient_bottom"]
            ),
            tuple(
                style["outline"]
            ),
            tuple(
                style["shadow"]
            )
        )

        draw_gradient_text(
            image,
            (
                x2,
                START_Y + FONT_1_SIZE
            ),
            lines[1],
            font2,
            tuple(
                style["gradient_top"]
            ),
            tuple(
                style["gradient_bottom"]
            ),
            tuple(
                style["outline"]
            ),
            tuple(
                style["shadow"]
            )
        )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    image.save(
        OUTPUT_FILE,
        "PNG"
    )

    print()
    print("DONE")
    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()