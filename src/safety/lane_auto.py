"""
Automatic lane direction detection from vehicle trajectory clustering.

The system observes vehicle ground-contact anchors and velocity vectors during
a warmup window, then clusters them to determine:
  - Number of lanes (1 = one-way, 2 = bidirectional)
  - Permitted flow direction for each lane (auto-computed unit vector)
  - Lane boundary polygons (auto-split from the user-defined road zone)

No manual lanes or direction_vectors need to be specified in configs/zones.json.
"""
from __future__ import annotations

import math
from typing import List, Tuple, Optional
import numpy as np


class AutoDetectedLane:
    """
    A lane discovered automatically from trajectory clustering.
    Duck-type compatible with LaneConfig (.id, .polygon, .permitted_unit_vector).
    """
    __slots__ = ("id", "polygon", "permitted_unit_vector")

    def __init__(
        self,
        lane_id: str,
        polygon: np.ndarray,
        permitted_unit_vector: Tuple[float, float],
    ) -> None:
        self.id = lane_id
        self.polygon: List[List[int]] = polygon.tolist()
        self.permitted_unit_vector: Tuple[float, float] = tuple(permitted_unit_vector)

    def __repr__(self) -> str:
        ux, uy = self.permitted_unit_vector
        return f"AutoDetectedLane(id={self.id!r}, flow=({ux:+.3f}, {uy:+.3f}))"


class LaneAutoDetector:
    """
    Learns lane structure and permitted flow directions purely from tracked trajectories.

    How it works
    ------------
    1. During a *warmup window*, call ``observe()`` for every moving vehicle.
    2. After warmup, call ``detect_lanes()``:
       a. All collected velocity unit-vectors are summed to form the *resultant vector*.
       b. If |resultant| is HIGH  → one dominant direction → **one-way road**.
       c. If |resultant| is LOW   → opposing flows cancel out → **bidirectional road**.
    3. For a bidirectional road, PCA on the unit-vectors finds the primary travel axis.
       Vehicles are split into two clusters by their projection sign on that axis.
       The road polygon is then clipped into two halves along the axis, and each
       half gets the mean flow direction of its cluster.

    Parameters
    ----------
    road_polygon : array-like (N×2 pixel coords)
    min_speed_px : minimum speed threshold to accept an observation
    min_observations : minimum samples before ``detect_lanes()`` is meaningful
    bidir_threshold : resultant magnitude below this → treat road as bidirectional
    """

    def __init__(
        self,
        road_polygon,
        min_speed_px: float = 3.0,
        min_observations: int = 15,
        bidir_threshold: float = 0.40,
    ) -> None:
        self.road_polygon = np.array(road_polygon, dtype=float).reshape(-1, 2)
        self.min_speed_px = min_speed_px
        self.min_observations = min_observations
        self.bidir_threshold = bidir_threshold

        # Each entry: (anchor_xy: ndarray[2], unit_vec: ndarray[2])
        self._obs: List[Tuple[np.ndarray, np.ndarray]] = []

    # ------------------------------------------------------------------
    # Warmup API
    # ------------------------------------------------------------------

    def observe(
        self,
        anchor_x: float,
        anchor_y: float,
        vel_dx: float,
        vel_dy: float,
    ) -> None:
        """Record one vehicle ground-anchor observation with its velocity."""
        speed = math.hypot(vel_dx, vel_dy)
        if speed < self.min_speed_px:
            return
        self._obs.append((
            np.array([anchor_x, anchor_y]),
            np.array([vel_dx / speed, vel_dy / speed]),
        ))

    @property
    def has_enough_data(self) -> bool:
        return len(self._obs) >= self.min_observations

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_lanes(self) -> List[AutoDetectedLane]:
        """
        Return auto-detected lanes. Empty list if not enough warmup data.
        Returns 1 lane (one-way) or 2 lanes (bidirectional).
        """
        if not self.has_enough_data:
            return []

        unit_vecs = np.array([uv for _, uv in self._obs])   # (N, 2)
        mean_vec = unit_vecs.mean(axis=0)
        resultant = float(np.linalg.norm(mean_vec))

        if resultant >= self.bidir_threshold:
            # ---- One-way ----
            dominant = mean_vec / resultant
            return [AutoDetectedLane(
                lane_id="auto_lane_oneway",
                polygon=self.road_polygon.astype(np.int32),
                permitted_unit_vector=(float(dominant[0]), float(dominant[1])),
            )]

        # ---- Bidirectional ----
        return self._build_bidirectional_lanes(unit_vecs)

    # ------------------------------------------------------------------
    # Bidirectional helpers
    # ------------------------------------------------------------------

    def _build_bidirectional_lanes(
        self, unit_vecs: np.ndarray
    ) -> List[AutoDetectedLane]:
        """Cluster velocities and split road polygon into two directional lanes."""
        primary_axis = self._pca_primary_axis(unit_vecs)

        # Split unit-vectors by sign of projection onto primary axis
        projs = unit_vecs @ primary_axis
        mask_pos = projs >= 0
        mask_neg = ~mask_pos

        if mask_pos.sum() == 0 or mask_neg.sum() == 0:
            # Degenerate – fall back to one-way
            mean = self._safe_norm(unit_vecs.mean(axis=0))
            return [AutoDetectedLane(
                "auto_lane_oneway",
                self.road_polygon.astype(np.int32),
                (float(mean[0]), float(mean[1])),
            )]

        dir_pos = self._safe_norm(unit_vecs[mask_pos].mean(axis=0))
        dir_neg = self._safe_norm(unit_vecs[mask_neg].mean(axis=0))

        anchors = np.array([anc for anc, _ in self._obs])   # (N, 2)
        mean_pos_anchor = anchors[mask_pos].mean(axis=0)
        mean_neg_anchor = anchors[mask_neg].mean(axis=0)

        # Geometrically split the road polygon along the primary flow axis
        poly_a, poly_b = self._clip_polygon_by_axis(primary_axis)

        # Assign clusters to polygon halves by centroid proximity
        cen_a = poly_a.mean(axis=0)
        cen_b = poly_b.mean(axis=0)

        pos_in_a = (
            np.linalg.norm(mean_pos_anchor - cen_a)
            < np.linalg.norm(mean_pos_anchor - cen_b)
        )

        if pos_in_a:
            dir_a, dir_b = dir_pos, dir_neg
        else:
            dir_a, dir_b = dir_neg, dir_pos

        return [
            AutoDetectedLane(
                lane_id="auto_lane_a",
                polygon=poly_a.astype(np.int32),
                permitted_unit_vector=(float(dir_a[0]), float(dir_a[1])),
            ),
            AutoDetectedLane(
                lane_id="auto_lane_b",
                polygon=poly_b.astype(np.int32),
                permitted_unit_vector=(float(dir_b[0]), float(dir_b[1])),
            ),
        ]

    def _pca_primary_axis(self, unit_vecs: np.ndarray) -> np.ndarray:
        """Return the first principal component of unit-vectors (the dominant travel axis)."""
        cov = (unit_vecs.T @ unit_vecs) / len(unit_vecs)
        _, evecs = np.linalg.eigh(cov)      # eigenvalues ascending
        axis = evecs[:, -1]                 # largest eigenvalue → dominant axis
        # Canonical orientation: prefer +x, else +y
        if axis[0] < -1e-9 or (abs(axis[0]) < 1e-9 and axis[1] < 0):
            axis = -axis
        return axis

    def _clip_polygon_by_axis(
        self, primary_axis: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Clip the road polygon into two halves along a line through the centroid
        parallel to *primary_axis* (Sutherland-Hodgman-style edge walking).

        The perpendicular to primary_axis defines the "left" and "right" sides.
        """
        pts = self.road_polygon
        centroid = pts.mean(axis=0)

        ax, ay = primary_axis
        # Normal pointing "left" relative to the primary axis
        split_normal = np.array([-ay, ax])

        left_pts: List[np.ndarray] = []
        right_pts: List[np.ndarray] = []
        n = len(pts)

        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            d1 = float(np.dot(p1 - centroid, split_normal))
            d2 = float(np.dot(p2 - centroid, split_normal))

            (left_pts if d1 <= 0 else right_pts).append(p1.copy())

            # Edge crosses the divider line?
            if (d1 < 0 and d2 > 0) or (d1 > 0 and d2 < 0):
                t = d1 / (d1 - d2)
                cross = p1 + t * (p2 - p1)
                left_pts.append(cross)
                right_pts.append(cross)

        poly_a = self._sort_convex(np.array(left_pts))
        poly_b = self._sort_convex(np.array(right_pts))
        return poly_a, poly_b

    @staticmethod
    def _sort_convex(pts: np.ndarray) -> np.ndarray:
        """Sort polygon vertices counter-clockwise around their centroid."""
        if len(pts) < 3:
            return pts
        c = pts.mean(axis=0)
        angles = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
        return pts[np.argsort(angles)]

    @staticmethod
    def _safe_norm(vec: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(vec))
        return vec / n if n > 1e-9 else np.array([0.0, -1.0])
