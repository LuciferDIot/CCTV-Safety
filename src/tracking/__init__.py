"""Multi-object tracking, track stitching and identity management."""
from src.tracking.state import TrackState
from src.tracking.nms import suppress_duplicate_bikes
from src.tracking.manager import RobustTrackerManager

__all__ = ["TrackState", "suppress_duplicate_bikes", "RobustTrackerManager"]
