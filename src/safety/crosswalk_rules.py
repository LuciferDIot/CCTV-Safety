"""Kinematic and flow rules for crosswalk violation classification."""
import math
from typing import Tuple, List, Optional


def is_normal_lane_transit(
    dx: float,
    dy: float,
    lane_vectors: Optional[List[Tuple[float, float]]]
) -> bool:
    """Check if vehicle motion matches permitted longitudinal lane traffic flow."""
    v_len = math.hypot(dx, dy)
    if v_len <= 0.5 or not lane_vectors:
        return False

    v_norm = (dx / v_len, dy / v_len)
    for l_vec in lane_vectors:
        dot = v_norm[0] * l_vec[0] + v_norm[1] * l_vec[1]
        if dot >= 0.65 and abs(dy) >= 0.8 * abs(dx):
            return True
    return False


def classify_crosswalk_motion(
    corr_speed: float,
    cw_dist_corr: float,
    min_passage_dist_px: float,
    max_walking_speed: float,
    min_riding_speed: float
) -> str:
    """Classify crosswalk transit into EXEMPT_WALKING or CROSSWALK_RIDING."""
    if corr_speed <= max_walking_speed:
        return "EXEMPT_WALKING"
    if corr_speed >= min_riding_speed or cw_dist_corr >= min_passage_dist_px:
        return "CROSSWALK_RIDING"
    return "TRAVERSING_PRELIMINARY"

