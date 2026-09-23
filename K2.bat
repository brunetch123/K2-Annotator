@echo off
setlocal enabledelayedexpansion
:: K2 Annotator - Launcher (GC-MS Suspect Screening Pipeline)
:: Double-click to run. Automatically installs dependencies on first use
:: and re-installs them whenever requirements.txt changes.

cd /d "%~dp0"

:: -------------------------------------------------------
:: 1. Find Python
::    Prefer the Python launcher ("py -3"): it resolves a real
::    CPython install and never hits the Microsoft Store
::    "python" alias stub that Windows puts on the PATH.
:: -------------------------------------------------------
set "PY="
py -3 -c "import sys" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY=py -3"
) else (
    python -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY=python"
    )
)
if not defined PY (
    echo ===============================================================
    echo  ERROR: Python is not installed or not in your PATH.
    echo.
    echo  Please install Python 3.8+ from https://www.python.org/downloads/
    echo  During installation, CHECK "Add Python to PATH".
    echo  ^(If "python" opens the Microsoft Store, install real Python
    echo  from python.org or disable the Store alias in Settings ^>
    echo  Apps ^> Advanced app settings ^> App execution aliases.^)
    echo ===============================================================
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: 2. Auto-install dependencies (first run, or whenever
::    requirements.txt differs from the copy recorded at the
::    last successful install in .deps_installed)
:: -------------------------------------------------------
set "NEED_INSTALL=0"
if not exist ".deps_installed" (
    set "NEED_INSTALL=1"
) else (
    fc /b "requirements.txt" ".deps_installed" >nul 2>&1
    if !errorlevel! neq 0 set "NEED_INSTALL=1"
)

if "!NEED_INSTALL!"=="1" (
    echo ---------------------------------------------------------------
    echo  Installing/updating Python dependencies from requirements.txt
    echo  This may take a minute. Subsequent launches will be instant.
    echo ---------------------------------------------------------------
    echo.
    !PY! -m pip install --upgrade pip >nul 2>&1
    !PY! -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo ===============================================================
        echo  ERROR: Failed to install one or more dependencies.
        echo  Try running manually:  !PY! -m pip install -r requirements.txt
        echo ===============================================================
        pause
        exit /b 1
    )
    :: Record the requirements that were installed; a later edit to
    :: requirements.txt makes the fc comparison above fail and
    :: triggers a re-install.
    copy /y "requirements.txt" ".deps_installed" >nul
    echo.
    echo  Dependencies installed successfully!
    echo ---------------------------------------------------------------
    echo.
)

:: -------------------------------------------------------
:: 3. Launch K2 Annotator GUI
::    Optional: set K2_EPA_API_KEY in your environment to supply the
::    EPA CompTox API key without typing it into the GUI.
:: -------------------------------------------------------
!PY! scripts\k2_gui.py

pause
