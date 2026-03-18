@echo off
:: K2 GC-MS Pipeline - Create Distribution Package
:: This script packages the built executable with documentation into a ZIP file
::
:: Prerequisites:
::   - Run build_exe.bat first to create dist\K2\ folder
::
:: Output: K2_v3.0.2_Windows.zip

echo ============================================================
echo K2 GC-MS Pipeline - Create Distribution Package
echo ============================================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Check if build exists
if not exist "dist\K2\K2.exe" (
    echo ERROR: dist\K2\K2.exe not found.
    echo Please run build_exe.bat first to create the executable.
    pause
    exit /b 1
)

set DIST_DIR=K2_v3.0.3_Windows
set ZIP_NAME=K2_v3.0.3_Windows.zip

echo [1/4] Creating distribution folder: %DIST_DIR%
echo.

:: Remove old distribution folder if exists
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

:: Create distribution folder
mkdir "%DIST_DIR%"

echo [2/4] Copying files...
echo.

:: Copy built executable and dependencies
xcopy "dist\K2\*" "%DIST_DIR%\" /E /I /Q

:: Copy documentation
copy "K2_USER_GUIDE.md" "%DIST_DIR%\" >nul
copy "README.md" "%DIST_DIR%\" >nul
copy "CHANGELOG.md" "%DIST_DIR%\" >nul
copy "QUICK_START.md" "%DIST_DIR%\" >nul
copy "INSTALLATION.txt" "%DIST_DIR%\" >nul
copy "LICENSE" "%DIST_DIR%\" >nul

:: Ensure config folder is present
if not exist "%DIST_DIR%\config" mkdir "%DIST_DIR%\config"
xcopy "config\*" "%DIST_DIR%\config\" /E /I /Q 2>nul

:: Ensure users folder is present
if not exist "%DIST_DIR%\users" mkdir "%DIST_DIR%\users"
xcopy "users\*" "%DIST_DIR%\users\" /E /I /Q 2>nul

:: Ensure templates folder is present
if not exist "%DIST_DIR%\templates" mkdir "%DIST_DIR%\templates"
xcopy "templates\*" "%DIST_DIR%\templates\" /E /I /Q 2>nul

echo [2b/4] Restructuring distribution (moving docs to top level)...
echo.

:: Move documentation and resources from _internal to top level if they were placed there
if exist "%DIST_DIR%\_internal\K2_USER_GUIDE.md" (
    move /Y "%DIST_DIR%\_internal\K2_USER_GUIDE.md" "%DIST_DIR%\" >nul
)
if exist "%DIST_DIR%\_internal\README.md" (
    move /Y "%DIST_DIR%\_internal\README.md" "%DIST_DIR%\" >nul
)
if exist "%DIST_DIR%\_internal\CHANGELOG.md" (
    move /Y "%DIST_DIR%\_internal\CHANGELOG.md" "%DIST_DIR%\" >nul
)
if exist "%DIST_DIR%\_internal\QUICK_START.md" (
    move /Y "%DIST_DIR%\_internal\QUICK_START.md" "%DIST_DIR%\" >nul
)
if exist "%DIST_DIR%\_internal\K2Icon.png" (
    move /Y "%DIST_DIR%\_internal\K2Icon.png" "%DIST_DIR%\" >nul
)
if exist "%DIST_DIR%\_internal\K2Logo2.png" (
    move /Y "%DIST_DIR%\_internal\K2Logo2.png" "%DIST_DIR%\" >nul
)

:: Move folders to top level if they exist in _internal
if exist "%DIST_DIR%\_internal\templates" (
    if not exist "%DIST_DIR%\templates" mkdir "%DIST_DIR%\templates"
    xcopy "%DIST_DIR%\_internal\templates\*" "%DIST_DIR%\templates\" /E /I /Q /Y >nul
    rmdir /s /q "%DIST_DIR%\_internal\templates"
)
if exist "%DIST_DIR%\_internal\config" (
    if not exist "%DIST_DIR%\config" mkdir "%DIST_DIR%\config"
    xcopy "%DIST_DIR%\_internal\config\*" "%DIST_DIR%\config\" /E /I /Q /Y >nul
    rmdir /s /q "%DIST_DIR%\_internal\config"
)
if exist "%DIST_DIR%\_internal\users" (
    if not exist "%DIST_DIR%\users" mkdir "%DIST_DIR%\users"
    xcopy "%DIST_DIR%\_internal\users\*" "%DIST_DIR%\users\" /E /I /Q /Y >nul
    rmdir /s /q "%DIST_DIR%\_internal\users"
)

echo [3/4] Creating ZIP archive: %ZIP_NAME%
echo.

:: Remove old ZIP if exists
if exist "%ZIP_NAME%" del "%ZIP_NAME%"

:: Create ZIP using PowerShell
powershell -Command "Compress-Archive -Path '%DIST_DIR%' -DestinationPath '%ZIP_NAME%' -Force"

if errorlevel 1 (
    echo WARNING: Could not create ZIP file automatically.
    echo Please manually compress the %DIST_DIR% folder.
) else (
    echo ZIP archive created: %ZIP_NAME%
)

echo.
echo [4/4] Distribution package complete!
echo.
echo ============================================================
echo Distribution Contents:
echo ============================================================
dir /b "%DIST_DIR%"
echo.
echo ============================================================
echo.
echo Distribution folder: %DIST_DIR%\
echo ZIP archive: %ZIP_NAME%
echo.
echo Next steps:
echo   1. Test: Double-click %DIST_DIR%\K2.exe
echo   2. Upload %ZIP_NAME% to GitHub releases
echo   3. Share with collaborators
echo.

pause
