---
name: island-review
description: Island Promo Factory final review - inspect every output, write RUN_REPORT.md, hand over the promo pack with the portal upload checklist, and wait for the portal result before the next map.
---

# Review and handover

1. Open and LOOK at every file in `Projects/<slug>/promo_pack/`: 01-04 thumbnails (one character, nothing floating or cut, title readable and inside the safe area, bottom corners free), 05 logo, 06 lobby background, 07 gameplay, 08 trailer, 09 screenshots. Check colours (no purple/magenta cast), badges not distorted, no foreign text in the art.
2. Read `final/run_timings.json`, `last_run_all.log`, `UPLOAD_CHECKLIST.md`, `island_description_disclaimer.txt`.
3. Write `Projects/<slug>/RUN_REPORT.md`: map, seed, look, what is in the pack, anything imperfect, what the user must do by hand.
4. Open the pack folder for the user in Windows Explorer (`powershell -NoProfile -Command Start-Process explorer.exe "<absolute path of promo_pack>"`). Say that `final/` only holds working files and that the numbered files (01-09, gameplay and trailer included) to upload are in `promo_pack/`.
   Tell the user (short, in their language): where the pack is, the three things to check in the portal, and that the island description needs the notice from `island_description_disclaimer.txt`.
5. Mention the gameplay policy: the pack has the edited montage unless `--gameplay-look off` was used; if the portal rejects it, rebuild the unedited cut and retry.
6. Stop. The next map starts only after the user reports whether the portal accepted this one.
