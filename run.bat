@echo off
title Tapo-Viewer Launcher
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
    exit /b 0
)

echo ========================================================
echo   Tapo-Viewer: First-Time Setup
echo ========================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.10+ was not found on your system!
    echo Please install Python from https://www.python.org/downloads/
    echo or run: winget install Python.Python.3.12
    echo.
    pause
    exit /b 1
)

echo [1/2] Creating local virtual environment (.venv)...
python -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/2] Installing requirements (customtkinter, pytapo, pillow)...
".venv\Scripts\pip.exe" install --upgrade pip
".venv\Scripts\pip.exe" install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Setup completed successfully! Launching Tapo-Viewer...
start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0
