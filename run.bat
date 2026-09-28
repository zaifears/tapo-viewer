@echo off
title Tapo-Viewer
cd /d "%~dp0"
echo Starting Tapo-Viewer...

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
) else (
    start "" pythonw app.py
)
exit
