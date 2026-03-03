# Face Recognition System - Setup Guide

## System Requirements

- **OS**: Windows 10/11 or Linux (Ubuntu 20.04+)
- **Python**: 3.10 or higher
- **RAM**: 8GB minimum (16GB recommended)
- **Camera**: USB webcam or RTSP IP camera

---

## Installation

### 1. Create Virtual Environment

```bash
cd c:\Users\narab\OneDrive\Desktop\IoT
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

> [!NOTE]
> First run will download InsightFace models (~300MB). This happens automatically on first use.

### 3. Verify Installation

```bash
python -c "from insightface.app import FaceAnalysis; print('InsightFace OK')"
python -c "import cv2; print('OpenCV OK')"
```

---

## Configuration

### Camera Setup

Edit `config.py` to set your camera URLs:

```python
class Config:
    # For RTSP cameras
    ENTRY_CAMERA_URL = 'rtsp://username:password@192.168.1.100:554/stream'
    EXIT_CAMERA_URL = 'rtsp://username:password@192.168.1.101:554/stream'
    
    # For USB webcam (uncomment)
    # ENTRY_CAMERA_URL = 0  # First USB camera
    # EXIT_CAMERA_URL = 1   # Second USB camera
```

### Recognition Thresholds

Edit `services/face_config.py`:

```python
# Lower = more matches (higher false positive risk)
# Higher = fewer matches (may miss valid users)
SIMILARITY_THRESHOLD: float = 0.45  # Default: 0.45

# Face quality settings
MIN_BLUR_SCORE: float = 50.0        # Lower for RTSP cameras
MIN_FACE_SIZE: int = 80             # Minimum face pixels
```

---

## Running the Application

```bash
cd c:\Users\narab\OneDrive\Desktop\IoT
python app.py
```

Access at: http://localhost:5000

---

## Migrating from DeepFace

Since this update replaces DeepFace with InsightFace:

1. **Backup existing data**:
   ```bash
   copy data\faces data\faces_backup
   ```

2. **Clear old embeddings**:
   ```bash
   del data\faces\embeddings\*.npy
   ```

3. **Re-register all users** through the web interface

---

## Troubleshooting

### "InsightFace not installed"
```bash
pip uninstall insightface onnxruntime
pip install insightface==0.7.3 onnxruntime==1.16.3
```

### "Model download failed"
- Check internet connection
- Models are cached in: `~/.insightface/models/`
- Manual download: https://github.com/deepinsight/insightface/releases

### "No face detected"
- Ensure good lighting
- Face should be at least 80x80 pixels
- Look directly at camera
- Avoid blurry images

### "Recognition fails / Low accuracy"
1. Re-register with better image quality
2. Add multiple enrollment images (3-5 recommended)
3. Lower threshold in `face_config.py` (try 0.40)

---

## Performance Tuning

### For CPU (default)
```python
# In face_config.py
USE_GPU: bool = False
NUM_THREADS: int = 4  # Match your CPU cores
```

### For GPU (NVIDIA)
```bash
pip install onnxruntime-gpu
```
```python
# In face_config.py
USE_GPU: bool = True
```

Expected performance:
- CPU: 15-25 FPS
- GPU: 40-60 FPS
