"""KMeans lane direction clustering and splitting."""
import math
from typing import List, Tuple
import numpy as np
from scipy.cluster.vq import kmeans2
from models.zone import AutoDetectedLane


def safe_norm(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    return vec / n if n > 1e-9 else np.array([0.0, -1.0])


def sort_convex(pts: np.ndarray) -> np.ndarray:
    if len(pts) < 3: return pts
    c = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    return pts[np.argsort(angles)]


def compute_pca_axis(unit_vecs: np.ndarray) -> np.ndarray:
    cov = (unit_vecs.T @ unit_vecs) / len(unit_vecs)
    _, evecs = np.linalg.eigh(cov)
    axis = evecs[:, -1]
    if axis[0] < -1e-9 or (abs(axis[0]) < 1e-9 and axis[1] < 0): axis = -axis
    return axis


def clip_polygon_by_axis(pts: np.ndarray, primary_axis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    centroid = pts.mean(axis=0)
    ax, ay = primary_axis
    split_normal = np.array([-ay, ax])
    left_pts, right_pts = [], []
    n = len(pts)
    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        d1, d2 = float(np.dot(p1 - centroid, split_normal)), float(np.dot(p2 - centroid, split_normal))
        (left_pts if d1 <= 0 else right_pts).append(p1.copy())
        if (d1 < 0 and d2 > 0) or (d1 > 0 and d2 < 0):
            cross = p1 + (d1 / (d1 - d2)) * (p2 - p1)
            left_pts.append(cross)
            right_pts.append(cross)
    return sort_convex(np.array(left_pts)), sort_convex(np.array(right_pts))


class LaneAutoDetector:
    def __init__(self, road_polygon, min_speed_px: float = 3.0, min_observations: int = 15, bidir_threshold: float = 0.40):
        self.road_polygon = np.array(road_polygon, dtype=float).reshape(-1, 2)
        self.min_speed_px = min_speed_px
        self.min_observations = min_observations
        self.bidir_threshold = bidir_threshold
        self._obs: List[Tuple[np.ndarray, np.ndarray]] = []

    def observe(self, anchor_x: float, anchor_y: float, vel_dx: float, vel_dy: float) -> None:
        speed = math.hypot(vel_dx, vel_dy)
        if speed >= self.min_speed_px and len(self._obs) < 500:
            self._obs.append((np.array([anchor_x, anchor_y]), np.array([vel_dx / speed, vel_dy / speed])))

    def detect_lanes(self) -> List[AutoDetectedLane]:
        if len(self._obs) < self.min_observations: return []
        anchors, unit_vecs = np.array([anc for anc, _ in self._obs]), np.array([uv for _, uv in self._obs])
        mean_vec = unit_vecs.mean(axis=0)
        resultant = float(np.linalg.norm(mean_vec))
        if resultant >= 0.75:
            dom = mean_vec / resultant
            return [AutoDetectedLane("auto_lane_oneway", self.road_polygon.astype(np.int32), (float(dom[0]), float(dom[1])))]

        axis = compute_pca_axis(unit_vecs)
        x_span = max(float(anchors[:, 0].max() - anchors[:, 0].min()), 1.0)
        x_norm = (anchors[:, 0] - anchors[:, 0].min()) / x_span
        features = np.column_stack([x_norm, unit_vecs])
        try:
            _, labels = kmeans2(features, 2, minit="points")
            m0, m1 = (labels == 0), (labels == 1)
            if m0.sum() < 3 or m1.sum() < 3: m0, m1 = (unit_vecs @ axis) >= 0, (unit_vecs @ axis) < 0
        except Exception:
            m0, m1 = (unit_vecs @ axis) >= 0, (unit_vecs @ axis) < 0

        dir_0, dir_1 = safe_norm(unit_vecs[m0].mean(axis=0)), safe_norm(unit_vecs[m1].mean(axis=0))
        if float(np.dot(dir_0, dir_1)) > 0.40:
            dom = safe_norm(unit_vecs.mean(axis=0))
            return [AutoDetectedLane("auto_lane_oneway", self.road_polygon.astype(np.int32), (float(dom[0]), float(dom[1])))]

        poly_a, poly_b = clip_polygon_by_axis(self.road_polygon, axis)
        if len(poly_a) < 3 or len(poly_b) < 3:
            dom = safe_norm(unit_vecs.mean(axis=0))
            return [AutoDetectedLane("auto_lane_oneway", self.road_polygon.astype(np.int32), (float(dom[0]), float(dom[1])))]

        cen_a, cen_b = poly_a.mean(axis=0), poly_b.mean(axis=0)
        c0_in_a = np.linalg.norm(anchors[m0].mean(axis=0) - cen_a) < np.linalg.norm(anchors[m0].mean(axis=0) - cen_b)
        dir_a, dir_b = (dir_0, dir_1) if c0_in_a else (dir_1, dir_0)

        return [
            AutoDetectedLane("auto_lane_a", poly_a.astype(np.int32), (float(dir_a[0]), float(dir_a[1]))),
            AutoDetectedLane("auto_lane_b", poly_b.astype(np.int32), (float(dir_b[0]), float(dir_b[1]))),
        ]
