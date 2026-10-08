@echo off
rem Starts the ComfyUI that lives next to this folder (..\ComfyUI_windows_portable, third-party, installed separately).
setlocal
set "PF=%~dp0"
set "CU=%PF%..\ComfyUI_windows_portable"
if not exist "%CU%\run_nvidia_gpu.bat" set "CU=%PF%ComfyUI_windows_portable"
if exist "%CU%\run_nvidia_gpu.bat" (
  rem ComfyUI's own bat uses relative paths: it must run from its own folder.
  pushd "%CU%"
  call run_nvidia_gpu.bat
  popd
) else (
  echo ComfyUI_windows_portable not found next to %PF%
  echo Install ComfyUI portable there, or start your own ComfyUI and keep it on http://127.0.0.1:8188
  pause
)
