"""
Face Service
=============
High-level face recognition service for the attendance system.

This module provides the main interface for:
- Face registration (multi-image enrollment)
- Face recognition
- User management

Uses the FaceRecognitionEngine for core operations.
"""

import numpy as np
import os
import base64
import time
import logging
from io import BytesIO
from PIL import Image
from typing import Optional, Tuple, List
import cv2

from .face_config import DEFAULT_CONFIG, FaceRecognitionConfig
from .face_recognition_engine import (
    FaceRecognitionEngine,
    EmbeddingDatabase,
    FaceQuality
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceService:
    """
    Face Recognition Service for attendance system.
    
    This class provides the high-level API for face operations:
    - register_face(): Register a new user with face image(s)
    - recognize_face(): Identify a person from face image
    - delete_face(): Remove a user's face data
    - add_enrollment_image(): Add additional images for a user
    
    Example:
        service = FaceService('/path/to/faces')
        
        # Register new user
        success, message = service.register_face(base64_image, 'user123')
        
        # Recognize
        found, user_id, confidence = service.recognize_face(base64_image)
    """
    
    def __init__(self, faces_folder: str, config: Optional[FaceRecognitionConfig] = None):
        """
        Initialize the face service.
        
        Args:
            faces_folder: Path to store face images
            config: Configuration object (uses defaults if None)
        """
        self.config = config or DEFAULT_CONFIG
        self.faces_folder = faces_folder
        self.embeddings_folder = os.path.join(faces_folder, 'embeddings')
        self.enrollment_folder = os.path.join(faces_folder, 'enrollment')
        
        # Create directories
        for folder in [self.faces_folder, self.embeddings_folder, self.enrollment_folder]:
            os.makedirs(folder, exist_ok=True)
        
        # Initialize core engine
        self.engine = FaceRecognitionEngine(self.config)
        
        # Initialize embedding database
        self.database = EmbeddingDatabase(self.embeddings_folder)
        
        # Legacy compatibility - keep reference to known_faces
        self.known_faces = {}
        self._load_known_faces()
        
        logger.info(f"FaceService initialized with {len(self.database)} registered users")
    
    def _load_known_faces(self):
        """Load registered face images for reference"""
        for filename in os.listdir(self.faces_folder):
            if filename.endswith(('.jpg', '.jpeg', '.png')):
                # Skip hidden files
                if filename.startswith('_') or filename.startswith('.'):
                    continue
                
                user_id = filename.rsplit('.', 1)[0]
                self.known_faces[user_id] = os.path.join(self.faces_folder, filename)
    
    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """
        Decode a base64 string to PIL Image.
        
        Args:
            base64_string: Base64 encoded image (with or without header)
            
        Returns:
            PIL Image in RGB mode
        """
        # Remove header if present
        if ',' in base64_string:
            base64_string = base64_string.split(',', 1)[1]
        
        # Decode
        image_data = base64.b64decode(base64_string)
        image = Image.open(BytesIO(image_data))
        
        # Convert to RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image
    
    def _pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV BGR format"""
        rgb_array = np.array(pil_image)
        bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
        return bgr_array
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for face detection.
        Resizes large images for faster processing.
        """
        max_size = self.config.MAX_IMAGE_SIZE
        width, height = image.size
        
        if max(width, height) > max_size:
            scale = max_size / max(width, height)
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.LANCZOS)
        
        return image
    
    def register_face(
        self, 
        base64_image: str, 
        user_id: str,
        save_reference: bool = True
    ) -> Tuple[bool, str]:
        """
        Register a new user with their face image.
        
        This method:
        1. Decodes the base64 image
        2. Detects face and checks quality
        3. Extracts embedding
        4. Saves to database
        
        Args:
            base64_image: Base64 encoded face image
            user_id: Unique user identifier
            save_reference: Whether to save the reference image
            
        Returns:
            (success: bool, message: str)
        """
        if not self.engine.is_ready:
            return False, f"Face recognition engine not initialized (backend: {self.engine.backend})"
        
        try:
            start_time = time.time()
            
            # Decode image
            pil_image = self._decode_base64_image(base64_image)
            pil_image = self._preprocess_image(pil_image)
            cv_image = self._pil_to_cv2(pil_image)
            
            logger.info(f"Registering {user_id}: image size = {cv_image.shape}")
            
            # Detect face and extract embedding
            detection = self.engine.detect_and_extract(cv_image)
            
            if detection is None:
                # Try to give more specific error
                faces = self.engine.detect_faces(cv_image)
                logger.info(f"Detected {len(faces)} faces for {user_id}")
                
                if not faces:
                    return False, "No face detected in image. Please ensure face is clearly visible."
                elif len(faces) > 1:
                    return False, "Multiple faces detected. Please ensure only one person is in the image."
                else:
                    face = faces[0]
                    logger.info(f"Face quality: {face.quality.value}, score: {face.quality_score:.1f}, size: {face.width}x{face.height}")
                    
                    if face.quality == FaceQuality.TOO_BLURRY:
                        return False, f"Image is too blurry (score: {face.quality_score:.0f}). Please use a clearer image."
                    elif face.quality == FaceQuality.TOO_SMALL:
                        return False, f"Face is too small ({face.width}x{face.height}). Please move closer to the camera."
                    elif face.quality == FaceQuality.BAD_ANGLE:
                        return False, "Face angle is too extreme. Please face the camera directly."
                    elif face.embedding is None:
                        return False, "Could not extract face embedding. Please try with a clearer image."
                    else:
                        return False, f"Face quality check failed: {face.quality.value}"
            
            # Save embedding to database
            self.database.add(user_id, detection.embedding, detection.quality_score)
            
            # Save reference image
            if save_reference:
                image_path = os.path.join(self.faces_folder, f"{user_id}.jpg")
                pil_image.save(image_path, 'JPEG', quality=95)
                self.known_faces[user_id] = image_path
            
            elapsed = time.time() - start_time
            logger.info(f"Registered {user_id} in {elapsed:.2f}s (quality: {detection.quality_score:.1f})")
            
            return True, f"Registration successful (ArcFace embedding, quality: {detection.quality_score:.0f})"
            
        except Exception as e:
            logger.error(f"Registration error for {user_id}: {e}")
            return False, f"Registration failed: {str(e)}"
    
    def register_face_multi(
        self,
        base64_images: List[str],
        user_id: str,
        save_reference: bool = True
    ) -> Tuple[bool, str]:
        """
        Register a new user with multiple face images (multi-angle).
        
        This method:
        1. Decodes each base64 image
        2. Detects face and extracts embedding from each
        3. Aggregates all embeddings into one robust embedding
        4. Saves to database
        
        Args:
            base64_images: List of base64 encoded face images (different angles)
            user_id: Unique user identifier
            save_reference: Whether to save reference images
            
        Returns:
            (success: bool, message: str)
        """
        if not self.engine.is_ready:
            return False, f"Face recognition engine not initialized (backend: {self.engine.backend})"
        
        if not base64_images:
            return False, "No images provided"
        
        min_images = self.config.MIN_MULTI_ANGLE_IMAGES
        if len(base64_images) < min_images:
            return False, f"At least {min_images} images required, got {len(base64_images)}"
        
        try:
            start_time = time.time()
            embeddings = []
            quality_scores = []
            pil_images = []
            
            for i, b64_img in enumerate(base64_images):
                # Decode image
                pil_image = self._decode_base64_image(b64_img)
                pil_image = self._preprocess_image(pil_image)
                cv_image = self._pil_to_cv2(pil_image)
                pil_images.append(pil_image)
                
                logger.info(f"Multi-angle registration {user_id}: processing image {i+1}/{len(base64_images)}")
                
                # Detect face and extract embedding
                detection = self.engine.detect_and_extract(cv_image)
                
                if detection is None:
                    pose_label = self.config.MULTI_ANGLE_POSES[i][2] if i < len(self.config.MULTI_ANGLE_POSES) else f"Image {i+1}"
                    return False, f"No face detected in '{pose_label}'. Please retake."
                
                if detection.embedding is None:
                    pose_label = self.config.MULTI_ANGLE_POSES[i][2] if i < len(self.config.MULTI_ANGLE_POSES) else f"Image {i+1}"
                    return False, f"Could not extract embedding from '{pose_label}'. Please retake."
                
                embeddings.append(detection.embedding)
                quality_scores.append(detection.quality_score)
            
            # Aggregate embeddings
            aggregated = self.engine.aggregate_embeddings(embeddings)
            avg_quality = sum(quality_scores) / len(quality_scores)
            
            # Save aggregated embedding to database
            self.database.add(user_id, aggregated, avg_quality)
            
            if save_reference:
                # Save first image (front) as main reference
                image_path = os.path.join(self.faces_folder, f"{user_id}.jpg")
                pil_images[0].save(image_path, 'JPEG', quality=95)
                self.known_faces[user_id] = image_path
                
                # Save all images to enrollment folder
                user_folder = os.path.join(self.enrollment_folder, user_id)
                os.makedirs(user_folder, exist_ok=True)
                
                for i, (pil_img, emb) in enumerate(zip(pil_images, embeddings)):
                    pose_label = self.config.MULTI_ANGLE_POSES[i][0] if i < len(self.config.MULTI_ANGLE_POSES) else f"angle_{i}"
                    img_path = os.path.join(user_folder, f"{pose_label}.jpg")
                    pil_img.save(img_path, 'JPEG', quality=90)
                    
                    emb_path = os.path.join(user_folder, f"{pose_label}.npy")
                    np.save(emb_path, emb)
            
            elapsed = time.time() - start_time
            logger.info(
                f"Multi-angle registered {user_id} with {len(embeddings)} images "
                f"in {elapsed:.2f}s (avg quality: {avg_quality:.1f})"
            )
            
            return True, f"Multi-angle registration successful ({len(embeddings)} images, avg quality: {avg_quality:.0f})"
            
        except Exception as e:
            logger.error(f"Multi-angle registration error for {user_id}: {e}")
            return False, f"Registration failed: {str(e)}"
    
    def add_enrollment_image(
        self, 
        base64_image: str, 
        user_id: str
    ) -> Tuple[bool, str, int]:
        """
        Add an additional enrollment image for a user.
        
        This improves recognition accuracy by capturing different angles/lighting.
        The user's embedding will be updated to the average of all enrollment images.
        
        Args:
            base64_image: Base64 encoded face image
            user_id: User ID (must already be registered)
            
        Returns:
            (success: bool, message: str, total_images: int)
        """
        if user_id not in self.database:
            return False, "User not registered. Please register first.", 0
        
        try:
            # Decode and detect
            pil_image = self._decode_base64_image(base64_image)
            pil_image = self._preprocess_image(pil_image)
            cv_image = self._pil_to_cv2(pil_image)
            
            detection = self.engine.detect_and_extract(cv_image)
            
            if detection is None:
                return False, "Could not extract face from image", 0
            
            # Count existing enrollment images
            user_folder = os.path.join(self.enrollment_folder, user_id)
            os.makedirs(user_folder, exist_ok=True)
            
            existing = [f for f in os.listdir(user_folder) if f.endswith('.npy')]
            
            if len(existing) >= self.config.MAX_ENROLLMENT_IMAGES:
                return False, f"Maximum enrollment images ({self.config.MAX_ENROLLMENT_IMAGES}) reached", len(existing)
            
            # Save embedding
            idx = len(existing) + 1
            emb_path = os.path.join(user_folder, f"emb_{idx}.npy")
            np.save(emb_path, detection.embedding)
            
            # Save image for reference
            img_path = os.path.join(user_folder, f"img_{idx}.jpg")
            pil_image.save(img_path, 'JPEG', quality=90)
            
            # Re-aggregate all embeddings
            all_embeddings = [self.database.get(user_id)]  # Original
            for f in os.listdir(user_folder):
                if f.endswith('.npy'):
                    emb = np.load(os.path.join(user_folder, f))
                    all_embeddings.append(emb)
            
            # Average and update
            aggregated = self.engine.aggregate_embeddings(all_embeddings)
            self.database.add(user_id, aggregated, detection.quality_score)
            
            total = len(existing) + 1
            logger.info(f"Added enrollment image {total} for {user_id}")
            
            return True, f"Enrollment image {total} added successfully", total
            
        except Exception as e:
            logger.error(f"Enrollment error for {user_id}: {e}")
            return False, f"Failed to add enrollment image: {str(e)}", 0
    
    def recognize_face_image(
        self, 
        cv_image: np.ndarray,
        threshold: Optional[float] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        Recognize a face from an OpenCV BGR image.
        
        Args:
            cv_image: OpenCV BGR image
            threshold: Custom similarity threshold
            
        Returns:
            (found: bool, user_id or None, confidence: float)
        """
        if not self.engine.is_ready:
            return False, None, 0.0
            
        try:
            # Extract embedding
            detection = self.engine.detect_and_extract(cv_image)
            
            if detection is None:
                return False, None, 0.0
                
            # Find best match
            gallery = self.database.get_all()
            matched_id, confidence, _ = self.engine.find_best_match(
                detection.embedding,
                gallery,
                threshold
            )
            
            if matched_id:
                return True, matched_id, confidence
            else:
                return False, None, confidence
                
        except Exception as e:
            logger.error(f"Recognition error from image: {e}")
            return False, None, 0.0

    def recognize_face(
        self, 
        base64_image: str,
        threshold: Optional[float] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        Recognize a face from the registered database.
        
        Args:
            base64_image: Base64 encoded face image
            threshold: Custom similarity threshold (uses config default if None)
            
        Returns:
            (found: bool, user_id or None, confidence: float)
        """
        if not self.engine.is_ready:
            logger.error(f"Engine not initialized (backend: {self.engine.backend})")
            return False, None, 0.0
        
        if len(self.database) == 0:
            logger.warning("No registered users in database")
            return False, None, 0.0
        
        try:
            start_time = time.time()
            
            # Decode and detect
            pil_image = self._decode_base64_image(base64_image)
            pil_image = self._preprocess_image(pil_image)
            cv_image = self._pil_to_cv2(pil_image)
            
            # Detect and extract
            detection = self.engine.detect_and_extract(cv_image)
            
            if detection is None:
                return False, None, 0.0
            
            # Find best match
            gallery = self.database.get_all()
            matched_id, confidence, all_matches = self.engine.find_best_match(
                detection.embedding,
                gallery,
                threshold
            )
            
            elapsed = time.time() - start_time
            
            if matched_id:
                logger.info(f"Recognized {matched_id} with confidence {confidence:.4f} in {elapsed:.2f}s")
                return True, matched_id, confidence
            else:
                logger.info(f"Unknown face (best: {confidence:.4f}) in {elapsed:.2f}s")
                return False, None, confidence
            
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return False, None, 0.0
    
    def delete_face(self, user_id: str) -> bool:
        """
        Delete a user's face data.
        
        Removes:
        - Reference image
        - Embedding
        - All enrollment images
        
        Args:
            user_id: User to delete
            
        Returns:
            True if deleted, False if not found
        """
        deleted_something = False
        
        # Delete reference image
        for ext in ['.jpg', '.jpeg', '.png']:
            filepath = os.path.join(self.faces_folder, f"{user_id}{ext}")
            if os.path.exists(filepath):
                os.remove(filepath)
                deleted_something = True
        
        # Delete embedding from database
        if self.database.remove(user_id):
            deleted_something = True
        
        # Delete enrollment folder
        user_folder = os.path.join(self.enrollment_folder, user_id)
        if os.path.exists(user_folder):
            import shutil
            shutil.rmtree(user_folder)
            deleted_something = True
        
        # Update known_faces cache
        if user_id in self.known_faces:
            del self.known_faces[user_id]
        
        if deleted_something:
            logger.info(f"Deleted face data for {user_id}")
        
        return deleted_something
    
    def get_registration_stats(self, user_id: str) -> Optional[dict]:
        """
        Get registration statistics for a user.
        
        Returns:
            Dict with enrollment count, quality scores, etc.
        """
        if user_id not in self.database:
            return None
        
        stats = {
            'user_id': user_id,
            'has_embedding': True,
            'has_reference_image': user_id in self.known_faces,
            'enrollment_images': 0,
            'quality_score': self.database.metadata.get(user_id, {}).get('quality_score', 0)
        }
        
        # Count enrollment images
        user_folder = os.path.join(self.enrollment_folder, user_id)
        if os.path.exists(user_folder):
            stats['enrollment_images'] = len([
                f for f in os.listdir(user_folder) if f.endswith('.npy')
            ])
        
        return stats
    
    def list_registered_users(self) -> List[str]:
        """Get list of all registered user IDs"""
        return list(self.database.embeddings.keys())
    
    @property
    def known_embeddings(self) -> dict:
        """
        Legacy compatibility property.
        Returns the embeddings dictionary.
        """
        return self.database.embeddings
