@echo off
:: Setup virtual environment for GC-MS Pipeline
:: Run this once to set up the environment

cd /d "%~dp0"

echo ======================================================
echo GC-MS Pipeline Environment Setup
echo ======================================================
echo.

:: Check if .venv exists
if exist ".venv" (
    echo Virtual environment already exists.
    set /p REBUILD="Rebuild it? (y/N): "
    if /i "%REBUILD%"=="y" (
        echo Removing old environment...
        rmdir /s /q .venv
    ) else (
        goto :install
    )
)

echo Creating virtual environment...
python -m venv .venv

:install
echo.
echo Activating environment...
call .venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install --upgrade pip
pip install numpy pandas

::: Check if there's a requirements.txt
if exist "requirements.txt" (
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
) else if exist "scripts\requirements.txt" (
    echo Installing additional dependencies from scripts\requirements.txt...
    pip install -r scripts\requirements.txt
)

echo.
echo ======================================================
echo Setup Complete!
echo ======================================================
echo.
echo Usage:
echo   run_pipeline.bat --from-raw "path\to\D_files"
echo   run_pipeline.bat --from-mzml "path\to\mzML_files"  
echo   run_pipeline.bat --from-mzmine "path\to\mzmine_output"
echo.
echo Or activate manually:
echo   .venv\Scripts\activate
echo   python scripts\gcms_pipeline.py --help
echo.

pause
