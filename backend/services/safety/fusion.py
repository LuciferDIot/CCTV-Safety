"""Safety rules for rider-to-motorcycle spatial fusion and walking ped disambiguation.

Real-world intuition:
- Multimodal Rider-Bike Vertical Fusion: Object detectors (YOLO) often detect a mounted
  motorcyclist twice: once as a "person" (torso/helmet) and once as a "motorcycle" (chassis/wheels).
  We match horizontal center alignment and vertical stacking (rider above chassis) to merge
  them into a single motorcycle detection, suppressing ghost pedestrian tracks.
- Aspect Ratio Reclassification: In active traffic lanes, squat boxes (aspect ratio < 1.80)
  moving faster than walking speed are reclassified from pedestrians to motorcycles.
"""
from typing import Optional, Any
import numpy as np
from services.safety.geometry import point_to_polygon_dist


def _match_rider_to_bike(person_box: np.ndarray, bike_indices: np.ndarray, detections: Any) -> bool:
    """Fuse vertically stacked person onto detected motorcycle chassis."""
    person_center_x = (person_box[0] + person_box[2]) / 2.0
    person_width = person_box[2] - person_box[0]

    for bike_idx in bike_indices:
        bike_box = detections.xyxy[bike_idx]
        bike_center_x = (bike_box[0] + bike_box[2]) / 2.0
        bike_width = bike_box[2] - bike_box[0]

        center_offset_x = abs(person_center_x - bike_center_x)
        # Vertical stacking: rider's lower body near bike top, torso above bike
        vertical_overlap = (person_box[3] >= bike_box[1] - 50.0 and person_box[1] <= bike_box[3])
        horizontal_aligned = center_offset_x <= max(75.0, 0.75 * max(person_width, bike_width))

        if horizontal_aligned and vertical_overlap:
            detections.xyxy[bike_idx][0] = min(detections.xyxy[bike_idx][0], person_box[0])
            detections.xyxy[bike_idx][1] = min(detections.xyxy[bike_idx][1], person_box[1])
            detections.xyxy[bike_idx][2] = max(detections.xyxy[bike_idx][2], person_box[2])
            detections.xyxy[bike_idx][3] = max(detections.xyxy[bike_idx][3], person_box[3])
            return True
    return False


def _is_walking_ped(tracker_id: Optional[int], track_history: Optional[dict]) -> bool:
    """Check if track displacement indicates pedestrian walking speed (<= 4.0 px/frame)."""
    if tracker_id is None or not track_history or tracker_id not in track_history:
        return False
    history_points = track_history[tracker_id]
    if len(history_points) < 3:
        return False
    dx = history_points[-1][0] - history_points[0][0]
    dy = history_points[-1][1] - history_points[0][1]
    avg_speed = np.hypot(dx, dy) / max(1, len(history_points) - 1)
    return avg_speed <= 4.0


def resolve_riders_and_pedestrians(
    detections: Any, lane_zones: list, crosswalk_zones: list, track_history: Optional[dict] = None
) -> Any:
    """Merge mounted riders into motorcycle bounding boxes and filter ghost pedestrians."""
    if len(detections) == 0:
        return detections

    person_indices = np.where(detections.class_id == 0)[0]
    bike_indices = np.where(np.isin(detections.class_id, [1, 3]))[0]
    suppress_indices = []

    for person_idx in person_indices:
        person_box = detections.xyxy[person_idx]
        if _match_rider_to_bike(person_box, bike_indices, detections):
            suppress_indices.append(person_idx)
            continue

        person_center_x = (person_box[0] + person_box[2]) / 2.0
        person_width = person_box[2] - person_box[0]
        person_height = person_box[3] - person_box[1]

        # Pedestrians safely on crosswalks are not reclassified
        in_crosswalk = any(point_to_polygon_dist((person_center_x, person_box[3]), z.polygon) >= -10 for z in crosswalk_zones)
        if in_crosswalk:
            continue

        # In vehicle traffic lanes, reclassify squat non-walking shapes to motorcycles (class 3)
        in_traffic_lane = any(point_to_polygon_dist((person_center_x, person_box[3]), z.polygon) >= -10 for z in lane_zones)
        if in_traffic_lane:
            aspect_ratio = person_height / max(1.0, person_width)
            tracker_id = detections.tracker_id[person_idx] if detections.tracker_id is not None else None
            if aspect_ratio < 1.80 and not _is_walking_ped(tracker_id, track_history):
                detections.class_id[person_idx] = 3

    keep_mask = np.ones(len(detections), dtype=bool)
    keep_mask[suppress_indices] = False
    return detections[keep_mask]
