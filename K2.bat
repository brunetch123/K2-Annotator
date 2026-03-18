@echo off
:: K2 - GC-MS Analysis GUI Launcher

cd /d "%~dp0"

:: Activate .venv if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Launch K2 GUI
python scripts\k2_gui.py

pause
