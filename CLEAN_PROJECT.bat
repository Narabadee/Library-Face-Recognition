@echo off
setlocal

:: Change to the directory where this script lives
cd /d "%~dp0"

echo ==================================================
echo   🧹 Face Scanner - Project Cleanup Tool
echo ==================================================
echo.
echo This script will reduce folder size for sharing by removing:
echo 1. Virtual Environment (.venv) - To be rebuilt on target system.
echo 2. Python Cache Folders (__pycache__)
echo 3. Redundant AI Models
echo.
set /p confirm="Are you sure you want to clean the project? (y/n): "
if /i "%confirm%" neq "y" exit /b

echo.
echo [1/3] 🗑️ Deleting .venv (This might take a few seconds)...
if exist .venv rmdir /s /q .venv

echo [2/3] 🗑️ Deleting cache folders...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if exist .pytest_cache rmdir /s /q .pytest_cache

echo [3/3] 🗑️ Deleting redundant large models...
if exist "models\1k3d68.onnx" del /f /q "models\1k3d68.onnx"
if exist "models\2d106det.onnx" del /f /q "models\2d106det.onnx"
if exist "models\genderage.onnx" del /f /q "models\genderage.onnx"
if exist "models\buffalo_l" rmdir /s /q "models\buffalo_l"

echo.
echo --------------------------------------------------
echo   🔒 PRIVACY CHECK
echo --------------------------------------------------
set /p wipe="Do you want to WIPE all your registered faces, students, and camera configs? (y/n): "
if /i "%wipe%"=="y" (
    echo 🗑️ Wiping sensitive data...
    if exist "data\faces" rmdir /s /q "data\faces"
    mkdir "data\faces"
    mkdir "data\faces\embeddings"
    mkdir "data\faces\enrollment"
    if exist "data\line_config" rmdir /s /q "data\line_config"
    mkdir "data\line_config"
    if exist "config\zones" rmdir /s /q "config\zones"
    mkdir "config\zones"
    if exist "data\library.db" del /f /q "data\library.db"
    if exist "line_config.json" del /f /q "line_config.json"
    if exist "app.log" del /f /q "app.log"
    if exist "data\*.log" del /f /q "data\*.log"
    echo ✅ Data wiped. Your friend will receive a completely fresh system.
) else (
    echo 📁 Keeping data. Your friend will see your registered students and camera settings.
)

echo.
echo ✨ Done! Your project is now optimized for sharing.
echo.
echo 🚀 Next Steps:
echo 1. Right-click the 'IoT' folder on your desktop.
echo 2. Select 'Compress to ZIP file' (or 'Send to' -> 'Compressed (zipped) folder').
echo 3. Send the ZIP to your friend!
echo.
pause
