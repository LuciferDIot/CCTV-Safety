"""Automatic lane detection and soft lane assignment."""
from typing import List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.core.perspective import compute_perspective_scale
from src.core.motion import point_to_polygon_dist
from src.safety.lane_geometry import point_to_segment_dist


class AutoLaneDetector:
    """Manages road and lane polygon zones with soft divider ambiguity detection."""

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

    def calibrate(self, fallback_lanes: Optional[List[Any]] = None) -> None:
        """Initialize lane polygon zones and the dividing boundary line."""
        if fallback_lanes:
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

    def assign_lane(self, point: Tuple[float, float]) -> Tuple[Optional[int], bool, float]:
        """Soft lane assignment returning (lane_idx, is_ambiguous, dist_to_divider)."""
        cx, cy = point
        scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
        margin = self.ambiguity_margin_px * scale

        contained = []
        for idx, lane in enumerate(self.lanes):
            poly = np.array(lane.polygon, dtype=np.int32)
            d = point_to_polygon_dist((cx, cy), poly)
            if d >= 0:
                contained.append((idx, d))

        if not contained:
            return (None, False, -1.0)

        contained.sort(key=lambda x: x[1], reverse=True)
        best_idx = contained[0][0]

        dist_div = float("inf")
        if self.divider_segment:
            dist_div = point_to_segment_dist((cx, cy), self.divider_segment[0], self.divider_segment[1])

        return (best_idx, dist_div < margin, dist_div)
