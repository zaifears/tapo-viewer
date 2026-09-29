@echo off
title Tapo-Viewer Executable Builder
cd /d "%~dp0"
echo ========================================================
echo   Building Standalone Tapo-Viewer.exe with PyInstaller
echo ========================================================
echo.

if not exist ".venv\Scripts\pyinstaller.exe" (
    echo Installing PyInstaller in virtual environment...
    ".venv\Scripts\pip.exe" install pyinstaller
)

echo Packaging application into dist\Tapo-Viewer.exe...
".venv\Scripts\pyinstaller.exe" --noconsole --onefile --clean --collect-all customtkinter --add-data "assets;assets" --icon "assets\icon.ico" --name "Tapo-Viewer" app.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  Build SUCCESS!
    echo  Standalone executable created at:
    echo    dist\Tapo-Viewer.exe
    echo ========================================================
) else (
    echo.
    echo [ERROR] Build failed with exit code %ERRORLEVEL%.
)
pause
