"""Safety rules for rider-to-motorcycle spatial fusion and walking ped disambiguation."""
from typing import Optional, Any
import numpy as np
from services.safety.geometry import point_to_polygon_dist


def _match_rider_to_bike(pb: np.ndarray, b_indices: np.ndarray, detections: Any) -> bool:
    """Fuse vertically stacked person onto detected motorcycle chassis."""
    pcx, pw = (pb[0] + pb[2]) / 2.0, pb[2] - pb[0]
    for b_idx in b_indices:
        bb = detections.xyxy[b_idx]
        bcx, bw = (bb[0] + bb[2]) / 2.0, bb[2] - bb[0]
        dx = abs(pcx - bcx)
        y_overlap = (pb[3] >= bb[1] - 50.0 and pb[1] <= bb[3])
        if dx <= max(75.0, 0.75 * max(pw, bw)) and y_overlap:
            detections.xyxy[b_idx][0] = min(detections.xyxy[b_idx][0], pb[0])
            detections.xyxy[b_idx][1] = min(detections.xyxy[b_idx][1], pb[1])
            detections.xyxy[b_idx][2] = max(detections.xyxy[b_idx][2], pb[2])
            detections.xyxy[b_idx][3] = max(detections.xyxy[b_idx][3], pb[3])
            return True
    return False


def _is_walking_ped(tid: Optional[int], track_history: Optional[dict]) -> bool:
    if tid is None or not track_history or tid not in track_history:
        return False
    hist = track_history[tid]
    if len(hist) < 3:
        return False
    dx, dy = hist[-1][0] - hist[0][0], hist[-1][1] - hist[0][1]
    return (np.hypot(dx, dy) / max(1, len(hist) - 1)) <= 4.0


def resolve_riders_and_pedestrians(
    detections: Any, lane_zones: list, crosswalk_zones: list, track_history: Optional[dict] = None
) -> Any:
    """Merge mounted riders into motorcycle bounding boxes."""
    if len(detections) == 0:
        return detections

    p_indices = np.where(detections.class_id == 0)[0]
    b_indices = np.where(np.isin(detections.class_id, [1, 3]))[0]
    suppress = []

    for p_idx in p_indices:
        pb = detections.xyxy[p_idx]
        if _match_rider_to_bike(pb, b_indices, detections):
            suppress.append(p_idx)
            continue

        pcx, pw, ph = (pb[0] + pb[2]) / 2.0, pb[2] - pb[0], pb[3] - pb[1]
        in_cw = any(point_to_polygon_dist((pcx, pb[3]), z.polygon) >= -10 for z in crosswalk_zones)
        if in_cw:
            continue

        in_lane = any(point_to_polygon_dist((pcx, pb[3]), z.polygon) >= -10 for z in lane_zones)
        if in_lane:
            aspect = ph / max(1.0, pw)
            tid = detections.tracker_id[p_idx] if detections.tracker_id is not None else None
            if aspect < 1.80 and not _is_walking_ped(tid, track_history):
                detections.class_id[p_idx] = 3

    keep = np.ones(len(detections), dtype=bool)
    keep[suppress] = False
    return detections[keep]

