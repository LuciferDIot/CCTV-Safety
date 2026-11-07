"""Automatic lane detection and soft lane assignment."""
from typing import List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.safety.lane_auto import LaneAutoDetector, AutoDetectedLane
from src.safety.lane_assignment import assign_point_to_lane


class AutoLaneDetector:
    """Manages road and lane polygon zones with soft divider ambiguity detection."""

    def __init__(
        self, road_polygon: np.ndarray, warmup_frames: int = 40,
        min_tracks: int = 5, min_distance_px: float = 15.0,
        ambiguity_margin_px: float = 40.0, frame_height: float = 2160.0,
        perspective_cfg: Optional[Any] = None,
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
        self.lanes: List[Any] = []
        self.lane_zones: List[sv.PolygonZone] = []
        self.divider_segment: Optional[Tuple] = None
        self._auto_detector = LaneAutoDetector(
            road_polygon=road_polygon, min_speed_px=3.0,
            min_observations=15, bidir_threshold=0.40
        )

    def calibrate(self, fallback_lanes: Optional[List[Any]] = None) -> None:
        if not fallback_lanes:
            return
        self.lanes = list(fallback_lanes)
        self.lane_zones = [
            sv.PolygonZone(polygon=np.array(l.polygon, dtype=np.int32), triggering_anchors=[sv.Position.BOTTOM_CENTER])
            for l in self.lanes
        ]
        if len(self.lanes) >= 2:
            poly0 = self.lanes[0].polygon
            self.divider_segment = (tuple(poly0[1]), tuple(poly0[2]))
        self.is_calibrated = True

    def observe_warmup(self, anchor_x: float, anchor_y: float, vel_dx: float, vel_dy: float) -> None:
        self._auto_detector.observe(anchor_x, anchor_y, vel_dx, vel_dy)

    def auto_calibrate(self, force: bool = False) -> bool:
        if self.is_calibrated and not force:
            return True
        detected = self._auto_detector.detect_lanes()
        if not detected:
            return False
        self.lanes = detected
        self.lane_zones = [
            sv.PolygonZone(polygon=np.array(l.polygon, dtype=np.int32), triggering_anchors=[sv.Position.BOTTOM_CENTER])
            for l in self.lanes
        ]
        if len(self.lanes) >= 2:
            self._compute_divider_segment()
        self.is_calibrated = True
        return True

    def _compute_divider_segment(self) -> None:
        road_centroid = self.road_polygon.astype(float).mean(axis=0)
        inner_pts = []
        for lane in self.lanes:
            pts = np.array(lane.polygon, dtype=float)
            dists = np.linalg.norm(pts - road_centroid, axis=1)
            inner_pts.append(pts[np.argmin(dists)])
        if len(inner_pts) >= 2:
            self.divider_segment = (tuple(inner_pts[0].astype(int)), tuple(inner_pts[1].astype(int)))

    def assign_lane(self, point: Tuple[float, float]) -> Tuple[Optional[int], bool, float]:
        return assign_point_to_lane(
            point, self.lanes, self.divider_segment,
            self.ambiguity_margin_px, self.frame_height, self.perspective_cfg
        )
