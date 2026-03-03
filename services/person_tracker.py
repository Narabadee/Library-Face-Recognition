"""
Person Tracker Module
=====================
Lightweight centroid-based multi-person tracking for line crossing detection.
Maintains unique IDs across frames and tracks movement history.

Optimized for real-time performance (20+ FPS on CPU).
"""

import numpy as np
from collections import OrderedDict
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrackedPerson:
    """Represents a tracked person with position history."""
    id: int
    centroid: Tuple[int, int]
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    positions: List[Tuple[int, int]] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    crossed_line: bool = False
    cross_direction: Optional[str] = None  # "IN" or "OUT"
    
    def update(self, centroid: Tuple[int, int], bbox: Tuple[int, int, int, int]):
        """Update position and add to history."""
        self.positions.append(self.centroid)
        if len(self.positions) > 30:  # Keep last 30 positions
            self.positions.pop(0)
        self.centroid = centroid
        self.bbox = bbox
        self.last_seen = time.time()
    
    @property
    def velocity(self) -> Tuple[float, float]:
        """Calculate velocity from recent positions."""
        if len(self.positions) < 2:
            return (0.0, 0.0)
        
        # Average velocity over last 5 positions
        n = min(5, len(self.positions))
        dx = self.centroid[0] - self.positions[-n][0]
        dy = self.centroid[1] - self.positions[-n][1]
        return (dx / n, dy / n)


class CentroidTracker:
    """
    Centroid-based multi-object tracker.
    
    Assigns unique IDs to detected objects and maintains tracking
    across frames using distance-based association.
    """
    
    def __init__(
        self,
        max_disappeared: int = 30,
        max_distance: float = 80.0
    ):
        """
        Initialize the tracker.
        
        Args:
            max_disappeared: Max frames before removing a track
            max_distance: Max distance for centroid matching
        """
        self.next_id = 0
        self.objects: Dict[int, TrackedPerson] = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.disappeared: Dict[int, int] = OrderedDict()
    
    def register(self, centroid: Tuple[int, int], bbox: Tuple[int, int, int, int]) -> int:
        """Register a new object with the next available ID."""
        person = TrackedPerson(
            id=self.next_id,
            centroid=centroid,
            bbox=bbox
        )
        self.objects[self.next_id] = person
        self.disappeared[self.next_id] = 0
        self.next_id += 1
        return person.id
    
    def deregister(self, object_id: int):
        """Remove an object from tracking."""
        if object_id in self.objects:
            del self.objects[object_id]
        if object_id in self.disappeared:
            del self.disappeared[object_id]
    
    def update(self, detections: List[Tuple[int, int, int, int]]) -> Dict[int, TrackedPerson]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of bounding boxes [(x1, y1, x2, y2), ...]
            
        Returns:
            Dictionary of tracked persons {id: TrackedPerson}
        """
        # No detections - mark all as disappeared
        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects
        
        # Calculate centroids for new detections
        input_centroids = []
        for det in detections:
            x1, y1, x2, y2 = det
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            input_centroids.append((cx, cy))
        
        # If no existing objects, register all
        if len(self.objects) == 0:
            for i, centroid in enumerate(input_centroids):
                self.register(centroid, detections[i])
        else:
            # Match detections to existing objects
            object_ids = list(self.objects.keys())
            object_centroids = [self.objects[oid].centroid for oid in object_ids]
            
            # Calculate distance matrix
            distances = np.zeros((len(object_centroids), len(input_centroids)))
            for i, oc in enumerate(object_centroids):
                for j, ic in enumerate(input_centroids):
                    distances[i, j] = np.sqrt((oc[0] - ic[0])**2 + (oc[1] - ic[1])**2)
            
            # Hungarian algorithm approximation using greedy matching
            rows = distances.min(axis=1).argsort()
            cols = distances.argmin(axis=1)[rows]
            
            used_rows = set()
            used_cols = set()
            
            for row, col in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                
                if distances[row, col] > self.max_distance:
                    continue
                
                object_id = object_ids[row]
                self.objects[object_id].update(input_centroids[col], detections[col])
                self.disappeared[object_id] = 0
                
                used_rows.add(row)
                used_cols.add(col)
            
            # Handle unmatched existing objects
            unused_rows = set(range(len(object_centroids))) - used_rows
            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            
            # Register new detections
            unused_cols = set(range(len(input_centroids))) - used_cols
            for col in unused_cols:
                self.register(input_centroids[col], detections[col])
        
        return self.objects
    
    def get_all_tracks(self) -> List[TrackedPerson]:
        """Get all currently tracked persons."""
        return list(self.objects.values())
    
    def reset(self):
        """Reset the tracker."""
        self.objects.clear()
        self.disappeared.clear()
        self.next_id = 0
