@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   UI AI Automation Setup
echo ==========================================
echo.

REM --- Find Python ---
set "PYTHON_CMD="
python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
    echo ERROR: Python not found on PATH. Install Python 3.12 and re-run.
    pause
    exit /b 1
)
echo [1/5] Python found:
%PYTHON_CMD% --version

REM --- Create venv if missing ---
if not exist ".venv\Scripts\python.exe" (
    echo [2/5] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/5] Virtual environment already exists
)

REM --- Upgrade pip ---
echo [3/5] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

REM --- Install dependencies ---
echo [4/5] Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo       Installing Playwright Chromium...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo ERROR: Playwright Chromium installation failed.
    pause
    exit /b 1
)

REM --- Verify key imports ---
echo       Verifying...
".venv\Scripts\python.exe" -c "import flask; print('       Flask: OK')"
".venv\Scripts\python.exe" -c "import docx; print('       python-docx: OK')"
".venv\Scripts\python.exe" -c "import dotenv; print('       python-dotenv: OK')"
".venv\Scripts\python.exe" -c "from playwright.sync_api import sync_playwright; print('       Playwright: OK')"

REM --- Create shortcut ---
echo [5/5] Creating desktop shortcut...
".venv\Scripts\python.exe" create_shortcut.py
if errorlevel 1 (
    echo WARNING: Shortcut creation failed. App still works via launch_dashboard.vbs.
)

echo.
echo ==========================================
echo   Setup complete
echo ==========================================
echo.
echo Launch "UI AI Automation" from your Desktop,
echo or double-click launch_dashboard.vbs
echo.
pause