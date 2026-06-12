@echo off
setlocal
set "DIR=%~dp0"
set "PATH=%DIR%venv\Scripts;%PATH%"
if not exist "%DIR%venv\Scripts\python.exe" (
    echo Venv not found! Run setup.bat first.
    pause
    exit /b 1
)
"%DIR%venv\Scripts\python.exe" "%DIR%SpDL.py" %*
if %errorlevel% neq 0 pause
