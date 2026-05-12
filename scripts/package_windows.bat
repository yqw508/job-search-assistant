@echo off
setlocal

cd /d "%~dp0\.."

set "LOG_DIR=build\logs"
set "LOG_FILE=%CD%\%LOG_DIR%\package_windows.log"

if /i "%~1"=="--inner" goto :main

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
echo Building Windows package. Log file:
echo %LOG_FILE%
echo.

call "%~f0" --inner > "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

type "%LOG_FILE%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo Package build failed. The command window is kept open so you can read the error.
    echo Log file: %LOG_FILE%
) else (
    echo Package build succeeded.
    echo Log file: %LOG_FILE%
)

if not defined PACKAGE_NO_PAUSE pause
exit /b %EXIT_CODE%

:main
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
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"

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
if errorlevel 1 exit /b 1
xcopy /e /i /y docs "%RELEASE_DIR%\docs" >nul
if errorlevel 1 exit /b 1
copy /y README.md "%RELEASE_DIR%\README.md" >nul
if errorlevel 1 exit /b 1
copy /y config.yaml "%RELEASE_DIR%\config.yaml" >nul
if errorlevel 1 exit /b 1

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
    if errorlevel 1 exit /b 1
) else (
    echo Inno Setup was not found. Portable package is ready:
    echo %CD%\%DIST_ROOT%\%APP_NAME%.zip
    echo To build Setup.exe, install Inno Setup and run this script again.
)

echo Package build finished.
exit /b 0
