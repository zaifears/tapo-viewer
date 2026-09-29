@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo.
echo ==========================================
echo Building Tapo-Viewer
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -3.13 -m venv .venv

    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        exit /b 1
    )
)

echo Updating build tools...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel

if errorlevel 1 (
    echo ERROR: Could not update Python build tools.
    exit /b 1
)

echo Installing application dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    exit /b 1
)

echo Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller

if errorlevel 1 (
    echo ERROR: PyInstaller installation failed.
    exit /b 1
)

if not exist "vendor\ffmpeg\ffmpeg.exe" (
    echo ERROR: vendor\ffmpeg\ffmpeg.exe is missing.
    exit /b 1
)

if not exist "vendor\ffmpeg\ffprobe.exe" (
    echo ERROR: vendor\ffmpeg\ffprobe.exe is missing.
    exit /b 1
)

if not exist "vendor\vlc\libvlc.dll" (
    echo ERROR: vendor\vlc\libvlc.dll is missing.
    exit /b 1
)

if not exist "vendor\vlc\libvlccore.dll" (
    echo ERROR: vendor\vlc\libvlccore.dll is missing.
    exit /b 1
)

if not exist "vendor\vlc\plugins" (
    echo ERROR: vendor\vlc\plugins is missing.
    exit /b 1
)

echo Removing previous build output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo Building standalone executable...
".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    "TapoViewer.spec"

if errorlevel 1 (
    echo.
    echo ERROR: Tapo-Viewer build failed.
    exit /b 1
)

if not exist "dist\Tapo-Viewer.exe" (
    echo ERROR: Build completed without producing Tapo-Viewer.exe.
    exit /b 1
)

echo.
echo ==========================================
echo Build completed successfully
echo Output: dist\Tapo-Viewer.exe
echo ==========================================
echo.

endlocal
