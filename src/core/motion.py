"""Motion kinematics, displacement vectors, and signed polygon distances."""
import math
from typing import List, Tuple, Optional, Any
import cv2
import numpy as np
from src.core.perspective import compute_perspective_scale


def get_motion_metrics(
    history: List[Tuple[float, float]],
    window: int = 5,
    frame_height: float = 2160.0,
    perspective_cfg: Optional[Any] = None
) -> Tuple[float, float, float, float, float]:
    """Calculate recent corrected speed, total distance, raw speed, and (dx, dy)."""
    if len(history) < 2:
        return (0.0, 0.0, 0.0, 0.0, 0.0)

    p_start, p_end = history[0], history[-1]
    dx = p_end[0] - p_start[0]
    dy = p_end[1] - p_start[1]
    raw_dist = math.hypot(dx, dy)

    avg_y = (p_start[1] + p_end[1]) / 2.0
    scale = compute_perspective_scale(avg_y, frame_height, perspective_cfg)
    total_dist_corr = raw_dist / max(0.1, scale)

    n_recent = min(window, len(history) - 1)
    p_prev = history[-n_recent - 1]
    r_dx = p_end[0] - p_prev[0]
    r_dy = p_end[1] - p_prev[1]
    recent_speed = math.hypot(r_dx, r_dy) / float(n_recent)

    recent_avg_y = (p_prev[1] + p_end[1]) / 2.0
    r_scale = compute_perspective_scale(recent_avg_y, frame_height, perspective_cfg)
    recent_corrected_speed = recent_speed / max(0.1, r_scale)

    return (recent_corrected_speed, total_dist_corr, recent_speed, dx, dy)


def point_to_polygon_dist(point: Tuple[float, float], polygon: np.ndarray) -> float:
    """Calculate signed distance from a point to a polygon in pixels."""
    poly_pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    pt = (float(point[0]), float(point[1]))
    return float(cv2.pointPolygonTest(poly_pts, pt, measureDist=True))

