# Step 1 of the publication: create the GitHub repo with ONLY the legal and community files (no code yet).
# Run from this folder, after `gh auth login`. The code is published later with .\publish.ps1 (step 2, v1.0.0).
$ErrorActionPreference = "Stop"
$files = @("LICENSE", "NOTICE.md", "DISCLAIMER.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", ".gitignore",
           ".github/SECURITY.md", ".github/CODEOWNERS", ".github/PULL_REQUEST_TEMPLATE.md",
           ".github/ISSUE_TEMPLATE/config.yml", ".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/feature_request.yml")
foreach ($f in $files) { if (-not (Test-Path $f)) { throw "missing file: $f" } }
if (-not (Test-Path .git)) { git init -b main }
git add -- $files
# the short README of the skeleton is committed under the name README.md without touching your real README.md
$blob = git hash-object -w docs/README.skeleton.md
git update-index --add --cacheinfo "100644,$blob,README.md"
git status --short
git commit -m "docs: legal and community files (code follows with v1.0.0)"
$remote = git remote 2>$null
if (-not $remote) {
  gh repo create mimmo-the-root/island-promo-factory --public --source . --remote origin --push `
    --description "Free toolkit that prepares promo material (thumbnails, logo, trailer, gameplay video) for UEFN islands. Unofficial, not affiliated with Epic Games."
} else { git push -u origin main }
gh repo edit mimmo-the-root/island-promo-factory --add-topic uefn --add-topic fortnite-creative --add-topic thumbnail-generator --add-topic comfyui --add-topic promo-tools
gh repo edit mimmo-the-root/island-promo-factory --enable-issues --enable-wiki=false
Write-Host "Repo created: https://github.com/mimmo-the-root/island-promo-factory"
Write-Host "Next: Settings > Code security > enable Private vulnerability reporting (see docs/GITHUB_SETUP.md)."
