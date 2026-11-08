"""Safety rules for wrong-way traffic detection and velocity vector alignment.

Real-world intuition:
- Vector Alignment: Dot product of unit velocity and permitted lane direction equals cos(theta).
  A value < -0.60 indicates motion opposing permitted traffic flow by > 127 degrees.
- Lateral Filtering: Turning, parking, or lane-changing vehicles exhibit lateral motion
  exceeding longitudinal counter-flow (lat_dot >= abs(long_dot)) and are suppressed.
- Sustained Gating: Requires consecutive frames of counter-flow to confirm a violation.
"""
from collections import defaultdict
import math
from typing import Dict, Tuple, Optional, Any, List
import numpy as np
from services.safety.geometry import compute_perspective_scale


def get_motion_metrics(
    history: List[Tuple[float, float]], window: int = 5, frame_height: float = 2160.0, perspective_cfg: Optional[Any] = None
) -> Tuple[float, float, float, float, float]:
    """Calculate speed, total distance, raw speed, and displacement vector (dx, dy)."""
    if len(history) < 2:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    start_point, end_point = history[0], history[-1]
    dx = float(end_point[0] - start_point[0])
    dy = float(end_point[1] - start_point[1])
    raw_distance = math.hypot(dx, dy)
    mid_y = (start_point[1] + end_point[1]) / 2.0
    perspective_scale = compute_perspective_scale(mid_y, frame_height, perspective_cfg)
    total_dist_corr = raw_distance / max(0.1, perspective_scale)

    recent_steps = min(window, len(history) - 1)
    window_start_point = history[-recent_steps - 1]
    recent_dx = float(end_point[0] - window_start_point[0])
    recent_dy = float(end_point[1] - window_start_point[1])
    recent_mid_y = (window_start_point[1] + end_point[1]) / 2.0
    recent_scale = compute_perspective_scale(recent_mid_y, frame_height, perspective_cfg)
    recent_raw_speed = math.hypot(recent_dx, recent_dy) / float(recent_steps)
    recent_corrected_speed = recent_raw_speed / max(0.1, recent_scale)
    return (recent_corrected_speed, total_dist_corr, recent_raw_speed, dx, dy)


class DirectionChecker:
    """Evaluates vehicle trajectories against permitted lane flow vectors."""

    def __init__(self, min_frames: int = 5, min_sustained_frames: int = 5, min_recent_speed: float = 2.0, min_total_dist_px: float = 20.0, wrong_way_threshold: float = -0.60, frame_height: float = 2160.0, perspective_cfg: Optional[Any] = None):
        self.min_frames = min_frames
        self.min_sustained_frames = min_sustained_frames
        self.min_recent_speed = min_recent_speed
        self.min_total_dist_px = min_total_dist_px
        self.wrong_way_threshold = wrong_way_threshold
        self.frame_height, self.perspective_cfg = frame_height, perspective_cfg
        self.wrong_way_streaks: Dict[int, int] = defaultdict(int)
        self.first_detected_frame: Dict[int, int] = {}
        self.last_detected_frame: Dict[int, int] = {}

    def _eval_vehicle(self, tid: int, hist: list, permitted_flow_vec: Tuple[float, float], is_ambiguous: bool, frame_idx: int) -> Tuple[bool, bool]:
        pts = [(h[1], h[2]) if isinstance(h, (tuple, list)) and len(h) >= 3 else (h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]
        spd, dist, _, dx, dy = get_motion_metrics(pts, 5, self.frame_height, self.perspective_cfg)
        if spd < self.min_recent_speed or dist < self.min_total_dist_px:
            self.wrong_way_streaks[tid] = max(0, self.wrong_way_streaks[tid] - 1)
            return (False, False)

        motion_length = math.hypot(dx, dy)
        if motion_length <= 0: return (False, False)
        vel_dir_x, vel_dir_y = dx / motion_length, dy / motion_length
        perm_x, perm_y = permitted_flow_vec[0], permitted_flow_vec[1]
        # Longitudinal alignment (cos theta) and lateral deflection across lane
        long_dot = vel_dir_x * perm_x + vel_dir_y * perm_y
        lat_dot = abs(vel_dir_x * (-perm_y) + vel_dir_y * perm_x)

        if lat_dot >= abs(long_dot) or long_dot >= self.wrong_way_threshold:
            self.wrong_way_streaks[tid] = max(0, self.wrong_way_streaks[tid] - 1)
            return (False, False)

        self.wrong_way_streaks[tid] += 1
        self.last_detected_frame[tid] = frame_idx
        self.first_detected_frame.setdefault(tid, frame_idx)
        return (self.wrong_way_streaks[tid] >= self.min_sustained_frames and not is_ambiguous, True)

    def check_detections(self, detections: Any, permitted_vector: Any, track_history: dict, lane_id: str = "lane", frame_idx: int = 0, ambiguous_mask: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        n = len(detections)
        if n == 0 or getattr(detections, "tracker_id", None) is None:
            return (np.zeros(n, dtype=bool), np.zeros(n, dtype=bool))
        conf_m, susp_m = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
        for i, tid in enumerate(detections.tracker_id):
            if tid is None or tid not in track_history or len(track_history[tid]) < self.min_frames: continue
            is_ambig = bool(ambiguous_mask[i]) if ambiguous_mask is not None else False
            p_vec = permitted_vector[i] if isinstance(permitted_vector, (list, np.ndarray)) and len(permitted_vector) == n else permitted_vector
            c, s = self._eval_vehicle(tid, track_history[tid], p_vec, is_ambig, frame_idx)
            conf_m[i], susp_m[i] = c, s

        if len(self.last_detected_frame) > 300:
            active = set(track_history.keys())
            for t in list(self.last_detected_frame.keys()):
                if t not in active:
                    self.wrong_way_streaks.pop(t, None)
                    self.first_detected_frame.pop(t, None)
                    self.last_detected_frame.pop(t, None)
        return (conf_m, susp_m)
