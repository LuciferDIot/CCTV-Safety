"""Geometric polygon clipping, PCA axis finding, and normal helpers for lane splitting."""
from typing import List, Tuple
import numpy as np


def safe_norm(vec: np.ndarray) -> np.ndarray:
    """Normalize vector safely, defaulting to (0, -1) on zero length."""
    n = float(np.linalg.norm(vec))
    return vec / n if n > 1e-9 else np.array([0.0, -1.0])


def sort_convex(pts: np.ndarray) -> np.ndarray:
    """Sort polygon vertices counter-clockwise around their centroid."""
    if len(pts) < 3:
        return pts
    c = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    return pts[np.argsort(angles)]


def compute_pca_axis(unit_vecs: np.ndarray) -> np.ndarray:
    """Return the primary travel axis from collected unit-vectors."""
    cov = (unit_vecs.T @ unit_vecs) / len(unit_vecs)
    _, evecs = np.linalg.eigh(cov)
    axis = evecs[:, -1]
    if axis[0] < -1e-9 or (abs(axis[0]) < 1e-9 and axis[1] < 0):
        axis = -axis
    return axis


def clip_polygon_by_axis(
    pts: np.ndarray, primary_axis: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Clip polygon into two halves along primary travel axis through its centroid."""
    centroid = pts.mean(axis=0)
    ax, ay = primary_axis
    split_normal = np.array([-ay, ax])
    left_pts: List[np.ndarray] = []
    right_pts: List[np.ndarray] = []
    n = len(pts)

    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        d1 = float(np.dot(p1 - centroid, split_normal))
        d2 = float(np.dot(p2 - centroid, split_normal))
        (left_pts if d1 <= 0 else right_pts).append(p1.copy())
        if (d1 < 0 and d2 > 0) or (d1 > 0 and d2 < 0):
            cross = p1 + (d1 / (d1 - d2)) * (p2 - p1)
            left_pts.append(cross)
            right_pts.append(cross)

    return sort_convex(np.array(left_pts)), sort_convex(np.array(right_pts))
