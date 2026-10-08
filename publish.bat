@echo off
rem Runs publish.ps1 without changing the system execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish.ps1" %*
