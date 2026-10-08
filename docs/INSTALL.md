# Installation guide

Time needed: about 30-60 minutes, most of it downloading models. You only do this once.

## 0. What you need
- Windows 10/11, an NVIDIA GPU (about 12 GB VRAM is enough with the int8 model below) and ~40 GB of free disk.
- Without a GPU/ComfyUI you can still use everything except the AI horizontal art (see "Light install").

## 1. Install the basics
| What | Where to get it | Notes |
|---|---|---|
| Python 3.10+ | https://www.python.org/downloads/ | tick "Add Python to PATH". Not needed if you use ComfyUI's embedded Python |
| Pillow | `pip install pillow` | image composition. numpy is installed with ComfyUI; otherwise `pip install numpy` |
| ffmpeg + ffprobe | `winget install Gyan.FFmpeg` (then open a NEW terminal) | video tools. Or put `ffmpeg.exe`/`ffprobe.exe` in `Resources\bin\` |
| Git (optional) | https://git-scm.com/downloads | or download the ZIP from the Releases page |

## 2. Get Island Promo Factory
Pick a root folder for everything, for example `C:\IslandPromoFactory`. Inside it:

```
C:\IslandPromoFactory\
  ComfyUI_windows_portable\      <-- ComfyUI (third-party), installed in step 3
  Projects\                      <-- YOUR work: one folder per map (made by new_map.bat), never touched by updates
    <your-map>\
  island-promo-factory\        <-- this project: git clone, or the unzipped release (code only)
    scripts\  workflows\  Resources\  docs\  tests\
    dashboard.bat  run_all.bat  run_factory.bat  run_trailer.bat  new_map.bat  update.bat  start_comfyui.bat
```
Get it with `git clone https://github.com/mimmo-the-root/island-promo-factory` (run inside `C:\IslandPromoFactory`) or download the latest ZIP
from **Releases** and unzip it as `island-promo-factory`. The `.bat` files find ComfyUI's embedded Python by themselves. If ComfyUI lives
somewhere else nothing breaks: the scripts then use the `python` on your PATH (or set `PROMO_PYTHON`), and ComfyUI is reached through
http://127.0.0.1:8188 wherever it runs. Maps live in `..\Projects` next to the repo (or `Projects\` inside it if there is no sibling; `PROMO_PROJECTS_DIR` points anywhere, e.g. another disk).

## 3. Install ComfyUI (for the AI horizontal art)
Download the portable build from https://www.comfy.org/download (or https://github.com/comfyanonymous/ComfyUI) and keep it **up to date**
(the int8 model needs a recent version). Start it once (`start_comfyui.bat`, or its own `run_nvidia_gpu.bat`) to check that it opens on http://127.0.0.1:8188.

## 4. Download the models and put them in the right folders
All paths are relative to `ComfyUI_windows_portable\ComfyUI\models\`.

| File | Folder | Download |
|---|---|---|
| `qwen_image_edit_2511_int8_convrot.safetensors` | `diffusion_models\` | https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `text_encoders\` | https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/blob/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors |
| `qwen_image_vae.safetensors` | `vae\` | https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/blob/main/split_files/vae/qwen_image_vae.safetensors |
| `RealESRGAN_x4plus.pth` *(optional upscaler)* | `upscale_models\` | https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth |
| `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` *(optional, faster)* | `loras\` | https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/blob/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors |

Use the file names exactly as shown: `workflows/qwen_workflow_api.json` refers to them. Check each model's licence on its page.
The official ComfyUI tutorial for these models: https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511

## 5. Your own brand files (optional but recommended)
| File | Folder | Why |
|---|---|---|
| a `.otf`/`.ttf` title font | `Resources\brand\font\` | titles and logo. Without it the bundled open font is used |
| `pegi.png` | `Resources\badges\` | PEGI badge, trailer only |
| `developed_in_fortnite.png` | `Resources\badges\` | "Developed in Fortnite" badge, trailer only |
| `music.mp3` (licensed, optional) | `Projects\<map>\audio\` | trailer soundtrack. Without it an original track is generated for you |

## 6. Check that everything works
1. Double-click **`doctor.bat`**. It lists what is ready (OK), what is optional and missing (WARN) and what blocks you (FAIL), with the exact fix for each line.
   Run it again after every fix until it says READY.
2. Double-click **`demo.bat`**. It draws an original demo map (`NEON SENTINEL`, no AI, no game assets) and runs the whole kit on it in about two minutes:
   thumbnails, logo, promo pack, a trailer and the "Kit Lightbox" preview board. A live console opens in your browser; when it says COMPLETE open
   `Projects\demo\promo_pack\`. No GPU or ComfyUI needed.
3. Optional developer check: `python tests\smoke_test.py` (builds a synthetic map with a mock ComfyUI, about one minute).
4. Your own map: `new_map.bat my-first-map "MY TITLE"`, add the two images (see the README Quick start), then `run_all.bat my-first-map`.
   With ComfyUI running (`start_comfyui.bat`) you get the AI horizontal art; without it add `--no-qwen`.

If a stage fails, open `last_run.log` (images) or `last_run_all.log` (full run).

## Light install (no ComfyUI, no GPU)
Skip steps 3-4. Use `python scripts\factory.py --project <map> --no-qwen` with your own horizontal art in
`Projects\<map>\final\artwork.png`; vertical art, title, logo, thumbnails, promo pack and trailer all work.

## Folder map after installing
```
C:\PromoFactory\                       (your root folder, any name)
  ComfyUI_windows_portable\            ComfyUI (third-party)
  Projects\<map>\                      input, background, characters, captures, final, promo_pack  (your work)
  island-promo-factory\
    Resources\brand\font\             your font
    Resources\badges\                  your badges
    Resources\bin\                     optional ffmpeg.exe / ffprobe.exe
    doctor.bat  demo.bat  dashboard.bat  run_all.bat  new_map.bat  update.bat  start_comfyui.bat
```
