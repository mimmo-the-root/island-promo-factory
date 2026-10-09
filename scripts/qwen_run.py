"""Qwen Image Edit runner (ComfyUI API) for the active map (PROMO_PROJECT).

Usage: python qwen_run.py <mode>
  horizontal  background(+clean) + character_01 -> final/artwork.png            (16:9, ONE character)
  vertical    background_vertical + character_01 -> final/artwork_vertical.png (3:4,  ONE character)
  clean       background -> background/background_clean.png (removes unwanted objects)
  untitle     final/thumbnail_horizontal_title.png (a finished thumbnail) -> final/_untitle_raw.png (removes ONLY the text; characters stay)
              (case "make my thumbnail conform"; then `conform.py art` makes final/thumbnail_horizontal.png)

Prompts: Resources/prompts/qwen_{prompt,negative}_<mode>.txt (a file with the same
name inside the project folder overrides it). Horizontal uses the project's
qwen_prompt_final.txt (built by qwen_prompt_builder.py).
Env: COMFY_URL, PROMO_PROJECT, PROMO_SEED, PROMO_DEBUG=1
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comfy_common as cc  # noqa: E402
import promo_project as pp  # noqa: E402

BACKGROUND_NODE, CHARACTER_NODE = "41", "197"
POSITIVE_NODE, NEGATIVE_NODE = "170:151", "170:149"
SAVE_NODE = "195"


def feather_clipped_edges(char, px):
    """Fade the left/right edge of a cut-out when the asset is clipped there
    (opaque pixels touch the image border), so it dissolves instead of a hard cut."""
    from PIL import Image, ImageChops, ImageDraw
    a = char.getchannel("A")
    w, h = char.size
    touches_left = sum(1 for y in range(h) if a.getpixel((0, y)) > 8) > h * 0.04
    touches_right = sum(1 for y in range(h) if a.getpixel((w - 1, y)) > 8) > h * 0.04
    if not (touches_left or touches_right):
        return char
    px = max(2, min(px, w // 4))
    mask = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(mask)
    for i in range(px):
        v = int(255 * ((i + 1) / px) ** 1.5)
        if touches_left:
            d.line([(i, 0), (i, h)], fill=v)
        if touches_right:
            d.line([(w - 1 - i, 0), (w - 1 - i, h)], fill=v)
    print(f"  feather clipped edges: left={touches_left} right={touches_right} ({px}px)")
    char = char.copy()
    char.putalpha(ImageChops.multiply(a, mask))
    return char


def build_plan_b_composite(background_path, character_path, dest):
    """Plan B: paste the original RGBA cut-out at a controlled size/position.

    Env: PROMO_CHAR_H (character height / image height, default 0.50),
         PROMO_CHAR_FEET (feet y / image height, default 0.66),
         PROMO_CHAR_X (center x / image width, default 0.50).
    """
    from PIL import Image, ImageDraw, ImageFilter

    char_h = float(os.environ.get("PROMO_CHAR_H", "0.50"))
    feet_y = float(os.environ.get("PROMO_CHAR_FEET", "0.66"))
    center_x = float(os.environ.get("PROMO_CHAR_X", "0.50"))

    bg = Image.open(background_path).convert("RGBA")
    char = Image.open(character_path).convert("RGBA")
    bbox = char.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not bbox:
        cc.fail(f"Character has no opaque pixels: {character_path}")
    char = char.crop(bbox)

    target_h = int(bg.height * char_h)
    target_w = int(char.width * target_h / char.height)
    char = char.resize((target_w, target_h), Image.LANCZOS)

    x = int(bg.width * center_x - target_w / 2)
    y = int(bg.height * feet_y - target_h)

    # soft contact shadow under the feet so the cut-out is grounded
    shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    sw, sh = int(target_w * 0.9), int(target_h * 0.06)
    cx, cy = x + target_w // 2, y + target_h - sh // 4
    draw.ellipse((cx - sw // 2, cy - sh // 2, cx + sw // 2, cy + sh // 2), fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(4, sh // 3)))
    bg = Image.alpha_composite(bg, shadow)
    bg.alpha_composite(char, (x, y))

    dest.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(dest)
    print(f"  plan B composite: char {target_w}x{target_h} at ({x},{y}) "
          f"| height={char_h} feet={feet_y} x={center_x} -> {dest.name}")


def build_plan_b_direct(background_path, character_path, dest):
    """Plan B direct: no Qwen. Cut-out pasted + local integration with Pillow.

    Same env as build_plan_b_composite. Adds a warm rim glow, a slight color
    match, a contact shadow and a smoke/dust cloud that dissolves the feet.
    """
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

    char_h = float(os.environ.get("PROMO_CHAR_H", "0.50"))
    feet_y = float(os.environ.get("PROMO_CHAR_FEET", "0.66"))
    center_x = float(os.environ.get("PROMO_CHAR_X", "0.50"))

    bg = Image.open(background_path).convert("RGBA")
    char = Image.open(character_path).convert("RGBA")
    bbox = char.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not bbox:
        cc.fail(f"Character has no opaque pixels: {character_path}")
    char = char.crop(bbox)
    target_h = int(bg.height * char_h)
    target_w = int(char.width * target_h / char.height)
    char = char.resize((target_w, target_h), Image.LANCZOS)
    char = feather_clipped_edges(char, int(os.environ.get("PROMO_EDGE_FEATHER", "70")))

    # slight color match: a touch warmer and a bit less contrast
    rgb, alpha = char.convert("RGB"), char.getchannel("A")
    r, g, b = rgb.split()
    r = r.point(lambda v: min(255, int(v * 1.03)))
    b = b.point(lambda v: int(v * 0.95))
    rgb = ImageEnhance.Contrast(Image.merge("RGB", (r, g, b))).enhance(0.96)

    # feet dissolve into the dust: fade alpha over the bottom 6%
    fade = int(target_h * 0.06)
    grad = Image.new("L", (target_w, target_h), 255)
    gd = ImageDraw.Draw(grad)
    for i in range(fade):
        gd.line([(0, target_h - fade + i), (target_w, target_h - fade + i)],
                fill=int(255 * (1 - (i + 1) / fade * 0.85)))
    alpha = ImageChops.multiply(alpha, grad)
    char = Image.merge("RGBA", (*rgb.split(), alpha))

    x = int(bg.width * center_x - target_w / 2)
    y = int(bg.height * feet_y - target_h)

    # warm rim glow behind the character
    glow_mask = Image.new("L", bg.size, 0)
    glow_mask.paste(alpha, (x, y))
    glow_mask = glow_mask.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(14))
    glow = Image.new("RGBA", bg.size, (255, 140, 60, 0))
    glow.putalpha(glow_mask.point(lambda v: int(v * 0.38)))
    bg = Image.alpha_composite(bg, glow)

    # contact shadow
    sw, sh = int(target_w * 1.0), int(target_h * 0.07)
    cx, cy = x + target_w // 2, y + target_h - sh // 5
    shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((cx - sw // 2, cy - sh // 2, cx + sw // 2, cy + sh // 2),
                                   fill=(0, 0, 0, 170))
    bg = Image.alpha_composite(bg, shadow.filter(ImageFilter.GaussianBlur(max(5, sh // 3))))

    bg.alpha_composite(char, (x, y))

    # smoke/dust cloud over the feet (drawn after the character)
    dust = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    dw, dh = int(target_w * 1.7), int(target_h * 0.10)
    dd.ellipse((cx - dw // 2, cy - dh // 2, cx + dw // 2, cy + dh // 2), fill=(70, 58, 52, 150))
    dd.ellipse((cx - dw // 3, cy - dh // 3, cx + dw // 3, cy + dh // 3), fill=(210, 110, 50, 70))
    bg = Image.alpha_composite(bg, dust.filter(ImageFilter.GaussianBlur(max(8, dh // 2))))

    dest.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(dest)
    print(f"  plan B direct: char {target_w}x{target_h} at ({x},{y}) -> {dest.name}")


def accent_color(bg):
    """Accent colour of a background: mean of its brightest, most saturated pixels, normalised to a vivid colour.
    A fire map gives orange, a storm gives electric blue... PROMO_ACCENT="R,G,B" overrides."""
    import numpy as np
    env = os.environ.get("PROMO_ACCENT")
    if env:
        try:
            r, g, b = [int(v) for v in env.split(",")]
            return (r, g, b)
        except ValueError:
            pass
    a = np.asarray(bg.convert("RGB").resize((96, 54))).astype(float)
    mx, mn = a.max(axis=2), a.min(axis=2)
    score = mx * (0.35 + (mx - mn) / np.maximum(mx, 1))      # bright AND colourful
    idx = np.argsort(score.ravel())[-max(8, score.size // 25):]
    c = a.reshape(-1, 3)[idx].mean(axis=0)
    c = c * (255.0 / max(c.max(), 1))
    return tuple(int(v) for v in c)


def build_plan_b_bust(background_path, character_path, dest):
    """Plan B bust: large half-body character fading into the smoke (no legs).

    Env: PROMO_BUST_CROP (fraction of the character kept from the top, 0.58),
         PROMO_BUST_H (bust height / image height, 0.52),
         PROMO_BUST_TOP (top of the head / image height, 0.10),
         PROMO_CHAR_X (center x / image width, 0.50).
    Adds: soft backlight, thin warm rim, ember sparks, smoke fade at the cut,
    dark bottom gradient (keeps the title readable).
    """
    import random
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

    keep = float(os.environ.get("PROMO_BUST_CROP", "0.58"))
    bust_h = float(os.environ.get("PROMO_BUST_H", "0.52"))
    top_y = float(os.environ.get("PROMO_BUST_TOP", "0.10"))
    center_x = float(os.environ.get("PROMO_CHAR_X", "0.50"))

    bg = Image.open(background_path).convert("RGBA")
    W, H = bg.size
    acc = accent_color(bg)
    print(f"  plan B accent colour: {acc}")
    char = Image.open(character_path).convert("RGBA")
    bbox = char.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not bbox:
        cc.fail(f"Character has no opaque pixels: {character_path}")
    char = char.crop(bbox)
    char = char.crop((0, 0, char.width, int(char.height * keep)))

    th = int(H * bust_h)
    tw = int(char.width * th / char.height)
    char = char.resize((tw, th), Image.LANCZOS)
    char = feather_clipped_edges(char, int(os.environ.get("PROMO_EDGE_FEATHER", "70")))

    rgb, alpha = char.convert("RGB"), char.getchannel("A")
    r, g, b = rgb.split()
    r = r.point(lambda v: min(255, int(v * 1.03)))
    b = b.point(lambda v: int(v * 0.95))
    rgb = ImageEnhance.Contrast(Image.merge("RGB", (r, g, b))).enhance(0.97)

    # fade the cut edge into the smoke (smooth ease over the bottom 24%)
    fade = int(th * 0.24)
    grad = Image.new("L", (tw, th), 255)
    gd = ImageDraw.Draw(grad)
    for i in range(fade):
        t = (i + 1) / fade
        gd.line([(0, th - fade + i), (tw, th - fade + i)], fill=int(255 * (1 - t * t)))
    alpha = ImageChops.multiply(alpha, grad)
    char = Image.merge("RGBA", (*rgb.split(), alpha))

    x = int(W * center_x - tw / 2)
    y = int(H * top_y)

    # large soft backlight behind the torso (fire glow), then a thin rim
    back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    cx, cy = x + tw // 2, y + int(th * 0.45)
    bd.ellipse((cx - int(tw * 0.9), cy - int(th * 0.6), cx + int(tw * 0.9), cy + int(th * 0.6)),
               fill=acc + (85,))
    bg = Image.alpha_composite(bg, back.filter(ImageFilter.GaussianBlur(110)))

    rim_mask = Image.new("L", (W, H), 0)
    rim_mask.paste(alpha, (x, y))
    rim_mask = rim_mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8))
    rim = Image.new("RGBA", (W, H), tuple(min(255, int(v * 0.6 + 100)) for v in acc) + (0,))
    rim.putalpha(rim_mask.point(lambda v: int(v * 0.22)))
    bg = Image.alpha_composite(bg, rim)

    bg.alpha_composite(char, (x, y))

    # smoke bank at the cut line
    dust = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    ey = y + th - int(th * 0.04)
    dd.ellipse((cx - int(tw * 1.1), ey - 70, cx + int(tw * 1.1), ey + 90), fill=(60, 50, 46, 170))
    dd.ellipse((cx - int(tw * 0.6), ey - 40, cx + int(tw * 0.6), ey + 50), fill=acc + (70,))
    bg = Image.alpha_composite(bg, dust.filter(ImageFilter.GaussianBlur(45)))

    # ember sparks drifting up around the character
    rnd = random.Random(7)
    sparks = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sparks)
    for _ in range(70):
        px = rnd.randint(int(W * 0.15), int(W * 0.85))
        py = rnd.randint(int(H * 0.12), int(H * 0.70))
        rad = rnd.choice((2, 2, 3, 3, 4, 5))
        sd.ellipse((px - rad, py - rad, px + rad, py + rad),
                   fill=tuple(int(v + (255 - v) * rnd.uniform(0.0, 0.55)) for v in acc) + (rnd.randint(150, 255),))
    bg = Image.alpha_composite(bg, sparks.filter(ImageFilter.GaussianBlur(1.2)))

    # dark gradient over the bottom 40% (title readability, hides the floor)
    shade = Image.new("L", (W, H), 0)
    sd2 = ImageDraw.Draw(shade)
    start = int(H * 0.60)
    for yy in range(start, H):
        t = (yy - start) / (H - start)
        sd2.line([(0, yy), (W, yy)], fill=int(150 * t))
    black = Image.new("RGBA", (W, H), (8, 8, 12, 0))
    black.putalpha(shade)
    bg = Image.alpha_composite(bg, black)

    dest.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(dest)
    print(f"  plan B bust: {tw}x{th} at ({x},{y}) keep={keep} -> {dest.name}")


def artifact_score(art_path, bg_path):
    """(changed fraction in the right 58%, changed fraction in its top 30%) vs the source environment."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = Image.open(art_path).convert("RGB")
    b = Image.open(bg_path).convert("RGB").resize(a.size, Image.LANCZOS)
    A = np.asarray(a.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    B = np.asarray(b.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    d = np.abs(A - B).max(axis=2)
    x0 = int(a.size[0] * 0.42)
    return float((d[:, x0:] > 60).mean()), float((d[: int(a.size[1] * 0.30), x0:] > 60).mean())


def extra_objects(art_path, bg_path, scale=8, grow=3, thr=60):
    """Find things Qwen added next to the character. The pixels that differ from the source environment form
    ONE blob (the character). Any other blob is an invented creature/object.
    Returns (area of the biggest extra blob as a fraction of the image, x-centre 0..1 of the main blob)."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = Image.open(art_path).convert("RGB")
    b = Image.open(bg_path).convert("RGB").resize(a.size, Image.LANCZOS)
    A = np.asarray(a.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    B = np.asarray(b.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    m = np.abs(A - B).max(axis=2) > thr
    h, w = m.shape
    small = Image.fromarray((m * 255).astype("uint8")).resize((w // scale, h // scale), Image.BILINEAR)
    g = np.asarray(small.filter(ImageFilter.MaxFilter(2 * grow + 1))) > 100
    H, W = g.shape
    seen = np.zeros(g.shape, bool)
    blobs = []  # (area fraction, x-centre)
    for y0 in range(H):
        for x0 in range(W):
            if g[y0, x0] and not seen[y0, x0]:
                stack, n, xs = [(y0, x0)], 0, []
                seen[y0, x0] = True
                while stack:
                    y, x = stack.pop()
                    n += 1
                    xs.append(x)
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        y2, x2 = y + dy, x + dx
                        if 0 <= y2 < H and 0 <= x2 < W and g[y2, x2] and not seen[y2, x2]:
                            seen[y2, x2] = True
                            stack.append((y2, x2))
                blobs.append((n / (H * W), (min(xs) + max(xs)) / 2 / W))
    blobs.sort(reverse=True)
    if not blobs:
        return 0.0, 0.5
    return (blobs[1][0] if len(blobs) > 1 else 0.0), blobs[0][1]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("horizontal", "vertical", "clean", "untitle"):
        cc.fail("usage: qwen_run.py horizontal|vertical|clean|untitle")

    project = pp.project_dir()
    bg_dir = project / "background"
    pp.normalize_background(bg_dir / "background.png")
    final_dir = project / "final"
    character = project / "characters" / "character_01.png"
    print(f"=== Qwen {mode} | map: {pp.project_name()} ===")

    if mode == "horizontal":
        clean = bg_dir / "background_clean.png"
        background = clean if clean.exists() else bg_dir / "background.png"
        prompt = (project / "qwen_prompt_final.txt")
        if not prompt.exists():
            cc.fail(f"Missing {prompt} (run qwen_prompt_builder.py first)")
        prompt_text = prompt.read_text(encoding="utf-8")
        output = final_dir / "artwork.png"
        runs, label, prefix = final_dir / "_runs", "artwork", "Qwen_Horizontal"
        needs_character = True
    elif mode == "vertical" and os.environ.get("PROMO_PLAN_B") in ("direct", "bust"):
        # Plan B direct: no ComfyUI at all, the 1440x1920 composite is the artwork.
        src_bg = bg_dir / "background_vertical.png"
        if not src_bg.exists() or not character.exists():
            cc.fail("Plan B needs background_vertical.png and characters/character_01.png")
        output = final_dir / "artwork_vertical.png"
        if os.environ.get("PROMO_PLAN_B") == "bust":
            build_plan_b_bust(src_bg, character, output)
        else:
            build_plan_b_direct(src_bg, character, output)
        print("QWEN VERTICAL SUCCESS (plan B direct, no Qwen)")
        return
    elif mode == "vertical" and os.environ.get("PROMO_PLAN_B") == "1":
        # Plan B: character pasted by script, Qwen only harmonizes the whole image.
        background = bg_dir / "vertical_composite.png"
        if not (bg_dir / "background_vertical.png").exists() or not character.exists():
            cc.fail("Plan B needs background_vertical.png and characters/character_01.png")
        build_plan_b_composite(bg_dir / "background_vertical.png", character, background)
        prompt_text = pp.load_prompt("qwen_prompt_vertical_harmonize.txt")
        output = final_dir / "artwork_vertical.png"
        runs, label, prefix = final_dir / "_runs", "artwork_vertical", "Qwen_Vertical_PlanB"
        needs_character = False
    elif mode == "vertical":
        background = bg_dir / "background_vertical.png"
        prompt_text = pp.load_prompt("qwen_prompt_vertical.txt")
        output = final_dir / "artwork_vertical.png"
        runs, label, prefix = final_dir / "_runs", "artwork_vertical", "Qwen_Vertical_OneCharacter"
        needs_character = True
    elif mode == "untitle":
        background = final_dir / "thumbnail_horizontal_title.png"
        prompt_text = pp.load_prompt("qwen_prompt_untitle.txt")
        output = final_dir / "_untitle_raw.png"
        runs, label, prefix = final_dir / "_runs", "untitle", "Qwen_Untitle"
        needs_character = False
    else:
        background = bg_dir / "background.png"
        prompt_text = pp.load_prompt("qwen_prompt_clean_background.txt")
        output = bg_dir / "background_clean.png"
        runs, label, prefix = bg_dir / "_runs", "background_clean", "Qwen_BackgroundClean"
        needs_character = False

    negative = pp.load_prompt(f"qwen_negative_{ {'clean': 'clean_background'}.get(mode, mode) }.txt")
    workflow_file = pp.workflow_path()

    needed = [workflow_file, background] + ([character] if needs_character else [])
    for f in needed:
        if not Path(f).exists():
            cc.fail(f"Missing input: {f}")

    print(f"  background: {background.name}")
    cc.check_server()
    wf = json.loads(Path(workflow_file).read_text(encoding="utf-8"))
    for n in (BACKGROUND_NODE, CHARACTER_NODE, POSITIVE_NODE, NEGATIVE_NODE, SAVE_NODE):
        if n not in wf:
            cc.fail(f"Workflow node {n} not found")

    wf[BACKGROUND_NODE]["inputs"]["image"] = cc.upload_image(background, f"promo_{mode}_bg")
    if needs_character:
        wf[CHARACTER_NODE]["inputs"]["image"] = cc.upload_image(character, f"promo_{mode}_char")
    for n in (POSITIVE_NODE, NEGATIVE_NODE):
        wf[n]["inputs"].pop("image3", None)  # one character at most
        if not needs_character:
            wf[n]["inputs"].pop("image2", None)  # environment only
    wf[POSITIVE_NODE]["inputs"]["prompt"] = prompt_text
    wf[NEGATIVE_NODE]["inputs"]["prompt"] = negative
    wf[SAVE_NODE]["inputs"]["filename_prefix"] = prefix
    if cc.DEBUG:
        print(prompt_text)

    # Quality gate (horizontal only): Qwen sometimes paints gibberish text/logos into the scene even though the
    # prompt forbids it. The right part of the picture must stay close to the source environment, so a large
    # difference there means a hallucination: retry with a new seed (PROMO_QC=0 disables, PROMO_QC_TRIES=3).
    tries = 1
    if mode == "horizontal" and os.environ.get("PROMO_QC", "1") != "0":
        tries = max(1, int(os.environ.get("PROMO_QC_TRIES", "3")))
    best = None  # (score, bytes)
    for attempt in range(1, tries + 1):
        cc.randomize_seed(wf)
        hist = cc.submit_and_wait(wf)
        cc.download_output(hist, output, runs, label)
        if tries == 1:
            break
        frac, top = artifact_score(output, background)
        print(f"  quality check {attempt}/{tries}: changed area {frac:.3f}, top band {top:.3f} (limit 0.030 / 0.020)")
        extra, cx = extra_objects(output, background)
        print(f"  quality check {attempt}/{tries}: extra objects {extra:.3f} (limit 0.008), character centre {cx:.2f} (limit 0.40)")
        score = max(frac / 0.03, top / 0.02, extra / 0.008, (1.01 if cx > 0.40 else 0.0))
        if best is None or score < best[0]:
            best = (score, output.read_bytes())
        if score <= 1.0:
            break
        print("  -> painted text, an invented creature/object or a wrong position: trying a new seed")
    else:
        output.write_bytes(best[1])
        print("WARNING: every attempt failed the quality check; kept the best one. LOOK AT IT before uploading.")
    print(f"QWEN {mode.upper()} SUCCESS")


if __name__ == "__main__":
    main()
