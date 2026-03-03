"""
Face Recognition Configuration
==============================
Centralized configuration for the face recognition system.
All thresholds and parameters are tuned for production use.
"""

from dataclasses import dataclass, field
from typing import List
import os


@dataclass
class FaceRecognitionConfig:
    """
    Configuration class for face recognition system.
    
    Attributes are grouped by function:
    - Detection: Face detector settings
    - Quality: Face quality assessment thresholds
    - Recognition: Embedding and matching settings
    - Enrollment: Multi-image registration settings
    - Paths: File system paths
    """
    
    # ==================== Detection Settings ====================
    # RetinaFace detector confidence threshold
    # Lower = more faces detected (including false positives)
    # Higher = fewer faces, more confident detections
    DETECTION_THRESHOLD: float = 0.5
    
    # Minimum face size in pixels (width and height)
    # Faces smaller than this will be rejected
    MIN_FACE_SIZE: int = 50  # Relaxed from 80
    
    # ==================== Quality Assessment ====================
    # Laplacian variance threshold for blur detection
    # Lower values = blurrier images
    # Recommended: 100 for webcams, 50 for RTSP cameras
    MIN_BLUR_SCORE: float = 20.0  # Relaxed from 50 for RTSP
    
    # Maximum allowed yaw angle (left-right rotation) in degrees
    # Faces turned more than this will be rejected
    MAX_YAW_ANGLE: float = 60.0  # Relaxed to support multi-angle enrollment
    
    # Maximum allowed pitch angle (up-down tilt) in degrees
    MAX_PITCH_ANGLE: float = 35.0  # Relaxed from 25
    
    # Minimum eye aspect ratio (detects closed eyes)
    MIN_EYE_ASPECT_RATIO: float = 0.15
    
    # ==================== Recognition Settings ====================
    # Cosine similarity threshold for positive match
    # Range: 0.0 to 1.0 (higher = stricter)
    # Recommended: 0.4-0.5 for ArcFace
    SIMILARITY_THRESHOLD: float = 0.75  # 75% threshold
    
    # Enable adaptive thresholding based on gallery statistics
    ADAPTIVE_THRESHOLD_ENABLED: bool = True
    
    # Adaptive threshold range
    ADAPTIVE_THRESHOLD_MIN: float = 0.35
    ADAPTIVE_THRESHOLD_MAX: float = 0.55
    
    # Margin required between best match and second-best match
    # Helps avoid ambiguous matches between similar-looking people
    MIN_MATCH_MARGIN: float = 0.05
    
    # ==================== Enrollment Settings ====================
    # Minimum number of images required for enrollment
    MIN_ENROLLMENT_IMAGES: int = 1
    
    # Recommended number of images for robust enrollment
    RECOMMENDED_ENROLLMENT_IMAGES: int = 3
    
    # Maximum number of images per user
    MAX_ENROLLMENT_IMAGES: int = 5
    
    # Strategy for combining multiple embeddings
    # Options: "average", "centroid", "all" (store all, match any)
    EMBEDDING_AGGREGATION: str = "average"
    
    # ==================== Multi-Angle Enrollment ====================
    # Poses to capture during multi-angle registration
    # Each entry: (label, instruction_th, instruction_en)
    MULTI_ANGLE_POSES: List[tuple] = field(default_factory=lambda: [
        ("front", "มองตรง", "Look straight ahead"),
        ("left", "หันซ้ายเล็กน้อย", "Turn slightly left"),
        ("right", "หันขวาเล็กน้อย", "Turn slightly right"),
    ])
    
    # Minimum images required for multi-angle enrollment
    MIN_MULTI_ANGLE_IMAGES: int = 3
    
    # ==================== Performance Settings ====================
    # Maximum image dimension for processing
    # Larger images will be resized
    MAX_IMAGE_SIZE: int = 640
    
    # Use GPU if available (requires onnxruntime-gpu)
    USE_GPU: bool = False
    
    # Number of threads for ONNX inference
    NUM_THREADS: int = 4
    
    # ==================== Logging Settings ====================
    # Enable detailed diagnostic logging
    VERBOSE_LOGGING: bool = False  # #3 perf: disable per-scan logging
    
    # Log similarity scores for all comparisons
    LOG_ALL_SCORES: bool = False  # #3 perf: disable per-scan logging
    
    # ==================== Paths ====================
    # These are set dynamically based on the application
    BASE_DIR: str = ""
    FACES_FOLDER: str = ""
    EMBEDDINGS_FOLDER: str = ""
    MODELS_FOLDER: str = ""
    
    def __post_init__(self):
        """Initialize paths after dataclass creation"""
        if not self.BASE_DIR:
            self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if not self.FACES_FOLDER:
            self.FACES_FOLDER = os.path.join(self.BASE_DIR, 'data', 'faces')
        
        if not self.EMBEDDINGS_FOLDER:
            self.EMBEDDINGS_FOLDER = os.path.join(self.FACES_FOLDER, 'embeddings')
        
        if not self.MODELS_FOLDER:
            self.MODELS_FOLDER = os.path.join(self.BASE_DIR, 'models')
        
        # Ensure directories exist
        for folder in [self.FACES_FOLDER, self.EMBEDDINGS_FOLDER, self.MODELS_FOLDER]:
            os.makedirs(folder, exist_ok=True)
    
    def get_threshold(self, gallery_size: int = 0) -> float:
        """
        Get the similarity threshold, optionally adjusted for gallery size.
        
        Args:
            gallery_size: Number of registered users
            
        Returns:
            Similarity threshold to use
        """
        if not self.ADAPTIVE_THRESHOLD_ENABLED or gallery_size == 0:
            return self.SIMILARITY_THRESHOLD
        
        # Increase threshold slightly as gallery grows to reduce false positives
        # Formula: base + (log2(gallery_size) * 0.02), clamped to range
        import math
        adjustment = math.log2(max(1, gallery_size)) * 0.02
        adaptive = self.SIMILARITY_THRESHOLD + adjustment
        
        return max(self.ADAPTIVE_THRESHOLD_MIN, 
                   min(self.ADAPTIVE_THRESHOLD_MAX, adaptive))


# Global default configuration
DEFAULT_CONFIG = FaceRecognitionConfig()
