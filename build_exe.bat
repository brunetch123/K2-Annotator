@echo off
:: K2 GC-MS Pipeline - Build Executable Script
:: This script creates a standalone Windows executable using PyInstaller
::
:: Prerequisites:
::   - Python 3.8+ with pip
::   - Virtual environment activated (optional but recommended)
::
:: Output: dist\K2\ folder containing K2.exe and dependencies

echo ============================================================
echo K2 GC-MS Pipeline - Build Script
echo ============================================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ and add to PATH.
    pause
    exit /b 1
)

echo [1/5] Checking/Installing dependencies...
echo.

:: Install required packages
pip install pyinstaller pillow --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/5] Creating Windows icon...
echo.

:: Convert PNG to ICO if needed
if not exist "K2Icon.ico" (
    python -c "from PIL import Image; img=Image.open('K2Icon.png'); img.save('K2Icon.ico', format='ICO', sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])"
    if errorlevel 1 (
        echo WARNING: Could not create icon file. Using default icon.
    ) else (
        echo Icon created: K2Icon.ico
    )
) else (
    echo Icon already exists: K2Icon.ico
)

echo.
echo [3/5] Cleaning previous build...
echo.

:: Clean previous builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo [4/5] Building executable (this may take several minutes)...
echo.

:: Run PyInstaller
pyinstaller K2.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo [5/5] Build complete!
echo.
echo ============================================================
echo SUCCESS: Executable created at dist\K2\K2.exe
echo ============================================================
echo.
echo Next steps:
echo   1. Test the executable: dist\K2\K2.exe
echo   2. Copy documentation to dist\K2\ folder
echo   3. Create ZIP archive for distribution
echo.
echo To create distribution package, run: create_distribution.bat
echo.

pause
