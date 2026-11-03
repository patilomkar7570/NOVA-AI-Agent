@echo off
setlocal EnableExtensions

rem NOVA Alpha 0.5 portable startup.
rem Place this file in the project root, beside api.py and agent.py.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo ==========================================
echo          NOVA ALPHA 0.5 STARTUP
echo ==========================================
echo Project: "%ROOT%"
echo.

if not exist "%ROOT%\api.py" (
    echo ERROR: api.py was not found beside this batch file.
    pause
    exit /b 1
)

if not exist "%ROOT%\agent.py" (
    echo ERROR: agent.py was not found beside this batch file.
    pause
    exit /b 1
)

if not exist "%ROOT%\frontend\package.json" (
    echo ERROR: frontend\package.json was not found.
    pause
    exit /b 1
)

rem Prefer this project's virtual environment when one exists.
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python was not found. Install Python and make sure python.exe is on PATH,
        echo or create the project's .venv folder and install requirements.txt into it.
        pause
        exit /b 1
    )
    for /f "delims=" %%P in ('where python 2^>nul') do (
        set "PYTHON_EXE=%%P"
        goto :python_found
    )
)
:python_found

where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm was not found. Install Node.js LTS and reopen this terminal.
    pause
    exit /b 1
)

where ollama >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama was not found. Install Ollama for Windows and reopen this terminal.
    pause
    exit /b 1
)

echo Python: "%PYTHON_EXE%"
echo.

rem Start Ollama only when its local API is not already responding.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Starting Ollama...
    start "NOVA - Ollama" cmd /k "ollama serve"
) else (
    echo Ollama is already running.
)

rem Start the Python backend.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Starting NOVA backend...
    start "NOVA - Backend" cmd /k "cd /d ""%ROOT%"" && ""%PYTHON_EXE%"" -u api.py"
) else (
    echo NOVA backend is already running.
)

rem Start the Vite frontend if its normal development port is not responding.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Starting NOVA frontend...
    start "NOVA - Frontend" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev -- --host 127.0.0.1"
) else (
    echo NOVA frontend is already running on port 5173.
)

echo.
echo Startup commands sent.
echo Open the frontend URL shown in the NOVA Frontend window, normally:
echo http://127.0.0.1:5173
echo.
echo For local Voice Mode, open Voicebox separately and wait for its
echo local server to become ready at http://127.0.0.1:17493.
echo Keep the backend and frontend windows open while using NOVA.
echo.
pause
