---
description: Start a new map (or continue an existing one) - Claude runs the whole Island Promo Factory pipeline
---

Load the `island-promo` skill and follow it from step 0. First check for a newer release (`update.py --check`) and say the result in one line.
Then list the existing maps (`intake.py`) and ask first, in plain text: continue one of them, or a new map? For an existing map go to the intake checks. For a NEW map ask the user ONLY for the island code and the title (as shown in Discover). Create the map, open the live console right away,
then tell the user the exact folder for each file to drop in. The title style and the character description you decide yourself by looking at the images.
You run every command yourself (ComfyUI, the live console, the pipeline); the user never has to double-click a .bat file. Extra text from the user: $ARGUMENTS
