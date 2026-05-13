@echo off
setlocal

cd /d "%~dp0\.."

set "LOG_DIR=build\logs"
set "LOG_FILE=%CD%\%LOG_DIR%\package_windows.log"

if /i "%~1"=="--inner" goto :main

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
echo Building Windows single-file exe. Log file:
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
    echo App exe: %CD%\dist\JobSearchAssistant.exe
    echo Log file: %LOG_FILE%
)

if not defined PACKAGE_NO_PAUSE pause
exit /b %EXIT_CODE%

:main
set "APP_NAME=JobSearchAssistant"
set "DIST_ROOT=dist"
set "APP_EXE=%DIST_ROOT%\%APP_NAME%.exe"
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

echo [3/6] Building frontend assets...
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo npm was not found. Please install Node.js 20+ before packaging the Vue admin UI.
    exit /b 1
)
if not exist frontend\node_modules (
    pushd frontend
    call npm.cmd install
    set "NPM_INSTALL_EXIT=%ERRORLEVEL%"
    popd
    if not "%NPM_INSTALL_EXIT%"=="0" (
        echo npm install failed.
        exit /b 1
    )
)
pushd frontend
call npm.cmd run build
set "NPM_BUILD_EXIT=%ERRORLEVEL%"
popd
if not "%NPM_BUILD_EXIT%"=="0" (
    echo Frontend build failed.
    exit /b 1
)

echo [4/6] Cleaning previous package output...
if exist build\pyinstaller rmdir /s /q build\pyinstaller
if exist "%APP_EXE%" del /q "%APP_EXE%"
if exist "%DIST_ROOT%\JobSearchAssistantSetup.exe" del /q "%DIST_ROOT%\JobSearchAssistantSetup.exe"
if not exist "%DIST_ROOT%" mkdir "%DIST_ROOT%"

echo [5/6] Building single-file executable...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name "%APP_NAME%" ^
  --distpath "%DIST_ROOT%" ^
  --workpath build\pyinstaller ^
  --specpath build\pyinstaller ^
  --add-data "%CD%\config.yaml;." ^
  --add-data "%CD%\extension;extension" ^
  --add-data "%CD%\docs;docs" ^
  --add-data "%CD%\frontend\dist;frontend\dist" ^
  --add-data "%CD%\README.md;." ^
  "%CD%\src\boss_job_assistant\desktop_launcher.py"
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

echo [6/6] Checking optional installer builder...
where ISCC >nul 2>&1
if not errorlevel 1 (
    echo Building installer with Inno Setup...
    ISCC installer\inno\job-search-assistant.iss
    if errorlevel 1 exit /b 1
) else (
    echo Inno Setup was not found. Single-file app exe is ready:
    echo %CD%\%APP_EXE%
    echo To build Setup.exe, install Inno Setup and run this script again.
)

echo Package build finished.
exit /b 0
