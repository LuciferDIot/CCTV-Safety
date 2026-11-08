"""Geometric and perspective calculations on CCTV 2D/3D ground plane.

Real-world intuition:
- Ground Anchor: Tires or feet touch the pavement at the bounding box bottom-center.
- Perspective Foreshortening: Distant objects (top of frame) traverse fewer pixels
  per meter than foreground objects (bottom of frame).
- Segment Distance: Vector projection identifies closest point on finite roadway boundaries.
"""
import math
from typing import Tuple, Optional, Any
import cv2
import numpy as np


def get_box_geometry(bbox: np.ndarray) -> Tuple[float, float, float, float]:
    """Extract width, height, area, and aspect ratio (H/W) from bounding box."""
    box_width = max(1.0, float(bbox[2] - bbox[0]))
    box_height = max(1.0, float(bbox[3] - bbox[1]))
    box_area = box_width * box_height
    aspect_ratio = box_height / box_width
    return (box_width, box_height, box_area, aspect_ratio)


def get_ground_anchor(bbox: np.ndarray) -> Tuple[float, float]:
    """Calculate bottom-center ground contact point ((x1+x2)/2, y2) on road plane."""
    center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
    ground_y = float(bbox[3])  # Pavement contact level
    return (center_x, ground_y)


def compute_perspective_scale(
    y_or_point: Any, frame_height: float,
    perspective_cfg: Optional[Any] = None, frame_width: Optional[float] = None
) -> float:
    """Calculate scaling weight w(y) to compensate for perspective foreshortening."""
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
    """Calculate signed distance from a point to a polygon boundary in pixels."""
    poly_pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    return float(cv2.pointPolygonTest(poly_pts, (float(point[0]), float(point[1])), measureDist=True))


def point_to_segment_dist(
    query_point: Tuple[float, float], seg_start: Tuple[float, float], seg_end: Tuple[float, float]
) -> float:
    """Calculate Euclidean distance from query_point to finite line segment (seg_start -> seg_end)."""
    px, py = query_point[0], query_point[1]
    ax, ay = seg_start[0], seg_start[1]
    bx, by = seg_end[0], seg_end[1]
    seg_dx, seg_dy = bx - ax, by - ay
    seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)
    # Project vector (seg_start -> query_point) onto segment vector, clamped to [0, 1]
    projection_t = max(0.0, min(1.0, ((px - ax) * seg_dx + (py - ay) * seg_dy) / seg_len_sq))
    closest_x = ax + projection_t * seg_dx
    closest_y = ay + projection_t * seg_dy
    return math.hypot(px - closest_x, py - closest_y)
