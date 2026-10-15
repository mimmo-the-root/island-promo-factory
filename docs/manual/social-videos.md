# Social videos

An optional extra, made after the kit: vertical 9:16 videos (1080x1920) for TikTok, Instagram Reels and YouTube Shorts, with English promotional subtitles. They go in `promo_pack\social\` and are not for the Creator Portal.

## How to make them

- In the console, press **CREATE SOCIAL VIDEOS** once the kit is done.
- In Claude Code, answer yes when Claude asks after delivering the kit; it drafts the texts and waits for your approval.
- From the command line: `python scripts\social_video.py --project my-map` or `run_all.bat my-map --social`.

## The texts

`Projects\my-map\social.json` holds variants A and B: a hook, two or three selling points and a call to action with your island code. If the file is missing the kit writes neutral drafts and marks them `"draft": true`. Edit them, remove the flag and run again.

## What you get

For each variant an MP4 (15 to 30 seconds, BT.709), a `.srt` subtitle file, and `captions.txt` with a description and hashtags per platform. The layout keeps the subtitles in the middle band, clear of the app's bottom bar and right-hand buttons, and the cuts snap to the music's beat.
