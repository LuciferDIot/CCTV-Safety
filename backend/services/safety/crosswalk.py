"""Safety rules for crosswalk traversals and motorcycle riding detection.

Real-world intuition:
- Lane Transit Suppression: Crosswalk paint is painted across roadways. Vehicles driving
  legally along lane flow cross the paint without committing a violation.
- Dismounted Walking Exemption: Pushing a bike at walking speed (<= 3.8 px/frame) is legal.
"""
from collections import defaultdict
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from services.safety.geometry import get_ground_anchor, compute_perspective_scale, point_to_polygon_dist
from services.safety.direction import get_motion_metrics


def is_normal_lane_transit(dx: float, dy: float, lane_vectors: Optional[List[Tuple[float, float]]]) -> bool:
    """Check if vehicle motion matches permitted longitudinal lane flow across crosswalk paint."""
    speed = math.hypot(dx, dy)
    if speed <= 0.5 or not lane_vectors: return False
    vel_dir_x, vel_dir_y = dx / speed, dy / speed
    for lane_x, lane_y in lane_vectors:
        lane_len = math.hypot(lane_x, lane_y)
        if lane_len <= 1e-6: continue
        lane_unit_x, lane_unit_y = lane_x / lane_len, lane_y / lane_len
        # Longitudinal alignment along lane flow and lateral deflection across lane
        long_dot = vel_dir_x * lane_unit_x + vel_dir_y * lane_unit_y
        lat_dot = abs(vel_dir_x * (-lane_unit_y) + vel_dir_y * lane_unit_x)
        if long_dot >= 0.65 and long_dot >= 0.80 * lat_dot: return True
    return False


def classify_crosswalk_motion(
    corr_speed: float, cw_dist_corr: float, min_passage_dist_px: float, max_walking_speed: float, min_riding_speed: float
) -> str:
    """Classify crosswalk transit into EXEMPT_WALKING or CROSSWALK_RIDING."""
    if corr_speed <= max_walking_speed: return "EXEMPT_WALKING"
    if corr_speed >= min_riding_speed or cw_dist_corr >= min_passage_dist_px: return "CROSSWALK_RIDING"
    return "TRAVERSING_PRELIMINARY"


class CrosswalkSafetyChecker:
    """Evaluates motorcycle traversals over designated crosswalk zones."""

    def __init__(self, crosswalk_polygons: List[np.ndarray], min_passage_dist_px: float = 40.0, max_walking_speed: float = 3.8, min_riding_speed: float = 4.8, min_traversal_frames: int = 5, frame_height: float = 2160.0, perspective_cfg: Optional[Any] = None):
        self.crosswalk_polygons = [np.array(p, dtype=np.int32) for p in crosswalk_polygons]
        self.min_passage_dist_px, self.max_walking_speed = min_passage_dist_px, max_walking_speed
        self.min_riding_speed, self.min_traversal_frames = min_riding_speed, min_traversal_frames
        self.frame_height, self.perspective_cfg = frame_height, perspective_cfg
        self.frames_in_cw: Dict[int, int] = defaultdict(int)
        self.entry_point: Dict[int, Tuple[float, float]] = {}
        self.status_cache: Dict[int, str] = {}

    def _eval_bike(self, tid: int, xyxy: np.ndarray, hist: list, l_vecs: Optional[List[Tuple[float, float]]]) -> Optional[str]:
        anchor_x, anchor_y = get_ground_anchor(xyxy)
        pts = [(h[1], h[2]) if isinstance(h, (tuple, list)) and len(h) >= 3 else (h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]
        speed, dist, _, dx, dy = get_motion_metrics(pts, 5, self.frame_height, self.perspective_cfg)

        if not any(point_to_polygon_dist((anchor_x, anchor_y), p) >= 0 for p in self.crosswalk_polygons):
            self.frames_in_cw[tid] = 0
            self.entry_point.pop(tid, None)
            return None

        self.frames_in_cw[tid] += 1
        self.entry_point.setdefault(tid, (anchor_x, anchor_y))
        if is_normal_lane_transit(dx, dy, l_vecs): return None
        if speed < 1.5 or dist < 15.0: return "STOPPED_NEAR_CROSSWALK"

        perspective_scale = compute_perspective_scale(anchor_y, self.frame_height, self.perspective_cfg)
        entry_x, entry_y = self.entry_point[tid]
        crosswalk_dist_scaled = math.hypot(anchor_x - entry_x, anchor_y - entry_y) / max(0.1, perspective_scale)
        if crosswalk_dist_scaled < self.min_passage_dist_px or self.frames_in_cw[tid] < self.min_traversal_frames:
            return "TRAVERSING_PRELIMINARY"

        status = classify_crosswalk_motion(speed, crosswalk_dist_scaled, self.min_passage_dist_px, self.max_walking_speed, self.min_riding_speed)
        self.status_cache[tid] = status
        return status

    def check_motorcycles(self, detections: Any, track_history: dict, frame_idx: int, lane_vectors: Optional[List[Tuple[float, float]]] = None) -> Dict[int, str]:
        results = {}
        if len(detections) == 0 or getattr(detections, "tracker_id", None) is None:
            return results
        bike_mask = np.isin(detections.class_id, [1, 3])
        if not np.any(bike_mask): return results
        for box, tid in zip(detections[bike_mask].xyxy, detections[bike_mask].tracker_id):
            if tid is not None and tid in track_history and len(track_history[tid]) >= 3:
                res = self._eval_bike(tid, box, track_history[tid], lane_vectors)
                if res: results[tid] = res
        if len(self.frames_in_cw) > 300:
            active = set(track_history.keys())
            for t in list(self.frames_in_cw.keys()):
                if t not in active:
                    self.frames_in_cw.pop(t, None)
                    self.entry_point.pop(t, None)
                    self.status_cache.pop(t, None)
        return results
