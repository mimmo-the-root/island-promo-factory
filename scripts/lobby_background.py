from pathlib import Path
import sys
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promo_project  # noqa: E402

PROJECT = promo_project.project_dir()
SOURCE = PROJECT / "background" / "background.png"
OUTPUT = PROJECT / "background" / "lobby_background.png"

TARGET_WIDTH = 2048
TARGET_HEIGHT = 1024


def resize_cover(image, width, height):
    source_width, source_height = image.size
    target_ratio = width / height
    source_ratio = source_width / source_height

    if source_ratio > target_ratio:
        # Source is wider: fit height, crop left/right.
        new_height = height
        new_width = round(source_width * (height / source_height))
    else:
        # Source is taller: fit width, crop top/bottom.
        new_width = width
        new_height = round(source_height * (width / source_width))

    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    left = max(0, (new_width - width) // 2)
    top = max(0, (new_height - height) // 2)

    return image.crop((left, top, left + width, top + height))


def main():
    print("\n" + "=" * 64)
    print(" LOBBY BACKGROUND")
    print("=" * 64)

    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source background: {SOURCE}")

    promo_project.normalize_background(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(SOURCE) as source:
        source = source.convert("RGB")
        result = resize_cover(source, TARGET_WIDTH, TARGET_HEIGHT)

    import exposure
    result, g = exposure.lift_image(result)
    if g > 1.0:
        print(f"Exposure: dark background lifted (gamma {g:.2f})")
    result.save(OUTPUT, "PNG", optimize=True)

    with Image.open(OUTPUT) as check:
        if check.size != (TARGET_WIDTH, TARGET_HEIGHT):
            raise RuntimeError(
                f"Wrong output size: {check.size}, "
                f"expected {(TARGET_WIDTH, TARGET_HEIGHT)}"
            )

    print(f"OK: {OUTPUT}")
    print(f"Size: {TARGET_WIDTH}x{TARGET_HEIGHT}")
    print("Environment-only source preserved.")
    print("No text, title, characters, logo or UI added.")


if __name__ == "__main__":
    main()
