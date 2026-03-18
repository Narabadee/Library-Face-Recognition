"""
ONNX Face Recognition
=====================
Direct ONNX inference for face detection and embedding.
Does NOT require InsightFace compilation.

Uses:
- det_10g.onnx (RetinaFace) for detection
- w600k_r50.onnx (ArcFace) for embeddings
"""

import numpy as np
import cv2
import os
import logging
from typing import Optional, Tuple, List

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

logger = logging.getLogger(__name__)


class ONNXRetinaFace:
    """
    RetinaFace detector using ONNX Runtime.
    Detects faces and extracts 5-point landmarks.
    """
    
    def __init__(self, model_path: str, input_size: Tuple[int, int] = (640, 640)):
        """
        Initialize RetinaFace detector.
        
        Args:
            model_path: Path to det_10g.onnx
            input_size: Input size for detection (width, height)
        """
        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX Runtime not installed")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        self.input_size = input_size
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )
        
        # Get input/output info
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        
        # Detection parameters
        self.nms_threshold = 0.4
        self.det_threshold = 0.5
        
        # Anchor settings for RetinaFace
        self._fmc = 3
        self._feat_stride_fpn = [8, 16, 32]
        self._num_anchors = 2
        
        logger.info(f"RetinaFace ONNX model loaded: {model_path}")
    
    def detect(self, image: np.ndarray, threshold: float = 0.5) -> List[dict]:
        """
        Detect faces in image.
        
        Args:
            image: BGR image
            threshold: Detection confidence threshold
            
        Returns:
            List of dicts with 'bbox', 'landmarks', 'confidence'
        """
        self.det_threshold = threshold
        
        # Preprocess
        input_height, input_width = self.input_size
        im_ratio = float(image.shape[0]) / image.shape[1]
        model_ratio = float(input_height) / input_width
        
        if im_ratio > model_ratio:
            new_height = input_height
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_width
            new_height = int(new_width * im_ratio)
        
        det_scale = float(new_height) / image.shape[0]
        resized = cv2.resize(image, (new_width, new_height))
        
        # Pad to input size
        det_img = np.zeros((input_height, input_width, 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized
        
        # Normalize and transpose
        input_blob = (det_img.astype(np.float32) - 127.5) / 128.0
        input_blob = input_blob.transpose(2, 0, 1)
        input_blob = np.expand_dims(input_blob, axis=0)
        
        # Run inference
        outputs = self.session.run(self.output_names, {self.input_name: input_blob})
        
        # Parse outputs
        faces = self._postprocess(outputs, det_scale)
        
        return faces
    
    def _postprocess(self, outputs: List[np.ndarray], det_scale: float) -> List[dict]:
        """Parse RetinaFace outputs"""
        scores_list = []
        bboxes_list = []
        kpss_list = []
        
        fmc = self._fmc
        
        for idx, stride in enumerate(self._feat_stride_fpn):
            scores = outputs[idx]
            bbox_preds = outputs[idx + fmc]
            kps_preds = outputs[idx + fmc * 2] if len(outputs) > fmc * 2 else None
            
            height = self.input_size[0] // stride
            width = self.input_size[1] // stride
            
            # Generate anchor centers
            anchor_centers = np.stack(
                np.mgrid[:height, :width][::-1], axis=-1
            ).astype(np.float32)
            anchor_centers = (anchor_centers * stride).reshape((-1, 2))
            
            if self._num_anchors > 1:
                anchor_centers = np.stack(
                    [anchor_centers] * self._num_anchors, axis=1
                ).reshape((-1, 2))
            
            # Parse scores
            scores = scores.flatten()
            
            # Parse bboxes
            bbox_preds = bbox_preds.reshape((-1, 4))
            bbox_preds *= stride
            
            # Parse keypoints if available
            if kps_preds is not None:
                kps_preds = kps_preds.reshape((-1, 10))
                kps_preds *= stride
            
            # Apply threshold
            pos_inds = np.where(scores >= self.det_threshold)[0]
            
            if len(pos_inds) > 0:
                scores_list.append(scores[pos_inds])
                
                bboxes = self._distance2bbox(anchor_centers, bbox_preds)
                bboxes_list.append(bboxes[pos_inds])
                
                if kps_preds is not None:
                    kpss = self._distance2kps(anchor_centers, kps_preds)
                    kpss_list.append(kpss[pos_inds])
        
        if len(scores_list) == 0:
            return []
        
        scores = np.concatenate(scores_list)
        bboxes = np.concatenate(bboxes_list)
        kpss = np.concatenate(kpss_list) if kpss_list else None
        
        # Scale back
        bboxes /= det_scale
        if kpss is not None:
            kpss /= det_scale
        
        # NMS
        keep = self._nms(bboxes, scores, self.nms_threshold)
        
        faces = []
        for i in keep:
            face = {
                'bbox': bboxes[i],
                'confidence': float(scores[i]),
                'landmarks': kpss[i].reshape((5, 2)) if kpss is not None else None
            }
            faces.append(face)
        
        return faces
    
    def _distance2bbox(self, points: np.ndarray, distance: np.ndarray) -> np.ndarray:
        """Convert distance to bounding box"""
        x1 = points[:, 0] - distance[:, 0]
        y1 = points[:, 1] - distance[:, 1]
        x2 = points[:, 0] + distance[:, 2]
        y2 = points[:, 1] + distance[:, 3]
        return np.stack([x1, y1, x2, y2], axis=-1)
    
    def _distance2kps(self, points: np.ndarray, distance: np.ndarray) -> np.ndarray:
        """Convert distance to keypoints"""
        kps = distance.copy()
        for i in range(0, 10, 2):
            kps[:, i] = points[:, 0] + distance[:, i]
            kps[:, i + 1] = points[:, 1] + distance[:, i + 1]
        return kps
    
    def _nms(self, bboxes: np.ndarray, scores: np.ndarray, threshold: float) -> List[int]:
        """Non-maximum suppression"""
        x1 = bboxes[:, 0]
        y1 = bboxes[:, 1]
        x2 = bboxes[:, 2]
        y2 = bboxes[:, 3]
        
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            
            inds = np.where(ovr <= threshold)[0]
            order = order[inds + 1]
        
        return keep


class ONNXArcFace:
    """
    ArcFace embedding extractor using ONNX Runtime.
    Produces 512-dimensional face embeddings.
    """
    
    def __init__(self, model_path: str):
        """
        Initialize ArcFace embedding extractor.
        
        Args:
            model_path: Path to w600k_r50.onnx
        """
        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX Runtime not installed")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )
        
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.input_size = (112, 112)
        
        logger.info(f"ArcFace ONNX model loaded: {model_path}")
    
    def get_embedding(self, face_img: np.ndarray) -> np.ndarray:
        """
        Extract face embedding.
        
        Args:
            face_img: Aligned face image (112x112, BGR)
            
        Returns:
            512-dimensional normalized embedding
        """
        # Ensure correct size
        if face_img.shape[:2] != self.input_size:
            face_img = cv2.resize(face_img, self.input_size)
        
        # Preprocess: normalize and transpose
        blob = (face_img.astype(np.float32) - 127.5) / 127.5
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        
        # Run inference
        outputs = self.session.run(None, {self.input_name: blob})
        embedding = outputs[0].flatten()
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding


class FaceAligner:
    """
    Align faces using 5-point landmarks.
    Standard ArcFace alignment to 112x112.
    """
    
    # Standard reference landmarks for 112x112
    REFERENCE = np.array([
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041]
    ], dtype=np.float32)
    
    @staticmethod
    def align(image: np.ndarray, landmarks: np.ndarray, output_size: Tuple[int, int] = (112, 112)) -> Optional[np.ndarray]:
        """
        Align face using similarity transformation.
        
        Args:
            image: BGR image
            landmarks: 5-point landmarks (5, 2)
            output_size: Output size
            
        Returns:
            Aligned face image or None if failed
        """
        if landmarks is None or len(landmarks) < 5:
            return None
        
        try:
            src = np.array(landmarks[:5], dtype=np.float32)
            
            # Scale reference to output size
            dst = FaceAligner.REFERENCE.copy()
            if output_size != (112, 112):
                dst[:, 0] *= output_size[0] / 112
                dst[:, 1] *= output_size[1] / 112
            
            # Estimate similarity transform
            tform = cv2.estimateAffinePartial2D(src, dst)[0]
            
            if tform is None:
                return None
            
            aligned = cv2.warpAffine(image, tform, output_size, borderValue=(0, 0, 0))
            return aligned
            
        except Exception as e:
            logger.error(f"Face alignment failed: {e}")
            return None
