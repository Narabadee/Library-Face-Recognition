"""
Line Crossing Detection Module
==============================
Detects when people cross a virtual line using YOLOv8 detection and centroid tracking.
Supports configurable line placement per camera and direction detection (IN/OUT).

Features:
- YOLOv8 person detection
- Multi-person tracking
- Configurable virtual line
- Direction detection
- Event logging with timestamps
"""

import cv2
import numpy as np
import json
import os
import time
import logging
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

import onnxruntime as ort

# Check onnxruntime is available for YOLO inference
ONNX_YOLO_AVAILABLE = False
try:
    ort.get_available_providers()
    ONNX_YOLO_AVAILABLE = True
except Exception as e:
    logger.warning(f"onnxruntime not available for YOLO: {e}")


@dataclass
class CrossingEvent:
    """Represents a line crossing event."""
    person_id: int
    direction: str  # "IN" or "OUT"
    timestamp: datetime
    camera_id: str
    position: Tuple[int, int]
    confidence: float = 0.0
    face_id: Optional[str] = None  # If face was recognized
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'person_id': self.person_id,
            'direction': self.direction,
            'timestamp': self.timestamp.isoformat(),
            'camera_id': self.camera_id,
            'position': self.position,
            'confidence': self.confidence,
            'face_id': self.face_id
        }


@dataclass 
class VirtualLine:
    """Represents a configurable virtual crossing line."""
    start: Tuple[int, int]
    end: Tuple[int, int]
    direction_vector: Tuple[float, float] = field(init=False)
    
    def __post_init__(self):
        # Calculate perpendicular direction vector
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        length = np.sqrt(dx**2 + dy**2)
        if length > 0:
            # Perpendicular (normal) vector - points to "IN" side
            self.direction_vector = (-dy / length, dx / length)
        else:
            self.direction_vector = (0, 1)
    
    def get_side(self, point: Tuple[int, int]) -> int:
        """
        Determine which side of the line a point is on.
        
        Returns:
            1 for "IN" side, -1 for "OUT" side, 0 on the line
        """
        # Vector from line start to point
        px = point[0] - self.start[0]
        py = point[1] - self.start[1]
        
        # Dot product with direction vector
        dot = px * self.direction_vector[0] + py * self.direction_vector[1]
        
        if dot > 5:
            return 1  # IN side
        elif dot < -5:
            return -1  # OUT side
        return 0  # On line
    
    def to_dict(self) -> Dict:
        return {
            'start': list(self.start),
            'end': list(self.end)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VirtualLine':
        return cls(
            start=tuple(data['start']),
            end=tuple(data['end'])
        )


class LineCrossingDetector:
    """
    Main line crossing detection system.
    
    Combines YOLOv8 person detection with centroid tracking
    to detect when people cross a virtual line.
    """
    
    def __init__(
        self,
        camera_id: str,
        model_path: str = "yolov8n.onnx",
        config_folder: str = "data/line_config"
    ):
        """
        Initialize the line crossing detector.
        
        Args:
            camera_id: Unique identifier for this camera
            model_path: Path to YOLOv8 model (or model name to download)
            config_folder: Folder to save line configurations
        """
        self.camera_id = camera_id
        self.config_folder = config_folder
        os.makedirs(config_folder, exist_ok=True)
        
        # Load YOLOv8 ONNX model via onnxruntime
        self.model = None
        self.input_name = None
        if ONNX_YOLO_AVAILABLE:
            try:
                logger.info(f"Loading YOLOv8 ONNX model: {model_path}")
                self.model = ort.InferenceSession(
                    model_path,
                    providers=['CPUExecutionProvider']
                )
                self.input_name = self.model.get_inputs()[0].name
                logger.info("YOLOv8 model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load YOLOv8 ONNX model: {e}")
        
        # Import tracker
        from .person_tracker import CentroidTracker
        self.tracker = CentroidTracker(max_disappeared=30, max_distance=100)
        
        # Virtual line
        self.line: Optional[VirtualLine] = None
        self._load_line_config()
        
        # Track which persons have crossed
        self.crossed_persons: Dict[int, str] = {}  # person_id -> direction
        
        # Event history
        self.events: deque = deque(maxlen=100)
        
        # Counters
        self.in_count = 0
        self.out_count = 0
        
        # Previous positions for crossing detection
        self.prev_sides: Dict[int, int] = {}
    
    def _get_config_path(self) -> str:
        """Get path to config file for this camera."""
        return os.path.join(self.config_folder, f"{self.camera_id}_line.json")
    
    def _load_line_config(self):
        """Load line configuration from file."""
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                self.line = VirtualLine.from_dict(data['line'])
                self.in_count = data.get('in_count', 0)
                self.out_count = data.get('out_count', 0)
                logger.info(f"Loaded line config for {self.camera_id}")
            except Exception as e:
                logger.error(f"Failed to load line config: {e}")
    
    def _save_line_config(self):
        """Save line configuration to file."""
        if self.line is None:
            return
        
        config_path = self._get_config_path()
        try:
            data = {
                'line': self.line.to_dict(),
                'in_count': self.in_count,
                'out_count': self.out_count
            }
            with open(config_path, 'w') as f:
                json.dump(data, f)
            logger.info(f"Saved line config for {self.camera_id}")
        except Exception as e:
            logger.error(f"Failed to save line config: {e}")
    
    def set_line(self, start: Tuple[int, int], end: Tuple[int, int]):
        """
        Set the virtual crossing line.
        
        Args:
            start: Starting point (x, y)
            end: Ending point (x, y)
        """
        self.line = VirtualLine(start=start, end=end)
        self._save_line_config()
        logger.info(f"Line set: {start} -> {end}")
    
    def reset_counters(self):
        """Reset IN/OUT counters."""
        self.in_count = 0
        self.out_count = 0
        self._save_line_config()
    
    def detect_persons(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect persons in frame using YOLOv8 ONNX model.

        Args:
            frame: BGR image

        Returns:
            List of bounding boxes [(x1, y1, x2, y2), ...]
        """
        if self.model is None:
            return []

        orig_h, orig_w = frame.shape[:2]
        input_size = 640

        # Letterbox resize to 640x640
        scale = min(input_size / orig_w, input_size / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        resized = cv2.resize(frame, (new_w, new_h))
        canvas = np.zeros((input_size, input_size, 3), dtype=np.uint8)
        pad_x = (input_size - new_w) // 2
        pad_y = (input_size - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        # BGR→RGB, normalize, add batch dim
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis]  # (1, 3, 640, 640)

        # Run ONNX inference
        output = self.model.run(None, {self.input_name: blob})[0]  # (1, 84, 8400)
        output = output[0].T  # (8400, 84): cx,cy,w,h + 80 class scores

        # Filter by person class (index 0) confidence
        person_scores = output[:, 4]   # class 0 score
        mask = person_scores >= 0.5
        if not np.any(mask):
            return []

        boxes_raw = output[mask, :4]   # cx, cy, w, h
        confs = person_scores[mask]

        # Convert center format → corner format, scale to original image
        x1 = ((boxes_raw[:, 0] - boxes_raw[:, 2] / 2 - pad_x) / scale).astype(int)
        y1 = ((boxes_raw[:, 1] - boxes_raw[:, 3] / 2 - pad_y) / scale).astype(int)
        x2 = ((boxes_raw[:, 0] + boxes_raw[:, 2] / 2 - pad_x) / scale).astype(int)
        y2 = ((boxes_raw[:, 1] + boxes_raw[:, 3] / 2 - pad_y) / scale).astype(int)

        x1 = np.clip(x1, 0, orig_w); y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w); y2 = np.clip(y2, 0, orig_h)

        # NMS via OpenCV
        boxes_list = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).astype(float).tolist()
        indices = cv2.dnn.NMSBoxes(boxes_list, confs.tolist(), 0.5, 0.45)

        detections = []
        if len(indices) > 0:
            for i in np.array(indices).flatten():
                detections.append((int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])))
        return detections
    
    def check_line_crossing(self, person) -> Optional[str]:
        """
        Check if a person has crossed the line.
        
        Args:
            person: TrackedPerson object
            
        Returns:
            "IN", "OUT", or None if no crossing
        """
        if self.line is None:
            return None
        
        # Get current side
        current_side = self.line.get_side(person.centroid)
        
        # Get previous side
        prev_side = self.prev_sides.get(person.id, 0)
        
        # Store current side for next frame
        self.prev_sides[person.id] = current_side
        
        # Check for crossing
        if prev_side != 0 and current_side != 0 and prev_side != current_side:
            # Person crossed the line
            if current_side == 1:
                return "IN"
            else:
                return "OUT"
        
        return None
    
    def process_frame(
        self, 
        frame: np.ndarray,
        face_recognizer=None
    ) -> Tuple[np.ndarray, List[CrossingEvent]]:
        """
        Process a frame for line crossing detection.
        
        Args:
            frame: BGR image
            face_recognizer: Optional FaceService for identity recognition
            
        Returns:
            (annotated_frame, list of new crossing events)
        """
        new_events = []
        
        # Detect persons
        detections = self.detect_persons(frame)
        
        # Update tracker
        tracked = self.tracker.update(detections)
        
        # Check line crossings
        for person_id, person in tracked.items():
            # Skip if already counted
            if person_id in self.crossed_persons:
                continue
            
            direction = self.check_line_crossing(person)
            if direction:
                # Line crossed!
                self.crossed_persons[person_id] = direction
                
                if direction == "IN":
                    self.in_count += 1
                else:
                    self.out_count += 1
                
                # Try face recognition if available
                face_id = None
                if face_recognizer:
                    try:
                        # Crop person region for face recognition
                        x1, y1, x2, y2 = person.bbox
                        person_crop = frame[y1:y2, x1:x2]
                        # This would need base64 encoding - simplified here
                        # face_id = face_recognizer.recognize_face(...)
                    except:
                        pass
                
                # Create event
                event = CrossingEvent(
                    person_id=person_id,
                    direction=direction,
                    timestamp=datetime.now(),
                    camera_id=self.camera_id,
                    position=person.centroid,
                    face_id=face_id
                )
                
                new_events.append(event)
                self.events.append(event)
                
                logger.info(f"Line crossing: Person {person_id} -> {direction}")
        
        # Clean up old crossed persons
        active_ids = set(tracked.keys())
        self.crossed_persons = {
            pid: d for pid, d in self.crossed_persons.items() 
            if pid in active_ids
        }
        
        # Clean up prev_sides
        self.prev_sides = {
            pid: s for pid, s in self.prev_sides.items() 
            if pid in active_ids
        }
        
        # Draw annotations
        annotated = self.draw_overlay(frame, tracked)
        
        # Save config periodically
        if len(new_events) > 0:
            self._save_line_config()
        
        return annotated, new_events
    
    def draw_overlay(
        self, 
        frame: np.ndarray, 
        tracked: Dict
    ) -> np.ndarray:
        """Draw detection overlay on frame."""
        output = frame.copy()
        
        # Draw virtual line
        if self.line:
            cv2.line(
                output, 
                self.line.start, 
                self.line.end, 
                (0, 255, 255),  # Yellow
                3
            )
            
            # Draw direction indicator
            mid = (
                (self.line.start[0] + self.line.end[0]) // 2,
                (self.line.start[1] + self.line.end[1]) // 2
            )
            in_side = (
                int(mid[0] + self.line.direction_vector[0] * 30),
                int(mid[1] + self.line.direction_vector[1] * 30)
            )
            cv2.arrowedLine(output, mid, in_side, (0, 255, 0), 2)
            cv2.putText(output, "IN", in_side, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw tracked persons
        for person_id, person in tracked.items():
            x1, y1, x2, y2 = person.bbox
            
            # Color based on crossing status
            color = (0, 255, 0)  # Green by default
            if person_id in self.crossed_persons:
                if self.crossed_persons[person_id] == "IN":
                    color = (255, 0, 0)  # Blue for IN
                else:
                    color = (0, 0, 255)  # Red for OUT
            
            # Draw bounding box
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            
            # Draw ID
            cv2.putText(
                output, 
                f"ID:{person_id}", 
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                color, 
                2
            )
            
            # Draw centroid
            cv2.circle(output, person.centroid, 4, color, -1)
        
        # Draw counters
        cv2.putText(
            output, 
            f"IN: {self.in_count}", 
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (255, 0, 0),  # Blue
            2
        )
        cv2.putText(
            output, 
            f"OUT: {self.out_count}", 
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (0, 0, 255),  # Red
            2
        )
        
        return output
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            'camera_id': self.camera_id,
            'in_count': self.in_count,
            'out_count': self.out_count,
            'net_count': self.in_count - self.out_count,
            'line_configured': self.line is not None,
            'tracker_active': len(self.tracker.objects),
            'yolo_available': ONNX_YOLO_AVAILABLE
        }
    
    def get_recent_events(self, limit: int = 20) -> List[Dict]:
        """Get recent crossing events."""
        events = list(self.events)[-limit:]
        return [e.to_dict() for e in events]
    
    @property
    def is_ready(self) -> bool:
        """Check if detector is ready."""
        return self.model is not None and self.line is not None
