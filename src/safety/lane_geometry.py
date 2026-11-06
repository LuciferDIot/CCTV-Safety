"""Lane boundary geometry and segment distance calculation."""
import math
from typing import Tuple


def point_to_segment_dist(
    p: Tuple[float, float],
    a: Tuple[float, float],
    b: Tuple[float, float]
) -> float:
    """Calculate Euclidean distance from point p to line segment ab."""
    px, py = p
    ax, ay = a
    bx, by = b
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / seg_len_sq))
    proj_x = ax + t * abx
    proj_y = ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)

