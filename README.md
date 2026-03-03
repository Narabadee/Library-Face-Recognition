# Face Scanner Library System

Flask-based face recognition system for university library attendance tracking with **advanced AI-powered recognition**.

## Features

- **ArcFace Recognition** - 512-dimensional embeddings for high accuracy
- **80% Confidence Threshold** - Strict matching to prevent false positives
- **Automatic Face Alignment** - Handles tilted/rotated faces
- **ROI Detection** - Focus scanning on specific screen region
- **Motion Detection** - Trigger scans only when movement detected
- **Realtime Scanning** - Continuous automatic check-in/check-out
- **USB Webcam Support** - Works with standard webcams

## Setup

```bash
pip install -r requirements.txt
python app.py
```

## Usage

1. Open http://localhost:5000
2. **Register** - Capture student faces at `/register`
3. **Scan** - Start realtime scanning at `/scan`
   - Toggle ROI to focus on specific area
   - Enable motion detection for efficiency
4. **History** - View attendance logs at `/history`

## Scan Settings

| Setting | Description |
|---------|-------------|
| ROI Mode | Darkens outside area, scans only within box |
| Motion Detection | Only scans when movement crosses virtual line |
| Cooldown | 4 seconds between scans to prevent duplicates |
