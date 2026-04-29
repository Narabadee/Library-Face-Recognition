@echo off
chcp 65001 > nul
set PYTHONUTF8=1
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
echo.
echo ==================================================
echo   [OK] Python 3.12 installed successfully!
echo ==================================================
echo.
echo   IMPORTANT: You must now CLOSE this window completely,
echo   then DOUBLE-CLICK RUN_WINDOWS.bat again to start.
echo.
echo   (Windows needs a fresh terminal to see the new Python.)
echo   Do NOT click restart inside this window - it will not work.
echo.
pause
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
    "!UV_CMD!" pip install -r requirements.txt > install_log.txt 2>&1
) else (
    pip install -r requirements.txt > install_log.txt 2>&1
)
if !errorlevel! neq 0 (
    echo.
    echo ==================================================
    echo   [ERROR] Dependency installation failed!
    echo   Actual error:
    echo ==================================================
    echo.
    type install_log.txt
    echo.
    :: Test if PyPI is reachable
    curl -s --max-time 5 https://pypi.org >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo   [NETWORK] Cannot reach PyPI ^(pypi.org^).
        echo   Your internet or firewall may be blocking package downloads.
    )
    echo.
    echo   Full log saved to: "%cd%\install_log.txt"
    echo.
    goto :FAIL
)
if exist install_log.txt del /f /q install_log.txt

echo.
echo ==================================================
echo   [OK] All dependencies installed successfully!
echo ==================================================
echo.

:: ---- Step 4.5: Download AI models (first time only) ----
echo [STEP *] Checking AI models (first-time may download ~275MB)...
python -c "from services.model_manager import ensure_models; ok = ensure_models(); exit(0 if ok else 1)"
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Failed to download AI models!
    echo    Please check your internet connection and try again.
    echo.
    goto :FAIL
)
echo [OK] AI models ready.
echo.

:: ---- Step 4.6: Check PostgreSQL and Database ----
echo [STEP *] Checking PostgreSQL installation...
set "PSQL_CMD="
where psql >nul 2>&1
if !errorlevel! equ 0 (
    set "PSQL_CMD=psql"
    goto :FOUND_PSQL
)

for /d %%i in ("%ProgramFiles%\PostgreSQL\*") do (
    if exist "%%i\bin\psql.exe" (
        set "PSQL_CMD=%%i\bin\psql.exe"
        goto :FOUND_PSQL
    )
)

echo.
echo ==================================================
echo   [ERROR] PostgreSQL is not installed or not found.
echo   Please install PostgreSQL ^(version 12 or higher recommended^).
echo   IMPORTANT: During installation, set the password for 'postgres' to: 1234
echo.
echo   Download here: https://www.postgresql.org/download/windows/
echo ==================================================
echo.
goto :FAIL

:FOUND_PSQL
echo [OK] PostgreSQL found.
echo [STEP *] Checking database 'library_db'...
set PGPASSWORD=1234
"!PSQL_CMD!" -U postgres -p 5432 -h localhost -lq 2>nul | findstr /i "library_db" >nul
if !errorlevel! equ 0 (
    echo [OK] Database 'library_db' already exists.
) else (
    echo [INFO] Database 'library_db' not found. Creating it...
    "!PSQL_CMD!" -U postgres -p 5432 -h localhost -c "CREATE DATABASE library_db;" >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo ==================================================
        echo   [ERROR] Failed to create database 'library_db'.
        echo   Make sure PostgreSQL service is running.
        echo   Make sure the password for 'postgres' user is exactly: 1234
        echo ==================================================
        echo.
        goto :FAIL
    )
    echo [OK] Database 'library_db' created successfully.
)
set PGPASSWORD=
echo.

:: ---- Step 4.7: Check FFmpeg (required for RTSP) ----
echo [STEP *] Checking FFmpeg installation...
where ffmpeg >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] FFmpeg found in PATH.
    goto :FFMPEG_OK
)

:: Check common WinGet location for Gyan.FFmpeg
set "FFMPEG_FOUND=0"
for /d %%d in ("%USERPROFILE%\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
    for /d %%f in ("%%d\ffmpeg-*") do (
        if exist "%%f\bin\ffmpeg.exe" (
            echo [OK] FFmpeg found in WinGet folder.
            set "FFMPEG_FOUND=1"
            goto :FFMPEG_OK
        )
    )
)

if "!FFMPEG_FOUND!"=="0" (
    echo [WARNING] FFmpeg not found! Required for camera streaming.
    echo [INFO] Attempting to install FFmpeg via winget...
    winget --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] winget not found. Please install FFmpeg manually from https://ffmpeg.org/
        goto :FAIL
    )
    
    winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    if !errorlevel! equ 0 (
        echo.
        echo ==================================================
        echo   [OK] FFmpeg installed successfully!
        echo   IMPORTANT: Please CLOSE this window and RESTART
        echo   RUN_WINDOWS.bat to apply system changes.
        echo ==================================================
        pause
        exit /b
    )
    echo [ERROR] FFmpeg installation failed.
    goto :FAIL
)

:FFMPEG_OK
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
echo.
echo Press any key to close this window...
pause >nul

:END
echo.
echo Press any key to close this window...
pause >nul
