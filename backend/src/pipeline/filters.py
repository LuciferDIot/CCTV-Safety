"""Zone containment filtering and fallback ID assignment."""
from typing import List
import cv2
import numpy as np
import supervision as sv
from src.core.anchors import get_ground_anchor


def filter_inside_zones(
    detections: sv.Detections,
    road_poly: np.ndarray,
    crosswalk_polygons: List[np.ndarray]
) -> sv.Detections:
    """Filter out detections outside monitored road and crosswalk polygons."""
    if len(detections) == 0:
        return detections

    inside_mask = np.zeros(len(detections), dtype=bool)
    for idx, xyxy in enumerate(detections.xyxy):
        cx, cy = get_ground_anchor(xyxy)
        pt = (float(cx), float(cy))
        if cv2.pointPolygonTest(road_poly, pt, False) >= 0:
            inside_mask[idx] = True
        else:
            for cw_poly in crosswalk_polygons:
                if cv2.pointPolygonTest(cw_poly, pt, False) >= 0:
                    inside_mask[idx] = True
                    break
    return detections[inside_mask]


def assign_fallback_ids(detections: sv.Detections) -> sv.Detections:
    """Ensure every detection has a valid positive integer tracker ID."""
    if detections.tracker_id is None or len(detections.tracker_id) == 0:
        detections.tracker_id = np.arange(1, len(detections) + 1, dtype=int)
    else:
        tids = list(detections.tracker_id)
        for i in range(len(tids)):
            if tids[i] is None or tids[i] <= 0:
                tids[i] = i + 1
        detections.tracker_id = np.array(tids, dtype=int)
    return detections

