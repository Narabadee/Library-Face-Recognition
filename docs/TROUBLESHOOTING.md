# Troubleshooting Guide

## Common Issues and Solutions

---

## Installation Issues

### "ModuleNotFoundError: No module named 'insightface'"

```bash
pip install insightface==0.7.3 onnxruntime==1.16.3
```

### "ONNX Runtime error" or model loading fails

1. Clear model cache:
   ```bash
   # Windows
   rmdir /s %USERPROFILE%\.insightface
   
   # Linux
   rm -rf ~/.insightface
   ```

2. Reinstall ONNX Runtime:
   ```bash
   pip uninstall onnxruntime onnxruntime-gpu
   pip install onnxruntime==1.16.3
   ```

### InsightFace model download stuck

Models are downloaded from GitHub. If blocked:
1. Download manually from: https://github.com/deepinsight/insightface/releases
2. Extract to `~/.insightface/models/buffalo_l/`

---

## Recognition Issues

### "Recognition always fails" or "Unknown face"

**Check 1: Verify embeddings exist**
```python
import os
folder = "data/faces/embeddings"
files = [f for f in os.listdir(folder) if f.endswith('.npy')]
print(f"Found {len(files)} embeddings: {files}")
```

**Check 2: Test similarity manually**
```python
from services.face_service import FaceService
service = FaceService("data/faces")
print(f"Registered users: {service.list_registered_users()}")
```

**Check 3: Lower threshold**
```python
# In services/face_config.py
SIMILARITY_THRESHOLD = 0.40  # Try lower value
```

### Recognition accuracy is low

1. **Re-register with better images** - See DATASET_GUIDELINES.md
2. **Add more enrollment images**:
   ```python
   service.add_enrollment_image(base64_image, user_id)
   ```
3. **Check quality scores** in registration output

### "Multiple faces detected"

- Ensure only one person is in frame
- Adjust camera angle to exclude others

---

## Camera Issues

### RTSP camera not connecting

**Check 1: Test URL with VLC**
```
vlc rtsp://username:password@192.168.1.100:554/stream
```

**Check 2: Check network**
```bash
ping 192.168.1.100
```

**Check 3: Verify credentials**
- Username/password in URL must be correct
- Some cameras require specific stream paths

### USB camera not detected

**Check 1: Verify camera index**
```python
import cv2
for i in range(3):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"Camera {i}: Available")
        cap.release()
```

### Low FPS or lag

1. Reduce resolution in `face_config.py`:
   ```python
   MAX_IMAGE_SIZE = 480  # Lower for better FPS
   ```

2. Skip frames:
   ```python
   # In camera processing loop
   if frame_count % 2 == 0:  # Process every 2nd frame
       detect_face(frame)
   ```

---

## Database Issues

### "Database locked" error

SQLite doesn't handle concurrent writes well:
1. Restart the application
2. Delete `data/library.db.lock` if it exists
3. Use single-threaded mode or switch to PostgreSQL for production

### Embeddings not loading

```python
# Debug loading
from services.face_recognition_engine import EmbeddingDatabase
db = EmbeddingDatabase("data/faces/embeddings")
print(f"Loaded: {len(db)} embeddings")
for uid in db.embeddings:
    print(f"  - {uid}: shape {db.embeddings[uid].shape}")
```

---

## Performance Tuning

### Speed up recognition

1. **Enable GPU** (if available):
   ```bash
   pip install onnxruntime-gpu
   ```
   ```python
   USE_GPU = True
   ```

2. **Reduce image size**:
   ```python
   MAX_IMAGE_SIZE = 480
   ```

3. **Adjust detection threshold**:
   ```python
   DETECTION_THRESHOLD = 0.6  # Higher = faster (fewer detections)
   ```

### Reduce memory usage

```python
# Process one frame at a time
# Don't cache frames
# Use smaller model: buffalo_s instead of buffalo_l
```

---

## Threshold Calibration

### Finding the right threshold

1. **Collect test data**: 10+ images per user
2. **Run similarity analysis**:
   ```python
   from services.face_service import FaceService
   import numpy as np
   
   service = FaceService("data/faces")
   
   # Compare same person (should be high)
   same_person_scores = []
   
   # Compare different people (should be low)
   different_person_scores = []
   
   # Choose threshold that separates these distributions
   ```

3. **Recommended ranges**:
   | Environment | Threshold |
   |-------------|-----------|
   | Controlled (good lighting) | 0.50 |
   | Normal office | 0.45 |
   | Variable conditions | 0.40 |
   | High security | 0.55 |

---

## Logs and Diagnostics

### Enable verbose logging

```python
# In face_config.py
VERBOSE_LOGGING = True
LOG_ALL_SCORES = True
```

### Check console output

Recognition logs show:
```
==================================================
Recognition Results (threshold: 0.450)
>>> MATCH user123: 0.6234
    user456: 0.3421
    user789: 0.2891
==================================================
```

### Debug face quality

```python
from services.face_recognition_engine import FaceRecognitionEngine
engine = FaceRecognitionEngine()

# Check detection
faces = engine.detect_faces(cv_image)
for face in faces:
    print(f"Quality: {face.quality}, Score: {face.quality_score}")
```
