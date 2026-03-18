@echo off
REM K2 Post-Build Restore Script
REM Restores developer config after building distributable
REM Run this after: pyinstaller K2.spec --clean

echo ========================================
echo K2 Post-Build Restore
echo ========================================
echo.

REM Restore backed up config
if exist "%USERPROFILE%\.k2\k2_defaults.json.build_backup" (
    echo Restoring your local config file...
    move "%USERPROFILE%\.k2\k2_defaults.json.build_backup" "%USERPROFILE%\.k2\k2_defaults.json" >nul 2>&1
    echo Config file restored.
    echo.
) else (
    echo No backup config found to restore.
    echo.
)

echo ========================================
echo Restore Complete!
echo ========================================
echo.
echo Your development environment has been restored.
echo Build output is in: dist\K2\
echo.
pause
