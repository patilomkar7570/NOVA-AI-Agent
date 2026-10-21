@echo off
setlocal EnableExtensions
title NOVA AI Agent - One-Click Startup

set "NOVA_ROOT=C:\Users\dudha\OneDrive\Documents\AI-Agent"

echo ============================================
echo       NOVA AI AGENT - ONE-CLICK STARTUP
echo ============================================
echo.
echo Project folder:
echo %NOVA_ROOT%
echo.

if not exist "%NOVA_ROOT%\api.py" (
    echo [ERROR] Cannot find:
    echo "%NOVA_ROOT%\api.py"
    echo.
    echo Check that api.py is inside your AI-Agent folder.
    pause
    exit /b 1
)

if not exist "%NOVA_ROOT%\frontend\package.json" (
    echo [ERROR] Cannot find frontend\package.json.
    echo The frontend folder may be missing or in a different location.
    pause
    exit /b 1
)

if not exist "%NOVA_ROOT%\frontend\node_modules" (
    echo [WARNING] Frontend dependencies are not installed.
    echo Open a terminal in the frontend folder and run: npm install
    echo.
    pause
    exit /b 1
)

echo [1/2] Starting NOVA backend...
if exist "%NOVA_ROOT%\.venv\Scripts\python.exe" (
    start "NOVA Backend" /D "%NOVA_ROOT%" cmd /k ""%NOVA_ROOT%\.venv\Scripts\python.exe" api.py"
) else if exist "%NOVA_ROOT%\venv\Scripts\python.exe" (
    start "NOVA Backend" /D "%NOVA_ROOT%" cmd /k ""%NOVA_ROOT%\venv\Scripts\python.exe" api.py"
) else (
    start "NOVA Backend" /D "%NOVA_ROOT%" cmd /k "python api.py"
)

timeout /t 3 /nobreak >nul

echo [2/2] Starting NOVA frontend...
start "NOVA Frontend" /D "%NOVA_ROOT%\frontend" cmd /k "npm run dev"

echo.
echo Startup commands launched in separate windows.
echo Keep both windows open while testing NOVA.
echo If either window shows an error, copy that error message.
echo.
pause
endlocal
