"""Kinematic and flow rules for crosswalk violation classification."""
import math
from typing import Tuple, List, Optional


def is_normal_lane_transit(
    dx: float,
    dy: float,
    lane_vectors: Optional[List[Tuple[float, float]]]
) -> bool:
    """Check if vehicle motion matches permitted longitudinal lane traffic flow.
    Direction-agnostic: evaluates alignment relative to each lane vector rather than assuming vertical Y motion.
    """
    v_len = math.hypot(dx, dy)
    if v_len <= 0.5 or not lane_vectors:
        return False

    vx, vy = dx / v_len, dy / v_len
    for l_vec in lane_vectors:
        lx, ly = l_vec
        l_len = math.hypot(lx, ly)
        if l_len <= 1e-6:
            continue
        lux, luy = lx / l_len, ly / l_len

        # Longitudinal alignment (flow dot product) and lateral deviation
        longitudinal_dot = vx * lux + vy * luy
        lateral_dot = abs(vx * (-luy) + vy * lux)

        # Vehicle is aligned along lane flow corridor (within ~39 deg) without heavy lateral swerve
        if longitudinal_dot >= 0.65 and longitudinal_dot >= 0.80 * lateral_dot:
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
