"""Perspective foreshortening correction based on vertical screen position."""
from typing import Optional, Any
import numpy as np


def compute_perspective_scale(
    y: float,
    frame_height: float,
    perspective_cfg: Optional[Any] = None
) -> float:
    """Calculate scaling weight at y to compensate for camera foreshortening."""
    if perspective_cfg is None or frame_height <= 0:
        return 1.0

    y_top = getattr(perspective_cfg, "y_top", 0.1)
    y_bottom = getattr(perspective_cfg, "y_bottom", 1.0)
    w_top = getattr(perspective_cfg, "weight_top", 0.35)
    w_bottom = getattr(perspective_cfg, "weight_bottom", 1.0)

    y_norm = np.clip(y / float(frame_height), 0.0, 1.0)
    if y_bottom == y_top:
        return 1.0

    ratio = (y_norm - y_top) / (y_bottom - y_top)
    scale = w_top + ratio * (w_bottom - w_top)
    return float(np.clip(scale, min(w_top, w_bottom), max(w_top, w_bottom)))

