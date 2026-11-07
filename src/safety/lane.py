"""Automatic lane detection and soft lane assignment."""
from typing import List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.core.perspective import compute_perspective_scale
from src.core.motion import point_to_polygon_dist
from src.safety.lane_geometry import point_to_segment_dist
from src.safety.lane_auto import LaneAutoDetector, AutoDetectedLane


class AutoLaneDetector:
    """
    Manages road and lane polygon zones with soft divider ambiguity detection.

    Supports two calibration modes:
      - Manual:  call calibrate(fallback_lanes=...) with LaneConfig objects from zones.json
      - Auto:    call observe_warmup() during the warmup phase, then auto_calibrate()
                 to discover lanes purely from tracked vehicle trajectories.
    """

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
        self.lanes: List[Any] = []
        self.lane_zones: List[sv.PolygonZone] = []
        self.divider_segment: Optional[Tuple] = None

        # Auto-detector used when no manual lanes are configured
        self._auto_detector = LaneAutoDetector(
            road_polygon=road_polygon,
            min_speed_px=3.0,
            min_observations=15,
            bidir_threshold=0.40,
        )

    # ------------------------------------------------------------------
    # Manual calibration (from zones.json lanes array)
    # ------------------------------------------------------------------

    def calibrate(self, fallback_lanes: Optional[List[Any]] = None) -> None:
        """Initialize lane polygon zones from manually-configured LaneConfig objects."""
        if not fallback_lanes:
            return  # No manual lanes – will use auto-calibration
        self.lanes = list(fallback_lanes)
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

    # ------------------------------------------------------------------
    # Auto calibration (from warmup trajectory observations)
    # ------------------------------------------------------------------

    def observe_warmup(
        self, anchor_x: float, anchor_y: float, vel_dx: float, vel_dy: float
    ) -> None:
        """
        Feed a vehicle ground-anchor + velocity observation to the auto-detector.
        Only effective before auto_calibrate() is called.
        """
        if not self.is_calibrated:
            self._auto_detector.observe(anchor_x, anchor_y, vel_dx, vel_dy)

    def auto_calibrate(self) -> bool:
        """
        Detect lanes automatically from collected warmup observations.

        Returns True if calibration succeeded (enough data was collected),
        False if still waiting for more observations.
        """
        if self.is_calibrated:
            return True

        detected = self._auto_detector.detect_lanes()
        if not detected:
            print("[AutoLane] Not enough warmup data yet – continuing to collect.")
            return False

        self.lanes = detected
        self.lane_zones = [
            sv.PolygonZone(
                polygon=np.array(lane.polygon, dtype=np.int32),
                triggering_anchors=[sv.Position.BOTTOM_CENTER]
            )
            for lane in self.lanes
        ]

        if len(self.lanes) >= 2:
            self._compute_divider_segment()

        self.is_calibrated = True
        print(f"[AutoLane] Calibrated: {len(self.lanes)} lane(s) auto-detected.")
        for ln in self.lanes:
            print(f"  {ln}")
        return True

    def _compute_divider_segment(self) -> None:
        """
        Approximate the divider line between two auto-detected lanes.
        Uses the vertices from each lane polygon that are closest to the road centroid.
        """
        road_centroid = self.road_polygon.astype(float).mean(axis=0)
        inner_pts = []
        for lane in self.lanes:
            pts = np.array(lane.polygon, dtype=float)
            dists = np.linalg.norm(pts - road_centroid, axis=1)
            inner_pts.append(pts[np.argmin(dists)])
        if len(inner_pts) >= 2:
            self.divider_segment = (
                tuple(inner_pts[0].astype(int)),
                tuple(inner_pts[1].astype(int)),
            )

    # ------------------------------------------------------------------
    # Lane assignment (used per-frame for ambiguity detection)
    # ------------------------------------------------------------------

    def assign_lane(self, point: Tuple[float, float]) -> Tuple[Optional[int], bool, float]:
        """
        Soft lane assignment: returns (lane_idx, is_ambiguous, dist_to_divider).
        is_ambiguous=True means the point is within the ambiguity margin of the divider.
        """
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
            dist_div = point_to_segment_dist(
                (cx, cy), self.divider_segment[0], self.divider_segment[1]
            )

        return (best_idx, dist_div < margin, dist_div)
