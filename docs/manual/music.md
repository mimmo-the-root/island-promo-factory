# Music

The trailer needs music. The kit finds it in this order:

1. Your own file `audio\music.mp3` (or `.wav`): always wins and is never touched.
2. AI music made by ACE-Step through ComfyUI (three candidates, the best kept, the others in `audio\_candidates\`).
3. A built-in synthesiser when ComfyUI or the models are missing.

The mood comes from `music_mood` in `config.json`.

## Licensed Music Box

For a Discover request, Epic asks for its licensed music only. Set `"music_source": "licensed"` in `config.json` and put the track you chose in `audio\music.mp3`. The kit then generates no music, builds no montage, and keeps the original audio in the gameplay cut. Intake blocks the run if the track is missing.
