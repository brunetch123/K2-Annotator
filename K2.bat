@echo off
setlocal enabledelayedexpansion
:: K2 Annotator - Launcher (GC-MS Suspect Screening Pipeline)
:: Double-click to run. Automatically installs dependencies on first use.

cd /d "%~dp0"

:: -------------------------------------------------------
:: 1. Find Python
:: -------------------------------------------------------
where python >nul 2>&1
if !errorlevel! neq 0 (
    echo ===============================================================
    echo  ERROR: Python is not installed or not in your PATH.
    echo.
    echo  Please install Python 3.8+ from https://www.python.org/downloads/
    echo  During installation, CHECK "Add Python to PATH".
    echo ===============================================================
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: 2. Auto-install dependencies (only if needed)
:: -------------------------------------------------------
if not exist ".deps_installed" (
    echo ---------------------------------------------------------------
    echo  First-time setup: installing Python dependencies...
    echo  This may take a minute. Subsequent launches will be instant.
    echo ---------------------------------------------------------------
    echo.
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo ===============================================================
        echo  ERROR: Failed to install one or more dependencies.
        echo  Try running manually:  pip install -r requirements.txt
        echo ===============================================================
        pause
        exit /b 1
    )
    echo. > ".deps_installed"
    echo.
    echo  Dependencies installed successfully!
    echo ---------------------------------------------------------------
    echo.
)

:: -------------------------------------------------------
:: 3. Launch K2 Annotator GUI
:: -------------------------------------------------------
python scripts\k2_gui.py

pause
