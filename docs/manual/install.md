# Install

There are three setups. Pick one, run `doctor.bat`, and fix what it reports.

| Setup | You need | You get |
|---|---|---|
| Full | Windows, NVIDIA GPU with about 12 GB of video memory, about 55 GB of disk, ComfyUI and the models | Everything, including AI artwork, AI music and A/B variants |
| Light | Any Windows PC, Python, ffmpeg | Everything except AI artwork and AI music (you bring the landscape art, the music is synthesised) |
| Remote ComfyUI | Light plus a ComfyUI on another PC (set `COMFY_URL`) | The full result on a weak PC |

## Steps

1. Get the kit: download the latest release zip from the GitHub page, or `git clone` the repository, and unpack it next to your maps.
2. Install ffmpeg: `winget install Gyan.FFmpeg`, then open a new terminal.
3. For the Full setup, run `download_models.bat` (about 45 GB, once) and start ComfyUI with `start_comfyui.bat`.
4. Run `doctor.bat`. Add `--profile light` if you chose the Light setup.

> **Note** ComfyUI and the models are not part of the repository. They only add the AI horizontal artwork and the AI music.

## Fonts, badges and skins

The kit ships an open font. Put your own title font in `Resources\brand\font\`. The age-rating (ESRB) and "Developed in Fortnite" badges go in `Resources\badges\`. Both folders have a README that says what is expected.
