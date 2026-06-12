@echo off
title SpotDL GUI Setup
cd /d "%~dp0"

echo ==============================
echo  SpotDL GUI - Setup (Windows)
echo ==============================

REM --- Check Python ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 is not installed or not on PATH.
    echo Download it from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv venv

echo [2/3] Installing dependencies...
call venv\Scripts\activate
pip install --upgrade pip -q
pip install -r requirements.txt

echo [3/3] Done!
echo.
echo To run the app:
echo   Double-click start.bat
echo.
pause
