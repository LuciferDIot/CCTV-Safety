"""Warmup observation feeding for auto-lane calibration."""
from typing import Dict, Any
import numpy as np
from src.core.motion import point_to_polygon_dist


def feed_warmup_observations(
    lane_detector: Any, road_poly: np.ndarray, raw_hist: Dict[int, Any]
) -> None:
    """Feed vehicle anchor positions and velocities to the auto-lane detector."""
    for tid, hist in raw_hist.items():
        if len(hist) < 6:
            continue
        pts = [(h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist[-6:]]
        anchor_x, anchor_y = pts[-1]
        if point_to_polygon_dist((anchor_x, anchor_y), road_poly) < 0:
            continue
        vel_dx = pts[-1][0] - pts[0][0]
        vel_dy = pts[-1][1] - pts[0][1]
        lane_detector.observe_warmup(anchor_x, anchor_y, vel_dx, vel_dy)
