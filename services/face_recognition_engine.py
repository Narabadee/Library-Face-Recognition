"""
Face Recognition Engine
=======================
Production-quality face recognition using ONNX models.
Does NOT require InsightFace compilation.

Features:
- RetinaFace detection via ONNX
- ArcFace embedding extraction via ONNX
- Face quality assessment
- Multi-image enrollment support
"""

import numpy as np
import cv2
import os
import time
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check available backends
ONNX_AVAILABLE = False
INSIGHTFACE_AVAILABLE = False

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    logger.warning("ONNX Runtime not installed. Run: pip install onnxruntime")

try:
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    pass  # Will use ONNX backend


class FaceQuality(Enum):
    """Face quality assessment results"""
    GOOD = "good"
    TOO_SMALL = "too_small"
    TOO_BLURRY = "too_blurry"
    BAD_ANGLE = "bad_angle"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"


@dataclass
class FaceDetection:
    """Container for face detection results"""
    bbox: np.ndarray          # [x1, y1, x2, y2]
    landmarks: np.ndarray     # 5-point landmarks
    confidence: float         # Detection confidence
    embedding: Optional[np.ndarray] = None  # 512-dim embedding
    quality: FaceQuality = FaceQuality.GOOD
    quality_score: float = 0.0
    
    @property
    def width(self) -> int:
        return int(self.bbox[2] - self.bbox[0])
    
    @property
    def height(self) -> int:
        return int(self.bbox[3] - self.bbox[1])
    
    @property
    def center(self) -> Tuple[int, int]:
        return (
            int((self.bbox[0] + self.bbox[2]) / 2),
            int((self.bbox[1] + self.bbox[3]) / 2)
        )


class FaceRecognitionEngine:
    """
    Face recognition engine with multiple backend support.
    
    Priority:
    1. InsightFace (if installed and compiled)
    2. Direct ONNX (RetinaFace + ArcFace)
    3. YuNet fallback (detection only, simplified embeddings)
    """
    
    def __init__(self, config=None):
        """Initialize the face recognition engine."""
        if config is None:
            from .face_config import DEFAULT_CONFIG
            config = DEFAULT_CONFIG
        
        self.config = config
        self._initialized = False
        self._backend = None
        
        # Backend-specific objects
        self.app = None  # InsightFace
        self.detector = None  # ONNX RetinaFace or YuNet
        self.embedder = None  # ONNX ArcFace
        
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize face recognition with best available backend"""
        
        # Try InsightFace first
        if INSIGHTFACE_AVAILABLE:
            if self._try_insightface():
                return
        
        # Try ONNX models
        if ONNX_AVAILABLE:
            if self._try_onnx():
                return
        
        # Fallback to YuNet
        self._try_yunet()
    
    def _try_insightface(self) -> bool:
        """Try to initialize InsightFace"""
        try:
            logger.info("Trying InsightFace backend...")
            
            providers = ['CPUExecutionProvider']
            if self.config.USE_GPU:
                providers = ['CUDAExecutionProvider'] + providers
            
            self.app = FaceAnalysis(
                name='buffalo_l',
                root=self.config.MODELS_FOLDER,
                providers=providers
            )
            self.app.prepare(ctx_id=-1, det_size=(640, 640))
            
            self._backend = 'insightface'
            self._initialized = True
            logger.info("Using InsightFace backend")
            return True
            
        except Exception as e:
            logger.warning(f"InsightFace failed: {e}")
            return False
    
    def _try_onnx(self) -> bool:
        """Try to initialize direct ONNX models"""
        try:
            from .onnx_face import ONNXRetinaFace, ONNXArcFace
            from .model_manager import ensure_models, get_model_path, check_models
            
            logger.info("Trying ONNX backend...")
            
            # Ensure models are downloaded
            if not ensure_models():
                logger.warning("Failed to download models")
                return False
            
            # Get model paths
            status = check_models()
            
            if not status['retinaface']['available'] or not status['arcface']['available']:
                logger.warning("Models not available after download")
                return False
            
            # Initialize models
            self.detector = ONNXRetinaFace(status['retinaface']['path'])
            self.embedder = ONNXArcFace(status['arcface']['path'])
            
            self._backend = 'onnx'
            self._initialized = True
            logger.info("Using ONNX backend (RetinaFace + ArcFace)")
            return True
            
        except Exception as e:
            logger.warning(f"ONNX backend failed: {e}")
            return False
    
    def _try_yunet(self) -> bool:
        """Fallback to YuNet detector"""
        try:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'face_detection_yunet_2023mar.onnx'
            )
            
            if not os.path.exists(model_path):
                logger.error("YuNet model not found")
                return False
            
            self.detector = cv2.FaceDetectorYN.create(
                model=model_path,
                config="",
                input_size=(320, 320),
                score_threshold=self.config.DETECTION_THRESHOLD,
                nms_threshold=0.3,
                top_k=5000,
                backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                target_id=cv2.dnn.DNN_TARGET_CPU
            )
            
            self._backend = 'yunet'
            self._initialized = True
            logger.info("Using YuNet fallback (limited accuracy)")
            return True
            
        except Exception as e:
            logger.error(f"YuNet fallback failed: {e}")
            return False
    
    @property
    def is_ready(self) -> bool:
        return self._initialized
    
    @property
    def backend(self) -> str:
        return self._backend or 'none'
    
    def detect_faces(self, image: np.ndarray) -> List[FaceDetection]:
        """Detect all faces in an image."""
        if not self.is_ready:
            return []
        
        if self._backend == 'insightface':
            return self._detect_insightface(image)
        elif self._backend == 'onnx':
            return self._detect_onnx(image)
        elif self._backend == 'yunet':
            return self._detect_yunet(image)
        
        return []
    
    def _detect_insightface(self, image: np.ndarray) -> List[FaceDetection]:
        """Detect using InsightFace"""
        try:
            faces = self.app.get(image)
            detections = []
            
            for face in faces:
                if face.det_score < self.config.DETECTION_THRESHOLD:
                    continue
                
                detection = FaceDetection(
                    bbox=face.bbox,
                    landmarks=face.kps if hasattr(face, 'kps') else np.zeros((5, 2)),
                    confidence=float(face.det_score),
                    embedding=face.embedding if hasattr(face, 'embedding') else None
                )
                detection.quality, detection.quality_score = self._assess_quality(image, detection)
                detections.append(detection)
            
            return detections
        except Exception as e:
            logger.error(f"InsightFace detection error: {e}")
            return []
    
    def _detect_onnx(self, image: np.ndarray) -> List[FaceDetection]:
        """Detect using ONNX models"""
        try:
            from .onnx_face import FaceAligner
            
            faces = self.detector.detect(image, self.config.DETECTION_THRESHOLD)
            detections = []
            
            for face in faces:
                detection = FaceDetection(
                    bbox=np.array(face['bbox']),
                    landmarks=face['landmarks'],
                    confidence=face['confidence']
                )
                
                # SIMPLIFIED: Skip quality checks - always extract embedding
                detection.quality = FaceQuality.GOOD
                detection.quality_score = 100.0
                
                # Always extract embedding if we have landmarks
                if detection.landmarks is not None:
                    aligned = FaceAligner.align(image, detection.landmarks)
                    if aligned is not None:
                        detection.embedding = self.embedder.get_embedding(aligned)
                
                detections.append(detection)
            
            return detections
        except Exception as e:
            logger.error(f"ONNX detection error: {e}")
            return []
    
    def _detect_yunet(self, image: np.ndarray) -> List[FaceDetection]:
        """Detect using YuNet (fallback)"""
        try:
            height, width = image.shape[:2]
            self.detector.setInputSize((width, height))
            
            _, faces_data = self.detector.detect(image)
            detections = []
            
            if faces_data is not None:
                for face in faces_data:
                    confidence = face[14]
                    if confidence < self.config.DETECTION_THRESHOLD:
                        continue
                    
                    x, y, w, h = map(int, face[:4])
                    landmarks = np.array([
                        [face[4], face[5]],
                        [face[6], face[7]],
                        [face[8], face[9]],
                        [face[10], face[11]],
                        [face[12], face[13]]
                    ])
                    
                    detection = FaceDetection(
                        bbox=np.array([x, y, x+w, y+h]),
                        landmarks=landmarks,
                        confidence=float(confidence)
                    )
                    
                    detection.quality, detection.quality_score = self._assess_quality(image, detection)
                    
                    # Simple embedding for YuNet (histogram-based)
                    if detection.quality == FaceQuality.GOOD:
                        detection.embedding = self._extract_simple_embedding(image, detection)
                    
                    detections.append(detection)
            
            return detections
        except Exception as e:
            logger.error(f"YuNet detection error: {e}")
            return []
    
    def _extract_simple_embedding(self, image: np.ndarray, detection: FaceDetection) -> np.ndarray:
        """Extract simple histogram-based embedding (YuNet fallback)"""
        try:
            x1, y1, x2, y2 = map(int, detection.bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(image.shape[1], x2), min(image.shape[0], y2)
            
            face = cv2.resize(image[y1:y2, x1:x2], (112, 112))
            gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            
            # Histogram
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
            hist = hist / (np.sum(hist) + 1e-6)
            
            # Edge features
            edges = cv2.Canny(gray, 50, 150)
            edge_hist = cv2.calcHist([edges], [0], None, [256], [0, 256]).flatten()
            edge_hist = edge_hist / (np.sum(edge_hist) + 1e-6)
            
            embedding = np.concatenate([hist, edge_hist])
            embedding = np.pad(embedding, (0, max(0, 512 - len(embedding))))[:512]
            embedding = embedding / (np.linalg.norm(embedding) + 1e-6)
            
            return embedding.astype(np.float32)
        except:
            return np.zeros(512, dtype=np.float32)
    
    def detect_and_extract(self, image: np.ndarray) -> Optional[FaceDetection]:
        """Detect the primary face and extract its embedding."""
        detections = self.detect_faces(image)
        
        if not detections:
            return None
        
        primary = max(detections, key=lambda d: d.width * d.height)
        
        # SIMPLIFIED: Accept any detected face - no quality rejection
        # Just make sure we have an embedding
        if primary.embedding is None and self.embedder is not None:
            from .onnx_face import FaceAligner
            aligned = FaceAligner.align(image, primary.landmarks)
            if aligned is not None:
                primary.embedding = self.embedder.get_embedding(aligned)
        
        return primary
    
    def _assess_quality(self, image: np.ndarray, detection: FaceDetection) -> Tuple[FaceQuality, float]:
        """Assess face quality"""
        if detection.width < self.config.MIN_FACE_SIZE or detection.height < self.config.MIN_FACE_SIZE:
            return FaceQuality.TOO_SMALL, 0.0
        
        x1, y1, x2, y2 = map(int, detection.bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(image.shape[1], x2), min(image.shape[0], y2)
        
        face_region = image[y1:y2, x1:x2]
        if face_region.size == 0:
            return FaceQuality.NO_FACE, 0.0
        
        gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if blur_score < self.config.MIN_BLUR_SCORE:
            return FaceQuality.TOO_BLURRY, blur_score
        
        if detection.landmarks is not None and len(detection.landmarks) >= 5:
            yaw, pitch = self._estimate_pose(detection.landmarks)
            if abs(yaw) > self.config.MAX_YAW_ANGLE or abs(pitch) > self.config.MAX_PITCH_ANGLE:
                return FaceQuality.BAD_ANGLE, blur_score
        
        return FaceQuality.GOOD, min(100, blur_score / 2)
    
    def _estimate_pose(self, landmarks: np.ndarray) -> Tuple[float, float]:
        """Estimate face pose from landmarks"""
        try:
            left_eye = landmarks[0]
            right_eye = landmarks[1]
            nose = landmarks[2]
            
            eye_center = (left_eye + right_eye) / 2
            eye_distance = np.linalg.norm(right_eye - left_eye)
            
            if eye_distance < 1:
                return 0, 0
            
            yaw = np.arctan((nose[0] - eye_center[0]) / (eye_distance * 0.5)) * 180 / np.pi
            pitch = np.arctan((nose[1] - eye_center[1]) / eye_distance) * 180 / np.pi - 25
            
            return float(yaw), float(pitch)
        except:
            return 0, 0
    
    def compare_embeddings(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = np.dot(embedding1 / norm1, embedding2 / norm2)
        return float((similarity + 1) / 2)
    
    def find_best_match(
        self,
        query_embedding: np.ndarray,
        gallery: Dict[str, np.ndarray],
        threshold: Optional[float] = None
    ) -> Tuple[Optional[str], float, List[Dict[str, Any]]]:
        """Find best matching identity in gallery."""
        if not gallery:
            return None, 0.0, []
        
        if threshold is None:
            threshold = self.config.get_threshold(len(gallery))
        
        matches = []
        for user_id, stored in gallery.items():
            score = self.compare_embeddings(query_embedding, stored)
            matches.append({'id': user_id, 'score': score})
        
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        if self.config.VERBOSE_LOGGING and matches:
            logger.info(f"Recognition (threshold: {threshold:.3f}, backend: {self.backend})")
            for i, m in enumerate(matches[:5]):
                prefix = ">>> MATCH" if i == 0 and m['score'] >= threshold else "   "
                logger.info(f"{prefix} {m['id']}: {m['score']:.4f}")
        
        if matches and matches[0]['score'] >= threshold:
            if len(matches) > 1 and matches[0]['score'] - matches[1]['score'] < self.config.MIN_MATCH_MARGIN:
                return None, matches[0]['score'], matches
            return matches[0]['id'], matches[0]['score'], matches
        
        return None, matches[0]['score'] if matches else 0.0, matches
    
    def aggregate_embeddings(self, embeddings: List[np.ndarray], method: str = "average") -> np.ndarray:
        """Aggregate multiple embeddings."""
        if not embeddings:
            raise ValueError("No embeddings")
        if len(embeddings) == 1:
            return embeddings[0]
        
        aggregated = np.mean(np.stack(embeddings), axis=0)
        norm = np.linalg.norm(aggregated)
        return aggregated / norm if norm > 0 else aggregated


class EmbeddingDatabase:
    """Database for face embeddings."""
    
    def __init__(self, embeddings_folder: str):
        self.embeddings_folder = embeddings_folder
        self.embeddings: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, Dict] = {}
        
        os.makedirs(embeddings_folder, exist_ok=True)
        self._load_all()
    
    def _load_all(self):
        if not os.path.exists(self.embeddings_folder):
            return
        
        for f in os.listdir(self.embeddings_folder):
            if f.endswith('.npy'):
                user_id = f.rsplit('.', 1)[0]
                try:
                    self.embeddings[user_id] = np.load(os.path.join(self.embeddings_folder, f))
                except:
                    pass
        
        logger.info(f"Loaded {len(self.embeddings)} embeddings")
    
    def add(self, user_id: str, embedding: np.ndarray, quality_score: float = 0.0):
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        self.embeddings[user_id] = embedding
        self.metadata[user_id] = {'quality_score': quality_score, 'updated_at': time.time()}
        np.save(os.path.join(self.embeddings_folder, f"{user_id}.npy"), embedding)
    
    def get(self, user_id: str) -> Optional[np.ndarray]:
        return self.embeddings.get(user_id)
    
    def remove(self, user_id: str) -> bool:
        if user_id in self.embeddings:
            del self.embeddings[user_id]
            path = os.path.join(self.embeddings_folder, f"{user_id}.npy")
            if os.path.exists(path):
                os.remove(path)
            return True
        return False
    
    def get_all(self) -> Dict[str, np.ndarray]:
        return self.embeddings  # #4 perf: return direct ref, no copy needed during recognition
    
    def __len__(self) -> int:
        return len(self.embeddings)
    
    def __contains__(self, user_id: str) -> bool:
        return user_id in self.embeddings
