"""Track state representation for tracked objects."""
from collections import deque
from typing import Tuple, Optional
import numpy as np
from src.core.anchors import get_ground_anchor


class TrackState:
    """Maintains trajectory history and status for a single canonical vehicle track."""

    def __init__(self, canonical_id: int, initial_frame: int, xyxy: np.ndarray, class_id: int):
        self.canonical_id = canonical_id
        self.raw_tids = set()
        self.class_id = class_id
        self.history = deque(maxlen=60)
        self.last_seen_frame = initial_frame
        self.first_seen_frame = initial_frame
        self.missed_count = 0
        self.is_active = True
        self.status = "NORMAL"

        cx, cy = get_ground_anchor(xyxy)
        self.history.append((initial_frame, cx, cy, xyxy.copy()))

    def update(
        self,
        frame_idx: int,
        xyxy: np.ndarray,
        class_id: int,
        raw_tid: Optional[int] = None
    ) -> None:
        """Update track with a new detection box and timestamp."""
        if raw_tid is not None:
            self.raw_tids.add(raw_tid)
        self.class_id = class_id
        self.last_seen_frame = frame_idx
        self.missed_count = 0
        self.is_active = True
        cx, cy = get_ground_anchor(xyxy)
        self.history.append((frame_idx, cx, cy, xyxy.copy()))

    def predict_next(self) -> Tuple[float, float]:
        """Extrapolate next ground position using recent velocity."""
        if len(self.history) < 2:
            return (self.history[-1][1], self.history[-1][2])
        p1, p0 = self.history[-1], self.history[-2]
        dt = max(1, p1[0] - p0[0])
        vx = (p1[1] - p0[1]) / float(dt)
        vy = (p1[2] - p0[2]) / float(dt)
        return (p1[1] + vx, p1[2] + vy)

