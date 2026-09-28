@echo off
REM ASCII only: cmd garbles Thai text inside .bat files.
REM All Thai messages live in tools\msg\*.txt and are shown with "type".
chcp 65001 >nul
cd /d "%~dp0"
title Setup - OMR Grading

type "tools\msg\install_start.txt"
echo.

python --version >nul 2>&1
if errorlevel 1 goto nopython
for /f "tokens=*" %%v in ('python --version') do echo   %%v
echo.

if not exist ".venv\Scripts\python.exe" (
    type "tools\msg\install_venv.txt"
    python -m venv .venv
    if errorlevel 1 goto failed
)

type "tools\msg\install_wait.txt"
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
type "tools\msg\install_done.txt"
echo.
pause
exit /b 0

:nopython
type "tools\msg\no_python.txt"
echo.
pause
exit /b 1

:failed
echo.
type "tools\msg\install_failed.txt"
echo.
pause
exit /b 1
