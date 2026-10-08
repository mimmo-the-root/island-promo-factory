@echo off
setlocal
set "PF=%~dp0"
set "PY=python"
if exist "%PF%..\python_embeded\python.exe" set "PY=%PF%..\python_embeded\python.exe"
if exist "%PF%ComfyUI_windows_portable\python_embeded\python.exe" set "PY=%PF%ComfyUI_windows_portable\python_embeded\python.exe"
if exist "%PF%..\ComfyUI_windows_portable\python_embeded\python.exe" set "PY=%PF%..\ComfyUI_windows_portable\python_embeded\python.exe"
set "PD=%PF%Projects"
if exist "%PF%..\Projects" set "PD=%PF%..\Projects"
if defined PROMO_PROJECTS_DIR set "PD=%PROMO_PROJECTS_DIR%"
set "MAP=%~1"
if "%MAP%"=="" (
  echo Usage: %~nx0 ^<map-slug^>   - opens the results page of the last run. Maps available in Projects:
  for /d %%D in ("%PD%\*") do if exist "%%D\config.json" echo    %%~nxD
  pause
  exit /b 1
)
echo Results page for %MAP% - keep this window open to download files, close it to stop.
"%PY%" "%PF%scripts\dashboard.py" --project %MAP%
pause
