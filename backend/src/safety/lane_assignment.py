"""Lane assignment logic and divider boundary ambiguity checks."""
from typing import List, Tuple, Optional, Any
import numpy as np

from src.core.perspective import compute_perspective_scale
from src.core.motion import point_to_polygon_dist
from src.safety.lane_geometry import point_to_segment_dist


def assign_point_to_lane(
    point: Tuple[float, float],
    lanes: List[Any],
    divider_segment: Optional[Tuple],
    ambiguity_margin_px: float,
    frame_height: float,
    perspective_cfg: Optional[Any] = None,
) -> Tuple[Optional[int], bool, float]:
    """Soft lane assignment returning (lane_idx, is_ambiguous, dist_to_divider)."""
    cx, cy = point
    scale = compute_perspective_scale(cy, frame_height, perspective_cfg)
    margin = ambiguity_margin_px * scale

    contained = []
    for idx, lane in enumerate(lanes):
        poly = np.array(lane.polygon, dtype=np.int32)
        d = point_to_polygon_dist((cx, cy), poly)
        if d >= 0:
            contained.append((idx, d))

    if not contained:
        return (None, False, -1.0)

    contained.sort(key=lambda x: x[1], reverse=True)
    best_idx = contained[0][0]

    dist_div = float("inf")
    if divider_segment:
        dist_div = point_to_segment_dist(
            (cx, cy), divider_segment[0], divider_segment[1]
        )

    return (best_idx, dist_div < margin, dist_div)
