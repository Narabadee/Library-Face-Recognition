# Face Recognition System - Architecture

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              FACE RECOGNITION SYSTEM v2.0                           │
│                            (InsightFace + RetinaFace + ArcFace)                     │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           INPUT LAYER                                         │   │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐           │   │
│  │  │ USB Camera │   │RTSP Camera │   │ Base64 API │   │ File Upload│           │   │
│  │  │  (cv2:0)   │   │  (IP Cam)  │   │  (Web UI)  │   │  (.jpg/.png)│           │   │
│  │  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘           │   │
│  │        └────────────────┴────────────────┴────────────────┘                   │   │
│  │                                    │                                           │   │
│  │                            ┌───────▼────────┐                                  │   │
│  │                            │  CameraStream  │                                  │   │
│  │                            │  (app.py)      │                                  │   │
│  │                            └───────┬────────┘                                  │   │
│  └────────────────────────────────────┼────────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌────────────────────────────────────▼────────────────────────────────────────────┐ │
│  │                       FACE SERVICE LAYER (face_service.py)                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │ │
│  │  │  FaceService                                                                 │ │ │
│  │  │  ├── register_face(base64_image, user_id)  → (bool, message)                │ │ │
│  │  │  ├── add_enrollment_image(base64_image, user_id) → (bool, msg, count)       │ │ │
│  │  │  ├── recognize_face(base64_image) → (found, user_id, confidence)            │ │ │
│  │  │  ├── delete_face(user_id) → bool                                            │ │ │
│  │  │  └── list_registered_users() → List[str]                                    │ │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌────────────────────────────────────▼────────────────────────────────────────────┐ │
│  │              FACE RECOGNITION ENGINE (face_recognition_engine.py)                │ │
│  │                                                                                   │ │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                        FaceRecognitionEngine                               │  │ │
│  │  │                                                                            │  │ │
│  │  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────┐ │  │ │
│  │  │  │ RetinaFace   │──▶│ Quality      │──▶│ ArcFace      │──▶│ Matcher     │ │  │ │
│  │  │  │ Detector     │   │ Assessment   │   │ Embeddings   │   │ Engine      │ │  │ │
│  │  │  │              │   │              │   │              │   │             │ │  │ │
│  │  │  │ • detect_    │   │ • blur check │   │ • 512-dim    │   │ • cosine    │ │  │ │
│  │  │  │   faces()    │   │ • size check │   │   vectors    │   │   similarity│ │  │ │
│  │  │  │ • 5-point    │   │ • angle check│   │ • alignment  │   │ • adaptive  │ │  │ │
│  │  │  │   landmarks  │   │              │   │   112x112    │   │   threshold │ │  │ │
│  │  │  └──────────────┘   └──────────────┘   └──────────────┘   └─────────────┘ │  │ │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                   │ │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                         EmbeddingDatabase                                  │  │ │
│  │  │  • add(user_id, embedding)      • get(user_id) → embedding                │  │ │
│  │  │  • remove(user_id)              • get_all() → Dict[id, embedding]         │  │ │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌────────────────────────────────────▼────────────────────────────────────────────┐ │
│  │                         STORAGE LAYER                                            │ │
│  │                                                                                   │ │
│  │  ┌─────────────────────────┐    ┌─────────────────────────────────────────────┐ │ │
│  │  │    SQLite Database       │    │          File System                        │ │ │
│  │  │    (library.db)          │    │                                             │ │ │
│  │  │                          │    │  data/                                      │ │ │
│  │  │  ┌──────────────────┐   │    │  ├── faces/                                 │ │ │
│  │  │  │ students         │   │    │  │   ├── {user_id}.jpg    (reference)       │ │ │
│  │  │  │ ├── id           │   │    │  │   └── embeddings/                        │ │ │
│  │  │  │ ├── student_id   │   │    │  │       └── {user_id}.npy (512-dim)        │ │ │
│  │  │  │ ├── name         │   │    │  │                                          │ │ │
│  │  │  │ └── created_at   │   │    │  └── enrollment/                            │ │ │
│  │  │  └──────────────────┘   │    │      └── {user_id}/                         │ │ │
│  │  │                          │    │          ├── img_1.jpg                      │ │ │
│  │  │  ┌──────────────────┐   │    │          ├── emb_1.npy                      │ │ │
│  │  │  │ attendance_logs  │   │    │          ├── img_2.jpg                      │ │ │
│  │  │  │ ├── student_id   │   │    │          └── emb_2.npy                      │ │ │
│  │  │  │ ├── check_in     │   │    │                                             │ │ │
│  │  │  │ ├── check_out    │   │    └─────────────────────────────────────────────┘ │ │
│  │  │  │ └── date         │   │                                                     │ │
│  │  │  └──────────────────┘   │                                                     │ │
│  │  └─────────────────────────┘                                                     │ │
│  └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐│
│  │                          CONFIGURATION (face_config.py)                          ││
│  │                                                                                   ││
│  │  Detection          Quality             Recognition         Enrollment           ││
│  │  ─────────          ───────             ───────────         ──────────           ││
│  │  threshold: 0.5     blur: 50            similarity: 0.45    min_images: 1        ││
│  │  min_size: 80       max_yaw: 35°        adaptive: true      max_images: 5        ││
│  │                     max_pitch: 25°      margin: 0.05        strategy: average    ││
│  └──────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Registration Flow
```
1. Capture Image (Base64)
       │
       ▼
2. Decode & Preprocess
       │
       ▼
3. RetinaFace Detection
       │
       ├── No face? ──────────▶ Error: "No face detected"
       │
       ▼
4. Quality Assessment
       │
       ├── Too small? ────────▶ Error: "Face too small"
       ├── Too blurry? ───────▶ Error: "Image too blurry"
       ├── Bad angle? ────────▶ Error: "Bad face angle"
       │
       ▼
5. Face Alignment (112x112)
       │
       ▼
6. ArcFace Embedding (512-dim)
       │
       ▼
7. Save to Database
       │
       ├── {user_id}.jpg ─────▶ Reference Image
       └── {user_id}.npy ─────▶ Embedding File
```

### Recognition Flow
```
1. Capture Image (Base64)
       │
       ▼
2. Decode & Preprocess
       │
       ▼
3. RetinaFace Detection + Quality Check
       │
       ├── Failed? ───────────▶ Return: (False, None, 0.0)
       │
       ▼
4. Extract Embedding
       │
       ▼
5. Compare vs Gallery
       │
       ├── For each registered user:
       │   └── Calculate cosine similarity
       │
       ▼
6. Apply Threshold
       │
       ├── Best >= threshold ─▶ Return: (True, user_id, confidence)
       │
       └── Best < threshold ──▶ Return: (False, None, best_score)
```

## File Structure

```
IoT/
├── app.py                          # Flask application
├── config.py                       # App configuration
├── requirements.txt                # Dependencies
│
├── services/
│   ├── __init__.py
│   ├── face_config.py             # [NEW] Recognition config
│   ├── face_recognition_engine.py # [NEW] Core engine
│   ├── face_service.py            # [REFACTORED] High-level API
│   └── attendance_service.py      # Attendance logic
│
├── database/
│   ├── __init__.py
│   └── models.py                   # SQLAlchemy models
│
├── data/
│   ├── library.db                  # SQLite database
│   └── faces/
│       ├── embeddings/             # .npy embedding files
│       └── enrollment/             # Multi-image enrollment
│
├── docs/
│   ├── SETUP.md                    # [NEW] Installation guide
│   ├── DATASET_GUIDELINES.md       # [NEW] Enrollment best practices
│   └── TROUBLESHOOTING.md          # [NEW] Common issues
│
├── tests/
│   ├── __init__.py
│   └── test_face_recognition.py    # [NEW] Test suite
│
├── templates/                      # HTML templates
└── static/                         # CSS, JS, images
```
