"""
Direction Checker: Robust Wrong-Way Detection with Sustained Movement Verification
Protects stationary vehicles, suppresses lateral turns, and filters out ambiguous lane positions.
"""
from collections import defaultdict
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.core.geometry import get_ground_anchor, get_motion_metrics

class DirectionChecker:
    def __init__(
        self,
        min_frames: int = 5,
        min_sustained_frames: int = 5,
        min_recent_speed: float = 2.0,
        min_total_dist_px: float = 20.0,
        wrong_way_threshold: float = -0.60,
        frame_height: float = 2160.0,
        perspective_cfg: Optional[Any] = None
    ):
        self.min_frames = min_frames
        self.min_sustained_frames = min_sustained_frames
        self.min_recent_speed = min_recent_speed
        self.min_total_dist_px = min_total_dist_px
        self.wrong_way_threshold = wrong_way_threshold
        self.frame_height = frame_height
        self.perspective_cfg = perspective_cfg

        self.wrong_way_streaks: Dict[int, int] = defaultdict(int)
        self.first_detected_frame: Dict[int, int] = {}
        self.last_detected_frame: Dict[int, int] = {}

    def check_detections(
        self,
        detections: sv.Detections,
        permitted_vector: Tuple[float, float],
        track_history: dict,
        lane_id: str = "lane",
        frame_idx: int = 0,
        ambiguous_mask: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Evaluates vehicles for sustained wrong-way travel."""
        if len(detections) == 0 or detections.tracker_id is None:
            return (np.zeros(len(detections), dtype=bool), np.zeros(len(detections), dtype=bool))

        ux, uy = permitted_vector
        lat_ux, lat_uy = -uy, ux

        confirmed_mask = np.zeros(len(detections), dtype=bool)
        suspected_mask = np.zeros(len(detections), dtype=bool)

        for idx, (xyxy, tracker_id) in enumerate(zip(detections.xyxy, detections.tracker_id)):
            if tracker_id is None:
                continue

            if tracker_id not in track_history or len(track_history[tracker_id]) < self.min_frames:
                continue

            hist = track_history[tracker_id]
            pts = [(h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]

            corr_speed, corr_dist, raw_speed, dx, dy = get_motion_metrics(
                pts, window=5, frame_height=self.frame_height, perspective_cfg=self.perspective_cfg
            )

            if corr_speed < self.min_recent_speed or corr_dist < self.min_total_dist_px:
                self.wrong_way_streaks[tracker_id] = max(0, self.wrong_way_streaks[tracker_id] - 1)
                continue

            total_dist = math.hypot(dx, dy)
            if total_dist <= 0:
                continue
            vx = dx / total_dist
            vy = dy / total_dist

            long_dot = vx * ux + vy * uy
            lat_dot = abs(vx * lat_ux + vy * lat_uy)

            if lat_dot >= abs(long_dot):
                self.wrong_way_streaks[tracker_id] = max(0, self.wrong_way_streaks[tracker_id] - 1)
                continue

            is_ambiguous = (ambiguous_mask is not None and ambiguous_mask[idx])
            if long_dot < self.wrong_way_threshold:
                suspected_mask[idx] = True
                self.wrong_way_streaks[tracker_id] += 1
                self.last_detected_frame[tracker_id] = frame_idx
                if tracker_id not in self.first_detected_frame:
                    self.first_detected_frame[tracker_id] = frame_idx

                if self.wrong_way_streaks[tracker_id] >= self.min_sustained_frames and not is_ambiguous:
                    confirmed_mask[idx] = True
            else:
                self.wrong_way_streaks[tracker_id] = max(0, self.wrong_way_streaks[tracker_id] - 1)

        return (confirmed_mask, suspected_mask)
