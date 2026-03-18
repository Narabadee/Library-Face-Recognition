# Services package
from .face_service import FaceService
from .face_config import FaceRecognitionConfig, DEFAULT_CONFIG
from .face_recognition_engine import (
    FaceRecognitionEngine, 
    EmbeddingDatabase,
    FaceDetection,
    FaceQuality,
    INSIGHTFACE_AVAILABLE
)
from .attendance_service import AttendanceService

__all__ = [
    'FaceService',
    'FaceRecognitionConfig',
    'DEFAULT_CONFIG',
    'FaceRecognitionEngine',
    'EmbeddingDatabase',
    'FaceDetection',
    'FaceQuality',
    'AttendanceService',
    'INSIGHTFACE_AVAILABLE'
]
