"""Tracker integration, trajectory stitching, and motorcycle duplicate suppression."""
import math
from typing import Dict, Optional, Any
import numpy as np
import supervision as sv
from models.track import TrackState
from services.safety.geometry import get_ground_anchor, compute_perspective_scale


def suppress_duplicate_bikes(detections: sv.Detections, iou_threshold: float = 0.25) -> sv.Detections:
    """Suppress duplicate overlapping bounding boxes on motorcycles."""
    if len(detections) == 0:
        return detections
    bike_mask = np.isin(detections.class_id, [1, 3])
    if np.sum(bike_mask) <= 1:
        return detections
    b_idx = np.where(bike_mask)[0]
    boxes = detections.xyxy[b_idx]
    confs = detections.confidence[b_idx] if detections.confidence is not None else np.ones(len(boxes))
    order = np.argsort(confs)[::-1]
    keep = np.ones(len(b_idx), dtype=bool)

    for i in range(len(order)):
        ii = order[i]
        if not keep[ii]: continue
        bi, area_i = boxes[ii], (boxes[ii][2] - boxes[ii][0]) * (boxes[ii][3] - boxes[ii][1])
        for j in range(i + 1, len(order)):
            jj = order[j]
            if not keep[jj]: continue
            bj = boxes[jj]
            iw = max(0.0, min(bi[2], bj[2]) - max(bi[0], bj[0]))
            ih = max(0.0, min(bi[3], bj[3]) - max(bi[1], bj[1]))
            inter = iw * ih
            area_j = (bj[2] - bj[0]) * (bj[3] - bj[1])
            union = area_i + area_j - inter
            iou = inter / union if union > 0 else 0.0
            ioa = inter / min(area_i, area_j) if min(area_i, area_j) > 0 else 0.0
            if iou >= iou_threshold or ioa >= 0.40:
                keep[jj] = False

    final_keep = np.ones(len(detections), dtype=bool)
    final_keep[b_idx[~keep]] = False
    return detections[final_keep]


class RobustTrackerManager:
    """Manages object tracks, resolves identity switches, and stitches trajectories."""

    def __init__(self, max_reconnect_frames: int = 25, max_reconnect_dist_px: float = 180.0, frame_height: float = 2160.0, perspective_cfg: Optional[Any] = None):
        self.max_reconnect_frames = max_reconnect_frames
        self.max_reconnect_dist_px = max_reconnect_dist_px
        self.frame_height, self.perspective_cfg = frame_height, perspective_cfg
        self.next_canonical_id = 1
        self.raw_to_canonical: Dict[int, int] = {}
        self.tracks: Dict[int, TrackState] = {}

    def _attempt_stitch(self, xyxy: np.ndarray, class_id: int, frame_idx: int) -> Optional[int]:
        cx, cy = get_ground_anchor(xyxy)
        scale = compute_perspective_scale(cy, self.frame_height, self.perspective_cfg)
        max_dist = self.max_reconnect_dist_px * scale
        best_id, best_score = None, float("inf")
        for cid, trk in self.tracks.items():
            gap = frame_idx - trk.last_seen_frame
            if 1 <= gap <= self.max_reconnect_frames and trk.class_id == class_id:
                px, py = trk.predict_next()
                dist = math.hypot(cx - px, cy - py)
                if dist <= max_dist and (dist + gap * 2.0) < best_score:
                    best_score, best_id = dist + gap * 2.0, cid
        return best_id

    def update_tracks(self, detections: sv.Detections, frame_idx: int) -> sv.Detections:
        if len(detections) == 0 or detections.tracker_id is None:
            return detections
        c_ids = np.zeros(len(detections), dtype=int)
        for i, (box, r_tid, cid) in enumerate(zip(detections.xyxy, detections.tracker_id, detections.class_id)):
            c_id = self.raw_to_canonical.get(r_tid) or self._attempt_stitch(box, cid, frame_idx) or self.next_canonical_id
            if c_id == self.next_canonical_id:
                self.next_canonical_id += 1
            self.raw_to_canonical[r_tid] = c_id
            if c_id not in self.tracks:
                self.tracks[c_id] = TrackState(c_id, frame_idx, box, cid)
            else:
                self.tracks[c_id].update(frame_idx, box, cid, r_tid)
            c_ids[i] = c_id

        for trk in list(self.tracks.values()):
            if trk.last_seen_frame < frame_idx:
                trk.missed_count += 1
                if trk.missed_count > self.max_reconnect_frames: trk.is_active = False
                if trk.missed_count > self.max_reconnect_frames * 2: self.tracks.pop(trk.canonical_id, None)

        if len(self.raw_to_canonical) > 500:
            active_cids = set(self.tracks.keys())
            self.raw_to_canonical = {r: c for r, c in self.raw_to_canonical.items() if c in active_cids}

        detections.tracker_id = c_ids
        return detections
