@echo off
setlocal
set "PF=%~dp0"
set "PY=python"
if exist "%PF%..\python_embeded\python.exe" set "PY=%PF%..\python_embeded\python.exe"
if exist "%PF%ComfyUI_windows_portable\python_embeded\python.exe" set "PY=%PF%ComfyUI_windows_portable\python_embeded\python.exe"
if exist "%PF%..\ComfyUI_windows_portable\python_embeded\python.exe" set "PY=%PF%..\ComfyUI_windows_portable\python_embeded\python.exe"
"%PY%" "%PF%scripts\update.py" %*
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  pause
  exit /b %EC%
)
echo.
echo This window closes in 10 seconds (Ctrl+C to keep it).
timeout /t 10 >nul 2>&1
exit /b 0
