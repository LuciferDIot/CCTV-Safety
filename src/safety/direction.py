"""Direction Checker: Robust wrong-way detection with sustained movement."""
from collections import defaultdict
import math
from typing import Dict, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.core.motion import get_motion_metrics


class DirectionChecker:
    """Evaluates tracked vehicle trajectories against permitted lane flow vectors."""

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

    def _eval_vehicle(
        self, tid: int, hist: list, u_vec: Tuple[float, float], is_ambiguous: bool, frame_idx: int
    ) -> Tuple[bool, bool]:
        """Evaluate single vehicle kinematics for counter-flow travel."""
        pts = [(h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]
        corr_spd, corr_dist, _, dx, dy = get_motion_metrics(
            pts, window=5, frame_height=self.frame_height, perspective_cfg=self.perspective_cfg
        )
        if corr_spd < self.min_recent_speed or corr_dist < self.min_total_dist_px:
            self.wrong_way_streaks[tid] = max(0, self.wrong_way_streaks[tid] - 1)
            return (False, False)

        dist = math.hypot(dx, dy)
        if dist <= 0:
            return (False, False)

        vx, vy = dx / dist, dy / dist
        long_dot = vx * u_vec[0] + vy * u_vec[1]
        lat_dot = abs(vx * -u_vec[1] + vy * u_vec[0])

        if lat_dot >= abs(long_dot) or long_dot >= self.wrong_way_threshold:
            self.wrong_way_streaks[tid] = max(0, self.wrong_way_streaks[tid] - 1)
            return (False, False)

        self.wrong_way_streaks[tid] += 1
        self.last_detected_frame[tid] = frame_idx
        self.first_detected_frame.setdefault(tid, frame_idx)

        confirmed = (self.wrong_way_streaks[tid] >= self.min_sustained_frames and not is_ambiguous)
        return (confirmed, True)

    def check_detections(
        self,
        detections: sv.Detections,
        permitted_vector: Tuple[float, float],
        track_history: dict,
        lane_id: str = "lane",
        frame_idx: int = 0,
        ambiguous_mask: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Evaluate detections returning (confirmed_mask, suspected_mask)."""
        n = len(detections)
        if n == 0 or detections.tracker_id is None:
            return (np.zeros(n, dtype=bool), np.zeros(n, dtype=bool))

        conf_m, susp_m = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
        for i, tid in enumerate(detections.tracker_id):
            if tid is None or tid not in track_history or len(track_history[tid]) < self.min_frames:
                continue
            is_ambig = bool(ambiguous_mask[i]) if ambiguous_mask is not None else False
            c, s = self._eval_vehicle(tid, track_history[tid], permitted_vector, is_ambig, frame_idx)
            conf_m[i], susp_m[i] = c, s

        return (conf_m, susp_m)
