"""
Automatic Lane Segmentation, Permitted Direction Discovery, and Soft Lane Assignment
Accounts for perspective distortion and lane boundary ambiguity along the divider line.
"""
from collections import defaultdict
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.core.geometry import compute_perspective_scale, point_to_polygon_dist

def point_to_segment_dist(p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Computes Euclidean distance from point p to line segment ab."""
    px, py = p
    ax, ay = a
    bx, by = b
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / seg_len_sq))
    proj_x = ax + t * abx
    proj_y = ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)

class AutoLaneDetector:
    def __init__(
        self,
        road_polygon: np.ndarray,
        warmup_frames: int = 40,
        min_tracks: int = 5,
        min_distance_px: float = 15.0,
        ambiguity_margin_px: float = 40.0,
        frame_height: float = 2160.0,
        perspective_cfg: Optional[Any] = None
    ):
        self.road_polygon = np.array(road_polygon, dtype=np.int32)
        self.warmup_frames = warmup_frames
        self.min_tracks = min_tracks
        self.min_distance_px = min_distance_px
        self.ambiguity_margin_px = ambiguity_margin_px
        self.frame_height = frame_height
        self.perspective_cfg = perspective_cfg

        self.road_zone = sv.PolygonZone(
            polygon=self.road_polygon,
            triggering_anchors=[sv.Position.BOTTOM_CENTER]
        )

        self.is_calibrated = False
        self.lanes = []
        self.lane_zones = []
        self.divider_segment = None

    def calibrate(self, fallback_lanes: Optional[List[Any]] = None):
        """Initializes lane zones and extracts the dividing boundary segment between lanes."""
        if fallback_lanes is not None and len(fallback_lanes) > 0:
            self.lanes = fallback_lanes
            self.lane_zones = [
                sv.PolygonZone(
                    polygon=np.array(lane.polygon, dtype=np.int32),
                    triggering_anchors=[sv.Position.BOTTOM_CENTER]
                )
                for lane in self.lanes
            ]
            if len(self.lanes) >= 2:
                poly0 = self.lanes[0].polygon
                self.divider_segment = (tuple(poly0[1]), tuple(poly0[2]))
            self.is_calibrated = True

    def assign_lane(
        self,
        point: Tuple[float, float]
    ) -> Tuple[Optional[int], bool, float]:
        """Soft lane assignment. Returns (best_lane_idx, is_ambiguous, distance_to_divider)."""
        cx, cy = point
        scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
        margin = self.ambiguity_margin_px * scale

        contained_lanes = []
        for idx, lane in enumerate(self.lanes):
            poly = np.array(lane.polygon, dtype=np.int32)
            d = point_to_polygon_dist((cx, cy), poly)
            if d >= 0:
                contained_lanes.append((idx, d))

        if not contained_lanes:
            return (None, False, -1.0)

        contained_lanes.sort(key=lambda x: x[1], reverse=True)
        best_lane_idx = contained_lanes[0][0]

        dist_to_divider = float("inf")
        if self.divider_segment:
            dist_to_divider = point_to_segment_dist((cx, cy), self.divider_segment[0], self.divider_segment[1])

        is_ambiguous = (dist_to_divider < margin)
        return (best_lane_idx, is_ambiguous, dist_to_divider)
