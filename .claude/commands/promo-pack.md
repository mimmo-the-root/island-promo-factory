---
description: Create the promo package (thumbnails, logo, videos) of an island - new, or continue one already started
---

Load the `island-promo` skill and follow it from step 0. First check for a newer release (`update.py --check`) and say the result in one line.
Then list the existing maps (`intake.py`) and ask first, in plain text: continue one of those packages, or create a new package? For an existing map go to the intake checks. For a NEW package ask ONLY for the island code and the title (as shown in Discover), then one question: make new artwork from separate images, or make my existing thumbnail conform (skill `island-conform`)? Create the project, open the live console right away,
then tell the user the exact folder for each file to drop in (file names are examples, any name works) and that they can drop the files now or come back later: the next `/promo-pack` continues the saved map. The title style and the character description you decide yourself by looking at the images.
You run every command yourself (ComfyUI, the live console, the pipeline); the user never has to double-click a .bat file. Extra text from the user: $ARGUMENTS
