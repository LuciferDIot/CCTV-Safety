"""Event record data model for safety violations and exemptions."""
from typing import Dict, List, Optional, Any, Tuple
import numpy as np


class EventRecord:
    """Represents a timestamped, tracked safety event or infraction."""

    def __init__(
        self, event_id: str, event_type: str, start_frame: int,
        start_ts: float, track_id: int, confidence: float = 0.88,
        details: str = "", lane_or_zone: str = ""
    ):
        self.id = event_id
        self.event_type = event_type
        self.start_frame = start_frame
        self.end_frame = start_frame
        self.start_ts = round(start_ts, 2)
        self.end_ts = round(start_ts, 2)
        self.track_id = track_id
        self.confidence = confidence
        self.details = details
        self.lane_or_zone = lane_or_zone
        self.status = "ACTIVE"
        self.frame_indices: List[int] = [start_frame]
        self.bounding_boxes: List[np.ndarray] = []
        self.positions: List[Tuple[float, float]] = []

    def update(
        self, frame_idx: int, timestamp: float,
        xyxy: Optional[np.ndarray] = None, pos: Optional[Tuple[float, float]] = None
    ) -> None:
        """Update active event bounds and timestamps."""
        self.end_frame = frame_idx
        self.end_ts = round(timestamp, 2)
        self.frame_indices.append(frame_idx)
        if xyxy is not None:
            self.bounding_boxes.append(xyxy.copy())
        if pos is not None:
            self.positions.append(pos)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary schema with exact frame and seconds."""
        status_val = "CONFIRMED"
        if self.event_type == "EXEMPT_WALKING":
            status_val = "EXEMPT"
        elif self.event_type == "INSUFFICIENT_EVIDENCE":
            status_val = "INSUFFICIENT_EVIDENCE"

        duration = round(float(self.end_ts - self.start_ts), 2)
        return {
            "id": str(self.id),
            "event_id": str(self.id),
            "status": status_val,
            "event_type": str(self.event_type),
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "start_ts": float(self.start_ts),
            "end_ts": float(self.end_ts),
            "time_start": float(self.start_ts),
            "time_end": float(self.end_ts),
            "track_id": int(self.track_id),
            "track_ids": [int(self.track_id)],
            "confidence": round(float(self.confidence), 3),
            "lane_or_zone": str(self.lane_or_zone),
            "details": str(self.details),
            "explanation": str(self.details),
            "duration_s": duration,
            "duration_sec": duration
        }
