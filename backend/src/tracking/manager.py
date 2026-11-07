"""Robust tracking manager with identity maintenance and track stitching."""
import math
from typing import Dict, Optional, Any
import numpy as np
import supervision as sv

from src.core.anchors import get_ground_anchor
from src.core.perspective import compute_perspective_scale
from src.tracking.state import TrackState
from src.tracking.nms import suppress_duplicate_bikes


class RobustTrackerManager:
    """Manages object tracks, resolves identity switches, and stitches trajectories."""

    def __init__(
        self,
        max_reconnect_frames: int = 25,
        max_reconnect_dist_px: float = 180.0,
        frame_height: float = 2160.0,
        perspective_cfg: Optional[Any] = None
    ):
        self.max_reconnect_frames = max_reconnect_frames
        self.max_reconnect_dist_px = max_reconnect_dist_px
        self.frame_height = frame_height
        self.perspective_cfg = perspective_cfg

        self.next_canonical_id = 1
        self.raw_to_canonical: Dict[int, int] = {}
        self.tracks: Dict[int, TrackState] = {}

    def suppress_duplicate_bikes(
        self,
        detections: sv.Detections,
        iou_threshold: float = 0.25
    ) -> sv.Detections:
        """Filter duplicate bike boxes."""
        return suppress_duplicate_bikes(detections, iou_threshold)

    def _attempt_stitch(self, xyxy: np.ndarray, class_id: int, frame_idx: int) -> Optional[int]:
        """Match detection to lost tracks via perspective-aware distance."""
        cx, cy = get_ground_anchor(xyxy)
        scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
        max_dist = self.max_reconnect_dist_px * scale

        best_id, best_score = None, float("inf")
        for cid, trk in self.tracks.items():
            gap = frame_idx - trk.last_seen_frame
            if 1 <= gap <= self.max_reconnect_frames and trk.class_id == class_id:
                px, py = trk.predict_next()
                dist = math.hypot(cx - px, cy - py)
                if dist <= max_dist:
                    score = dist + gap * 2.0
                    if score < best_score:
                        best_score, best_id = score, cid
        return best_id

    def update_tracks(self, detections: sv.Detections, frame_idx: int) -> sv.Detections:
        """Update active tracks and assign canonical IDs."""
        if len(detections) == 0 or detections.tracker_id is None:
            return detections

        canonical_ids = np.zeros(len(detections), dtype=int)
        for i, (box, r_tid, cid) in enumerate(zip(detections.xyxy, detections.tracker_id, detections.class_id)):
            if r_tid in self.raw_to_canonical:
                c_id = self.raw_to_canonical[r_tid]
            else:
                c_id = self._attempt_stitch(box, cid, frame_idx) or self.next_canonical_id
                if c_id == self.next_canonical_id:
                    self.next_canonical_id += 1
                self.raw_to_canonical[r_tid] = c_id

            if c_id not in self.tracks:
                self.tracks[c_id] = TrackState(c_id, frame_idx, box, cid)
            else:
                self.tracks[c_id].update(frame_idx, box, cid, r_tid)
            canonical_ids[i] = c_id

        for trk in self.tracks.values():
            if trk.last_seen_frame < frame_idx:
                trk.missed_count += 1
                if trk.missed_count > self.max_reconnect_frames:
                    trk.is_active = False

        detections.tracker_id = canonical_ids
        return detections

