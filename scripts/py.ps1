# Runs a kit script with the right Python (ComfyUI's embedded one if present, else python / py).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\py.ps1 <script.py> [args]
$root = Split-Path -Parent $PSScriptRoot
$cands = @("$root\..\ComfyUI_windows_portable\python_embeded\python.exe", "$root\ComfyUI_windows_portable\python_embeded\python.exe", "$root\..\python_embeded\python.exe")
$py = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { $c = Get-Command python -ErrorAction SilentlyContinue; if ($c) { $py = $c.Source } }
if (-not $py) { $c = Get-Command py -ErrorAction SilentlyContinue; if ($c) { $py = $c.Source } }
if (-not $py) { Write-Host "Python not found: install ComfyUI portable next to this folder or Python 3.10+"; exit 1 }
$script = $args[0]
if (-not (Test-Path $script)) { $script = Join-Path $PSScriptRoot $script }
$rest = @($args | Select-Object -Skip 1)
& $py $script @rest
exit $LASTEXITCODE
