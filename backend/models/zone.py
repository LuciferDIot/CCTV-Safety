"""Domain model for road zones, auto-detected lanes, and flow directions."""
from typing import List, Tuple
import numpy as np


class AutoDetectedLane:
    """Domain model representing a directional traffic corridor."""
    __slots__ = ("id", "polygon", "permitted_unit_vector")

    def __init__(self, lane_id: str, polygon: np.ndarray, permitted_unit_vector: Tuple[float, float]) -> None:
        self.id = lane_id
        self.polygon: List[List[int]] = polygon.tolist()
        self.permitted_unit_vector = tuple(permitted_unit_vector)

    def __repr__(self) -> str:
        ux, uy = self.permitted_unit_vector
        return f"AutoDetectedLane(id={self.id!r}, flow=({ux:+.3f}, {uy:+.3f}))"

