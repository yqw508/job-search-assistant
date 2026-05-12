@echo off
setlocal

cd /d "%~dp0"

set "SSLKEYLOGFILE="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Please install Python 3 and make sure it is available on PATH.
    pause
    exit /b 1
)
python --version

echo [2/4] Checking pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip was not found. Trying to bootstrap pip...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo Failed to bootstrap pip. Please reinstall Python and include pip.
        pause
        exit /b 1
    )
)

echo [3/4] Checking Python packages...
python -c "import yaml" >nul 2>&1
if errorlevel 1 (
    echo Required Python packages are missing. Installing from requirements.txt...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install required Python packages. Please check your Python and pip setup.
        pause
        exit /b 1
    )
    echo Required Python packages installed.
) else (
    echo Required Python packages are installed.
)

echo [4/4] Starting local service...
python -m boss_job_assistant.local_service

echo Service exited.
pause
