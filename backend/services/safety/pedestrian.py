"""Safety rules for pedestrian crosswalk vs traffic lane intrusion."""
from typing import Tuple, Optional, Any
import numpy as np


class PedestrianSafetyChecker:
    """Evaluates pedestrian safety between crosswalks and active vehicle lanes."""

    def __init__(self, min_confirm_frames: int = 2):
        self.min_confirm_frames = min_confirm_frames

    def check_safety(
        self, detections: Any, lane_zones: list, crosswalk_zones: list,
        track_history: Optional[dict] = None, frame_idx: int = 0
    ) -> Tuple[Any, Any]:
        """Segregate pedestrians into safe crosswalk walkers vs active-lane hazards."""
        if len(detections) == 0:
            return (detections[0:0], detections[0:0])

        persons = detections[detections.class_id == 0]
        if len(persons) == 0:
            return (persons[0:0], persons[0:0])

        in_any_lane_mask = np.zeros(len(persons), dtype=bool)
        for l_zone in lane_zones:
            in_any_lane_mask |= l_zone.trigger(detections=persons)

        in_crosswalk_mask = np.zeros(len(persons), dtype=bool)
        for cw_zone in crosswalk_zones:
            in_crosswalk_mask |= cw_zone.trigger(detections=persons)

        safe_pedestrians = persons[in_crosswalk_mask]
        hazard_pedestrians = persons[in_any_lane_mask & ~in_crosswalk_mask]
        return (hazard_pedestrians, safe_pedestrians)

