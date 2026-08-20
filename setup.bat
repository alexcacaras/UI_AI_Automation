@echo off
setlocal

cd /d "%~dp0"

echo ==========================================
echo   UI AI Automation Setup
echo ==========================================
echo.

REM ------------------------------------------
REM 1. Check Python
REM ------------------------------------------
REM ------------------------------------------
REM Find Python
REM ------------------------------------------

set "PYTHON_CMD="

REM Try normal python command
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :python_found
)

REM Try Windows Python launcher
py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :python_found
)

REM If .venv already exists, use its Python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    goto :venv_already_exists
)

echo ERROR: Python could not be located.
echo.
echo Python may be installed but not available on the Windows PATH.
echo.
pause
exit /b 1


:python_found

echo [1/7] Python found:
%PYTHON_CMD% --version


REM ------------------------------------------
REM Create virtual environment
REM ------------------------------------------

if not exist ".venv\Scripts\python.exe" (
    echo [2/7] Creating virtual environment...

    %PYTHON_CMD% -m venv .venv

    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/7] Virtual environment already exists
)

goto :continue_setup


:venv_already_exists

echo [1/7] Using existing virtual environment
echo [2/7] Virtual environment already exists


:continue_setup

echo [1/7] Python found

REM ------------------------------------------
REM 2. Create virtual environment
REM ------------------------------------------

if not exist ".venv\Scripts\python.exe" (
    echo [2/7] Creating virtual environment...
    python -m venv .venv

    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/7] Virtual environment already exists
)

REM ------------------------------------------
REM 3. Upgrade pip
REM ------------------------------------------

echo [3/7] Updating pip...

".venv\Scripts\python.exe" -m pip install --upgrade pip

if errorlevel 1 (
    echo ERROR: Could not update pip.
    pause
    exit /b 1
)

REM ------------------------------------------
REM 4. Install Python dependencies
REM ------------------------------------------

echo [4/7] Installing Python dependencies...

".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Python dependency installation failed.
    pause
    exit /b 1
)

REM ------------------------------------------
REM 5. Install Playwright Chromium
REM ------------------------------------------

echo [5/7] Installing Playwright Chromium...

".venv\Scripts\python.exe" -m playwright install chromium

if errorlevel 1 (
    echo ERROR: Playwright Chromium installation failed.
    pause
    exit /b 1
)

REM ------------------------------------------
REM 6. Build React dashboard
REM ------------------------------------------

echo [6/7] Building dashboard...

where npm >nul 2>&1

if errorlevel 1 (
    echo ERROR: npm / Node.js was not found.
    echo Please install Node.js LTS and run setup again.
    pause
    exit /b 1
)

pushd dashboard

call npm install

if errorlevel 1 (
    echo ERROR: npm install failed.
    popd
    pause
    exit /b 1
)

call npm run build

if errorlevel 1 (
    echo ERROR: dashboard build failed.
    popd
    pause
    exit /b 1
)

popd

REM ------------------------------------------
REM 7. Create shortcut
REM ------------------------------------------

echo [7/7] Creating desktop shortcut...

".venv\Scripts\python.exe" create_shortcut.py

if errorlevel 1 (
    echo WARNING: Shortcut creation failed.
    echo The application itself is still installed.
)

echo.
echo ==========================================
echo   Setup complete
echo ==========================================
echo.
echo You can now launch:
echo   UI AI Automation
echo from your Desktop.
echo.
pause