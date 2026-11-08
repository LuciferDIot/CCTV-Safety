"""Safety rules package."""
from services.safety.geometry import (
    get_box_geometry, get_ground_anchor, compute_perspective_scale,
    point_to_polygon_dist, point_to_segment_dist
)
from services.safety.direction import DirectionChecker, get_motion_metrics
from services.safety.crosswalk import (
    is_normal_lane_transit, classify_crosswalk_motion, CrosswalkSafetyChecker
)
from services.safety.vehicles import classify_vehicle_type
from services.safety.pedestrian import PedestrianSafetyChecker
from services.safety.fusion import resolve_riders_and_pedestrians
from services.safety.clustering import LaneAutoDetector, clip_polygon_by_axis

__all__ = [
    "get_box_geometry", "get_ground_anchor", "compute_perspective_scale",
    "point_to_polygon_dist", "point_to_segment_dist",
    "DirectionChecker", "get_motion_metrics",
    "is_normal_lane_transit", "classify_crosswalk_motion", "CrosswalkSafetyChecker",
    "classify_vehicle_type", "PedestrianSafetyChecker",
    "resolve_riders_and_pedestrians", "LaneAutoDetector", "clip_polygon_by_axis"
]

