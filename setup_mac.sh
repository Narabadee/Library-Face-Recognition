#!/bin/bash

# Face Scanner - Mac Setup Script
# This script is called by START_MAC.command

# Change to the directory where this script lives
cd "$(dirname "$0")"

echo ""
echo "=================================================="
echo "  Face Scanner - Setup (macOS)"
echo "=================================================="
echo "  Running from: $(pwd)"
echo "=================================================="
echo ""

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found!"
    echo "  Please install it from python.org or using 'brew install python'"
    echo ""
    return 1 2>/dev/null || exit 1
fi

# Get Python version
PY_VER=$(python3 --version | cut -d' ' -f2)
PY_MAJOR=$(echo "$PY_VER" | cut -d'.' -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d'.' -f2)
echo "[OK] Detected Python $PY_VER"

# Check version (Require 3.9+)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
    echo "[ERROR] Python $PY_VER is too old. Need at least Python 3.9."
    return 1 2>/dev/null || exit 1
fi

if [ "$PY_MINOR" -gt 12 ]; then
    echo ""
    echo "[NOTE] You are using a very new Python version."
    echo "  Most things will work fine, but some AI libraries might be experimental."
    echo ""
fi

# 1.5. Install uv (fast package manager)
UV_CMD=""
if command -v uv &> /dev/null; then
    UV_CMD="uv"
    echo "[OK] uv is already installed. Packages will install fast!"
elif [ -f "$HOME/.local/bin/uv" ]; then
    UV_CMD="$HOME/.local/bin/uv"
    echo "[OK] uv found. Packages will install fast!"
else
    echo "[INFO] Installing uv (fast package manager - first-time only)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
    if [ -f "$HOME/.local/bin/uv" ]; then
        UV_CMD="$HOME/.local/bin/uv"
        echo "[OK] uv installed. Packages will install up to 10x faster!"
    else
        echo "[WARNING] Could not install uv. Using pip instead (standard speed)."
    fi
fi

# 2. Handle Virtual Environment
if [ -d ".venv" ]; then
    if [ ! -f ".venv/bin/activate" ]; then
        echo "[STEP 1/4] Virtual environment is broken. Rebuilding..."
        rm -rf .venv
    else
        echo "[STEP 1/4] Virtual environment exists. OK."
    fi
fi

if [ ! -d ".venv" ]; then
    echo "[STEP 1/4] Creating virtual environment..."
    if [ -n "$UV_CMD" ]; then
        "$UV_CMD" venv .venv --python python3
    else
        python3 -m venv .venv
    fi
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment!"
        return 1 2>/dev/null || exit 1
    fi
    echo "[OK] Virtual environment created."
fi

# 3. Activate
echo "[STEP 2/4] Activating environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate environment."
    echo "  Deleting broken .venv, please run this script again."
    rm -rf .venv
    return 1 2>/dev/null || exit 1
fi
echo "[OK] Environment activated."

# 4. Upgrade Pip (skipped when using uv)
if [ -z "$UV_CMD" ]; then
    echo "[STEP 3/4] Upgrading pip..."
    pip install --upgrade pip --quiet
    echo "[OK] pip upgraded."
else
    echo "[STEP 3/4] Skipping pip upgrade (uv handles this automatically)."
fi

# 5. Install Dependencies
echo ""
echo "[STEP 4/4] Installing dependencies..."
if [ -n "$UV_CMD" ]; then
    echo "  Using uv for fast installation. This should only take about a minute!"
else
    echo "  This might take a few minutes. Please be patient."
fi
echo ""

if [ -n "$UV_CMD" ]; then
    "$UV_CMD" pip install -r requirements.txt
else
    pip install -r requirements.txt
fi

if [ $? -ne 0 ]; then
    echo ""
    echo "=================================================="
    echo "  [ERROR] Dependency installation failed!"
    echo "=================================================="
    echo ""
    echo "  If you're on Apple Silicon (M1/M2/M3), try:"
    echo "    pip install onnxruntime-silicon"
    echo ""
    return 1 2>/dev/null || exit 1
fi

# 6. Check for Apple Silicon
ARCH=$(uname -m)
if [ "$ARCH" == "arm64" ]; then
    echo "[INFO] Apple Silicon Mac detected."
fi

echo ""
echo "=================================================="
echo "  [OK] Setup Complete!"
echo "=================================================="
echo ""
