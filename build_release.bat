@echo off
REM K2 Complete Release Build Script
REM Performs cleanup, build, and restore in one step

echo ========================================
echo K2 Release Build
echo ========================================
echo.

REM Step 1: Cleanup
echo [1/4] Running pre-build cleanup...
call build_clean.bat
if errorlevel 1 (
    echo Error during cleanup!
    pause
    exit /b 1
)

REM Step 2: Build
echo.
echo [2/4] Building K2 executable...
pyinstaller K2.spec --clean
if errorlevel 1 (
    echo Error during build!
    echo Restoring config...
    call build_restore.bat
    pause
    exit /b 1
)

REM Step 3: Restore
echo.
echo [3/4] Restoring development environment...
call build_restore.bat

REM Step 4: Verify
echo.
echo [4/4] Verifying build...
if exist "dist\K2\K2.exe" (
    echo SUCCESS! Build complete.
    echo.
    echo Output location: dist\K2\
    echo Executable: dist\K2\K2.exe
    echo.
) else (
    echo WARNING: K2.exe not found in expected location!
    echo Check build output for errors.
    echo.
)

echo ========================================
echo Build Process Complete!
echo ========================================
echo.
pause
