@echo off
REM K2 Pre-Build Cleanup Script
REM Removes developer-specific config files before building distributable
REM Run this before: pyinstaller K2.spec --clean

echo ========================================
echo K2 Pre-Build Cleanup
echo ========================================
echo.

REM Backup current config (optional)
if exist "%USERPROFILE%\.k2\k2_defaults.json" (
    echo Found local config file. Creating backup...
    copy "%USERPROFILE%\.k2\k2_defaults.json" "%USERPROFILE%\.k2\k2_defaults.json.backup" >nul 2>&1
    echo Backup saved to: %USERPROFILE%\.k2\k2_defaults.json.backup
    echo.
)

REM Clean PyInstaller artifacts
echo Cleaning previous build artifacts...
if exist "build" rd /s /q "build" 2>nul
if exist "dist" rd /s /q "dist" 2>nul
if exist "K2.spec.bak" del "K2.spec.bak" 2>nul
echo Build artifacts cleaned.
echo.

REM Remove local user config temporarily
if exist "%USERPROFILE%\.k2\k2_defaults.json" (
    echo IMPORTANT: Temporarily moving your local config file...
    move "%USERPROFILE%\.k2\k2_defaults.json" "%USERPROFILE%\.k2\k2_defaults.json.build_backup" >nul 2>&1
    echo Config file moved to prevent inclusion in build.
    echo It will be restored after the build completes.
    echo.
)

echo ========================================
echo Cleanup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Run: pyinstaller K2.spec --clean
echo 2. After build completes, run: build_restore.bat
echo.
pause
