"""
Face Recognition System - Test Suite
=====================================
Unit and integration tests for the face recognition engine.

Run with: python -m pytest tests/test_face_recognition.py -v
"""

import pytest
import numpy as np
import os
import sys
import cv2
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestFaceConfig:
    """Test configuration module"""
    
    def test_config_initialization(self):
        """Test that default config initializes correctly"""
        from services.face_config import FaceRecognitionConfig, DEFAULT_CONFIG
        
        config = FaceRecognitionConfig()
        assert config.SIMILARITY_THRESHOLD > 0
        assert config.SIMILARITY_THRESHOLD < 1
        assert config.MIN_FACE_SIZE > 0
        assert config.MAX_ENROLLMENT_IMAGES >= config.MIN_ENROLLMENT_IMAGES
    
    def test_adaptive_threshold(self):
        """Test adaptive threshold calculation"""
        from services.face_config import FaceRecognitionConfig
        
        config = FaceRecognitionConfig()
        config.ADAPTIVE_THRESHOLD_ENABLED = True
        
        # Small gallery should have lower threshold
        small_threshold = config.get_threshold(gallery_size=5)
        
        # Large gallery should have higher threshold
        large_threshold = config.get_threshold(gallery_size=100)
        
        assert large_threshold >= small_threshold
        assert config.ADAPTIVE_THRESHOLD_MIN <= small_threshold <= config.ADAPTIVE_THRESHOLD_MAX
    
    def test_paths_created(self):
        """Test that config creates necessary directories"""
        from services.face_config import FaceRecognitionConfig
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = FaceRecognitionConfig(
                BASE_DIR=tmpdir,
                FACES_FOLDER=os.path.join(tmpdir, 'faces'),
                EMBEDDINGS_FOLDER=os.path.join(tmpdir, 'faces', 'embeddings'),
                MODELS_FOLDER=os.path.join(tmpdir, 'models')
            )
            
            assert os.path.exists(config.FACES_FOLDER)
            assert os.path.exists(config.EMBEDDINGS_FOLDER)
            assert os.path.exists(config.MODELS_FOLDER)


class TestEmbeddingDatabase:
    """Test embedding database operations"""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing"""
        from services.face_recognition_engine import EmbeddingDatabase
        return EmbeddingDatabase(str(tmp_path / "embeddings"))
    
    def test_add_and_get(self, temp_db):
        """Test adding and retrieving embeddings"""
        embedding = np.random.randn(512).astype(np.float32)
        
        temp_db.add("user123", embedding, quality_score=85.0)
        
        retrieved = temp_db.get("user123")
        assert retrieved is not None
        assert retrieved.shape == (512,)
    
    def test_remove(self, temp_db):
        """Test removing embeddings"""
        embedding = np.random.randn(512).astype(np.float32)
        temp_db.add("user_to_delete", embedding)
        
        assert "user_to_delete" in temp_db
        
        result = temp_db.remove("user_to_delete")
        assert result is True
        assert "user_to_delete" not in temp_db
    
    def test_persistence(self, tmp_path):
        """Test that embeddings persist to disk"""
        from services.face_recognition_engine import EmbeddingDatabase
        
        folder = str(tmp_path / "persist_test")
        
        # Create and add
        db1 = EmbeddingDatabase(folder)
        embedding = np.random.randn(512).astype(np.float32)
        db1.add("persistent_user", embedding)
        
        # Create new instance - should load from disk
        db2 = EmbeddingDatabase(folder)
        assert "persistent_user" in db2
        
        retrieved = db2.get("persistent_user")
        assert retrieved is not None
    
    def test_get_all(self, temp_db):
        """Test getting all embeddings"""
        for i in range(3):
            embedding = np.random.randn(512).astype(np.float32)
            temp_db.add(f"user_{i}", embedding)
        
        all_embeddings = temp_db.get_all()
        assert len(all_embeddings) == 3
        assert all(uid in all_embeddings for uid in ["user_0", "user_1", "user_2"])


class TestFaceRecognitionEngine:
    """Test core face recognition engine"""
    
    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        try:
            from services.face_recognition_engine import FaceRecognitionEngine
            from services.face_config import FaceRecognitionConfig
            import tempfile
            
            with tempfile.TemporaryDirectory() as tmpdir:
                config = FaceRecognitionConfig(
                    MODELS_FOLDER=tmpdir,
                    VERBOSE_LOGGING=False
                )
                engine = FaceRecognitionEngine(config)
                if engine.is_ready:
                    return engine
                else:
                    pytest.skip("InsightFace not available")
        except ImportError:
            pytest.skip("InsightFace not installed")
    
    def test_embedding_comparison_same(self):
        """Test that same embedding gives similarity 1.0"""
        from services.face_recognition_engine import FaceRecognitionEngine
        from services.face_config import FaceRecognitionConfig
        
        config = FaceRecognitionConfig(VERBOSE_LOGGING=False)
        
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        # Create minimal engine just for comparison
        engine = object.__new__(FaceRecognitionEngine)
        engine.config = config
        
        similarity = engine.compare_embeddings(embedding, embedding)
        assert abs(similarity - 1.0) < 0.0001
    
    def test_embedding_comparison_different(self):
        """Test that different embeddings give lower similarity"""
        from services.face_recognition_engine import FaceRecognitionEngine
        from services.face_config import FaceRecognitionConfig
        
        config = FaceRecognitionConfig(VERBOSE_LOGGING=False)
        
        emb1 = np.random.randn(512).astype(np.float32)
        emb2 = np.random.randn(512).astype(np.float32)
        
        engine = object.__new__(FaceRecognitionEngine)
        engine.config = config
        
        similarity = engine.compare_embeddings(emb1, emb2)
        
        # Random embeddings should have low similarity (around 0.5 for random unit vectors)
        assert similarity < 0.8
    
    def test_embedding_aggregation(self):
        """Test multi-embedding aggregation"""
        from services.face_recognition_engine import FaceRecognitionEngine
        from services.face_config import FaceRecognitionConfig
        
        config = FaceRecognitionConfig(VERBOSE_LOGGING=False)
        engine = object.__new__(FaceRecognitionEngine)
        engine.config = config
        
        # Create similar embeddings (simulating same person)
        base = np.random.randn(512).astype(np.float32)
        embeddings = [
            base + np.random.randn(512) * 0.1 for _ in range(5)
        ]
        
        aggregated = engine.aggregate_embeddings(embeddings)
        
        assert aggregated.shape == (512,)
        # Aggregated should be normalized
        assert abs(np.linalg.norm(aggregated) - 1.0) < 0.01
    
    def test_find_best_match(self):
        """Test gallery matching"""
        from services.face_recognition_engine import FaceRecognitionEngine
        from services.face_config import FaceRecognitionConfig
        
        config = FaceRecognitionConfig(VERBOSE_LOGGING=False, MIN_MATCH_MARGIN=0.0)
        engine = object.__new__(FaceRecognitionEngine)
        engine.config = config
        
        # Create gallery
        gallery = {
            "user_a": np.random.randn(512).astype(np.float32),
            "user_b": np.random.randn(512).astype(np.float32),
        }
        
        # Normalize
        for k in gallery:
            gallery[k] = gallery[k] / np.linalg.norm(gallery[k])
        
        # Query with user_a's embedding
        query = gallery["user_a"].copy()
        
        matched_id, score, all_matches = engine.find_best_match(query, gallery, threshold=0.9)
        
        assert matched_id == "user_a"
        assert score > 0.99


class TestFaceQuality:
    """Test face quality assessment"""
    
    def test_quality_enum_values(self):
        """Test quality enum has expected values"""
        from services.face_recognition_engine import FaceQuality
        
        assert FaceQuality.GOOD.value == "good"
        assert FaceQuality.TOO_SMALL.value == "too_small"
        assert FaceQuality.TOO_BLURRY.value == "too_blurry"
        assert FaceQuality.BAD_ANGLE.value == "bad_angle"


class TestIntegration:
    """Integration tests (require InsightFace)"""
    
    @pytest.fixture
    def face_service(self, tmp_path):
        """Create face service for testing"""
        try:
            from services.face_service import FaceService
            from services.face_recognition_engine import INSIGHTFACE_AVAILABLE
            
            if not INSIGHTFACE_AVAILABLE:
                pytest.skip("InsightFace not installed")
            
            service = FaceService(str(tmp_path / "faces"))
            if not service.engine.is_ready:
                pytest.skip("Face engine not initialized")
            
            return service
        except ImportError as e:
            pytest.skip(f"Import error: {e}")
    
    def test_service_initialization(self, face_service):
        """Test that service initializes correctly"""
        assert face_service.engine.is_ready
        assert len(face_service.database) >= 0
    
    def test_list_users_empty(self, face_service):
        """Test listing users on empty database"""
        users = face_service.list_registered_users()
        assert isinstance(users, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
