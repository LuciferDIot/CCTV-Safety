"""Geometric and perspective calculations on CCTV 2D/3D ground plane."""
import math
from typing import Tuple, Optional, Any
import cv2
import numpy as np


def get_box_geometry(bbox: np.ndarray) -> Tuple[float, float, float, float]:
    """Extract width, height, area, and aspect ratio (H/W) from bbox."""
    w = max(1.0, float(bbox[2] - bbox[0]))
    h = max(1.0, float(bbox[3] - bbox[1]))
    return (w, h, w * h, h / w)


def get_ground_anchor(bbox: np.ndarray) -> Tuple[float, float]:
    """Calculate bottom-center ground contact point on road plane."""
    return ((float(bbox[0]) + float(bbox[2])) / 2.0, float(bbox[3]))


def compute_perspective_scale(
    y_or_point: Any, frame_height: float,
    perspective_cfg: Optional[Any] = None, frame_width: Optional[float] = None
) -> float:
    """Calculate scaling weight to compensate for perspective foreshortening."""
    if perspective_cfg is None or frame_height <= 0:
        return 1.0

    if isinstance(y_or_point, (tuple, list, np.ndarray)) and len(y_or_point) >= 2:
        x_val, y_val = float(y_or_point[0]), float(y_or_point[1])
    else:
        x_val, y_val = 0.0, float(y_or_point)

    axis = getattr(perspective_cfg, "axis", "y").lower() if hasattr(perspective_cfg, "axis") else "y"

    if axis == "x" and frame_width and frame_width > 0:
        x_left = getattr(perspective_cfg, "x_left", 0.1)
        x_right = getattr(perspective_cfg, "x_right", 1.0)
        w_left = getattr(perspective_cfg, "weight_left", 0.35)
        w_right = getattr(perspective_cfg, "weight_right", 1.0)
        x_norm = np.clip(x_val / float(frame_width), 0.0, 1.0)
        if x_right == x_left:
            return 1.0
        ratio = (x_norm - x_left) / (x_right - x_left)
        return float(np.clip(w_left + ratio * (w_right - w_left), min(w_left, w_right), max(w_left, w_right)))

    y_top = getattr(perspective_cfg, "y_top", 0.1)
    y_bottom = getattr(perspective_cfg, "y_bottom", 1.0)
    w_top = getattr(perspective_cfg, "weight_top", 0.35)
    w_bottom = getattr(perspective_cfg, "weight_bottom", 1.0)

    y_norm = np.clip(y_val / float(frame_height), 0.0, 1.0)
    if y_bottom == y_top:
        return 1.0

    ratio = (y_norm - y_top) / (y_bottom - y_top)
    return float(np.clip(w_top + ratio * (w_bottom - w_top), min(w_top, w_bottom), max(w_top, w_bottom)))


def point_to_polygon_dist(point: Tuple[float, float], polygon: np.ndarray) -> float:
    """Calculate signed distance from a point to a polygon in pixels."""
    poly_pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    return float(cv2.pointPolygonTest(poly_pts, (float(point[0]), float(point[1])), measureDist=True))


def point_to_segment_dist(p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Calculate Euclidean distance from point p to line segment ab."""
    px, py, ax, ay, bx, by = p[0], p[1], a[0], a[1], b[0], b[1]
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / seg_len_sq))
    return math.hypot(px - (ax + t * abx), py - (ay + t * aby))

