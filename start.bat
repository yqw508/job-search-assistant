@echo off
setlocal

cd /d "%~dp0"

set "SSLKEYLOGFILE="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PLAYWRIGHT_BROWSERS_PATH=%CD%\.playwright-browsers"

echo [1/5] Checking Python...
python --version >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python 3.10 or newer first.
    pause
    exit /b 1
)
python --version

echo [2/5] Checking pip...
python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip was not found. Trying to bootstrap pip...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo Failed to bootstrap pip.
        pause
        exit /b 1
    )
)

echo [3/5] Checking Python packages...
python -c "import importlib.util, sys; mods={'playwright':'playwright','PyYAML':'yaml','openpyxl':'openpyxl','pytest':'pytest'}; missing=[name for name,mod in mods.items() if importlib.util.find_spec(mod) is None]; print('Missing packages: ' + ', '.join(missing) if missing else 'All Python packages are installed.'); sys.exit(1 if missing else 0)"
if errorlevel 1 (
    echo Installing missing Python packages from requirements.txt...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install Python packages. Check your network/proxy and try again.
        pause
        exit /b 1
    )
)

echo [4/5] Ensuring Playwright Chromium is installed...
echo Browser cache: %PLAYWRIGHT_BROWSERS_PATH%
set "BOSS_BROWSER_CHANNEL="
set "BOSS_BROWSER_EXE="
set "BOSS_CDP_ENDPOINT="

where chrome >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where chrome') do if not defined BOSS_BROWSER_EXE set "BOSS_BROWSER_EXE=%%I"
)

if not defined BOSS_BROWSER_EXE (
    if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BOSS_BROWSER_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
)

if not defined BOSS_BROWSER_EXE (
    if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "BOSS_BROWSER_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if not defined BOSS_BROWSER_EXE (
    where msedge >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%I in ('where msedge') do if not defined BOSS_BROWSER_EXE set "BOSS_BROWSER_EXE=%%I"
    )
)

if not defined BOSS_BROWSER_EXE (
    if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BOSS_BROWSER_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
)

if not defined BOSS_BROWSER_EXE (
    if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BOSS_BROWSER_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
)

if not defined BOSS_BROWSER_EXE (
    if exist "%LocalAppData%\Microsoft\Edge\Application\msedge.exe" set "BOSS_BROWSER_EXE=%LocalAppData%\Microsoft\Edge\Application\msedge.exe"
)

if defined BOSS_BROWSER_EXE (
    echo Found system browser: %BOSS_BROWSER_EXE%
    set "BOSS_CDP_ENDPOINT=http://127.0.0.1:9222"
    echo Starting system browser in CDP attach mode...
    start "" "%BOSS_BROWSER_EXE%" --remote-debugging-port=9222 --user-data-dir="%CD%\.browser-profile-cdp" --no-first-run --no-default-browser-check about:blank
    timeout /t 2 /nobreak >nul
) else (
    python -m playwright install chromium
    if errorlevel 1 (
        echo Default Playwright download failed. Retrying with alternate download host...
        set "PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net"
        python -m playwright install chromium
        if errorlevel 1 (
            echo Failed to install Playwright Chromium. Check your network/proxy and try again.
            echo You can also install Google Chrome or Microsoft Edge, then rerun this script.
            pause
            exit /b 1
        )
    )
)

echo [5/5] Starting Boss job assistant...
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
python -m boss_job_assistant.boss_job_assistant config.yaml

echo.
echo Program exited.
pause
