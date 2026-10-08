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
if not exist "%PD%\demo\config.json" "%PY%" "%PF%scripts\make_demo.py"
call "%PF%run_all.bat" demo --no-qwen
