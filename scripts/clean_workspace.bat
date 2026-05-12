@echo off
setlocal

cd /d "%~dp0\.."

set "CLEAN_DIST=0"
set "CLEAN_OUTPUT=0"
set "CLEAN_VENV=0"

:parse_args
if "%~1"=="" goto :main
if /i "%~1"=="--dist" set "CLEAN_DIST=1"
if /i "%~1"=="--output" set "CLEAN_OUTPUT=1"
if /i "%~1"=="--venv" set "CLEAN_VENV=1"
if /i "%~1"=="--all" (
    set "CLEAN_DIST=1"
    set "CLEAN_OUTPUT=1"
    set "CLEAN_VENV=1"
)
if /i "%~1"=="--help" goto :help
shift
goto :parse_args

:main
echo Cleaning local workspace generated files...
echo Project: %CD%
echo.

call :remove_dir ".tmp" || exit /b 1
call :remove_dir ".pytest_cache" || exit /b 1
call :remove_dir ".pytest-tmp" || exit /b 1
call :remove_dir ".pytest-tmp-review" || exit /b 1
call :remove_dir ".browser-profile" || exit /b 1
call :remove_dir ".browser-profile-cdp" || exit /b 1
call :remove_dir ".playwright-browsers" || exit /b 1
call :remove_dir "build" || exit /b 1

if "%CLEAN_DIST%"=="1" call :remove_dir "dist" || exit /b 1
if "%CLEAN_OUTPUT%"=="1" call :remove_dir "output" || exit /b 1
if "%CLEAN_VENV%"=="1" call :remove_dir ".venv" || exit /b 1

echo.
echo Done.
if "%CLEAN_DIST%"=="0" echo Kept dist\. Use --dist to remove packaged exe files.
if "%CLEAN_OUTPUT%"=="0" echo Kept output\. Use --output to remove local SQLite data.
if "%CLEAN_VENV%"=="0" echo Kept .venv\. Use --venv to remove the local Python environment.
exit /b 0

:remove_dir
if exist "%~1" (
    echo Removing %~1
    rmdir /s /q "%~1"
    if errorlevel 1 (
        echo Failed to remove %~1
        exit /b 1
    )
) else (
    echo Skipping %~1
)
exit /b 0

:help
echo Usage:
echo   scripts\clean_workspace.bat
echo   scripts\clean_workspace.bat --dist
echo   scripts\clean_workspace.bat --output
echo   scripts\clean_workspace.bat --venv
echo   scripts\clean_workspace.bat --all
echo.
echo Default cleanup keeps dist\, output\, and .venv\.
exit /b 0
