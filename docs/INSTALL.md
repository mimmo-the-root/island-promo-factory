# Installation guide

Pick your setup first, then follow only the steps marked for it. You do this once.

| Setup | For whom | Steps | Time |
|---|---|---|---|
| **Full** | Windows PC with an NVIDIA GPU (about 12 GB VRAM), ~40 GB free disk | 1, 2, 3, 4, 5, 6 | 30-60 min, mostly downloads |
| **Light** | any Windows PC, no GPU or little disk | 1, 2, 5, 6 | 10 min |
| **Remote ComfyUI** | weak PC + a ComfyUI running on another PC or in the cloud | 1, 2, 5, 6 and set `COMFY_URL` (see step 4) | 10 min |

**Important: ComfyUI and the AI models are NOT part of this kit.** You download them yourself (step 3-4), they live in their own folder and
are used for one thing only: the AI-generated horizontal artwork. If you skip them (Light), everything else works.
Claude Code (step 7) is optional in every setup.

## 1. Install the basics (all setups)
| What | Where to get it | Notes |
|---|---|---|
| ffmpeg + ffprobe | in a terminal: `winget install Gyan.FFmpeg`, then open a NEW terminal | video tools (gameplay, trailer, screenshots). Or put `ffmpeg.exe` and `ffprobe.exe` in `Resources\bin\` |
| Python 3.10+ with Pillow | https://www.python.org/downloads/ (tick "Add Python to PATH"), then `pip install pillow numpy` | **Full setup: skip this.** ComfyUI brings its own Python with everything the kit needs, and the kit uses it automatically |
| Git (optional) | https://git-scm.com/downloads | or download the ZIP from the Releases page |

## 2. Get Island Promo Factory (all setups)
Pick a root folder for everything, for example `C:\IslandPromoFactory`. Inside it:

```
C:\IslandPromoFactory\
  ComfyUI_windows_portable\      <-- ComfyUI (third-party), step 3. Not needed for Light
  Projects\                      <-- YOUR work: one folder per map, never touched by updates
    <your-map>\
  island-promo-factory\          <-- this project: git clone, or the unzipped release (code only)
    scripts\  workflows\  Resources\  docs\  tests\  .claude\
```
Get it with `git clone https://github.com/mimmo-the-root/island-promo-factory` (run inside `C:\IslandPromoFactory`), or download the latest ZIP from
**Releases** and unzip it as `island-promo-factory`. The helper `.bat` files find ComfyUI's Python by themselves.
Maps live in `..\Projects` next to the repo (`PROMO_PROJECTS_DIR` points anywhere else, e.g. another disk).

## 3. Install ComfyUI (Full only)
1. Open https://www.comfy.org/download and download **ComfyUI for Windows (portable)**. (The same build is on https://github.com/comfyanonymous/ComfyUI/releases as `ComfyUI_windows_portable_nvidia.7z`.)
2. Extract it with 7-Zip (https://www.7-zip.org/) so you get `C:\IslandPromoFactory\ComfyUI_windows_portable\` containing `run_nvidia_gpu.bat`.
   Do not extract it inside `island-promo-factory`.
3. Update it once: run `ComfyUI_windows_portable\update\update_comfyui.bat` (the int8 model needs a recent ComfyUI).
4. Start it: run `start_comfyui.bat` from this kit (or ComfyUI's own `run_nvidia_gpu.bat`). A black window opens; keep it open. Open http://127.0.0.1:8188 in your browser: if you see the ComfyUI canvas, it works.
   You do **not** need to install anything else for ComfyUI: no extra Python, no extra nodes.

## 4. Download the models (Full only)
Put each file in the folder shown, inside `C:\IslandPromoFactory\ComfyUI_windows_portable\ComfyUI\models\`. Use the file names exactly as written (`workflows/qwen_workflow_api.json` refers to them).
On a Hugging Face page click the **download** arrow next to the file name; wait for it to finish (these files are several GB each, about 30 GB in total).

| File | Put it in | Download page |
|---|---|---|
| `qwen_image_edit_2511_int8_convrot.safetensors` | `diffusion_models\` | https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/blob/main/split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `text_encoders\` | https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/blob/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors |
| `qwen_image_vae.safetensors` | `vae\` | https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/blob/main/split_files/vae/qwen_image_vae.safetensors |
| `RealESRGAN_x4plus.pth` *(optional upscaler)* | `upscale_models\` | https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth |
| `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` *(optional, faster)* | `loras\` | https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/blob/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors |

Restart ComfyUI after copying the files. Check each model's licence on its page. The official tutorial for these models: https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511

**Remote ComfyUI:** install ComfyUI and the same models on the other machine, start it with `--listen`, and on your PC set the environment variable `COMFY_URL` (for example `http://192.168.1.50:8188`). Only do this on a network you trust: ComfyUI has no password.

## 5. Your own brand files (optional but recommended, all setups)
| File | Folder (inside `island-promo-factory`) | Why |
|---|---|---|
| a `.otf`/`.ttf` title font | `Resources\brand\font\` | titles and logo. Without it the bundled open font is used |
| `rating.png` (or `esrb_teen.png`) | `Resources\badges\` (per map: `Projects\<map>\badges\`) | age-rating badge of the map (ESRB), trailer only |
| `developed_in_fortnite.png` | `Resources\badges\` | "Developed in Fortnite" badge, trailer only |
| `music.mp3` (licensed, optional) | `Projects\<map>\audio\` | soundtrack. Without it an original track is generated for you |

## 6. Check that everything works
1. Double-click **`doctor.bat`** (Light: `doctor.bat --profile light`). It lists what is ready (OK), what is optional and missing (WARN) and what blocks you (FAIL), with the exact fix for each line. Run it again after every fix until it says READY.
2. Double-click **`demo.bat`**. It draws an original demo map (`NEON SENTINEL`, no AI, no game assets) and runs the whole kit on it in about two minutes: thumbnails, logo, promo pack, a trailer and the "Kit Lightbox" preview board.
   The live console opens in your browser; when it says COMPLETE open `Projects\demo\promo_pack\`. No GPU or ComfyUI needed.
3. Your own map: `new_map.bat my-first-map "MY TITLE"`, add the images (see the README), then `run_all.bat my-first-map` (Light or no ComfyUI running: add `--no-qwen`).
   Light setup: put your own horizontal art in `Projects\<map>\final\artwork.png` and run `python scripts\factory.py --project <map> --no-qwen`.

If a stage fails, open `last_run.log` (images) or `last_run_all.log` (full run).

## 7. Claude Code (optional, all setups)
Open the `island-promo-factory` folder in Claude Code and type `/promo-pack`. Claude asks for the island code, the title and your files, starts ComfyUI and the live console, runs every stage and reviews the results.
The skills and commands are already in the folder (`.claude/`). Without Claude, steps 1-6 and the `.bat` files are all you need.

## Folder map after installing
```
C:\IslandPromoFactory\                 (your root folder, any name)
  ComfyUI_windows_portable\            ComfyUI (third-party, Full only)
  Projects\<map>\                      input, background, characters, captures, final, promo_pack  (your work)
  island-promo-factory\
    Resources\brand\font\              your font
    Resources\badges\                  your badges
    Resources\bin\                     optional ffmpeg.exe / ffprobe.exe
    doctor.bat  demo.bat  dashboard.bat  run_all.bat  new_map.bat  update.bat  start_comfyui.bat
```
