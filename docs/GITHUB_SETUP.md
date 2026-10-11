# GitHub setup (maintainer checklist)

## Step 1 - repo with legal and community files only (no code)
```
cd C:\IslandPromoFactory\island-promo-factory
gh auth login
.\publish_skeleton.bat
```
It commits only: LICENSE, NOTICE, DISCLAIMER, CODE_OF_CONDUCT, CONTRIBUTING, SECURITY, CODEOWNERS, PR and issue templates, `.gitignore`
and a short "setting up" README. Nothing else is staged: check the output of `git status --short` that the script prints.

## Step 2 - settings on github.com (once)
1. **Settings > Code security**: enable *Private vulnerability reporting* (the link in SECURITY.md needs it), *Dependabot alerts*, *Secret scanning*.
2. **Settings > General**: description and topics are set by the script; add a website link if you have one; disable Wiki and Projects if unused;
   enable Discussions only if you want to answer questions there.
3. **Settings > Branches**: protect `main` (require a pull request and the `tests` check once CI exists).
4. **Social preview** (Settings > General): upload a lightbox image made from a map that contains no Epic or franchise artwork.

## Step 3 - the code (v1.0.0), after the final tests
```
.\publish.ps1
```
It runs the version check, commits everything that is not ignored, pushes, tags `v1.0.0` and lets the CI build the Release.
Before running it, check nothing protected is staged: `git add -A -n | Select-String "Projects/|badges/|esrb|uefn|burbank|ffmpeg|safetensors"`
must list only `Projects/.gitkeep` and `Resources/badges/README.txt`.
