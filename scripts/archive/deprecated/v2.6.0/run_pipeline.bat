@echo off
:: GC-MS Pipeline Runner
:: Usage: run_pipeline.bat [arguments]
::
:: Examples:
::   run_pipeline.bat --from-raw "X:\Data\raw"
::   run_pipeline.bat --from-mzml "X:\Data\converted" --threads 4
::   run_pipeline.bat --from-mzmine "X:\Data\mzmine_output\run_001"

cd /d "%~dp0"

:: Activate .venv if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python scripts\gcms_pipeline.py %*

pause
