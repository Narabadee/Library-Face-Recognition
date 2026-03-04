@echo off
setlocal enabledelayedexpansion

:: IMPORTANT: Change to the directory where this script lives
cd /d "%~dp0"

echo ==================================================
echo   Face Scanner - Zero-Setup Launcher [Windows]
echo ==================================================
echo   Running from: %cd%
echo ==================================================
echo.

:: ---- Step 0: Check for Python ----
set "PY_CMD="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :FOUND_PYTHON
)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py"
    goto :FOUND_PYTHON
)

echo [WARNING] Python is NOT installed!
goto :INSTALL_PYTHON

:FOUND_PYTHON
:: Get version info
for /f "tokens=2" %%v in ('!PY_CMD! --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

echo [OK] Detected Python !PY_VER!

:: Check minimum version (Require 3.9+)
if !PY_MAJOR! lss 3 goto :OLD_PYTHON
if !PY_MAJOR! gtr 3 goto :PYTHON_OK
if !PY_MINOR! lss 9 goto :OLD_PYTHON
if !PY_MINOR! leq 12 goto :PYTHON_OK

:: Python 3.13+ note
echo.
echo [NOTE] You are using a very new Python version.
echo    Most things will work fine, but some AI libraries might be experimental.
echo.
goto :PYTHON_OK

:OLD_PYTHON
echo [WARNING] Your Python version is too old for the AI libraries.
echo    We need at least Python 3.9.
goto :INSTALL_PYTHON

:INSTALL_PYTHON
echo Downloading stable Python 3.12 for you...
echo.
curl -o python_installer.exe https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Failed to download Python installer!
    echo    Please check your internet connection and try again.
    echo.
    goto :FAIL
)
echo Installing Python 3.12... Please wait, this might take a minute.
start /wait python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
if exist python_installer.exe del /f /q python_installer.exe
echo [OK] Python 3.12 installed successfully!
echo [INFO] Restarting script to apply changes...
echo.
pause
start "" "%~f0"
exit /b

:PYTHON_OK

:: ---- Step 0.5: Install uv (fast package installer) ----
set "UV_CMD="
where uv >nul 2>&1
if %errorlevel% equ 0 (
    set "UV_CMD=uv"
    echo [OK] uv is already installed. Packages will install fast!
    goto :FOUND_UV
)
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV_CMD=%USERPROFILE%\.local\bin\uv.exe"
    echo [OK] uv found. Packages will install fast!
    goto :FOUND_UV
)
echo [INFO] Installing uv (fast package manager - first-time only)...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >nul 2>&1
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV_CMD=%USERPROFILE%\.local\bin\uv.exe"
    echo [OK] uv installed. Packages will install up to 10x faster!
    goto :FOUND_UV
)
echo [WARNING] Could not install uv. Using pip instead (standard speed).
:FOUND_UV

:: ---- Step 1: Create Virtual Environment ----
if exist .venv (
    if not exist ".venv\Scripts\activate.bat" (
        echo [STEP 1/4] Virtual environment is broken. Rebuilding...
        rmdir /s /q .venv
    ) else (
        echo [STEP 1/4] Virtual environment exists. OK.
    )
)
if not exist .venv (
    echo [STEP 1/4] Creating virtual environment...
    if defined UV_CMD (
        "!UV_CMD!" venv .venv --python !PY_CMD!
    ) else (
        !PY_CMD! -m venv .venv
    )
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment!
        goto :FAIL
    )
    echo [OK] Virtual environment created.
)

:: ---- Step 2: Activate ----
echo [STEP 2/4] Activating environment...
call ".venv\Scripts\activate.bat"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to activate environment.
    echo    Deleting broken .venv, please run this script again.
    rmdir /s /q .venv
    goto :FAIL
)
echo [OK] Environment activated.

:: ---- Step 3: Upgrade pip (skipped when using uv) ----
if not defined UV_CMD (
    echo [STEP 3/4] Upgrading pip...
    python -m pip install --upgrade pip >nul 2>&1
    echo [OK] pip upgraded.
) else (
    echo [STEP 3/4] Skipping pip upgrade ^(uv handles this automatically^).
)

:: ---- Step 4: Install dependencies ----
echo.
echo [STEP 4/4] Installing dependencies...
if defined UV_CMD (
    echo    Using uv for fast installation. This should only take about a minute!
) else (
    echo    This might take a few minutes. Please be patient.
)
echo.
if defined UV_CMD (
    "!UV_CMD!" pip install -r requirements.txt
) else (
    pip install -r requirements.txt
)
if !errorlevel! neq 0 (
    echo.
    echo ==================================================
    echo   [ERROR] Dependency installation failed!
    echo ==================================================
    echo.
    echo   This often happens if your Python version is too new.
    echo.
    set /p "fix=Install stable Python 3.12 instead? [y/n]: "
    if /i "!fix!"=="y" goto :INSTALL_PYTHON
    goto :FAIL
)

echo.
echo ==================================================
echo   [OK] All dependencies installed successfully!
echo ==================================================
echo.

:: ---- Step 5: System check ----
echo Running quick system check...
python check_env.py
echo.

:: ---- Step 6: Launch app ----
echo ==================================================
echo   Starting Face Scanner Library System...
echo ==================================================
echo.
python serve.py

echo.
echo ==================================================
echo   Application has stopped.
echo ==================================================
goto :END

:FAIL
echo.
echo ==================================================
echo   Setup did NOT complete successfully.
echo   Review the errors above for details.
echo ==================================================

:END
echo.
echo Press any key to close this window...
pause >nul
