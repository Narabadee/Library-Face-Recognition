# Dataset Collection Guidelines

## Best Practices for Enrollment Photos

High-quality enrollment photos are **critical** for recognition accuracy. Follow these guidelines when registering new users.

---

## Recommended: Multi-Image Enrollment

For best accuracy, register each user with **3-5 images** covering:

| Image | Description | Purpose |
|-------|-------------|---------|
| 1 | Front-facing, neutral | Primary reference |
| 2 | Slight left turn (~15°) | Capture angle variation |
| 3 | Slight right turn (~15°) | Capture angle variation |
| 4 | Different lighting | Handle lighting changes |
| 5 | With glasses (if applicable) | Handle accessory changes |

---

## Image Quality Requirements

### ✅ Good Images

- **Resolution**: Face at least 112x112 pixels (larger is better)
- **Lighting**: Even, natural lighting on face
- **Focus**: Sharp, clear image (no blur)
- **Pose**: Looking at camera, face visible
- **Expression**: Neutral or slight smile
- **Obstructions**: No hands, hair, or objects covering face

### ❌ Images to Avoid

- Blurry or motion-blurred images
- Extreme angles (looking away from camera)
- Heavy shadows on face
- Overexposed or underexposed
- Sunglasses or face masks
- Multiple people in frame
- Very distant (face too small)

---

## Capture Process

### Step-by-Step Registration

1. **Position subject** 50-100cm from camera
2. **Check lighting** - avoid backlighting
3. **Frame the shot** - face fills 1/3 of frame
4. **Capture frontal image** first
5. **Capture angle variations** (left, right)
6. **Review quality** before saving

### Environment Setup

```
Lighting Diagram:

    [Light Source]
         |
         v
    +---------+
    |         |
    | Subject | <-- Camera
    |         |
    +---------+
         |
    [No harsh shadows]
```

---

## Technical Specifications

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| Face width | 80 px | 150+ px |
| Image resolution | 640x480 | 1280x720 |
| Blur score | 50+ | 100+ |
| Yaw angle | ±35° | ±15° |
| Pitch angle | ±25° | ±10° |

---

## Quality Feedback

The system provides quality feedback during registration:

| Message | Cause | Solution |
|---------|-------|----------|
| "Face too small" | Too far from camera | Move closer |
| "Image too blurry" | Motion or focus issue | Hold still, refocus |
| "Bad angle" | Looking away | Face camera directly |
| "Multiple faces" | Others in frame | Ensure one person |
| "No face detected" | Face not visible | Check framing/lighting |

---

## Storage Format

Registered data is stored as:

```
data/
├── faces/
│   ├── {user_id}.jpg          # Reference image
│   └── embeddings/
│       └── {user_id}.npy      # 512-dim ArcFace embedding
└── enrollment/
    └── {user_id}/
        ├── img_1.jpg          # Additional enrollment images
        ├── emb_1.npy
        ├── img_2.jpg
        └── emb_2.npy
```

---

## Updating Registrations

To improve recognition for an existing user:

1. Navigate to user management
2. Select "Add Enrollment Image"
3. Capture new image following guidelines
4. System will automatically re-aggregate embeddings

You can add up to **5 enrollment images** per user.
