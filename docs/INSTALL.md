# Face Scanner - Installation Guide

## 📋 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.9 | 3.11 or 3.12 |
| RAM | 4 GB | 8 GB |
| Disk Space | 500 MB | 1 GB |
| Webcam | USB or Built-in | Any |
| Internet | Required for first setup | - |

> **Note:** Python 3.13 also works but some AI libraries may show warnings.

---

## 🪟 Windows Installation

### One-Click Install (Recommended)
1. **Unzip** the project folder to your desired location (e.g., Desktop).
2. **Double-click** `RUN_WINDOWS.bat`.
3. **Wait for the setup** — you will see progress like this:
   ```
   [OK] Detected Python 3.12
   [STEP 1/4] Creating virtual environment...
   [STEP 2/4] Activating environment...
   [STEP 3/4] Upgrading pip...
   [STEP 4/4] Installing dependencies...
   ```
4. **First run takes 3-10 minutes** depending on your internet speed (downloads ~500MB of AI libraries).
5. **Done!** The app starts at `http://localhost:5000` — open this URL in your browser.

> The window will **never close by itself**. If something goes wrong, you'll see the error on screen.

#### What if Python is missing?
- The script will detect that Python is not installed.
- It will automatically download and install Python 3.12 for you.
- After installation, it restarts itself and continues the setup.

### Manual Install (Advanced)
```powershell
# 1. Install Python 3.9-3.12 from python.org
# 2. Open PowerShell in the project folder
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## 🍎 macOS Installation

### One-Click Install (Recommended)
1. **Unzip** the project folder.
2. **Right-click** `START_MAC.command` → **Open** (first time only, to bypass Gatekeeper).
3. **Allow permissions** if macOS asks about Terminal or Camera access.
4. **Wait for the setup** — same progress indicators as Windows.
5. **Done!** The app starts at `http://localhost:5000`.

> On first run, macOS may ask for Camera permissions. Click **Allow**.

### Manual Install (Advanced)
```bash
# 1. Install Python 3.9+ from python.org or Homebrew
brew install python
# 2. Open Terminal in the project folder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

### Apple Silicon (M1/M2/M3) Note
The standard `onnxruntime` works on Apple Silicon. If you encounter issues:
```bash
pip install onnxruntime-silicon
```

---

## 📱 Mobile Access

1. Connect your laptop to **Wi-Fi**.
2. Make sure your phone/tablet is on the **same Wi-Fi**.
3. Look at the terminal — it shows a Network URL like `http://192.168.1.XX:5000`.
4. Open that URL in your phone's browser.

---

## 🧹 Sharing the Project

To send the project to a friend:
1. **Run** `CLEAN_PROJECT.bat` (Windows) to remove the large `.venv` folder and caches.
2. **Zip** the folder and send it.
3. Your friend just needs to double-click `RUN_WINDOWS.bat` or `START_MAC.command` — everything rebuilds automatically.

---

## 🚀 Quick Reference

| Action | Windows | Mac |
|--------|---------|-----|
| Start App | Double-click `RUN_WINDOWS.bat` | Double-click `START_MAC.command` |
| Clean for Sharing | `CLEAN_PROJECT.bat` | Delete `.venv` folder manually |
| Manual Start | `.venv\Scripts\activate` → `python app.py` | `source .venv/bin/activate` → `python3 app.py` |

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| Script window closes instantly | Fixed in latest version — update `RUN_WINDOWS.bat` |
| "Python not found" | Install from [python.org](https://python.org/downloads/) or let the script auto-install |
| "Failed to activate environment" | Delete the `.venv` folder and run the launcher again |
| "Module not found" | Delete `.venv` folder, run launcher again |
| Camera not working | Check permissions in System Settings (Mac) or Privacy Settings (Windows) |
| Slow first start | Normal — AI models are loading (~30 seconds) |
| Dependencies fail on Python 3.13 | The launcher will offer to install Python 3.12 for you |
