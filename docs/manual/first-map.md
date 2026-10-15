# Your first map

A map is a folder in `Projects\` with your files and a `config.json`. The kit works on one map at a time.

## Create it

Run `new_map.bat my-map "MY MAP TITLE" --style NEON`. With Claude Code, `/promo-pack` asks for everything and creates it for you.

## Put your files in

| File | What it is |
|---|---|
| `background\background.png` | The environment, no characters, at least 1920 px wide |
| `characters\character_01.png` | One character, transparent PNG with margin on every side |
| `captures\gameplay\<recording>.mp4` | Your gameplay recording, ideally 5 minutes or more (optional, needed for video and screenshots) |

Then edit `config.json`: the island code (format 1234-5678-9012), the title, the title style (SCI_FI, HORROR, FIRE, ICE, NEON, GOLD or WHITE) and one sentence describing the character.

## No character yet?

Choosing is explicit, nothing is picked silently: your own skin in `characters\`, a random one from `Resources\Characters\` (`python scripts\default_skin.py --project my-map --random`), or none (`--none`). Epic's official renders are at brand.epicgames.com/document/469; download them yourself.

## Check before you run

`python scripts\intake.py --project my-map` lists every BLOCK and WARN. It also checks that the title font can draw your title and island code. When it prints READY, go to [Run and rerun](ch:run-and-rerun).
