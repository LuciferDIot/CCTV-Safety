"""Warmup observation feeding and multi-frame auto-lane calibration."""
from typing import Dict, Any, Optional
import numpy as np
from src.core.motion import point_to_polygon_dist
from src.pipeline.annotators import create_annotators, PipelineAnnotators


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


def step_auto_calibration(
    lane_detector: Any, road_poly: np.ndarray, raw_hist: Dict[int, Any],
    frame_idx: int, warmup_frames: int, crosswalk_zones: list
) -> Optional[PipelineAnnotators]:
    """Accumulate observations across multiple frames and calibrate/refine lanes."""
    if frame_idx < 150:
        feed_warmup_observations(lane_detector, road_poly, raw_hist)

    should_calibrate = (
        (not lane_detector.is_calibrated and frame_idx >= warmup_frames)
        or (lane_detector.is_calibrated and frame_idx in (90, 150))
    )
    if should_calibrate:
        if lane_detector.auto_calibrate(force=lane_detector.is_calibrated):
            return create_annotators([road_poly], crosswalk_zones)
    return None
