@echo off
setlocal

cd /d "%~dp0"

set "SSLKEYLOGFILE="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Please install Python 3 and make sure it is available on PATH.
    pause
    exit /b 1
)

python -c "import yaml, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo Required Python packages are missing. Installing PyYAML and openpyxl...
    python -m pip install "PyYAML>=6.0.1" "openpyxl>=3.1.2"
    if errorlevel 1 (
        echo Failed to install required Python packages. Please check your Python and pip setup.
        pause
        exit /b 1
    )
)

echo Starting local service...
python -m boss_job_assistant.local_service

echo Service exited.
pause
