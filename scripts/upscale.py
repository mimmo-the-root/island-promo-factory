"""Optional AI upscale of the raw Qwen artworks (ComfyUI core nodes, no custom nodes).

final/artwork.png          -> final/artwork_up.png          (2x size)
final/artwork_vertical.png -> final/artwork_vertical_up.png (2x size)
Pipeline: UpscaleModelLoader -> ImageUpscaleWithModel (4x) -> ImageScale lanczos to 2x
-> thumbnail_factory then downsizes to the Epic sizes (sharper than LANCZOS from ~1 MP).

If no upscale model is installed this stage SKIPS (exit 0) and thumbnail_factory keeps
using the raw artwork + unsharp mask. Install a model in ComfyUI/models/upscale_models
(recommended: RealESRGAN_x4plus.pth, BSD-3 licence). Avoid models with non-commercial licences.
Env: PROMO_UPSCALE_MODEL (exact file name), COMFY_URL, PROMO_PROJECT, PROMO_DEBUG=1
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comfy_common as cc  # noqa: E402
import promo_project as pp  # noqa: E402
from PIL import Image  # noqa: E402

PREFERRED = ("RealESRGAN_x4plus", "4x-UltraSharp", "4x_foolhardy", "x4")  # order of preference


def available_models():
    info = cc.get_json(f"{cc.COMFY_URL}/object_info/UpscaleModelLoader")
    spec = info["UpscaleModelLoader"]["input"]["required"]["model_name"]
    # old ComfyUI: [[names...]]; new ComfyUI: ["COMBO", {"options": [names...]}]
    if isinstance(spec[0], list):
        return spec[0]
    if len(spec) > 1 and isinstance(spec[1], dict):
        return list(spec[1].get("options", []))
    return []


def pick_model(models):
    wanted = os.environ.get("PROMO_UPSCALE_MODEL")
    if wanted:
        return wanted if wanted in models else None
    for key in PREFERRED:
        for m in models:
            if key.lower() in m.lower():
                return m
    return models[0] if models else None


def build_workflow(image_name, model, width, height):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "ImageScale", "inputs": {"image": ["3", 0], "upscale_method": "lanczos",
                                                     "width": width, "height": height, "crop": "disabled"}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": "PromoUpscale"}},
    }


def main():
    final = pp.project_dir() / "final"
    print(f"=== Upscale | map: {pp.project_name()} ===")
    cc.check_server()

    try:
        models = available_models()
    except Exception as e:
        print(f"Could not list upscale models ({e}): SKIPPED (raw artwork + unsharp will be used).")
        return
    model = pick_model(models)
    if not model:
        print("No upscale model installed in ComfyUI\\models\\upscale_models: SKIPPED.")
        print("Install RealESRGAN_x4plus.pth there to enable AI upscaling.")
        return
    print(f"  model: {model}")

    for src_name, dst_name in (("artwork.png", "artwork_up.png"),
                               ("artwork_vertical.png", "artwork_vertical_up.png")):
        src = final / src_name
        if not src.exists():
            cc.fail(f"Missing {src}")
        with Image.open(src) as im:
            w, h = im.size
        name = cc.upload_image(src, "promo_upscale")
        wf = build_workflow(name, model, w * 2, h * 2)
        hist = cc.submit_and_wait(wf, timeout=1800)
        cc.download_output(hist, final / dst_name, final / "_runs", dst_name.replace(".png", ""))
    print("UPSCALE SUCCESS")


if __name__ == "__main__":
    main()
