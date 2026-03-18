#!/bin/bash

# Get the directory where this script is located
cd "$(dirname "$0")"

clear
echo "=================================================="
echo "  Face Scanner - Zero-Setup Launcher (macOS)"
echo "=================================================="
echo "  Running from: $(pwd)"
echo "=================================================="
echo ""

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 NOT found!"
    echo ""
    echo "  To install Python:"
    echo "  1. Go to: https://www.python.org/downloads/"
    echo "  2. Download the 'macOS 64-bit universal2 installer'"
    echo "  3. Run it, then come back and double-click this script again."
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi

# Get Python version
PY_VER=$(python3 --version | cut -d' ' -f2)
PY_MAJOR=$(echo "$PY_VER" | cut -d'.' -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d'.' -f2)

echo "[OK] Detected Python $PY_VER"

# Check version (Require 3.9+)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
    echo "[ERROR] Python $PY_VER is too old. Need at least Python 3.9."
    echo "  Please install Python 3.9 or newer from python.org"
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi

if [ "$PY_MINOR" -gt 12 ]; then
    echo ""
    echo "[NOTE] You are using a very new Python version."
    echo "  Most things will work fine, but some AI libraries might be experimental."
    echo ""
fi

# 2. Setup if needed (broken or missing .venv)
NEEDS_SETUP=false
if [ ! -d ".venv" ]; then
    NEEDS_SETUP=true
elif [ ! -f ".venv/bin/activate" ]; then
    echo "[WARNING] Virtual environment is broken. Will rebuild..."
    rm -rf .venv
    NEEDS_SETUP=true
fi

if [ "$NEEDS_SETUP" = true ]; then
    echo ""
    echo "First time setup detected. Preparing environment..."
    echo ""
    bash setup_mac.sh
    if [ $? -ne 0 ]; then
        echo ""
        echo "=================================================="
        echo "  Setup failed! Review the errors above."
        echo "=================================================="
        echo ""
        read -p "Press any key to exit..."
        exit 1
    fi
fi

# 3. Activate and verify
echo "[OK] Activating environment..."
source .venv/bin/activate

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate environment."
    echo "  Try deleting the .venv folder and running this script again."
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi

# Quick dependency check (quiet mode - only install missing)
# Use uv if available for faster resolution
if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt --quiet 2>/dev/null
elif [ -f "$HOME/.local/bin/uv" ]; then
    "$HOME/.local/bin/uv" pip install -r requirements.txt --quiet 2>/dev/null
else
    pip install -r requirements.txt --quiet 2>/dev/null
fi

# 4. System check
echo ""
echo "Running quick system check..."
python3 check_env.py

# 5. Launch
echo ""
echo "=================================================="
echo "  Starting Face Scanner Library System..."
echo "=================================================="
echo ""
python3 serve.py

# If app exits
echo ""
echo "=================================================="
echo "  Application has stopped."
echo "=================================================="
echo ""
read -p "Press any key to close..."
