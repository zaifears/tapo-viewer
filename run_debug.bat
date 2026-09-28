@echo off
title Tapo-Viewer (Console Debug Mode)
cd /d "%~dp0"
echo Starting Tapo-Viewer in Console Mode...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application stopped with exit code %ERRORLEVEL%.
    pause
)
