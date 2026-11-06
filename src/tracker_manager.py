"""
Tracker Manager: Robust Multi-Vehicle & Motorcycle Identity Maintenance
Handles occlusions, overlapping rider/chassis detections, missed detections,
and tracking ID changes (track stitching / ReID).
"""
from collections import defaultdict, deque
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.geometry_utils import get_box_geometry, get_ground_anchor, compute_perspective_scale

class TrackState:
    def __init__(self, canonical_id: int, initial_frame: int, xyxy: np.ndarray, class_id: int):
        self.canonical_id = canonical_id
        self.raw_tids = set()
        self.class_id = class_id
        self.history = deque(maxlen=60)  # Stores (frame_idx, cx, cy, bbox)
        self.last_seen_frame = initial_frame
        self.first_seen_frame = initial_frame
        self.missed_count = 0
        self.is_active = True
        self.status = "NORMAL"

        cx, cy = get_ground_anchor(xyxy)
        self.history.append((initial_frame, cx, cy, xyxy.copy()))

    def update(self, frame_idx: int, xyxy: np.ndarray, class_id: int, raw_tid: Optional[int] = None):
        if raw_tid is not None:
            self.raw_tids.add(raw_tid)
        self.class_id = class_id
        self.last_seen_frame = frame_idx
        self.missed_count = 0
        self.is_active = True
        cx, cy = get_ground_anchor(xyxy)
        self.history.append((frame_idx, cx, cy, xyxy.copy()))

    def predict_next(self) -> Tuple[float, float]:
        """Extrapolates next position using recent velocity."""
        if len(self.history) < 2:
            return (self.history[-1][1], self.history[-1][2])
        p1 = self.history[-1]
        p0 = self.history[-2]
        dt = max(1, p1[0] - p0[0])
        vx = (p1[1] - p0[1]) / float(dt)
        vy = (p1[2] - p0[2]) / float(dt)
        return (p1[1] + vx, p1[2] + vy)

class RobustTrackerManager:
    def __init__(
        self,
        max_reconnect_frames: int = 25,
        max_reconnect_dist_px: float = 180.0,
        frame_height: float = 2160.0,
        perspective_cfg: Optional[Any] = None
    ):
        self.max_reconnect_frames = max_reconnect_frames
        self.max_reconnect_dist_px = max_reconnect_dist_px
        self.frame_height = frame_height
        self.perspective_cfg = perspective_cfg

        self.next_canonical_id = 1
        self.raw_to_canonical: Dict[int, int] = {}
        self.tracks: Dict[int, TrackState] = {}

    def suppress_duplicate_bikes(self, detections: sv.Detections, iou_threshold: float = 0.25) -> sv.Detections:
        """Suppresses duplicate bounding boxes on the same motorcycle/bike."""
        if len(detections) == 0:
            return detections

        bike_mask = np.isin(detections.class_id, [1, 3])
        if np.sum(bike_mask) <= 1:
            return detections

        bike_indices = np.where(bike_mask)[0]
        boxes = detections.xyxy[bike_indices]
        confs = detections.confidence[bike_indices] if detections.confidence is not None else np.ones(len(boxes))
        order = np.argsort(confs)[::-1]
        keep = np.ones(len(bike_indices), dtype=bool)

        for i in range(len(order)):
            idx_i = order[i]
            if not keep[idx_i]:
                continue
            b_i = boxes[idx_i]
            area_i = (b_i[2] - b_i[0]) * (b_i[3] - b_i[1])

            for j in range(i + 1, len(order)):
                idx_j = order[j]
                if not keep[idx_j]:
                    continue
                b_j = boxes[idx_j]
                area_j = (b_j[2] - b_j[0]) * (b_j[3] - b_j[1])

                ix1 = max(b_i[0], b_j[0])
                iy1 = max(b_i[1], b_j[1])
                ix2 = min(b_i[2], b_j[2])
                iy2 = min(b_i[3], b_j[3])
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                iou = inter / (area_i + area_j - inter) if (area_i + area_j - inter) > 0 else 0
                ioa_smaller = inter / min(area_i, area_j) if min(area_i, area_j) > 0 else 0

                if iou >= iou_threshold or ioa_smaller >= 0.40:
                    keep[idx_j] = False

        suppress_indices = bike_indices[~keep]
        final_keep = np.ones(len(detections), dtype=bool)
        final_keep[suppress_indices] = False
        return detections[final_keep]

    def update_tracks(
        self,
        detections: sv.Detections,
        frame_idx: int
    ) -> sv.Detections:
        """
        Updates track states, handles track stitching across ID changes,
        and assigns canonical IDs.
        """
        if len(detections) == 0 or detections.tracker_id is None:
            return detections

        canonical_ids = np.zeros(len(detections), dtype=int)

        for i, (xyxy, raw_tid, cid) in enumerate(zip(detections.xyxy, detections.tracker_id, detections.class_id)):
            if raw_tid is None:
                continue

            # Check if this raw tracker ID is already known
            if raw_tid in self.raw_to_canonical:
                cid_canon = self.raw_to_canonical[raw_tid]
                track = self.tracks[cid_canon]
                track.update(frame_idx, xyxy, cid, raw_tid)
                canonical_ids[i] = cid_canon
            else:
                matched_canon_id = self._attempt_stitch(xyxy, cid, frame_idx)
                if matched_canon_id is not None:
                    self.raw_to_canonical[raw_tid] = matched_canon_id
                    track = self.tracks[matched_canon_id]
                    track.update(frame_idx, xyxy, cid, raw_tid)
                    canonical_ids[i] = matched_canon_id
                else:
                    new_id = self.next_canonical_id
                    self.next_canonical_id += 1
                    self.raw_to_canonical[raw_tid] = new_id
                    self.tracks[new_id] = TrackState(new_id, frame_idx, xyxy, cid)
                    self.tracks[new_id].raw_tids.add(raw_tid)
                    canonical_ids[i] = new_id

        # Update missed count for inactive tracks
        for canon_id, track in self.tracks.items():
            if track.last_seen_frame < frame_idx:
                track.missed_count += 1
                if track.missed_count > self.max_reconnect_frames:
                    track.is_active = False

        # Ensure all detections have a valid canonical track ID
        for i in range(len(canonical_ids)):
            if canonical_ids[i] == 0:
                new_id = self.next_canonical_id
                self.next_canonical_id += 1
                canonical_ids[i] = new_id
                self.tracks[new_id] = TrackState(new_id, frame_idx, detections.xyxy[i], detections.class_id[i])

        detections.tracker_id = canonical_ids
        return detections

    def _attempt_stitch(self, xyxy: np.ndarray, class_id: int, frame_idx: int) -> Optional[int]:
        """
        Spatial & directional track stitching across occlusions or ByteTrack ID switches.
        """
        cx, cy = get_ground_anchor(xyxy)
        scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
        max_dist = self.max_reconnect_dist_px * scale

        best_id = None
        best_score = float("inf")

        for canon_id, track in self.tracks.items():
            gap = frame_idx - track.last_seen_frame
            if 1 <= gap <= self.max_reconnect_frames and track.class_id == class_id:
                pred_x, pred_y = track.predict_next()
                dist = math.hypot(cx - pred_x, cy - pred_y)

                if dist <= max_dist:
                    score = dist + gap * 2.0
                    if score < best_score:
                        best_score = score
                        best_id = canon_id

        return best_id
