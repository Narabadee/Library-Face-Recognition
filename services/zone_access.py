"""
Zone-Based Access Control System
================================
Implements three-zone spatial filtering with per-person state machine
for intelligent access control.

Zones:
- Zone 1 (Detection): Lightweight person tracking only
- Zone 2 (Intent): Face detection + quality check, buffer frames
- Zone 3 (Auth): Full recognition + database commit

State Machine per person:
OUTSIDE → OBSERVED → INTENT → AUTH → EXIT
"""

import os
import cv2
import time
import logging
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


class PersonState(Enum):
    """State machine states for each tracked person."""
    OUTSIDE = "outside"      # Not yet detected
    OBSERVED = "observed"    # In Zone 1 - tracking only
    INTENT = "intent"        # Crossed Line A - face detection active
    AUTH = "auth"            # Crossed Line B - full recognition
    EXIT = "exit"            # Completed or left frame


@dataclass
class TrackedPerson:
    """Represents a tracked person with state machine."""
    person_id: int
    state: PersonState = PersonState.OUTSIDE
    
    # Position tracking
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x1, y1, x2, y2
    centroid: Tuple[int, int] = (0, 0)
    
    # State timestamps
    first_seen: float = field(default_factory=time.time)
    state_changed: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    # Face data (buffered in INTENT, used in AUTH)
    face_frames: deque = field(default_factory=lambda: deque(maxlen=5))
    best_face_quality: float = 0.0
    face_embedding: Optional[Any] = None
    
    # Recognition result
    matched_user_id: Optional[str] = None
    match_confidence: float = 0.0
    auth_completed: bool = False
    
    def update_position(self, bbox: Tuple[int, int, int, int]):
        """Update position from new detection."""
        self.bbox = bbox
        self.centroid = (
            (bbox[0] + bbox[2]) // 2,
            (bbox[1] + bbox[3]) // 2
        )
        self.last_seen = time.time()
    
    def transition_to(self, new_state: PersonState):
        """Transition to a new state."""
        if self.state != new_state:
            logger.info(f"Person {self.person_id}: {self.state.value} → {new_state.value}")
            self.state = new_state
            self.state_changed = time.time()
    
    def time_in_state(self) -> float:
        """Get time spent in current state."""
        return time.time() - self.state_changed
    
    def is_stale(self, timeout: float = 5.0) -> bool:
        """Check if person hasn't been seen recently."""
        return time.time() - self.last_seen > timeout


class ZoneAccessController:
    """
    Three-zone access control with state machine.
    
    Supports rectangular areas for each zone.
    """
    
    def __init__(
        self,
        camera_id: str,
        config_dir: str = "config/zones",
        state_timeout: float = 10.0
    ):
        self.camera_id = camera_id
        self.config_dir = config_dir
        self.state_timeout = state_timeout
        self.config_path = os.path.join(config_dir, f"{camera_id}_zones.json")
        
        # Ensure config dir exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Zone areas: { zone_id (1, 2, 3): {x, y, w, h} }
        # coordinates are normalized 0.0 - 1.0
        self.zone_areas: Dict[int, Dict[str, float]] = {
            1: None,
            2: None,
            3: None
        }
        
        # Tracked persons by ID
        self.persons: Dict[int, TrackedPerson] = {}
        
        # Counters
        self.auth_count = 0
        self.total_detected = 0
        
        # Callbacks (set by integrating code)
        self.on_intent_enter = None  # Called when entering Zone 2
        self.on_auth_enter = None    # Called when entering Zone 3
        self.on_auth_complete = None # Called after successful auth
        
        # Load existing config
        self.load_config()
    
    def load_config(self):
        """Load zone configuration from file."""
        import json
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    # Convert string keys to int
                    self.zone_areas = {int(k): v for k, v in data.get('zones', {}).items()}
                    logger.info(f"Loaded zone config for {self.camera_id}")
            except Exception as e:
                logger.error(f"Error loading zone config: {e}")

    def save_config(self):
        """Save zone configuration to file."""
        import json
        try:
            with open(self.config_path, 'w') as f:
                json.dump({'zones': self.zone_areas}, f)
                logger.info(f"Saved zone config for {self.camera_id}")
        except Exception as e:
            logger.error(f"Error saving zone config: {e}")

    def get_zone(self, x: float, y: float) -> int:
        """
        Determine which zone a normalized position (0-1) is in using point-in-polygon.
        
        Zones are checked in order: 3 (Auth), 2 (Intent), 1 (Detection).
        """
        import numpy as np
        
        point = (x, y)
        
        # Check in reverse order (highest priority zone first)
        for zone_id in [3, 2, 1]:
            points = self.zone_areas.get(zone_id)
            if points and isinstance(points, list) and len(points) >= 3:
                # points is a list of [x, y] normalized coordinates
                # Convert to numpy array for OpenCV
                pts_array = np.array(points, dtype=np.float32)
                
                # cv2.pointPolygonTest expects coordinates. 
                # Since we use normalized 0-1, we can just pass them as is.
                # result > 0: inside, 0: on edge, < 0: outside
                result = cv2.pointPolygonTest(pts_array, point, False)
                if result >= 0:
                    return zone_id
        return 0  # No zone
    
    def update(
        self,
        detections: List[Tuple[int, int, int, int]],  # List of bboxes (x1, y1, x2, y2)
        width: int,
        height: int,
        frame=None  # Optional frame for face processing
    ) -> List[TrackedPerson]:
        """
        Update tracking and state machine for all detections.
        """
        matched_ids = set()
        auth_needed = []
        
        # Simple centroid matching
        for bbox in detections:
            centroid = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
            norm_x = centroid[0] / width
            norm_y = centroid[1] / height
            
            # Find closest existing person
            best_match = None
            best_dist = float('inf')
            
            for pid, person in self.persons.items():
                if pid in matched_ids:
                    continue
                dist = ((person.centroid[0] - centroid[0])**2 + 
                        (person.centroid[1] - centroid[1])**2) ** 0.5
                if dist < 100 and dist < best_dist:
                    best_dist = dist
                    best_match = pid
            
            if best_match is not None:
                person = self.persons[best_match]
                matched_ids.add(best_match)
            else:
                # New person
                new_id = self.total_detected
                self.total_detected += 1
                person = TrackedPerson(person_id=new_id)
                self.persons[new_id] = person
                matched_ids.add(new_id)
            
            # Update position
            person.update_position(bbox)
            
            # Get current zone
            zone = self.get_zone(norm_x, norm_y)
            
            # State machine transitions
            if person.state == PersonState.OUTSIDE:
                if zone >= 1:
                    person.transition_to(PersonState.OBSERVED)
            
            if person.state == PersonState.OBSERVED and zone >= 2:
                person.transition_to(PersonState.INTENT)
                if self.on_intent_enter:
                    self.on_intent_enter(person)
            
            if person.state == PersonState.INTENT:
                # Buffer face frame
                if frame is not None:
                    x1, y1, x2, y2 = bbox
                    # Ensure bbox is within frame boundaries
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(width, x2), min(height, y2)
                    if x2 > x1 and y2 > y1:
                        face_crop = frame[y1:y2, x1:x2].copy()
                        person.face_frames.append(face_crop)
                
                if zone >= 3:
                    person.transition_to(PersonState.AUTH)
                    auth_needed.append(person)
                    if self.on_auth_enter:
                        self.on_auth_enter(person)
            
            if person.state == PersonState.AUTH and not person.auth_completed:
                auth_needed.append(person)
        
        # Clean up stale persons
        stale = [pid for pid, p in self.persons.items() 
                 if p.is_stale(self.state_timeout)]
        for pid in stale:
            del self.persons[pid]
        
        return auth_needed
    
    def complete_auth(self, person: TrackedPerson, user_id: str, confidence: float):
        """Mark person as authenticated."""
        person.matched_user_id = user_id
        person.match_confidence = confidence
        person.auth_completed = True
        person.transition_to(PersonState.EXIT)
        self.auth_count += 1
        
        if self.on_auth_complete:
            self.on_auth_complete(person)
        
        logger.info(f"Auth complete: Person {person.person_id} → {user_id} ({confidence:.1%})")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        state_counts = {}
        for state in PersonState:
            state_counts[state.value] = sum(
                1 for p in self.persons.values() if p.state == state
            )
        
        return {
            'camera_id': self.camera_id,
            'tracked_persons': len(self.persons),
            'auth_count': self.auth_count,
            'total_detected': self.total_detected,
            'zones': self.zone_areas,
            'states': state_counts
        }
    
    def set_areas(self, zones_data: Dict[int, Dict[str, float]]):
        """Update zone areas and save."""
        self.zone_areas = zones_data
        self.save_config()

