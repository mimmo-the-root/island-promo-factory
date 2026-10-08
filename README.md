# Island Promo Factory

**Epic-Discover-ready thumbnails, logo, promo pack and trailer for your UEFN islands — one map at a time, from one command.**

You give it an environment screenshot and a character render. It gives you the files the Creator Portal asks for,
already at the right size, inside the safe areas, validated, and named like the portal fields.

| Output | Spec |
|---|---|
| Landscape thumbnail (with title) | 1920x1080 PNG, < 5 MB |
| Landscape art only | 1920x1080 PNG, < 5 MB |
| Portrait thumbnail (with title / art only) | 1440x1920 PNG, < 5 MB |
| Island logo | 1440x608 transparent PNG, < 3 MB |
| Lobby background | 2048x1024 PNG, < 10 MB |
| Trailer v1 | 1920x1080 MP4, 10-40 s, < 400 MB, PEGI + "Developed in Fortnite" badges |

> Specs reflect the Fortnite Creator Portal in October 2026. Epic changes them: always check the portal.
> Details: [docs/SPECS.md](docs/SPECS.md).

## How it works

```
 environment.png + character.png
        |
        v
  [Qwen Image Edit via ComfyUI]  -> horizontal art (one character, no text)
  [deterministic composite]      -> vertical half-body art (no AI, full control)
        |
        v
  title + logo (your font)  ->  thumbnails  ->  validator  ->  promo_pack/
        |
        v
  trailer_builder (ffmpeg) -> trailer.mp4  ->  video_validate
```

- **AI makes art only.** Titles and logos are rendered with a real font, so text is always crisp and correct.
- **Every stage is checked.** A stage must exit 0 *and* create its file, otherwise the run stops with a clear message.
- **Nothing is deleted.** Old results move to `final/_previous/<timestamp>/`.
- **One map at a time.** Review, upload, learn, then the next map.

## Requirements

**Step-by-step install, with every download link and folder: [docs/INSTALL.md](docs/INSTALL.md). `doctor.bat` checks it for you.**

- Windows 10/11 (the `.bat` helpers; the Python scripts are cross-platform), Python 3.10+ with `pip install pillow`.
- For the AI horizontal art: [ComfyUI](https://github.com/comfyanonymous/ComfyUI) running on `127.0.0.1:8188` with the
  Qwen Image Edit 2511 models named in `workflows/qwen_workflow_api.json`; an NVIDIA GPU with about 12 GB VRAM works.
- For video: [ffmpeg](https://ffmpeg.org/) (`winget install Gyan.FFmpeg`).
- Optional: an upscale model (e.g. RealESRGAN_x4plus.pth in ComfyUI `models/upscale_models`).

Without ComfyUI you can still run `--no-qwen`: the vertical art, title, logo, thumbnails, validator, promo pack and trailer
all work with your own horizontal art.

## Quick start

**First time: double-click `doctor.bat` (checks your install and tells you what is missing), then `demo.bat` (builds a complete demo kit in two minutes, no GPU needed).**
Then make your own map:

```bat
git clone https://github.com/mimmo-the-root/island-promo-factory
cd island-promo-factory
pip install pillow

new_map.bat my-map "MY MAP TITLE" --style SCI_FI
:: put your files in Projects\my-map\
::   background\background.png     the environment, no characters, >= 1920 px wide
::   characters\character_01.png   ONE character, transparent PNG with margin on all sides
:: edit Projects\my-map\config.json  (title, style, character identity)

run_factory.bat my-map         :: horizontal art (needs ComfyUI), title, logo, thumbnails, validation, promo pack
run_vertical.bat my-map        :: vertical half-body art + promo pack in seconds (no GPU)
run_trailer.bat my-map         :: trailer.mp4 (needs ffmpeg)
```

Results: `Projects\my-map\final\` and the portal-ready `Projects\my-map\promo_pack\` (the `Projects` folder sits next to this repo, see docs/INSTALL.md).
If ComfyUI is installed next to this folder (`..\ComfyUI_windows_portable\`) the `.bat` files use its embedded Python automatically (see docs/INSTALL.md).
`scripts\cleanup.py --project my-map [--keep 3] [--apply]` moves old archived runs out of the way when a map folder grows.

## Your brand, your files (not included)

- **Font:** drop a `.otf`/`.ttf` in `Resources/brand/font/`. Without one, an open-licensed fallback font is used.
  Fortnite's Burbank is *not* distributed here.
- **Badges:** `Resources/badges/pegi.png` and `developed_in_fortnite.png` (video only). Get the official files from their owners.
- **Music:** optional `Projects/<map>/audio/music.mp3`. Use only music you are licensed to use.
- **Gameplay video and screenshots** for the portal must be real captures; the tool only *validates* them
  (`python scripts/video_validate.py clip.mp4 --kind gameplay`) and never edits them.

## Using it with Claude Code

`CLAUDE.md` describes the commands, folders and rules so an AI coding agent can run the whole loop for you:
create the map, run the stages, read `last_run.log`, review the images and write a report.

## Tuning

Environment variables (see [docs/USAGE.md](docs/USAGE.md)): `PROMO_PROJECT`, `PROMO_SEED`, `PROMO_DEBUG=1`,
`PROMO_TITLE_CX`, `PROMO_VTITLE_W`, `PROMO_VTITLE_CY`, `PROMO_BUST_CROP`, `PROMO_BUST_H`, `PROMO_BUST_TOP`,
`PROMO_CHAR_X`, `PROMO_TRAILER_SECONDS`, `PROMO_BADGE_MODE`, `COMFY_URL`.

## Tests

`python tests/smoke_test.py` builds a synthetic map end-to-end with a mock ComfyUI server: no GPU, no game assets.

## Limits you should know

- Qwen does not obey numeric positions, so the vertical art is composed by script, not by the model.
- A clipped character render shows hard edges (they are feathered, but give it margin).
- The trailer is built from stills (Ken Burns, embers, end card); it is not AI video.
- Unofficial tool, not affiliated with Epic Games. See [DISCLAIMER.md](DISCLAIMER.md) and [NOTICE.md](NOTICE.md). Security: [SECURITY.md](.github/SECURITY.md).

## Versions and updates
The console shows the installed version and tells you when a newer release exists; `update.bat` installs it without touching your maps or brand files. See [docs/UPDATING.md](docs/UPDATING.md) and [CHANGELOG.md](CHANGELOG.md).

## License

MIT for the code (see [LICENSE](LICENSE)). Models, fonts, badges and game content have their own licences.
