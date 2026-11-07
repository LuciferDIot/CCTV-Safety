"""Perspective foreshortening correction based on vertical and horizontal screen position."""
from typing import Optional, Any
import numpy as np


def compute_perspective_scale(
    y_or_point: Any,
    frame_height: float,
    perspective_cfg: Optional[Any] = None,
    frame_width: Optional[float] = None
) -> float:
    """Calculate scaling weight to compensate for camera perspective foreshortening.

    Supports vertical depth (Y-axis), horizontal depth (X-axis), and planar 2D depth.
    Backward compatible with single scalar y inputs.
    """
    if perspective_cfg is None or frame_height <= 0:
        return 1.0

    # Extract x and y if passed as a coordinate pair (cx, cy)
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
        scale = w_left + ratio * (w_right - w_left)
        return float(np.clip(scale, min(w_left, w_right), max(w_left, w_right)))

    # Default vertical Y-axis foreshortening (standard CCTV perspective)
    y_top = getattr(perspective_cfg, "y_top", 0.1)
    y_bottom = getattr(perspective_cfg, "y_bottom", 1.0)
    w_top = getattr(perspective_cfg, "weight_top", 0.35)
    w_bottom = getattr(perspective_cfg, "weight_bottom", 1.0)

    y_norm = np.clip(y_val / float(frame_height), 0.0, 1.0)
    if y_bottom == y_top:
        return 1.0

    ratio = (y_norm - y_top) / (y_bottom - y_top)
    scale = w_top + ratio * (w_bottom - w_top)
    return float(np.clip(scale, min(w_top, w_bottom), max(w_top, w_bottom)))
