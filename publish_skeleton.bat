@echo off
rem Runs publish_skeleton.ps1 without changing the system execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_skeleton.ps1" %*
