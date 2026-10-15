# Troubleshooting

Start with `doctor.bat`. Add `--fix` to let it repair the Claude kit, hooks and folders.

| Problem | What to do |
|---|---|
| "ffmpeg not found" | `winget install Gyan.FFmpeg`, then open a new terminal |
| "ComfyUI not reachable" | Start it with `start_comfyui.bat`, or run with `--no-qwen` |
| Intake says BLOCK | Read the line: it names the missing file or choice |
| A stage failed | Read `last_run_all.log`, fix that one thing, run again; finished stages are cached |
| The console shows an old version | Close it and reopen it; after an update it restarts by itself |
| Thumbnail looks too similar to another map | Read `final\similarity.json`; change pose, framing or colours |
| Video colours look washed out | Make sure you use the kit's own trailer and cuts: they carry BT.709 tags |
| Port 8791 is busy | Set `PROMO_CONSOLE_PORT` |

> **Tip** Set `PROMO_DEBUG=1` for extra diagnostic output.
