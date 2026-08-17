@echo off
REM Starts the runtime and opens the control centre.
REM
REM Double-clickable on purpose: the runtime is a background process, so
REM anything that needs a terminal left open is something people forget to
REM start, and a company that only runs while a window is open is not running.

setlocal
set GUILDLESS_HOME=%~dp0
set GUILDLESS_PORT=8780
set GUILDLESS_PY=%GUILDLESS_HOME%.venv\Scripts\python.exe

if not exist "%GUILDLESS_PY%" (
  echo Guildless: 実行環境が見つかりません（%GUILDLESS_PY%）
  echo   セットアップ: python -m venv .venv ^&^& .venv\Scripts\pip install -e .
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%GUILDLESS_HOME%scripts\start-guildless.ps1" -Port %GUILDLESS_PORT%
