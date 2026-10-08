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
"%PY%" "%PF%scripts\run_all.py" --project %MAP% --ui %2 %3 %4
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo FULL RUN FAILED - see last_run_all.log
  pause
  exit /b %EC%
)
echo.
echo This window closes in 10 seconds (Ctrl+C to keep it).
timeout /t 10 >nul 2>&1
exit /b 0
