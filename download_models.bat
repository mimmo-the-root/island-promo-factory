@echo off
setlocal
set "PF=%~dp0"
set "PY=python"
if exist "%PF%..\python_embeded\python.exe" set "PY=%PF%..\python_embeded\python.exe"
if exist "%PF%ComfyUI_windows_portable\python_embeded\python.exe" set "PY=%PF%ComfyUI_windows_portable\python_embeded\python.exe"
if exist "%PF%..\ComfyUI_windows_portable\python_embeded\python.exe" set "PY=%PF%..\ComfyUI_windows_portable\python_embeded\python.exe"
echo Island Promo Factory - AI model download (artwork: Qwen, about 30 GB / music: ACE-Step, about 15 GB).
echo Options: download_models.bat [--group image^|audio^|all] [--optional] [--dry-run]
echo It resumes if you stop it, and only downloads what is missing.
echo.
"%PY%" "%PF%scripts\models.py" download %*
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" echo Some files did not download. Run this again (it resumes) or use the manual links in docs\INSTALL.md step 4.
pause
exit /b %EC%
