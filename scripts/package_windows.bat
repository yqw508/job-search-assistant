@echo off
setlocal

cd /d "%~dp0\.."

set "APP_NAME=JobSearchAssistant"
set "DIST_ROOT=dist"
set "RELEASE_DIR=%DIST_ROOT%\%APP_NAME%"
set "EXE_NAME=job-search-assistant.exe"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Please install Python 3.10+ and add it to PATH.
    exit /b 1
)
python --version

echo [2/6] Installing build dependencies...
python -m pip install -r requirements-build.txt
if errorlevel 1 (
    echo Default pip source failed. Retrying PyInstaller from official PyPI with user install...
    python -m pip install --user --no-cache-dir --timeout 60 "pyinstaller>=6.6.0" -i https://pypi.org/simple
    if errorlevel 1 (
        echo Failed to install build dependencies.
        exit /b 1
    )
)

echo [3/6] Cleaning previous package output...
if exist build\pyinstaller rmdir /s /q build\pyinstaller
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
if exist "%DIST_ROOT%\%APP_NAME%.zip" del /q "%DIST_ROOT%\%APP_NAME%.zip"
mkdir "%RELEASE_DIR%"

echo [4/6] Building executable...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --name job-search-assistant ^
  --distpath "%RELEASE_DIR%" ^
  --workpath build\pyinstaller ^
  --specpath build\pyinstaller ^
  --add-data "%CD%\config.yaml;." ^
  "%CD%\src\boss_job_assistant\desktop_launcher.py"
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

echo [5/6] Copying release files...
xcopy /e /i /y extension "%RELEASE_DIR%\extension" >nul
xcopy /e /i /y docs "%RELEASE_DIR%\docs" >nul
copy /y README.md "%RELEASE_DIR%\README.md" >nul
copy /y config.yaml "%RELEASE_DIR%\config.yaml" >nul

echo [6/6] Creating portable zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%DIST_ROOT%\%APP_NAME%.zip' -Force"
if errorlevel 1 (
    echo Failed to create portable zip.
    exit /b 1
)

where ISCC >nul 2>&1
if not errorlevel 1 (
    echo Building installer with Inno Setup...
    ISCC installer\inno\job-search-assistant.iss
) else (
    echo Inno Setup was not found. Portable package is ready:
    echo %CD%\%DIST_ROOT%\%APP_NAME%.zip
    echo To build Setup.exe, install Inno Setup and run this script again.
)

echo Package build finished.
