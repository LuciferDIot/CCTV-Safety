"""Non-maximum suppression and duplicate detection suppression utilities."""
import numpy as np
import supervision as sv


def suppress_duplicate_bikes(detections: sv.Detections, iou_threshold: float = 0.25) -> sv.Detections:
    """Suppress duplicate overlapping bounding boxes on motorcycles."""
    if len(detections) == 0:
        return detections

    bike_mask = np.isin(detections.class_id, [1, 3])
    if np.sum(bike_mask) <= 1:
        return detections

    bike_indices = np.where(bike_mask)[0]
    boxes = detections.xyxy[bike_indices]
    confs = (
        detections.confidence[bike_indices]
        if detections.confidence is not None
        else np.ones(len(boxes))
    )
    order = np.argsort(confs)[::-1]
    keep = np.ones(len(bike_indices), dtype=bool)

    for i in range(len(order)):
        idx_i = order[i]
        if not keep[idx_i]:
            continue
        bi = boxes[idx_i]
        area_i = (bi[2] - bi[0]) * (bi[3] - bi[1])

        for j in range(i + 1, len(order)):
            idx_j = order[j]
            if not keep[idx_j]:
                continue
            bj = boxes[idx_j]
            area_j = (bj[2] - bj[0]) * (bj[3] - bj[1])

            inter_w = max(0.0, min(bi[2], bj[2]) - max(bi[0], bj[0]))
            inter_h = max(0.0, min(bi[3], bj[3]) - max(bi[1], bj[1]))
            inter = inter_w * inter_h

            union = area_i + area_j - inter
            iou = inter / union if union > 0 else 0.0
            ioa = inter / min(area_i, area_j) if min(area_i, area_j) > 0 else 0.0

            if iou >= iou_threshold or ioa >= 0.40:
                keep[idx_j] = False

    final_keep = np.ones(len(detections), dtype=bool)
    final_keep[bike_indices[~keep]] = False
    return detections[final_keep]

