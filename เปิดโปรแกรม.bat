@echo off
REM ASCII only. Thai messages live in tools\msg\*.txt (see the setup .bat for why).
chcp 65001 >nul
cd /d "%~dp0"
title OMR Grading

if not exist ".venv\Scripts\python.exe" goto notready

REM A .venv copied from another computer still points at that computer's
REM Python, so check that it actually runs before trying to start the app.
".venv\Scripts\python.exe" -c "import streamlit" >nul 2>&1
if errorlevel 1 goto notready

type "tools\msg\run_start.txt"
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
echo.
type "tools\msg\run_stopped.txt"
pause
exit /b 0

:notready
type "tools\msg\run_notready.txt"
echo.
pause
exit /b 1
