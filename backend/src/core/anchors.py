"""Bounding box geometry and road ground-contact anchor calculation."""
from typing import Tuple
import numpy as np


def get_box_geometry(bbox: np.ndarray) -> Tuple[float, float, float, float]:
    """Extract width, height, area, and aspect ratio (H/W) from bbox."""
    w = max(1.0, float(bbox[2] - bbox[0]))
    h = max(1.0, float(bbox[3] - bbox[1]))
    area = w * h
    aspect_ratio = h / w
    return (w, h, area, aspect_ratio)


def get_ground_anchor(bbox: np.ndarray) -> Tuple[float, float]:
    """Calculate bottom-center ground contact point on road plane."""
    cx = (float(bbox[0]) + float(bbox[2])) / 2.0
    cy = float(bbox[3])
    return (cx, cy)

