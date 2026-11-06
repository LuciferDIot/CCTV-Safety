"""
Common Geometry, Perspective Correction, Motion, and HUD Rendering Utilities
"""
import math
from typing import List, Tuple, Optional, Deque
import numpy as np
import cv2

def get_box_geometry(bbox: np.ndarray) -> Tuple[float, float, float, float]:
    """
    Extracts width, height, area, and aspect ratio (H/W) from a bounding box.
    """
    w = max(1.0, float(bbox[2] - bbox[0]))
    h = max(1.0, float(bbox[3] - bbox[1]))
    area = w * h
    aspect_ratio = h / w
    return (w, h, area, aspect_ratio)

def get_ground_anchor(bbox: np.ndarray) -> Tuple[float, float]:
    """
    Calculates bottom-center contact point on the road surface.
    """
    cx = (float(bbox[0]) + float(bbox[2])) / 2.0
    cy = float(bbox[3])
    return (cx, cy)

def compute_perspective_scale(
    y: float,
    frame_height: float,
    perspective_cfg: Optional[Any] = None
) -> float:
    """
    Calculates perspective scaling weight at vertical pixel coordinate y.
    Compensates for camera perspective foreshortening: objects far away (near horizon/top)
    appear much smaller and move fewer pixels per second than nearby objects.
    """
    if perspective_cfg is None or frame_height <= 0:
        return 1.0

    y_top = getattr(perspective_cfg, "y_top", 0.1)
    y_bottom = getattr(perspective_cfg, "y_bottom", 1.0)
    w_top = getattr(perspective_cfg, "weight_top", 0.35)
    w_bottom = getattr(perspective_cfg, "weight_bottom", 1.0)

    y_norm = np.clip(y / float(frame_height), 0.0, 1.0)

    if y_bottom == y_top:
        return 1.0

    # Linear interpolation of scale factor along optical tilt axis
    ratio = (y_norm - y_top) / (y_bottom - y_top)
    scale = w_top + ratio * (w_bottom - w_top)
    return float(np.clip(scale, min(w_top, w_bottom), max(w_top, w_bottom)))

def get_motion_metrics(
    history: List[Tuple[float, float]],
    window: int = 5,
    frame_height: float = 2160.0,
    perspective_cfg: Optional[Any] = None
) -> Tuple[float, float, float, float, float]:
    """
    Calculates recent speed (perspective-corrected px/frame), total displacement,
    raw speed, and displacement vector (dx, dy).
    
    Returns:
        (corrected_speed, total_dist_corr, raw_speed, dx, dy)
    """
    if len(history) < 2:
        return (0.0, 0.0, 0.0, 0.0, 0.0)

    # Total displacement
    p_start = history[0]
    p_end = history[-1]
    dx = p_end[0] - p_start[0]
    dy = p_end[1] - p_start[1]
    raw_total_dist = math.hypot(dx, dy)

    # Average Y over full track for perspective normalization
    avg_y = (p_start[1] + p_end[1]) / 2.0
    scale = compute_perspective_scale(avg_y, frame_height, perspective_cfg)
    total_dist_corr = raw_total_dist / max(0.1, scale)

    # Recent speed over last 'window' frames
    n_recent = min(window, len(history) - 1)
    p_prev = history[-n_recent - 1]
    recent_dx = p_end[0] - p_prev[0]
    recent_dy = p_end[1] - p_prev[1]
    recent_raw_dist = math.hypot(recent_dx, recent_dy)
    recent_raw_speed = recent_raw_dist / float(n_recent)

    recent_avg_y = (p_prev[1] + p_end[1]) / 2.0
    recent_scale = compute_perspective_scale(recent_avg_y, frame_height, perspective_cfg)
    recent_corrected_speed = recent_raw_speed / max(0.1, recent_scale)

    return (recent_corrected_speed, total_dist_corr, recent_raw_speed, dx, dy)

def point_to_polygon_dist(point: Tuple[float, float], polygon: np.ndarray) -> float:
    """
    Computes signed distance from a point to a polygon in pixels.
    Positive inside, negative outside, zero on edge.
    """
    poly_pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    return float(cv2.pointPolygonTest(poly_pts, (float(point[0]), float(point[1])), measureDist=True))

def draw_render_progress_bar(
    frame: np.ndarray,
    current_frame: int,
    total_frames: int,
    bar_height: int = 24,
    margin_bottom: int = 25,
) -> np.ndarray:
    """
    Renders an on-screen semi-transparent HUD percentage progress bar.
    """
    if total_frames <= 0:
        return frame

    h, w = frame.shape[:2]
    progress = np.clip(current_frame / total_frames, 0.0, 1.0)
    pct = progress * 100.0

    y_start = h - margin_bottom - bar_height - 35
    y_end = h - margin_bottom + 5
    x_start = 60
    x_end = w - 60

    overlay = frame.copy()
    cv2.rectangle(overlay, (x_start, y_start), (x_end, y_end), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    bar_x1 = x_start + 18
    bar_y1 = y_start + 34
    bar_x2 = x_end - 18
    bar_y2 = bar_y1 + bar_height
    bar_total_width = bar_x2 - bar_x1

    cv2.rectangle(frame, (bar_x1, bar_y1), (bar_x2, bar_y2), (70, 70, 70), 2)
    fill_width = int(bar_total_width * progress)
    if fill_width > 0:
        cv2.rectangle(frame, (bar_x1, bar_y1), (bar_x1 + fill_width, bar_y2), (255, 229, 0), -1)

    text = f"Safety Pipeline: Frame {current_frame:04d}/{total_frames:04d} ({pct:5.1f}%)"
    cv2.putText(frame, text, (bar_x1, y_start + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA)

    return frame

