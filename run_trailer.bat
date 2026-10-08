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
where ffmpeg >nul 2>&1
if errorlevel 1 (
  if not exist "%PF%Resources\bin\ffmpeg.exe" if "%FFMPEG_PATH%"=="" (
    echo ffmpeg NOT FOUND. Install it with:  winget install Gyan.FFmpeg
    echo Then open a NEW terminal, or set FFMPEG_PATH, or copy ffmpeg.exe/ffprobe.exe into Resources\bin\
    pause
    exit /b 1
  )
)
set PROMO_PROJECT=%MAP%
"%PY%" "%PF%scripts\trailer_builder.py" > "%PF%last_trailer.log" 2>&1
set "EC=%ERRORLEVEL%"
type "%PF%last_trailer.log"
if not "%EC%"=="0" (
  echo TRAILER BUILD FAILED - see last_trailer.log
  pause
  exit /b %EC%
)
echo Trailer: %PD%\%MAP%\final\trailer.mp4
pause
