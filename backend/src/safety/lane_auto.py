"""Automatic lane direction detection from vehicle trajectory clustering."""
from __future__ import annotations
import math
from typing import List, Tuple
import numpy as np
from src.safety.lane_split import safe_norm, compute_pca_axis, clip_polygon_by_axis


class AutoDetectedLane:
    """Duck-type compatible with LaneConfig (.id, .polygon, .permitted_unit_vector)."""
    __slots__ = ("id", "polygon", "permitted_unit_vector")

    def __init__(self, lane_id: str, polygon: np.ndarray, permitted_unit_vector: Tuple[float, float]) -> None:
        self.id = lane_id
        self.polygon: List[List[int]] = polygon.tolist()
        self.permitted_unit_vector = tuple(permitted_unit_vector)

    def __repr__(self) -> str:
        ux, uy = self.permitted_unit_vector
        return f"AutoDetectedLane(id={self.id!r}, flow=({ux:+.3f}, {uy:+.3f}))"


class LaneAutoDetector:
    """Learns lane structure and permitted flow directions purely from tracked trajectories."""

    def __init__(
        self, road_polygon, min_speed_px: float = 3.0,
        min_observations: int = 15, bidir_threshold: float = 0.40
    ) -> None:
        self.road_polygon = np.array(road_polygon, dtype=float).reshape(-1, 2)
        self.min_speed_px = min_speed_px
        self.min_observations = min_observations
        self.bidir_threshold = bidir_threshold
        self._obs: List[Tuple[np.ndarray, np.ndarray]] = []

    def observe(self, anchor_x: float, anchor_y: float, vel_dx: float, vel_dy: float) -> None:
        speed = math.hypot(vel_dx, vel_dy)
        if speed >= self.min_speed_px:
            self._obs.append((np.array([anchor_x, anchor_y]), np.array([vel_dx / speed, vel_dy / speed])))

    @property
    def has_enough_data(self) -> bool:
        return len(self._obs) >= self.min_observations

    def detect_lanes(self) -> List[AutoDetectedLane]:
        if not self.has_enough_data:
            return []
        unit_vecs = np.array([uv for _, uv in self._obs])
        mean_vec = unit_vecs.mean(axis=0)
        resultant = float(np.linalg.norm(mean_vec))
        if resultant >= self.bidir_threshold:
            dom = mean_vec / resultant
            return [AutoDetectedLane("auto_lane_oneway", self.road_polygon.astype(np.int32), (float(dom[0]), float(dom[1])))]
        return self._build_bidirectional_lanes(unit_vecs)

    def _build_bidirectional_lanes(self, unit_vecs: np.ndarray) -> List[AutoDetectedLane]:
        axis = compute_pca_axis(unit_vecs)
        mask_pos = (unit_vecs @ axis) >= 0
        mask_neg = ~mask_pos
        if mask_pos.sum() == 0 or mask_neg.sum() == 0:
            mean = safe_norm(unit_vecs.mean(axis=0))
            return [AutoDetectedLane("auto_lane_oneway", self.road_polygon.astype(np.int32), (float(mean[0]), float(mean[1])))]

        dir_pos = safe_norm(unit_vecs[mask_pos].mean(axis=0))
        dir_neg = safe_norm(unit_vecs[mask_neg].mean(axis=0))
        anchors = np.array([anc for anc, _ in self._obs])
        mean_pos_anchor = anchors[mask_pos].mean(axis=0)

        poly_a, poly_b = clip_polygon_by_axis(self.road_polygon, axis)
        cen_a, cen_b = poly_a.mean(axis=0), poly_b.mean(axis=0)
        pos_in_a = np.linalg.norm(mean_pos_anchor - cen_a) < np.linalg.norm(mean_pos_anchor - cen_b)
        dir_a, dir_b = (dir_pos, dir_neg) if pos_in_a else (dir_neg, dir_pos)

        return [
            AutoDetectedLane("auto_lane_a", poly_a.astype(np.int32), (float(dir_a[0]), float(dir_a[1]))),
            AutoDetectedLane("auto_lane_b", poly_b.astype(np.int32), (float(dir_b[0]), float(dir_b[1]))),
        ]
