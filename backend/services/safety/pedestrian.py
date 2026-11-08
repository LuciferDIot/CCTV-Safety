"""Safety rules for pedestrian crosswalk protection vs traffic lane intrusion.

Real-world intuition:
- Crosswalk Walkers: Pedestrians walking within designated crosswalk zones
  are legally crossing and protected (classified as safe pedestrians).
- Active Lane Intrusion: Pedestrians walking inside active vehicular traffic lanes
  outside marked crosswalk boundaries are at imminent risk of collision
  (classified as roadway hazards / jaywalkers).
"""
from typing import Tuple, Optional, Any
import numpy as np


class PedestrianSafetyChecker:
    """Evaluates pedestrian safety between marked crosswalks and active vehicle lanes."""

    def __init__(self, min_confirm_frames: int = 2):
        self.min_confirm_frames = min_confirm_frames

    def check_safety(
        self,
        detections: Any,
        lane_zones: list,
        crosswalk_zones: list,
        track_history: Optional[dict] = None,
        frame_idx: int = 0
    ) -> Tuple[Any, Any]:
        """Segregate pedestrians into safe crosswalk walkers vs active-lane hazards.

        Args:
            detections: Current frame detections (supervision.Detections).
            lane_zones: List of active vehicle roadway zones (PolygonZone).
            crosswalk_zones: List of designated pedestrian crosswalk zones (PolygonZone).
            track_history: Optional dictionary of trajectory histories by tracker ID.
            frame_idx: Current video frame index.

        Returns:
            Tuple of (hazard_pedestrians, safe_pedestrians).
        """
        if len(detections) == 0:
            return (detections[0:0], detections[0:0])

        # Filter detections for pedestrians (COCO class 0 = Person)
        persons = detections[detections.class_id == 0]
        if len(persons) == 0:
            return (persons[0:0], persons[0:0])

        # Step 1: Detect which pedestrians are located inside any vehicular traffic lane
        in_any_lane_mask = np.zeros(len(persons), dtype=bool)
        for lane_zone in lane_zones:
            in_any_lane_mask |= lane_zone.trigger(detections=persons)

        # Step 2: Detect which pedestrians are inside designated crosswalk boundaries
        in_crosswalk_mask = np.zeros(len(persons), dtype=bool)
        for crosswalk_zone in crosswalk_zones:
            in_crosswalk_mask |= crosswalk_zone.trigger(detections=persons)

        # Safe: Pedestrians inside the crosswalk
        safe_pedestrians = persons[in_crosswalk_mask]

        # Hazard: Pedestrians in traffic lanes but outside any designated crosswalk
        hazard_pedestrians = persons[in_any_lane_mask & ~in_crosswalk_mask]

        return (hazard_pedestrians, safe_pedestrians)
