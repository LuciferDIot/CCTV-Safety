"""
Crosswalk Checker: Detect Motorcycles Traversing Pedestrian Crossings
Distinguishes actual passage from boundary fringe overlap or stopping nearby.
Distinguishes CROSSWALK_RIDING from EXEMPT_WALKING (dismounted rider walking a bike).
"""
from collections import defaultdict
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.geometry_utils import get_ground_anchor, get_motion_metrics, point_to_polygon_dist, compute_perspective_scale

class CrosswalkSafetyChecker:
    def __init__(
        self,
        crosswalk_polygons: List[np.ndarray],
        min_passage_dist_px: float = 40.0,
        max_walking_speed: float = 3.8,
        min_riding_speed: float = 4.8,
        min_traversal_frames: int = 5,
        frame_height: float = 2160.0,
        perspective_cfg: Optional[Any] = None
    ):
        self.crosswalk_polygons = [np.array(p, dtype=np.int32) for p in crosswalk_polygons]
        self.crosswalk_zones = [
            sv.PolygonZone(polygon=p, triggering_anchors=[sv.Position.BOTTOM_CENTER])
            for p in self.crosswalk_polygons
        ]
        self.min_passage_dist_px = min_passage_dist_px
        self.max_walking_speed = max_walking_speed
        self.min_riding_speed = min_riding_speed
        self.min_traversal_frames = min_traversal_frames
        self.frame_height = frame_height
        self.perspective_cfg = perspective_cfg

        # Track history within crosswalk zones
        self.frames_in_cw: Dict[int, int] = defaultdict(int)
        self.entry_point: Dict[int, Tuple[float, float]] = {}
        self.status_cache: Dict[int, str] = {}

    def check_motorcycles(
        self,
        detections: sv.Detections,
        track_history: dict,
        frame_idx: int,
        lane_vectors: Optional[List[Tuple[float, float]]] = None
    ) -> Dict[int, str]:
        """
        Evaluates motorcycles for crosswalk traversal.
        Exempts normal motorcycles driving along their designated traffic lanes.
        Detects motorcycles traversing across the pedestrian crosswalk (lateral/pedestrian crossing).
        
        Returns:
            dict mapping tracker_id -> status in ["CROSSWALK_RIDING", "EXEMPT_WALKING", "STOPPED", "TOUCHING"]
        """
        results = {}
        if len(detections) == 0 or detections.tracker_id is None:
            return results

        # Only evaluate two-wheelers (Bike / Motorcycle)
        bike_mask = np.isin(detections.class_id, [1, 3])
        if not np.any(bike_mask):
            return results

        bike_dets = detections[bike_mask]

        for xyxy, tid, cid in zip(bike_dets.xyxy, bike_dets.tracker_id, bike_dets.class_id):
            if tid is None or tid not in track_history:
                continue

            hist = track_history[tid]
            if len(hist) < 3:
                continue

            cx, cy = get_ground_anchor(xyxy)
            pts = [(h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]

            corr_speed, corr_dist, raw_speed, dx, dy = get_motion_metrics(
                pts, window=5, frame_height=self.frame_height, perspective_cfg=self.perspective_cfg
            )

            # Check containment inside any crosswalk polygon
            in_cw = False
            for cw_poly in self.crosswalk_polygons:
                dist = point_to_polygon_dist((cx, cy), cw_poly)
                if dist >= 0:  # Ground anchor is strictly inside polygon
                    in_cw = True
                    break

            if not in_cw:
                self.frames_in_cw[tid] = 0
                if tid in self.entry_point:
                    del self.entry_point[tid]
                continue

            # Update crosswalk presence counter
            self.frames_in_cw[tid] += 1
            if tid not in self.entry_point:
                self.entry_point[tid] = (cx, cy)

            # 1. Distinguish Normal Lane Travel through Intersection
            # If the motorcycle is driving along the traffic lane in the permitted direction,
            # it is executing normal road travel, NOT a pedestrian crosswalk violation.
            v_len = math.hypot(dx, dy)
            if v_len > 0.5 and lane_vectors is not None:
                v_norm = (dx / v_len, dy / v_len)
                is_normal_flow = False
                for l_vec in lane_vectors:
                    dot = v_norm[0] * l_vec[0] + v_norm[1] * l_vec[1]
                    if dot >= 0.65 and abs(dy) >= 0.8 * abs(dx):
                        is_normal_flow = True
                        break
                if is_normal_flow:
                    continue

            # 2. Distinguish Stopped Nearby vs Actual Passage
            # If vehicle is stopped or moving negligibly, it's holding still (e.g. at red light)
            if corr_speed < 1.5 or corr_dist < 15.0:
                results[tid] = "STOPPED_NEAR_CROSSWALK"
                self.status_cache[tid] = "STOPPED_NEAR_CROSSWALK"
                continue

            # Check total traversal distance inside the crosswalk
            entry_x, entry_y = self.entry_point[tid]
            cw_dist = math.hypot(cx - entry_x, cy - entry_y)
            scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
            cw_dist_corr = cw_dist / max(0.1, scale)

            # Distinguish boundary touch from actual traversal
            if cw_dist_corr < self.min_passage_dist_px or self.frames_in_cw[tid] < self.min_traversal_frames:
                results[tid] = "TRAVERSING_PRELIMINARY"
                continue

            # 3. Distinguish Riding vs Walking a Motorcycle across the crosswalk
            # If moving at walking speed with low speed kinematics -> EXEMPT_WALKING
            if corr_speed <= self.max_walking_speed:
                results[tid] = "EXEMPT_WALKING"
                self.status_cache[tid] = "EXEMPT_WALKING"
            elif corr_speed >= self.min_riding_speed or cw_dist_corr >= self.min_passage_dist_px:
                results[tid] = "CROSSWALK_RIDING"
                self.status_cache[tid] = "CROSSWALK_RIDING"

        return results

