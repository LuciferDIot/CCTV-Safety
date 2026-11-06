"""Object detection, track updating, and rider-pedestrian fusion step."""
from typing import Tuple, Dict, Any, List
import numpy as np
import supervision as sv

from src.safety.fusion import resolve_riders_and_pedestrians
from src.pipeline.filters import filter_inside_zones, assign_fallback_ids


def detect_and_track_step(
    model: Any,
    tracker: Any,
    frame: np.ndarray,
    road_poly: np.ndarray,
    cw_polys: List[np.ndarray],
    lane_zones: list,
    cw_zones: list,
    frame_idx: int,
    imgsz: int = 960,
    device: str = "cpu"
) -> Tuple[sv.Detections, Dict[int, list]]:
    """Execute YOLO tracking, zone clipping, fallback IDs, and rider fusion."""
    res = model.track(
        frame, persist=True, tracker="bytetrack.yaml",
        classes=[0, 1, 2, 3, 5, 7], imgsz=imgsz, device=device, conf=0.20, verbose=False
    )[0]
    dets = sv.Detections.from_ultralytics(res)
    dets = filter_inside_zones(dets, road_poly, cw_polys)
    dets = assign_fallback_ids(dets)
    dets = tracker.suppress_duplicate_bikes(dets, iou_threshold=0.25)

    raw_hist = {cid: [(p[1], p[2]) for p in t.history] for cid, t in tracker.tracks.items()}
    dets = resolve_riders_and_pedestrians(dets, lane_zones, cw_zones, raw_hist)
    dets = tracker.update_tracks(dets, frame_idx)
    return dets, raw_hist

