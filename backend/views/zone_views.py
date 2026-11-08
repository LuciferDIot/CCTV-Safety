"""Views (DTOs) for intersection geometry and zone coordinates."""
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from pydantic import BaseModel, Field


class PerspectiveScale(BaseModel):
    y_top: float = 0.1
    y_bottom: float = 1.0
    weight_top: float = 0.35
    weight_bottom: float = 1.0


class RoadZoneConfig(BaseModel):
    id: str = "road"
    polygon: List[List[int]]
    warmup_frames: int = 40


class CrosswalkZoneConfig(BaseModel):
    id: str
    polygon: List[List[int]]


class LaneZoneConfig(BaseModel):
    id: str
    polygon: List[List[int]]
    permitted_direction_vector: Tuple[float, float] = (0.0, 1.0)


class IntersectionZonesConfig(BaseModel):
    camera_id: str = "cam_01"
    video_file: str = "intersection_01.mp4"
    fps: float = 30.0
    perspective_scale_by_y: Optional[PerspectiveScale] = None
    road: RoadZoneConfig
    crosswalks: List[CrosswalkZoneConfig] = Field(default_factory=list)
    lanes: List[LaneZoneConfig] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def parse_intersection_config(data: Dict[str, Any]) -> IntersectionZonesConfig:
    d = dict(data)
    if not d.get("perspective_scale_by_y"):
        d["perspective_scale_by_y"] = PerspectiveScale().model_dump()
    return IntersectionZonesConfig(**d)


def load_intersection_config(config_path: Path) -> IntersectionZonesConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        return parse_intersection_config(json.load(f))

