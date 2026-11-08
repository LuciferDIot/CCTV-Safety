"""KMeans lane direction clustering and Sutherland-Hodgman roadway splitting."""
import math
from typing import List, Tuple
import numpy as np
from scipy.cluster.vq import kmeans2
from models.zone import AutoDetectedLane


def safe_norm(vector: np.ndarray) -> np.ndarray:
    """Normalize vector to unit length; [0, -1] default points northbound away from camera."""
    length = float(np.linalg.norm(vector))
    return vector / length if length > 1e-9 else np.array([0.0, -1.0])


def sort_convex(polygon_pts: np.ndarray) -> np.ndarray:
    """Sort polygon vertices counter-clockwise by polar angle around centroid."""
    if len(polygon_pts) < 3: return polygon_pts
    centroid = polygon_pts.mean(axis=0)
    polar_angles = np.arctan2(polygon_pts[:, 1] - centroid[1], polygon_pts[:, 0] - centroid[0])
    return polygon_pts[np.argsort(polar_angles)]


def compute_pca_axis(unit_vecs: np.ndarray) -> np.ndarray:
    """Find dominant roadway axis via PCA covariance of bidirectional traffic flow."""
    cov_matrix = (unit_vecs.T @ unit_vecs) / len(unit_vecs)
    _, eigenvectors = np.linalg.eigh(cov_matrix)
    axis = eigenvectors[:, -1]
    if axis[0] < -1e-9 or (abs(axis[0]) < 1e-9 and axis[1] < 0): axis = -axis
    return axis


def clip_polygon_by_axis(polygon_pts: np.ndarray, flow_axis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Split road polygon along centerline normal into left and right lanes."""
    centroid = polygon_pts.mean(axis=0)
    split_normal = np.array([-flow_axis[1], flow_axis[0]])  # Perpendicular normal
    left_pts, right_pts = [], []
    num_pts = len(polygon_pts)
    for i in range(num_pts):
        pt_curr, pt_next = polygon_pts[i], polygon_pts[(i + 1) % num_pts]
        dist_curr = float(np.dot(pt_curr - centroid, split_normal))
        dist_next = float(np.dot(pt_next - centroid, split_normal))
        (left_pts if dist_curr <= 0 else right_pts).append(pt_curr.copy())
        if (dist_curr < 0 and dist_next > 0) or (dist_curr > 0 and dist_next < 0):
            edge_cut_ratio = dist_curr / (dist_curr - dist_next)
            intersection_pt = pt_curr + edge_cut_ratio * (pt_next - pt_curr)
            left_pts.append(intersection_pt); right_pts.append(intersection_pt)
    return sort_convex(np.array(left_pts)), sort_convex(np.array(right_pts))


class LaneAutoDetector:
    """Learns lane boundaries and permitted flow directions from observed vehicle trajectories."""

    def __init__(self, road_polygon, min_speed_px: float = 3.0, min_observations: int = 15, bidir_threshold: float = 0.75):
        self.road_polygon = np.array(road_polygon, dtype=float).reshape(-1, 2)
        self.min_speed_px, self.min_observations, self.bidir_threshold = min_speed_px, min_observations, bidir_threshold
        self._obs: List[Tuple[np.ndarray, np.ndarray]] = []

    def observe(self, anchor_x: float, anchor_y: float, vel_dx: float, vel_dy: float) -> None:
        speed = math.hypot(vel_dx, vel_dy)
        if speed >= self.min_speed_px and len(self._obs) < 500:
            self._obs.append((np.array([anchor_x, anchor_y]), np.array([vel_dx / speed, vel_dy / speed])))

    def detect_lanes(self) -> List[AutoDetectedLane]:
        """Cluster observed vehicle motions and partition the road into directional lanes."""
        if len(self._obs) < self.min_observations: return []
        poly_int = self.road_polygon.astype(np.int32)
        _oneway = lambda v: [AutoDetectedLane("auto_lane_oneway", poly_int, (float(v[0]), float(v[1])))]

        anchors, unit_vecs = np.array([o[0] for o in self._obs]), np.array([o[1] for o in self._obs])
        mean_vec = unit_vecs.mean(axis=0)
        # Resultant length >= bidir_threshold indicates vehicles travel in unison (one-way roadway)
        if float(np.linalg.norm(mean_vec)) >= self.bidir_threshold:
            return _oneway(mean_vec / float(np.linalg.norm(mean_vec)))

        axis = compute_pca_axis(unit_vecs)
        x_span = max(float(anchors[:, 0].max() - anchors[:, 0].min()), 1.0)
        features = np.column_stack([(anchors[:, 0] - anchors[:, 0].min()) / x_span, unit_vecs])
        try:
            _, labels = kmeans2(features, 2, minit="points")
            m0, m1 = (labels == 0), (labels == 1)
            if m0.sum() < 3 or m1.sum() < 3: m0, m1 = (unit_vecs @ axis) >= 0, (unit_vecs @ axis) < 0
        except Exception:
            m0, m1 = (unit_vecs @ axis) >= 0, (unit_vecs @ axis) < 0

        dir_0, dir_1 = safe_norm(unit_vecs[m0].mean(axis=0)), safe_norm(unit_vecs[m1].mean(axis=0))
        if float(np.dot(dir_0, dir_1)) > 0.40:
            return _oneway(safe_norm(unit_vecs.mean(axis=0)))

        poly_a, poly_b = clip_polygon_by_axis(self.road_polygon, axis)
        if len(poly_a) < 3 or len(poly_b) < 3: return _oneway(safe_norm(unit_vecs.mean(axis=0)))

        cen_a, cen_b = poly_a.mean(axis=0), poly_b.mean(axis=0)
        c0_in_a = np.linalg.norm(anchors[m0].mean(axis=0) - cen_a) < np.linalg.norm(anchors[m0].mean(axis=0) - cen_b)
        dir_a, dir_b = (dir_0, dir_1) if c0_in_a else (dir_1, dir_0)

        return [
            AutoDetectedLane("auto_lane_a", poly_a.astype(np.int32), (float(dir_a[0]), float(dir_a[1]))),
            AutoDetectedLane("auto_lane_b", poly_b.astype(np.int32), (float(dir_b[0]), float(dir_b[1]))),
        ]
