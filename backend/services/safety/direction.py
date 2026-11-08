"""Safety rules for wrong-way traffic detection and velocity vector alignment."""
from collections import defaultdict
import math
from typing import Dict, Tuple, Optional, Any, List
import numpy as np
from services.safety.geometry import compute_perspective_scale


def get_motion_metrics(history: List[Tuple[float, float]], window: int = 5, frame_height: float = 2160.0, perspective_cfg: Optional[Any] = None) -> Tuple[float, float, float, float, float]:
    """Calculate speed, total distance, raw speed, and displacement vector (dx, dy)."""
    if len(history) < 2:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    p_start, p_end = history[0], history[-1]
    dx, dy = p_end[0] - p_start[0], p_end[1] - p_start[1]
    raw_dist = math.hypot(dx, dy)
    scale = compute_perspective_scale((p_start[1] + p_end[1]) / 2.0, frame_height, perspective_cfg)
    total_dist_corr = raw_dist / max(0.1, scale)

    n_recent = min(window, len(history) - 1)
    p_prev = history[-n_recent - 1]
    r_dx, r_dy = p_end[0] - p_prev[0], p_end[1] - p_prev[1]
    r_scale = compute_perspective_scale((p_prev[1] + p_end[1]) / 2.0, frame_height, perspective_cfg)
    recent_corrected_speed = (math.hypot(r_dx, r_dy) / float(n_recent)) / max(0.1, r_scale)
    return (recent_corrected_speed, total_dist_corr, math.hypot(r_dx, r_dy) / float(n_recent), dx, dy)


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

    def _eval_vehicle(self, tid: int, hist: list, u_vec: Tuple[float, float], is_ambiguous: bool, frame_idx: int) -> Tuple[bool, bool]:
        pts = [(h[1], h[2]) if isinstance(h, (tuple, list)) and len(h) >= 3 else (h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]
        spd, dist, _, dx, dy = get_motion_metrics(pts, 5, self.frame_height, self.perspective_cfg)
        if spd < self.min_recent_speed or dist < self.min_total_dist_px:
            self.wrong_way_streaks[tid] = max(0, self.wrong_way_streaks[tid] - 1)
            return (False, False)

        v_dist = math.hypot(dx, dy)
        if v_dist <= 0: return (False, False)
        vx, vy = dx / v_dist, dy / v_dist
        long_dot = vx * u_vec[0] + vy * u_vec[1]
        lat_dot = abs(vx * -u_vec[1] + vy * u_vec[0])

        if lat_dot >= abs(long_dot) or long_dot >= self.wrong_way_threshold:
            self.wrong_way_streaks[tid] = max(0, self.wrong_way_streaks[tid] - 1)
            return (False, False)

        self.wrong_way_streaks[tid] += 1
        self.last_detected_frame[tid] = frame_idx
        self.first_detected_frame.setdefault(tid, frame_idx)
        return (self.wrong_way_streaks[tid] >= self.min_sustained_frames and not is_ambiguous, True)

    def check_detections(self, detections: Any, permitted_vector: Tuple[float, float], track_history: dict, lane_id: str = "lane", frame_idx: int = 0, ambiguous_mask: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        n = len(detections)
        if n == 0 or getattr(detections, "tracker_id", None) is None:
            return (np.zeros(n, dtype=bool), np.zeros(n, dtype=bool))
        conf_m, susp_m = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
        for i, tid in enumerate(detections.tracker_id):
            if tid is None or tid not in track_history or len(track_history[tid]) < self.min_frames: continue
            is_ambig = bool(ambiguous_mask[i]) if ambiguous_mask is not None else False
            c, s = self._eval_vehicle(tid, track_history[tid], permitted_vector, is_ambig, frame_idx)
            conf_m[i], susp_m[i] = c, s

        if len(self.last_detected_frame) > 300:
            active = set(track_history.keys())
            for t in list(self.last_detected_frame.keys()):
                if t not in active:
                    self.wrong_way_streaks.pop(t, None)
                    self.first_detected_frame.pop(t, None)
                    self.last_detected_frame.pop(t, None)
        return (conf_m, susp_m)
