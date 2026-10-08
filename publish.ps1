# Run from the repo folder on your PC (needs git + gh logged in: `gh auth login`).
# First publication: creates the GitHub repo and pushes. Later releases: use the same scheme (see docs/UPDATING.md):
#   python scripts/release.py bump patch ; edit CHANGELOG ; python scripts/release.py check ; .\publish.ps1
$ErrorActionPreference = "Stop"
python scripts/release.py check
if ($LASTEXITCODE -ne 0) { throw "VERSION / CHANGELOG mismatch" }
$ver = (Get-Content VERSION -Raw).Trim()
$title = (python scripts/release.py notes | Select-Object -First 1)
if (-not (Test-Path .git)) { git init -b main }
git add -A
git commit -m "v${ver}: $title"
$remote = git remote 2>$null
if (-not $remote) {
  gh repo create mimmo-the-root/island-promo-factory --public --source . --remote origin --push `
    --description "Free toolkit: Epic-Discover-compliant thumbnails, logo, promo pack and trailer for UEFN maps"
} else {
  git push
}
git tag "v$ver"
git push origin "v$ver"
Write-Host "Pushed v$ver. GitHub Actions now runs the tests and publishes the Release (zip + notes)."
Write-Host "https://github.com/mimmo-the-root/island-promo-factory/actions"
