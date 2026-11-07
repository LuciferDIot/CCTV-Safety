"""
Configuration Loader with Pydantic Validation for Intersection CCTV Safety
"""
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

class PerspectiveScaleConfig(BaseModel):
    y_top: float = Field(0.1, description="Normalized Y coordinate near horizon / top")
    y_bottom: float = Field(1.0, description="Normalized Y coordinate near camera / bottom")
    weight_top: float = Field(0.35, description="Scale weight at y_top (< 1.0 due to perspective foreshortening)")
    weight_bottom: float = Field(1.0, description="Scale weight at y_bottom")

class RoadConfig(BaseModel):
    polygon: List[Tuple[int, int]]
    mode: str = "auto"
    warmup_frames: int = 40

    @field_validator("polygon")
    @classmethod
    def validate_vertices(cls, v):
        if len(v) < 3:
            raise ValueError(f"Road polygon must have at least 3 vertices, got {len(v)}")
        return v

class LaneConfig(BaseModel):
    id: str
    polygon: List[Tuple[int, int]]
    permitted_unit_vector: Tuple[float, float]

    @field_validator("polygon")
    @classmethod
    def validate_vertices(cls, v):
        if len(v) < 3:
            raise ValueError(f"Lane polygon must have at least 3 vertices, got {len(v)}")
        return v

class CrosswalkConfig(BaseModel):
    id: str
    polygon: List[Tuple[int, int]]

    @field_validator("polygon")
    @classmethod
    def validate_vertices(cls, v):
        if len(v) < 3:
            raise ValueError(f"Crosswalk polygon must have at least 3 vertices, got {len(v)}")
        return v

class IntersectionConfig(BaseModel):
    camera_id: str
    video_file: str
    fps: float = 30.0
    perspective_scale_by_y: PerspectiveScaleConfig
    road: RoadConfig
    lanes: List[LaneConfig] = Field(default_factory=list)
    crosswalks: List[CrosswalkConfig] = Field(default_factory=list)

def parse_intersection_config(data: Dict[str, Any]) -> IntersectionConfig:
    """Parses and validates in-memory dictionary into IntersectionConfig."""
    d = dict(data)
    if not d.get("perspective_scale_by_y"):
        d["perspective_scale_by_y"] = PerspectiveScaleConfig().model_dump()
    return IntersectionConfig(**d)

def load_intersection_config(config_path: Path) -> IntersectionConfig:
    """Loads and validates intersection configuration JSON using Pydantic."""
    with open(config_path, "r", encoding="utf-8") as f:
        return parse_intersection_config(json.load(f))

