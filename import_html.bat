@echo off
setlocal

cd /d "%~dp0"

set "SSLKEYLOGFILE="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if not exist input_html mkdir input_html

echo Put saved Boss HTML files into:
echo %CD%\input_html
echo.
echo Then press any key to import and export Excel.
pause >nul

python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip was not found. Please install pip first.
    pause
    exit /b 1
)

python -c "import importlib.util, sys; mods={'PyYAML':'yaml','openpyxl':'openpyxl'}; missing=[name for name,mod in mods.items() if importlib.util.find_spec(mod) is None]; sys.exit(1 if missing else 0)"
if errorlevel 1 (
    echo Installing required Python packages...
    python -m pip install PyYAML>=6.0.1 openpyxl>=3.1.2
    if errorlevel 1 (
        echo Failed to install required Python packages.
        pause
        exit /b 1
    )
)

python -m boss_job_assistant.import_saved_html input_html config.yaml

echo.
echo Import finished.
pause
