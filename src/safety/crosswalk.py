"""Crosswalk Checker: Detect Motorcycles Traversing Pedestrian Crossings."""
from collections import defaultdict
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.core.anchors import get_ground_anchor
from src.core.perspective import compute_perspective_scale
from src.core.motion import get_motion_metrics, point_to_polygon_dist
from src.safety.crosswalk_rules import is_normal_lane_transit, classify_crosswalk_motion


class CrosswalkSafetyChecker:
    """Evaluates motorcycle traversals over designated crosswalk zones."""

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
        self.frames_in_cw: Dict[int, int] = defaultdict(int)
        self.entry_point: Dict[int, Tuple[float, float]] = {}
        self.status_cache: Dict[int, str] = {}

    def _eval_bike(
        self, tid: int, xyxy: np.ndarray, hist: list, l_vecs: Optional[List[Tuple[float, float]]]
    ) -> Optional[str]:
        cx, cy = get_ground_anchor(xyxy)
        pts = [(h[0], h[1]) if isinstance(h, (tuple, list)) else (h.cx, h.cy) for h in hist]
        spd, dist, _, dx, dy = get_motion_metrics(
            pts, 5, self.frame_height, self.perspective_cfg
        )
        if not any(point_to_polygon_dist((cx, cy), p) >= 0 for p in self.crosswalk_polygons):
            self.frames_in_cw[tid] = 0
            self.entry_point.pop(tid, None)
            return None

        self.frames_in_cw[tid] += 1
        self.entry_point.setdefault(tid, (cx, cy))
        if is_normal_lane_transit(dx, dy, l_vecs):
            return None
        if spd < 1.5 or dist < 15.0:
            return "STOPPED_NEAR_CROSSWALK"

        scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
        cw_d = math.hypot(cx - self.entry_point[tid][0], cy - self.entry_point[tid][1]) / max(0.1, scale)
        if cw_d < self.min_passage_dist_px or self.frames_in_cw[tid] < self.min_traversal_frames:
            return "TRAVERSING_PRELIMINARY"

        status = classify_crosswalk_motion(
            spd, cw_d, self.min_passage_dist_px, self.max_walking_speed, self.min_riding_speed
        )
        self.status_cache[tid] = status
        return status

    def check_motorcycles(
        self,
        detections: sv.Detections,
        track_history: dict,
        frame_idx: int,
        lane_vectors: Optional[List[Tuple[float, float]]] = None
    ) -> Dict[int, str]:
        """Check detections for crosswalk violations or exempt pedestrian walking."""
        results = {}
        if len(detections) == 0 or detections.tracker_id is None:
            return results
        bike_mask = np.isin(detections.class_id, [1, 3])
        if not np.any(bike_mask):
            return results

        for box, tid in zip(detections[bike_mask].xyxy, detections[bike_mask].tracker_id):
            if tid is not None and tid in track_history and len(track_history[tid]) >= 3:
                res = self._eval_bike(tid, box, track_history[tid], lane_vectors)
                if res:
                    results[tid] = res
        return results
