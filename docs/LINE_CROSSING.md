# Line Crossing Detection

## Overview
The system uses YOLOv8 for person detection and centroid tracking to detect when people cross a virtual line. Supports IN/OUT direction detection and integrates with face recognition.

## Quick Start

1. **Install YOLOv8**: `pip install ultralytics`
2. **Restart the app**: `python app.py`
3. **Open configuration**: Go to `http://localhost:5000/line-config`
4. **Draw the line**: Click "Draw Line" and click two points on the video
5. **Monitor crossings**: IN/OUT counters update automatically

## Configuration

### Web UI
Navigate to `/line-config` to:
- Draw virtual crossing lines for each camera
- View IN/OUT counters in real-time
- See recent crossing events
- Reset counters

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/line/{camera_id}/set` | POST | Set crossing line coordinates |
| `/api/line/{camera_id}/stats` | GET | Get IN/OUT statistics |
| `/api/line/{camera_id}/events` | GET | Get recent crossing events |
| `/api/line/{camera_id}/reset` | POST | Reset counters |

**camera_id**: `entry` or `exit`

### Example: Set Line via API
```bash
curl -X POST http://localhost:5000/api/line/entry/set \
  -H "Content-Type: application/json" \
  -d '{"start_x": 100, "start_y": 200, "end_x": 400, "end_y": 200}'
```

## Architecture

```
Frame → YOLOv8 Detection → Centroid Tracker → Line Crossing Logic → Event Log
                                ↓
                    Unique Person IDs maintained
```

## Files

| File | Description |
|------|-------------|
| `services/line_crossing.py` | Main detection class |
| `services/person_tracker.py` | Centroid-based tracking |
| `templates/line_config.html` | Configuration UI |

## Performance Tips

- Use `yolov8n.pt` (nano) for fastest speed
- Reduce frame processing to every 2nd frame if needed
- Line config is saved per camera in `data/line_config/`
