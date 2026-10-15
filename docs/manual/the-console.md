# The console

The live console shows a run while it happens: overall progress, the stages, a preview of what is being made and the log. It runs in the background, on your PC only (`http://127.0.0.1:8791`), and closes itself after 30 idle minutes.

Open it with `dashboard.bat my-map`, or with `/promo-console` in Claude Code.

## When the run is done

![The result card: lightbox and downloads](console-result.png)

The result card has two clearly separated sections. **Creator Portal files** are the numbered files you upload to the portal. **Social media videos** is an optional extra with its own button and its own ZIP; those files never go to the portal.

![The optional social media section](console-social.png)

## Good to know

- **Variants:** buttons make variants B and C of the images (a new seed). Version A is never touched.
- **Updates:** a bar tells you when a newer release exists, and when the kit on disk is newer than the console you are looking at (close it and reopen it).
- **Costs:** `/costs` shows tokens per model and per role for the Claude Code sessions of this folder.
- **Another tool on the same PC:** the console uses port 8791. Set `PROMO_CONSOLE_PORT` to change it.
