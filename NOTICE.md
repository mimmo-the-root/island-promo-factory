# Notices and third-party material

**Unofficial tool.** Island Promo Factory is an independent, community project. It is not
affiliated with, endorsed by or sponsored by Epic Games, Inc. "Fortnite", "Unreal Editor for
Fortnite (UEFN)" and "Epic Games" are trademarks of Epic Games, Inc. You are responsible for
following the current Fortnite Creator Portal rules and any licence of the IP used in your
island (for licensed franchises, follow the IP holder's brand rules).

## What is NOT included (supply your own)
- **Burbank / Fortnite fonts**: not distributed. Place your own licensed font in `Resources/brand/font/`.
- **ESRB (age rating) and "Developed in Fortnite" badges**: not distributed. Get the official files from their
  owners and place them in `Resources/badges/` (see the README there).
- **AI models** (Qwen Image Edit, its text encoder, VAE, optional upscaler and LoRA; ACE-Step 1.5 music model with its text encoders and VAE): not distributed.
  `download_models.bat` (or `python scripts/models.py download`) fetches them from their official Hugging Face / GitHub pages; check and respect each model's licence
  (ACE-Step is published under Apache-2.0) before using the results commercially.
- **Game / franchise artwork**: no screenshots or characters of any game are included.

## Bundled third-party files
- `Resources/fonts/LilitaOne-Regular.ttf` — Lilita One, (c) 2011 Juan Montoreano,
  SIL Open Font License 1.1 (`Resources/fonts/OFL.txt`).

## Tools used at runtime (not bundled)
ComfyUI (GPL-3.0), Pillow (HPND), ffmpeg (LGPL/GPL, depending on build), Real-ESRGAN (BSD-3-Clause, optional).

## Images in docs/img
The screenshots in `docs/img/` show the output of the kit for an example map built in UEFN. Fortnite and Unreal Editor for Fortnite are trademarks of Epic Games, Inc.; this project is unofficial.
