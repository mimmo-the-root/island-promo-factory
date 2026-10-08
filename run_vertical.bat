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
  echo Usage: %~nx0 ^<map-slug^>   - maps available in Projects:
  for /d %%D in ("%PD%\*") do if exist "%%D\config.json" echo    %%~nxD
  pause
  exit /b 1
)
set PROMO_PROJECT=%MAP%
set PROMO_PLAN_B=bust
"%PY%" "%PF%scripts\qwen_run.py" vertical > "%PF%last_qwen.log" 2>&1
set "EC=%ERRORLEVEL%"
type "%PF%last_qwen.log"
if not "%EC%"=="0" (
  echo VERTICAL FAILED - see last_qwen.log
  pause
  exit /b %EC%
)
"%PY%" "%PF%scripts\factory.py" --project %MAP% --no-qwen
pause
