@echo off
REM ASCII only: cmd garbles Thai text inside .bat files.
REM All Thai messages live in tools\msg\*.txt and are shown with "type".
chcp 65001 >nul
cd /d "%~dp0"
title Setup - OMR Grading
setlocal

type "tools\msg\install_start.txt"
echo.

REM ----------------------------------------------------------------
REM 1) Find a working Python.
REM    "python" on PATH is tried first, but on many machines it is the
REM    Microsoft Store stub (prints "Python was not found"), or Python was
REM    installed without ticking "Add python.exe to PATH". So also try the
REM    py launcher and the folders the installer uses by default.
REM ----------------------------------------------------------------
set "PY="
set "PYANY="

REM Ask the py launcher for 3.14 first, so 3.14 wins even when an older
REM Python sits earlier on PATH.
for /f "delims=" %%p in ('py -3.14 -c "import sys; print(sys.executable)" 2^>nul') do call :probe "%%p"
call :probe "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
call :probe python
call :probe py
for /f "delims=" %%p in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\python.exe" 2^>nul') do call :probe "%%p"
for /f "delims=" %%p in ('dir /b /s "%ProgramFiles%\Python*\python.exe" 2^>nul') do call :probe "%%p"
for /f "delims=" %%p in ('dir /b /s "C:\Python*\python.exe" 2^>nul') do call :probe "%%p"

REM Prefer the tested range 3.11-3.14 (PY); otherwise take any 3.11+ (PYANY).
if not defined PY if defined PYANY set "PY=%PYANY%"
if not defined PY goto nopython

echo.
for /f "tokens=*" %%v in ('%PY% --version') do echo   %%v
echo.

REM ----------------------------------------------------------------
REM 2) Prepare .venv. An existing one can be unusable: a .venv copied
REM    from another computer still points at that computer's Python.
REM ----------------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "pass" >nul 2>&1
    if errorlevel 1 (
        type "tools\msg\install_fixvenv.txt"
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    type "tools\msg\install_venv.txt"
    %PY% -m venv .venv
    if errorlevel 1 goto failed
)

REM ----------------------------------------------------------------
REM 3) Install the libraries.
REM    YOLO (ultralytics + torch) has no build for the newest Python
REM    releases yet. It is optional: without it the system still grades
REM    normally, it only skips the extra "please double-check" hints.
REM    So retry without it instead of failing the whole setup.
REM ----------------------------------------------------------------
type "tools\msg\install_wait.txt"
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    type "tools\msg\install_noyolo.txt"
    echo.
    ".venv\Scripts\python.exe" -m pip install -r tools\requirements-core.txt
    if errorlevel 1 goto failed
)

REM ----------------------------------------------------------------
REM 4) Verify the libraries really import before saying "done".
REM ----------------------------------------------------------------
".venv\Scripts\python.exe" -c "import cv2, imutils, skimage, scipy, streamlit, pandas, openpyxl, pillow_heif, reportlab" >nul 2>&1
if errorlevel 1 goto failed

echo.
type "tools\msg\install_done.txt"
echo.
pause
exit /b 0

REM ----------------------------------------------------------------
REM :probe <command> - keep the first interpreter that runs and is 3.11+
REM   PY    = first one in the tested range 3.11-3.14
REM   PYANY = first usable one of any version 3.11+
REM ----------------------------------------------------------------
:probe
if defined PY exit /b 0
set "CAND=%~1"
"%CAND%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
if not defined PYANY set "PYANY="%CAND%""
"%CAND%" -c "import sys; sys.exit(0 if sys.version_info < (3, 15) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set "PY="%CAND%""
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
